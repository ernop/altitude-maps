"""Type stub for rasterio.mask module."""
from typing import Any, Sequence

def mask(
    dataset: Any,
    shapes: Any,
    all_touched: bool = False,
    invert: bool = False,
    nodata: Any = None,
    filled: bool = True,
    crop: bool = False,
    pad: bool = False,
    pad_width: float = 0.5,
    indexes: Sequence[int] | None = None,
) -> tuple[Any, Any]: ...

__all__ = ["mask"]

