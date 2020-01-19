import glob
import logging
import math
import os

import pandas as pd

from algorithms.TrainInferencePipeline import TrainInferencePipeline


class InferencePipeline:
    def run(self, dataset, data_file, artifactsdir, out_dir, postives_filter_threshold=0.0):
        logger = logging.getLogger(__name__)

        predicted_confidence_field = "predicted_confidence"
        predicted_output_field = "predicted"

        final_df = self.run_prediction(dataset, artifactsdir, data_file, out_dir,
                                       predicted_confidence_field=predicted_confidence_field,
                                       predicted_field=predicted_output_field)

        logger.info("Completed {}, {}".format(final_df.shape, final_df.columns.values))

        final_df = self._filter_threshold(final_df, postives_filter_threshold, dataset.lambda_postive_field_filter,
                                          confidence_score_field=predicted_confidence_field,
                                          predicted_field=predicted_output_field)

        predictions_file = os.path.join(out_dir, "predicted.json")
        final_df.to_json(predictions_file)

        return final_df

    def _filter_threshold(self, final_df, postives_filter_threshold, filter_lambda,
                          confidence_score_field="predicted_confidence", predicted_field="predicted_field"):
        logger = logging.getLogger(__name__)

        if postives_filter_threshold == 0.0:
            return final_df

        logger.info(
            "Filtering True Positives with threshold > {}, currently {} records".format(postives_filter_threshold,
                                                                                        final_df.shape))

        final_df = final_df[final_df.apply(
            lambda x: filter_lambda(x[predicted_field]) and x[confidence_score_field] > postives_filter_threshold,
            axis=1)]

        logger.info("Post filter shape {}".format(final_df.shape))
        return final_df

    def run_prediction(self, dataset, artifactsdir, data_file, out_dir,
                       confidence_scores_dict_field="confidence_scores",
                       predicted_confidence_field="predicted_confidence",
                       predicted_field="predicted"):
        logger = logging.getLogger(__name__)

        if not os.path.exists(out_dir) or not os.path.isdir(out_dir):
            raise FileNotFoundError("The path {} should exist and must be a directory".format(out_dir))

        logger.info("Loading from file {}".format(data_file))

        df = pd.read_json(data_file)

        ensemble_artefacts_dir = [d for d in glob.glob("{}{}*".format(artifactsdir, os.path.sep)) if os.path.isdir(d)]

        predictor = TrainInferencePipeline.load_ensemble(ensemble_artefacts_dir)

        # Run prediction
        results, confidence_scores = predictor(dataset)
        df[predicted_field] = results
        df[confidence_scores_dict_field] = confidence_scores

        keys = list(df[confidence_scores_dict_field].iloc[0].keys())

        # This is log softmax, convert to softmax prob
        for k in keys:
            df[k] = df.apply(lambda x: math.exp(x[confidence_scores_dict_field][k]), axis=1)

        df[predicted_field] = df.apply(lambda r: keys[list(r[keys]).index(max(r[keys]))], axis=1)
        df[predicted_confidence_field] = df.apply(lambda r: max(r[keys] / sum(r[keys])), axis=1)

        return df
