import logging

import numpy as np
from torch import nn

from algorithms.DataPipeline import DataPipeline
from algorithms.LabelPipeline import LabelPipeline
from algorithms.PretrainedEmbedderLoaderMinimum import PretrainedEmbedderLoaderMinimum
from algorithms.Train import Train
from algorithms.TrainInferencePipeline import TrainInferencePipeline
from algorithms.network_factory_locator import NetworkFactoryLocator
from algorithms.transform_label_encoder import TransformLabelEncoder
from algorithms.transform_label_rehaper import TransformLabelReshaper
from algorithms.transform_sentence_tokeniser import TransformSentenceTokenisor
from algorithms.transform_text_index import TransformTextToIndex


class TrainInferenceBuilder:

    def __init__(self, dataset, embedding_dim, embedding_handle, model_dir, output_dir, epochs=100, patience_epochs=20,
                 extra_args=None, network_factory_name="RelationExtractorSimpleResnetCnnPosNetworkFactory"):
        self.network_factory_name = network_factory_name
        self.patience_epochs = patience_epochs
        self.model_dir = model_dir
        self.epochs = epochs
        self.dataset = dataset
        self.momentum = .9
        self.embedding_handle = embedding_handle
        self.embedding_dim = embedding_dim
        self.output_dir = output_dir
        self.protein_mask = "PROTEIN_{}"
        self.additional_args = extra_args or {}
        # self.lstm_hidden_size = int(self._get_value(self.additional_args, "lstmhiddensize", "100"))
        # self.pooling_kernel_size = int(self._get_value(self.additional_args, "poolingkernelsize", "4"))
        # self.fc_layer_size = int(self._get_value(self.additional_args, "fclayersize", "25"))
        # self.num_layers = int(self._get_value(self.additional_args, "numlayers", "2"))
        self.batch_size = int(self._get_value(self.additional_args, "batchsize", "32"))

    def _get_value(self, kwargs, key, default):
        value = kwargs.get(key, default)
        self.logger.info("Retrieving key {} with default {}, found {}".format(key, default, value))
        return value

    @property
    def logger(self):
        return logging.getLogger(__name__)

    def get_trainpipeline(self):
        # Embedder loader
        # embedder_loader = PretrainedEmbedderLoader(TransformTextToIndex.pad_token())
        embedder_loader = PretrainedEmbedderLoaderMinimum(TransformTextToIndex.pad_token(), dim=self.embedding_dim)

        # preprocess steps TransformProteinMask
        preprocess_steps = []
        special_words = self.dataset.entity_markers

        # Add sentence tokenisor
        sentence_tokenisor = TransformSentenceTokenisor(text_column_index=self.dataset.text_column_index,
                                                        eos_token=TransformTextToIndex.eos_token())
        preprocess_steps.append(("Sentence_tokenisor", sentence_tokenisor))

        # Create data and label pipeline
        text_to_index = TransformTextToIndex(max_feature_lens=self.dataset.feature_lens, special_words=special_words)
        data_pipeline = DataPipeline(preprocess_steps=preprocess_steps, text_to_index=text_to_index)

        # Label pipeline
        class_size = self.dataset.class_size
        label_reshaper = TransformLabelReshaper(num_classes=class_size)
        label_encoder = TransformLabelEncoder()
        label_pipeline = LabelPipeline(label_reshaper=label_reshaper, label_encoder=label_encoder)

        np_feature_lens = np.array(self.dataset.feature_lens)

        # network
        # model = RelationExtractorBiLstmNetwork(class_size=class_size, embedding_dim=self.embedding_dim,
        #                                        feature_lengths=np_feature_lens, hidden_size=self.lstm_hidden_size,
        #                                        dropout_rate_fc=self.dropout_rate_fc, num_layers=self.num_layers,
        #                                        kernal_size=self.pooling_kernel_size, fc_layer_size=self.fc_layer_size,
        #                                        lstm_dropout=.5)

        # dropout_rate_cnn = float(self._get_value(self.additional_args, "dropout_rate_cnn", ".5"))
        # cnn_output = int(self._get_value(self.additional_args, "cnn_output", "100"))
        # fc_drop_out_rate = float(self._get_value(self.additional_args, "fc_drop_out_rate", ".5"))
        # model = RelationExtractorCnnPosNetwork(class_size=class_size, embedding_dim=self.embedding_dim,
        #                                        feature_lengths=np_feature_lens, cnn_output=cnn_output,
        #                                        dropout_rate_cnn=dropout_rate_cnn,
        #                                        dropout_rate_fc=fc_drop_out_rate)

        special_words_dict = text_to_index.get_specialwords_dict()
        self.additional_args["entity_markers_indices"] = [special_words_dict[e] for e in self.dataset.entity_markers]
        model_factory = NetworkFactoryLocator().get_factory(self.network_factory_name)
        model = model_factory.get_network(class_size, self.embedding_dim, np_feature_lens, **self.additional_args)

        self.logger.info("Using model {}".format(type(model)))
        self.logger.info("\n{}".format(model))

        # Loss function
        loss_function = nn.CrossEntropyLoss()
        self.logger.info("Using loss function {}".format(type(loss_function)))

        # Trainer
        trainer = Train(epochs=self.epochs, early_stopping_patience=self.patience_epochs)

        # merge train val vocab
        merge_vocab_train_val = bool(int(self._get_value(self.additional_args, "train_val_vocab_merge", "0")))
        self.logger.info("Merging train val vocab true: {}".format(merge_vocab_train_val))

        pipeline = TrainInferencePipeline(model=model, loss_function=loss_function,
                                          trainer=trainer, train_vocab_extractor=text_to_index,
                                          model_dir=self.model_dir,
                                          embedder_loader=embedder_loader, batch_size=self.batch_size,
                                          embedding_handle=self.embedding_handle, embedding_dim=self.embedding_dim,
                                          label_pipeline=label_pipeline, data_pipeline=data_pipeline,
                                          class_size=class_size, pos_label=self.dataset.positive_label,
                                          output_dir=self.output_dir, additional_args=self.additional_args,
                                          merge_train_val_vocab=merge_vocab_train_val)

        return pipeline
