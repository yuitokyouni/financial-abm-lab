"""YH006 condition configs: C1 (FCN only), C2 (SG uniform), C3 (SG Pareto)."""

from .c1 import make_config as c1_config
from .c2 import make_config as c2_config
from .c3 import make_config as c3_config

__all__ = ["c1_config", "c2_config", "c3_config"]
