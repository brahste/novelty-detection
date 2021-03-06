import os
import glob
import unittest
import pytorch_lightning as pl

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from pathlib import Path
from utils import tools, callbacks, supported_preprocessing_transforms
from modules.vae_base_module import VAEBaseModule
from datasets import supported_datamodules
from models import supported_models


class TestVAETraining(unittest.TestCase):

    def test_vae_config_compatability(self):

        # TODO: Replace with glob once all models and configurations are operational (see test_cae_training.py)
        config_paths = [
            'configs/vae/vae_simple_mnist.yaml',
            'configs/vae/vae_simple_curiosity.yaml',
            'configs/vae/vae_baseline_curiosity.yaml'
        ]
        for pth in config_paths:
            logging.info(f"Testing training for: {pth}")
            config = tools.load_config(pth)

            module = _test_training_pipeline(config)

            log_path = Path('tests') / \
                'test_logs' / \
                config['experiment-parameters']['datamodule'] / \
                config['experiment-parameters']['model'] / \
                f'version_{module.version}'
            logging.info(log_path)

            self.assertTrue( (log_path / 'checkpoints').is_dir() )
            self.assertTrue( (log_path / 'configuration.yaml').is_file() )
            self.assertTrue( (log_path / 'model_summary.txt').is_file() )


def _test_training_pipeline(config):
    """This pipeline shadows the pipeline in trainers/train_vae.py with modifications for testing"""
    # Change log_dir for testing
    config['experiment-parameters']['log_dir'] = os.path.join('tests', 'test_logs')

    # Set up preprocessing routine
    preprocessing_transforms = supported_preprocessing_transforms[config['data-parameters']['preprocessing']]

    datamodule = supported_datamodules[config['experiment-parameters']['datamodule']](
        data_transforms=preprocessing_transforms,
        **config['data-parameters'])
    datamodule.prepare_data()
    datamodule.setup('train')

    model = supported_models[config['experiment-parameters']['model']](
        datamodule.data_shape, **config['module-parameters'])

    # Initialize experimental module
    module = VAEBaseModule(
        model,
        train_size=datamodule.train_size,
        val_size=datamodule.val_size,
        batch_size=datamodule.batch_size,
        **config['module-parameters'])

    # Initialize loggers to monitor training and validation
    logger = pl.loggers.TensorBoardLogger(
        config['experiment-parameters']['log_dir'],  # Temp location for dummy logs
        name=os.path.join(config['experiment-parameters']['datamodule'], config['experiment-parameters']['model']))

    # Initialize the Trainer object
    trainer = pl.Trainer(
        gpus=1,
        logger=logger,
        max_epochs=1,
        weights_summary=None,
        callbacks=[
            pl.callbacks.EarlyStopping(
                monitor='val_elbo_loss',
                patience=5 if config['experiment-parameters']['patience'] is None else config['experiment-parameters']['patience']),
            pl.callbacks.ModelCheckpoint(
                monitor='val_elbo_loss',
                filename='{val_elbo_loss:.2f}-{epoch}',
                save_last=True),
            pl.callbacks.GPUStatsMonitor(),
            callbacks.VAEVisualization()
        ])

    # Find learning rate
    lr, lr_finder_fig = callbacks.learning_rate_finder(trainer, module, datamodule, num_training=25)
    module.lr = lr
    config['module-parameters']['learning_rate'] = module.lr

    # Train the model
    trainer.fit(module, datamodule)

    # Remove try-except block for testing
    tools.save_object_to_version(
        config, version=module.version, filename='configuration.yaml', **config['experiment-parameters'])
    tools.save_object_to_version(
        str(model), version=module.version, filename='model_summary.txt', **config['experiment-parameters'])

    return module


if __name__ == '__main__':
    unittest.main()
