"""
Handles geographic border loading, caching, and operations.
Supports drawing borders on visualizations and masking data to country boundaries.
"""
import pickle
from pathlib import Path
from typing import Optional, Union, List, Tuple
import numpy as np

try:
    import geopandas as gpd
    from shapely.geometry import mapping
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


class BorderManager:
    """
    Manages geographic border data from Natural Earth.
    Provides caching, querying, and visualization utilities.
    """
    
    def __init__(self, cache_dir: str = "data/.cache/borders"):
        """
        Initialize the border manager.
        
        Args:
            cache_dir: Directory to cache downloaded border data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._world_data = None
        self._resolution = None
        
    def load_borders(self, resolution: str = '110m', force_reload: bool = False) -> gpd.GeoDataFrame:
        """
        Load Natural Earth border data with caching.
        
        Args:
            resolution: Natural Earth resolution ('10m', '50m', or '110m')
                       10m = high detail (large file)
                       50m = medium detail
                       110m = low detail (small file, good for global maps)
            force_reload: Force re-download even if cached
            
        Returns:
            GeoDataFrame with country borders
        """
        if not HAS_GEOPANDAS:
            raise ImportError("geopandas is required for border operations. Install with: pip install geopandas")
        
        cache_file = self.cache_dir / f"ne_{resolution}_countries.pkl"
        
        # Return cached data if available and not forcing reload
        if not force_reload and cache_file.exists():
            if self._world_data is not None and self._resolution == resolution:
                return self._world_data
            
            print(f"   - Loading borders from cache: {cache_file}")
            with open(cache_file, 'rb') as f:
                self._world_data = pickle.load(f)
                self._resolution = resolution
                return self._world_data
        
        # Download from Natural Earth
        print(f"   - Downloading Natural Earth {resolution} borders...")
        ne_url = f"https://naciscdn.org/naturalearth/{resolution}/cultural/ne_{resolution}_admin_0_countries.zip"
        self._world_data = gpd.read_file(ne_url)
        self._resolution = resolution
        
        # Cache for future use
        with open(cache_file, 'wb') as f:
            pickle.dump(self._world_data, f)
        print(f"   - Cached borders to: {cache_file}")
        
        return self._world_data
    
    def get_country(self, country_name: str, resolution: str = '110m') -> Optional[gpd.GeoDataFrame]:
        """
        Get border data for a specific country.
        
        Args:
            country_name: Country name (e.g., 'United States of America', 'Canada', 'Mexico')
            resolution: Natural Earth resolution
            
        Returns:
            GeoDataFrame for the country, or None if not found
        """
        world = self.load_borders(resolution)
        
        # Try exact match first
        country = world[world.ADMIN == country_name]
        
        # Try case-insensitive partial match if exact match fails
        if country.empty:
            country = world[world.ADMIN.str.contains(country_name, case=False, na=False)]
        
        if country.empty:
            available = sorted(world.ADMIN.unique())
            print(f"\n[!] Country '{country_name}' not found.")
            print(f"    Available countries: {', '.join(available[:10])}...")
            print(f"    (showing first 10 of {len(available)} countries)")
            return None
        
        return country
    
    def list_countries(self, resolution: str = '110m') -> List[str]:
        """
        List all available country names.
        
        Args:
            resolution: Natural Earth resolution
            
        Returns:
            Sorted list of country names
        """
        world = self.load_borders(resolution)
        return sorted(world.ADMIN.unique())
    
    def get_countries_in_bbox(self, bbox: Tuple[float, float, float, float], 
                            resolution: str = '110m') -> gpd.GeoDataFrame:
        """
        Get all countries that intersect with a bounding box.
        
        Args:
            bbox: Bounding box as (left, bottom, right, top) in lon/lat
            resolution: Natural Earth resolution
            
        Returns:
            GeoDataFrame with countries in the bbox
        """
        from shapely.geometry import box
        
        world = self.load_borders(resolution)
        bbox_geom = box(*bbox)
        
        # Find countries that intersect the bbox
        intersecting = world[world.intersects(bbox_geom)]
        
        return intersecting
    
    def mask_raster_to_country(self, raster_src: rasterio.DatasetReader, 
                              country_name: Union[str, List[str]], 
                              resolution: str = '110m',
                              invert: bool = False) -> Tuple[np.ndarray, rasterio.Affine]:
        """
        Mask a raster dataset to country boundaries.
        
        Args:
            raster_src: Open rasterio dataset
            country_name: Country name or list of country names
            resolution: Natural Earth resolution
            invert: If True, mask out the country (keep everything else)
            
        Returns:
            Tuple of (masked_array, transform)
        """
        if isinstance(country_name, str):
            country_name = [country_name]
        
        # Get country geometries
        countries = []
        for name in country_name:
            country = self.get_country(name, resolution)
            if country is not None and not country.empty:
                countries.append(country)
        
        if not countries:
            raise ValueError(f"No valid countries found from: {country_name}")
        
        # Combine all country geometries
        combined = gpd.GeoDataFrame(
            pd.concat(countries, ignore_index=True)
        )
        
        # Reproject to raster CRS
        combined = combined.to_crs(raster_src.crs)
        
        # Convert to geometries
        geoms = [mapping(geom) for geom in combined.geometry]
        
        # Mask the raster
        out_image, out_transform = rasterio_mask(
            raster_src, 
            geoms, 
            crop=False, 
            nodata=np.nan,
            invert=invert
        )
        
        return out_image[0], out_transform
    
    def get_border_coordinates(self, country_name: Union[str, List[str]], 
                             target_crs: Optional[str] = None,
                             resolution: str = '110m') -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Get border coordinates for plotting on maps.
        
        Args:
            country_name: Country name or list of country names
            target_crs: Target CRS to reproject to (e.g., rasterio.crs.CRS object)
            resolution: Natural Earth resolution
            
        Returns:
            List of (x_coords, y_coords) tuples for each border segment
        """
        if isinstance(country_name, str):
            country_name = [country_name]
        
        # Get country geometries
        countries = []
        for name in country_name:
            country = self.get_country(name, resolution)
            if country is not None and not country.empty:
                countries.append(country)
        
        if not countries:
            return []
        
        # Combine all country geometries
        combined = gpd.GeoDataFrame(
            pd.concat(countries, ignore_index=True)
        )
        
        # Reproject if needed
        if target_crs is not None:
            combined = combined.to_crs(target_crs)
        
        # Extract coordinates from each geometry
        border_coords = []
        for geom in combined.geometry:
            if geom.geom_type == 'Polygon':
                # Single polygon
                x, y = geom.exterior.xy
                border_coords.append((np.array(x), np.array(y)))
                
                # Also add holes (interior rings)
                for interior in geom.interiors:
                    x, y = interior.xy
                    border_coords.append((np.array(x), np.array(y)))
                    
            elif geom.geom_type == 'MultiPolygon':
                # Multiple polygons
                for poly in geom.geoms:
                    x, y = poly.exterior.xy
                    border_coords.append((np.array(x), np.array(y)))
                    
                    # Also add holes
                    for interior in poly.interiors:
                        x, y = interior.xy
                        border_coords.append((np.array(x), np.array(y)))
        
        return border_coords


def get_border_manager() -> BorderManager:
    """
    Get a singleton BorderManager instance.
    
    Returns:
        BorderManager instance
    """
    if not hasattr(get_border_manager, '_instance'):
        get_border_manager._instance = BorderManager()
    return get_border_manager._instance


# Import pandas here to avoid circular import
import pandas as pd

