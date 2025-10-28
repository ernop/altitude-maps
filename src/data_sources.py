"""
Data acquisition module for altitude-maps project.

This module handles downloading and caching climate and elevation data
from various public sources.
"""

import os
import sys
import io
import requests
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd
from tqdm import tqdm

# NOTE: This is a library module - do NOT wrap stdout/stderr
# Modern Python handles UTF-8 correctly by default


class DataManager:
    """Manages data downloads and caching for the project."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the data manager.
        
        Args:
            data_dir: Directory to store downloaded data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
    def download_file(self, url: str, filename: str, force: bool = False) -> Path:
        """
        Download a file with progress bar and caching.
        
        Args:
            url: URL to download from
            filename: Local filename to save as
            force: Force redownload even if file exists
            
        Returns:
            Path to the downloaded file
        """
        filepath = self.data_dir / filename
        
        if filepath.exists() and not force:
            print(f"✓ File already exists: {filename}")
            return filepath
            
        print(f"Downloading {filename}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filepath, 'wb') as f, tqdm(
            desc=filename,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                size = f.write(chunk)
                pbar.update(size)
                
        print(f"✓ Downloaded: {filename}")
        return filepath
    
    def get_sample_elevation_data(self) -> np.ndarray:
        """
        Generate sample elevation data for testing.
        
        Returns:
            2D array of elevation values
        """
        # Create synthetic elevation data (simulating a mountain range)
        x = np.linspace(-5, 5, 100)
        y = np.linspace(-5, 5, 100)
        X, Y = np.meshgrid(x, y)
        
        # Multiple peaks
        elevation = (
            3000 * np.exp(-(X**2 + Y**2) / 4) +  # Main peak
            2000 * np.exp(-((X-2)**2 + (Y-2)**2) / 2) +  # Secondary peak
            1500 * np.exp(-((X+2)**2 + (Y+1)**2) / 3)  # Third peak
        )
        
        # Add some noise for realism
        elevation += np.random.normal(0, 50, elevation.shape)
        elevation = np.maximum(0, elevation)  # No negative elevations
        
        return elevation
    
    def get_sample_temperature_data(self, elevation: np.ndarray) -> np.ndarray:
        """
        Generate sample temperature data based on elevation.
        Uses standard lapse rate: ~6.5°C per 1000m
        
        Args:
            elevation: 2D array of elevation values
            
        Returns:
            2D array of temperature values (Celsius)
        """
        # Base temperature at sea level (varies by latitude in reality)
        base_temp = 25.0
        
        # Standard atmospheric lapse rate
        lapse_rate = 6.5 / 1000  # degrees C per meter
        
        # Calculate temperature based on elevation
        temperature = base_temp - (elevation * lapse_rate)
        
        # Add some random variation
        temperature += np.random.normal(0, 2, temperature.shape)
        
        return temperature
    
    def create_sample_dataset(self) -> dict:
        """
        Create a complete sample dataset for visualization.
        
        Returns:
            Dictionary containing elevation, temperature, and coordinate data
        """
        elevation = self.get_sample_elevation_data()
        temperature = self.get_sample_temperature_data(elevation)
        
        # Create coordinate grids (lat/lon)
        lats = np.linspace(-45, 45, elevation.shape[0])
        lons = np.linspace(-90, 90, elevation.shape[1])
        
        return {
            'elevation': elevation,
            'temperature': temperature,
            'latitudes': lats,
            'longitudes': lons,
            'description': 'Sample mountain range with temperature gradients'
        }


# Public data source URLs (for future implementation)
DATA_SOURCES = {
    'elevation': {
        'srtm_sample': 'https://www2.jpl.nasa.gov/srtm/',
        'etopo1': 'https://www.ngdc.noaa.gov/mgg/global/global.html'
    },
    'climate': {
        'worldclim': 'https://www.worldclim.org/data/index.html',
        'noaa': 'https://www.ncei.noaa.gov/products/climate-data-records'
    }
}


if __name__ == "__main__":
    # Test the data manager
    dm = DataManager()
    dataset = dm.create_sample_dataset()
    
    print("\n=== Sample Dataset Created ===")
    print(f"Elevation range: {dataset['elevation'].min():.0f}m - {dataset['elevation'].max():.0f}m")
    print(f"Temperature range: {dataset['temperature'].min():.1f}°C - {dataset['temperature'].max():.1f}°C")
    print(f"Grid size: {dataset['elevation'].shape}")

