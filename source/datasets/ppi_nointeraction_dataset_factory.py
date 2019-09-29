from datasets.PpiNoInteractionDataset import PpiNoInteractionDataset
from datasets.custom_dataset_factory_base import CustomDatasetFactoryBase
from preprocessor.Preprocessor import Preprocessor
from preprocessor.ProteinMasker import ProteinMasker


class PpiNoInteractionDatasetFactory(CustomDatasetFactoryBase):

    def get_dataset(self, file_path):
        dataset = PpiNoInteractionDataset(file_path=file_path, interaction_type=None)

        mask = ProteinMasker(entity_column_indices=dataset.entity_column_indices, masks=["PROTEIN_1", "PROTEIN_2"],
                             text_column_index=dataset.text_column_index)

        transformer = Preprocessor([mask])

        dataset.transformer = transformer

        return dataset