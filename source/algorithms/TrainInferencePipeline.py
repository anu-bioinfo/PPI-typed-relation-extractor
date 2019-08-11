import glob
import logging
import os
import pickle

import torch

from algorithms.Predictor import Predictor


class TrainInferencePipeline:

    def __init__(self, model, optimiser, loss_function, trainer, embedder_loader, embedding_handle, embedding_dim: int,
                 label_pipeline, data_pipeline, class_size: int, pos_label, output_dir, ngram: int = 3,
                 epochs: int = 10, min_vocab_frequency=3, class_weights_dict=None):
        self.trainer = trainer
        self.class_weights_dict = class_weights_dict
        self.embedding_handle = embedding_handle
        self.embedder_loader = embedder_loader
        self.loss_function = loss_function
        self.optimiser = optimiser
        self.model = model
        self.data_pipeline = data_pipeline
        self.label_pipeline = label_pipeline

        self.pos_label = pos_label
        self.min_vocab_frequency = min_vocab_frequency
        self.epochs = epochs
        self.output_dir = output_dir
        self.ngram = ngram
        self.embedding_dim = embedding_dim
        self.class_size = class_size

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def __call__(self, train, validation):
        transformed_train_x = self.data_pipeline.fit_transform(train)
        transformed_val_x = self.data_pipeline.transform(validation)

        transformed_train_x = self.label_pipeline.fit_transform(transformed_train_x)
        transformed_val_x = self.label_pipeline.transform(transformed_val_x)

        self.embedding_handle.seek(0)
        self.data_pipeline.vocab, embedding_array = self.embedder_loader(self.embedding_handle,
                                                                         other_words_embed=self.data_pipeline.vocab)

        tensor_embeddings = torch.nn.Embedding.from_pretrained(torch.FloatTensor(embedding_array))
        self.model.set_embeddings(tensor_embeddings)
        # Set weights
        # if self.class_weights_dict is not None:
        #     self._class_weights = [1] * len(classes)
        #     for k, w in self.class_weights_dict.items():
        #         class_int = transformer_labels.transform([k])[0]
        #         self._class_weights[class_int] = w
        #     self._class_weights = torch.Tensor(self._class_weights)
        #     self.logger.info("Class weights dict is : {}".format(self.class_weights_dict))
        #     self.logger.info("Class weights are is : {}".format(self._class_weights))

        # Lengths of each column

        encoded_pos_label = self.label_pipeline.transform(self.pos_label)

        # Set up optimiser

        self.persist(outdir=self.output_dir)

        # Invoke trainer
        (val_results, val_actuals, val_predicted) = self.trainer(transformed_train_x, transformed_val_x,

                                                                 self.model, self.loss_function,
                                                                 self.optimiser,
                                                                 self.output_dir, epoch=self.epochs,
                                                                 pos_label=encoded_pos_label)

        # Reformat results so that the labels are back into their original form, rather than numbers
        val_actuals = self.label_pipeline.label_reverse_encoder_func(val_actuals)
        val_predicted = self.label_pipeline.label_reverse_encoder_func(val_predicted)

        return val_results, val_actuals, val_predicted

    def sum(self, x):
        return sum([len(getattr(x, c)) for c in x.__dict__ if c != 'label'])

    def persist(self, outdir):
        with open(os.path.join(outdir, "picked_datapipeline.pb"), "wb") as f:
            pickle.dump(self.data_pipeline, f)

        with open(os.path.join(outdir, "picked_labelpipeline.pb"), "wb") as f:
            pickle.dump(self.label_pipeline, f)

    @staticmethod
    def load(artifacts_dir):
        model_file = TrainInferencePipeline._find_artifact("{}/*model.pt".format(artifacts_dir))

        data_pipeline = TrainInferencePipeline._load_artifact("{}/*picked_datapipeline.pb".format(artifacts_dir))
        label_pipeline = TrainInferencePipeline._load_artifact("{}/*picked_labelpipeline.pb".format(artifacts_dir))

        model = torch.load(model_file)

        return lambda x: TrainInferencePipeline.predict(x, model, data_pipeline, label_pipeline)

    @staticmethod
    def _load_artifact(pickled_file_search_filter):
        datapipeline_file = TrainInferencePipeline._find_artifact(pickled_file_search_filter)
        with open(datapipeline_file, "rb") as f:
            datapipeline = pickle.load(f)

        return datapipeline

    @staticmethod
    def _find_artifact(pattern):
        matching = glob.glob(pattern)
        assert len(matching) == 1, "Expected exactly one in {}, but found {}".format(pattern,
                                                                                     len(matching))
        matched_file = matching[0]
        return matched_file

    @staticmethod
    def predict(dataloader, model, data_pipeline, label_pipeline):

        val_examples = data_pipeline.transform(dataloader)

        predictor = Predictor()

        predictions, confidence_scores = predictor.predict(model, val_examples)

        transformed_predictions = label_pipeline.label_reverse_encoder_func(predictions)

        transformed_conf_scores = TrainInferencePipeline._get_confidence_score_dict(label_pipeline, confidence_scores)

        return transformed_predictions, transformed_conf_scores

    @staticmethod
    def _get_confidence_score_dict(label_pipeline, confidence_scores):
        transformed_conf_scores = []
        for r in confidence_scores:
            conf_score = {}
            for i, s in enumerate(r):
                conf_score[label_pipeline.label_reverse_encoder_func(i)] = s
            transformed_conf_scores.append(conf_score)

        return transformed_conf_scores