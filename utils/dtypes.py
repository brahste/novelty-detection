from typing import List, Callable, Union, Any, TypeVar, Tuple, Optional, Iterable
from matplotlib import figure
from pathlib import Path
import torch
import numpy as np
from torchvision.transforms import Compose

Size = torch.Size
DataLoader = TypeVar('torch.utils.data.DataLoader')
Tensor = TypeVar('torch.tensor')
Figure = figure.Figure
