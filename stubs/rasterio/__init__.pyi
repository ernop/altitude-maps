"""Type stubs for rasterio module."""
from _typeshed import Incomplete
from rasterio.crs import CRS as CRS
from rasterio.env import Env as Env, ensure_env_with_credentials
from rasterio.mask import mask as mask
from rasterio.windows import Window as Window
from typing import Any, NamedTuple
from typing_extensions import Protocol

__all__ = ['band', 'open', 'pad', 'mask', 'Window', 'Band', 'Env', 'CRS', 'DatasetReader', 'DatasetWriter']

class FilePath: ...

class _PathLike(Protocol):
    def __fspath__(self) -> str: ...

FilePath = str | _PathLike

class DatasetReader:
    width: int
    height: int
    crs: Any
    transform: Any
    nodata: Any | None
    def read(self, indexes: int | None = None, window: Any | None = None, **kwargs: Any) -> Any: ...
    def __enter__(self) -> Any: ...
    def __exit__(self, *args: Any) -> None: ...

class DatasetWriter(DatasetReader): ...

@ensure_env_with_credentials
def open(
    fp: FilePath,
    mode: str = 'r',
    driver: Any | None = None,
    width: int | None = None,
    height: int | None = None,
    count: int | None = None,
    crs: Any | None = None,
    transform: Any | None = None,
    dtype: Any | None = None,
    nodata: Any | None = None,
    sharing: bool = False,
    opener: Any | None = None,
    **kwargs: Any
) -> Any: ...

class Band(NamedTuple):
    ds: Incomplete
    bidx: Incomplete
    dtype: Incomplete
    shape: Incomplete

def band(ds: Any, bidx: Any) -> Any: ...
def pad(array: Any, transform: Any, pad_width: Any, mode: Any = None, **kwargs: Any) -> Any: ...
