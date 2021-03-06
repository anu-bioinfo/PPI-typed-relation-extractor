import argparse

import boto3

from createrole import create_role


class RegisterJob:

    def __init__(self, client=None, account=None, aws_region=None):
        self.client = client or boto3.client('batch')
        self.account = account or boto3.client('sts').get_caller_identity().get('Account')
        self.region = aws_region or boto3.session.Session().region_name

    def run(self, container_name: str, data_bucket: str, interaction_types: str):
        """
        Registers a job with aws batch.
        :param data_bucket: the name of the s3 bucket that will hold the data
        :param container_name: The name of the container to use e.g 324346001917.dkr.ecr.us-east-2.amazonaws.com/awscomprehend-sentiment-demo:latest
        """
        job_def_name = "KeggPathWayExtractor_datapreppipeline"
        role_name = "AWSBatchECSRole_{}".format(job_def_name)

        ##This is mandatory for aws batch
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ecs-tasks.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        # This is custom for the batch
        access_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BucketAccess",
                    "Effect": "Allow",
                    "Action": [
                        "s3:PutObject",
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:DeleteObject",
                        "s3:HeadBucket"
                    ],
                    "Resource": [
                        "arn:aws:s3:::{}/*".format(data_bucket),
                        "arn:aws:s3:::{}".format(data_bucket)
                    ]
                }
            ]
        }

        managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"]

        create_role(role_name, assume_role_policy, access_policy, managed_policy_arns)

        job_definition = {
            "jobDefinitionName": job_def_name,
            "type": "container",
            "parameters": {
                "input_path": "s3://{}/prefix/".format(data_bucket),
                "output_path": "s3://{}/prefix_ouput/".format(data_bucket),
                "log_level": "INFO",
                "interaction_types": interaction_types

            },
            "containerProperties": {
                "image": container_name,
                "vcpus": 1,
                "memory": 2000,
                "command": [
                    "python",
                    "pipeline/main_pipeline_dataprep.py",
                    "Ref::input_path",
                    "Ref::output_path",
                    "--log-level",
                    "Ref::log_level",
                    "--interaction-types",
                    "Ref::interaction_types"
                ],
                "jobRoleArn": "arn:aws:iam::{}:role/{}".format(self.account, role_name),
                "volumes": [
                    {
                        "host": {
                            "sourcePath": "/dev/shm"
                        },
                        "name": "data"
                    }
                ],
                "environment": [
                    {
                        "name": "AWS_DEFAULT_REGION",
                        "value": self.region
                    }
                ],
                "mountPoints": [
                    {
                        "containerPath": "/data",
                        "readOnly": False,
                        "sourceVolume": "data"
                    }
                ],
                "readonlyRootFilesystem": False,
                "privileged": True,
                "ulimits": [],
                "user": ""
            },
            "retryStrategy": {
                "attempts": 1
            }
        }

        reponse = self.client.register_job_definition(**job_definition)
        return reponse


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("containerimage",
                        help="Container image, e.g docker pull lanax/kegg-pathway-extractor:latest")

    parser.add_argument("data_bucket",
                        help="The name of the s3 bucket that will contain the input/output data")

    parser.add_argument("interaction_types",
                        help="The interaction types to download",
                        default="phosphorylation,dephosphorylation,ubiquitination,methylation,acetylation,deubiquitination,demethylation")

    job = RegisterJob()
    args = parser.parse_args()
    result = job.run(args.containerimage, args.data_bucket, args.interaction_types)
    print(result)
