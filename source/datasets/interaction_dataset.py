import numpy as np
import pandas as pd

from datasets.custom_dataset_base import CustomDatasetBase


class InteractionDataset(CustomDatasetBase):
    """
    Represents the interaction only dataset
    """

    def __init__(self, file_path, transformer=None):
        self.transformer = transformer
        self._file_path = file_path
        # Read json
        data_df = pd.read_json(self._file_path)

        # Filter features
        self._data_df = data_df[["pubmedabstract"]]

        # Set up labels
        if "interactionType" in data_df.columns:
            self._labels = data_df[["interactionType"]]
            self._labels = np.reshape(self._labels.values.tolist(), (-1,))
        else:
            self._labels = np.reshape([-1] * data_df.shape[0], (-1,))

    def __len__(self):
        return self._data_df.shape[0]

    def __getitem__(self, index):
        x = self._data_df.iloc[index, :].tolist()
        y = self._labels[index].tolist()

        if self.transformer is not None:
            x = self.transformer(x)

        return x, y

    @property
    def class_size(self):
        return 7

    @property
    def positive_label(self):
        # Randomly return a label
        return self._labels[0]

    @property
    def lambda_postive_field_filter(self):
        return lambda x: x != "other"

    @property
    def feature_lens(self):
        return [250]

    @property
    def entity_column_indices(self):
        raise NotImplementedError

    @property
    def text_column_index(self):
        return 0

    @property
    def entity_markers(self):
        raise NotImplementedError
