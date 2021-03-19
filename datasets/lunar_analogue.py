# Datasets used in Novelty detection experiments
# Author: Braden Stefanuk
# Created: Dec 17, 2020

import torch
import numpy as np

from pathlib import Path
from torchvision import transforms
from skimage import io
from sklearn.model_selection import train_test_split
from utils import tools

from .base_datamodule import BaseDataModule


class LunarAnalogueDataset(torch.utils.data.Dataset):
    """Map style dataset of the lunar analogue terrain"""

    # TODO: Consider doing data augmentation to increase the number of training samples
    def __init__(
            self,
            root_data_path: str,
            glob_pattern: str,
            train: bool = True,
            data_transforms=None
    ):
        super().__init__()
        # We handle the training and testing data with various glob patterns, this helps
        # adapt and implement alternative labelling schemes.
        self._list_of_image_paths = list(Path(root_data_path).glob(glob_pattern))
        self._data_transforms = data_transforms
        self._train = train

    def __len__(self):
        return len(self._list_of_image_paths)

    def __getitem__(self, idx: int):

        image = io.imread(self._list_of_image_paths[idx])

        if self._data_transforms:
            image = self._data_transforms(image)

        return image, torch.tensor(self.get_label(idx))

    def get_label(self, idx: int):

        if 'typical/' in str(self._list_of_image_paths[idx]):
            return 0
        elif 'novel/' in str(self._list_of_image_paths[idx]):
            return 1
        else:
            raise ValueError('Cannot find typical/ or novel/ in file path')


class LunarAnalogueDataModule(BaseDataModule):
    """For use with Pytorch models only"""

    def __init__(
            self,
            root_data_path: str,
            batch_size: int = 8,
            train_fraction: float = 0.8,
            **kwargs
    ):
        super(LunarAnalogueDataModule, self).__init__()

        self._batch_size = batch_size if batch_size is not None else 8
        self._train_fraction = train_fraction if train_fraction is not None else 0.8
        self._val_fraction = 1 - self._train_fraction
        self._root_data_path = root_data_path

        self._data_transforms = transforms.Compose([
            tools.LunarAnaloguePreprocessingPipeline(),
            transforms.ToTensor(),
        ])

        # Handle the default and optionally passed additional kwargs
        self._glob_pattern_train = '**/nov-labelled/trainval/*.jpeg'
        self._glob_pattern_test = '**/nov-labelled/test/**/*.jpeg'
        for key in kwargs:
            if key == 'glob_pattern_train' and kwargs[key] is not None:
                self._glob_pattern_train = kwargs[key]
            elif key == 'glob_pattern_test' and kwargs[key] is not None:
                self._glob_pattern_test = kwargs[key]

    def prepare_data(self, **kwargs):
        pass

    def setup(self, stage: str = None):
        """
        Prepare the data by cascading processing operations to be conducted
        during import
        """
        # Have to use fit in the datamodule as per PL requirements
        if stage == 'fit' or stage == 'train' or stage is None:
            # Setup training and validation data for use in dataloaders
            trainval_set = LunarAnalogueDataset(
                self._root_data_path,
                self._glob_pattern_train,
                train=True,
                data_transforms=self._data_transforms
            )
            # Since setup is called from every process, setting state here is okay
            train_size = int(np.floor(len(trainval_set) * self._train_fraction))
            val_size = len(trainval_set) - train_size

            self._train_set, self._val_set = torch.utils.data.random_split(trainval_set, [train_size, val_size])

        if stage == 'test' or stage is None:
            # Setup testing data as well
            self._test_set = LunarAnalogueDataset(
                self._root_data_path,
                self._glob_pattern_test,
                train=False,
                data_transforms=self._data_transforms
            )

    def train_dataloader(self):
        return torch.utils.data.DataLoader(
            self._train_set,
            batch_size=self._batch_size,
            drop_last=True,
            num_workers=8
        )

    def val_dataloader(self):
        return torch.utils.data.DataLoader(
            self._val_set,
            batch_size=self._batch_size,
            drop_last=True,
            num_workers=8
        )

    def test_dataloader(self):
        return torch.utils.data.DataLoader(
            self._test_set,
            batch_size=self._batch_size,
            drop_last=True,
            num_workers=8
        )


class LunarAnalogueDataGenerator:
    """For use with sklearn models and other CPU-based algorithms"""
    # TODO: Make datagenerator comptabile with BaseDataModule parent class
    def __init__(
            self,
            root_data_path: str,
            glob_pattern_train: str,
            glob_pattern_test: str,
            batch_size: int = 8,
            train_fraction: float = 0.8
    ):
        super(LunarAnalogueDataGenerator, self).__init__()
        print(f'Loading {self.__class__.__name__}\n------')

        self._batch_size = batch_size
        self._train_fraction = train_fraction
        self._val_fraction = 1 - train_fraction
        self._glob_pattern_train = glob_pattern_train
        self._glob_pattern_test = glob_pattern_test
        self._root_data_path = root_data_path

        # Define preprocessing pipeline
        self._data_transforms = tools.PreprocessingPipeline()

    def setup(self, stage: str):

        if stage == 'train' or stage == 'val':
            # Instantiate training dataset
            self._trainval_set = LunarAnalogueDataset(
                self._root_data_path,
                self._glob_pattern_train,
                train=True,
                data_transforms=self._data_transforms
            )
            # Set training and validation split
            train_size = np.floor(len(self._trainval_set) * self._train_fraction).astype(int)
            val_size = np.floor(len(self._trainval_set) * self._val_fraction).astype(int)

            self._train_idxs, self._val_idxs = train_test_split(
                np.arange(len(self._trainval_set), dtype=int),
                test_size=val_size,
                train_size=train_size,
                random_state=42,
                shuffle=False
            )
            print(f'Training samples: {train_size}\nValidation samples: {val_size}\n')

        elif stage == 'test':
            # Setup testing data as well
            self._test_set = LunarAnalogueDataset(
                self._root_data_path,
                self._glob_pattern_test,
                train=False,
                data_transforms=self._data_transforms
            )
            print(f'Testing samples: {len(self._test_set)}\n')

        else:
            raise ValueError('Only accepts the following stages: \'train\', \'test\'.')

    def trainval_generator(self, stage: str):
        self.setup('train')
        assert hasattr(self, '_trainval_set'), 'Need to instantiate datagenerator with stage=\'train\'.'

        if stage == 'train':
            idxs = self._train_idxs
        elif stage == 'val':
            idxs = self._val_idxs
        else:
            raise ValueError('Generator only accepts \'train\' and \'val\' stages.')

        batch_out = np.empty((self._batch_size, *self._trainval_set[0].shape))
        batch_nb = 0

        while batch_nb < (len(idxs) // self._batch_size):
            # Use sliding batch number approach to select which data to generate
            for i, idx in enumerate(idxs[batch_nb * self._batch_size: (batch_nb + 1) * self._batch_size]):
                batch_out[i] = self._trainval_set[idx]

            batch_nb += 1
            yield batch_out

    def test_generator(self):
        self.setup('test')
        assert hasattr(self, '_test_set'), 'Need to instantiate datagenerator with stage=\'test\'.'

        batch_out = np.empty((self._batch_size, *self._test_set[0].shape))
        label_out = np.empty((self._batch_size,))
        batch_nb = 0

        while batch_nb < (len(self._test_set) // self._batch_size):
            for i in range(self._batch_size):
                # Use sliding batch number approach to select which data to generate
                batch_out[i] = self._test_set[batch_nb * self._batch_size + i]
                label_out[i] = self._test_set.get_label(batch_nb * self._batch_size + i)

            batch_nb += 1
            yield batch_out, label_out
