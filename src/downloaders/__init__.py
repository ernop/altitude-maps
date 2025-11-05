"""
Data downloaders for various elevation data sources.

This package contains download logic for different elevation data providers.
CLI wrappers in downloaders/ call these functions.
"""

from .opentopography import download_srtm, download_copernicus

__all__ = ['download_srtm', 'download_copernicus']

