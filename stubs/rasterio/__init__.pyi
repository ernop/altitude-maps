"""Type stubs for rasterio module."""
from typing import Any, NamedTuple

__all__ = ['open', 'DatasetReader', 'DatasetWriter', 'Band']

class DatasetReader:
    width: int
    height: int
    crs: Any
    transform: Any
    nodata: Any | None
    def read(self, *args: Any, **kwargs: Any) -> Any: ...
    def __enter__(self) -> Any: ...
    def __exit__(self, *args: Any) -> None: ...

class DatasetWriter(DatasetReader): ...

def open(*args: Any, **kwargs: Any) -> Any: ...

class Band(NamedTuple): ...
