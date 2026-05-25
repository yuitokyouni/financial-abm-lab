"""Model adapters — ABM implementations conforming to the ModelAdapter protocol."""

from prism.adapters.ci import CIAdapter
from prism.adapters.sg import SGAdapter

__all__ = ["SGAdapter", "CIAdapter"]
