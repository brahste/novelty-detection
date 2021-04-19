import os
import glob
import unittest
import torch
import pytorch_lightning as pl

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from utils import tools, callbacks
from modules.cae_base_module import CAEBaseModule
from datasets import supported_datamodules
from models import supported_models


class TestCAETraining(unittest.TestCase):

    def test_cae_config_compatability(self):

        def test_training_pipeline(config):
            # Change log_dir for testing
            config['experiment-parameters']['log_dir'] = os.path.join('tests', 'test_logs')

            datamodule = supported_datamodules[config['experiment-parameters']['datamodule']](
                **config['data-parameters'])
            datamodule.prepare_data()
            datamodule.setup('train')

            model = supported_models[config['experiment-parameters']['model']](datamodule.data_shape[0])

            # Initialize experimental module
            module = CAEBaseModule(model, **config['module-parameters'])

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
                        monitor='val_loss',
                        patience=5 if config['experiment-parameters']['patience'] is None else config['experiment-parameters']['patience']),
                    pl.callbacks.GPUStatsMonitor(),
                    pl.callbacks.ModelCheckpoint(
                        monitor='val_loss',
                        filename='{val_loss:.2f}-{epoch}',
                        save_last=True),
                    callbacks.VisualizationCallback()
                ]
            )

            # Always run lr_finder for testing
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
            if 'lr_finder_fig' in locals():
                tools.save_object_to_version(
                    lr_finder_fig, version=module.version, filename='lr-find.eps', **config['experiment-parameters'])

        config_paths = glob.glob('configs/cae/**')
        for pth in config_paths:
            logging.info(f"Testing training for: {pth}")
            config = tools.load_config(pth)
            test_training_pipeline(config)


if __name__ == '__main__':
    unittest.main()