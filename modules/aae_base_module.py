import torch
import torch.nn as nn
import torchvision.utils as vutils
import pytorch_lightning as pl

from utils.dtypes import *


class AAEBaseModule(pl.LightningModule):
    def __init__(
            self,
            model: nn.Module,
            learning_rate: float = 0.001,
            weight_decay_coefficient: float = 0.01,
            batch_size: int = 8,
            **kwargs):
        super().__init__()

        # The model must implement the following methods and attributes
        self.encoder = model.encoder
        self.decoder = model.decoder
        self.discriminator = model.discriminator
        self.discriminator_loss = model.discriminator_loss
        self.reconstruction_loss = model.reconstruction_loss
        self.generator_loss = model.generator_loss

        self.lr = learning_rate if learning_rate is not None else 0.001
        self.wd = weight_decay_coefficient if weight_decay_coefficient is not None else 0.01
        self._batch_size = batch_size if batch_size is not None else 8

    def configure_optimizers(self):
        opt_reconstruction = torch.optim.AdamW(
            [*self.encoder.parameters(), *self.decoder.parameters()],
            lr=self.lr,
            weight_decay=self.wd)
        opt_generator = torch.optim.AdamW(
            self.encoder.parameters(),
            lr=self.lr,
            weight_decay=self.wd)
        opt_discriminator = torch.optim.AdamW(
            self.discriminator.parameters(),
            lr=self.lr,
            weight_decay=self.wd)
        return [opt_reconstruction, opt_discriminator, opt_generator], []

    def training_step(self, batch, batch_idx, optimizer_idx):
        # See github.com/brahste/novelty-detection/figures/SimpleAAESchematic

        # Manage data layout
        batch_in, _ = self.handle_batch_shape(batch)

        # Reconstruction phase
        # ------
        if optimizer_idx == 0:
            reconstruction_loss = self.reconstruction_loss(batch_in)
            self.log('r_loss', reconstruction_loss, on_epoch=True, prog_bar=True)
            return reconstruction_loss

        # Regularization phase
        # ------
        if optimizer_idx == 1:
            discriminator_loss = self.discriminator_loss(batch_in)
            self.log('d_loss', discriminator_loss, on_epoch=True, prog_bar=True)
            return discriminator_loss

        if optimizer_idx == 2:
            generator_loss = self.generator_loss(batch_in)
            self.log('g_loss', generator_loss, on_epoch=True, prog_bar=True)
            return generator_loss

    def validation_step(self, batch, batch_idx):
        # Validate with reconstruction loss
        batch_in, _ = self.handle_batch_shape(batch)

        reconstruction_loss = self.reconstruction_loss(batch_in)
        self.log('val_r_loss', reconstruction_loss, prog_bar=True)
        return reconstruction_loss

    def test_step(self, batch, batch_nb):

        batch_in, batch_labels = self.handle_batch_shape(batch)
        image_shape = batch_in.shape

        batch_lt = self.encoder(batch_in)
        batch_rc = self.decoder(batch_lt)
        loss = nn.MSELoss()(batch_rc, batch_in)

        # Calculate individual novelty scores
        batch_scores = []
        for x_nb, (x_rc, x_in) in enumerate(zip(batch_rc, batch_in)):
            batch_scores.append(nn.MSELoss()(x_rc, x_in))

        return {
            'test_loss': loss,
            'scores': batch_scores,
            'labels': batch_labels,
            'images': {
                'batch_in': batch_in.detach().reshape(*image_shape),
                'batch_rc': batch_rc.detach().reshape(*image_shape),
                'batch_lt': batch_lt.detach()
            }
        }

    # @staticmethod
    def handle_batch_shape(self, batch):
        """
        Conducts an inplace operation to merge regions and batch size if NRE is being used.
        """
        batch_in, _ = batch
        assert any(len(batch_in.shape) == s for s in (4, 5)), f'Batch must have 4 or 5 dims, got {len(batch_in.shape)}'
        if len(batch_in.shape) == 5:
            batch_in = batch_in.view(-1, *batch_in.shape[2:])
        return batch_in, _

    @property
    def version(self):
        return self.logger.version
