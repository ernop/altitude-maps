"""
Handles geographic border loading, caching, and operations.
Supports drawing borders on visualizations and masking data to country boundaries.
"""
import pickle
from pathlib import Path
from typing import Optional, Union, List, Tuple
import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask

try:
    import geopandas as gpd
    from shapely.geometry import mapping
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
        self._state_data = None
        self._state_resolution = None
        
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
        
        # Mask the raster and crop to actual country bounds
        out_image, out_transform = rasterio_mask(
            raster_src, 
            geoms, 
            crop=True,  # Crop to minimum bounding box containing the geometry
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
    
    def load_state_borders(self, resolution: str = '110m', force_reload: bool = False) -> gpd.GeoDataFrame:
        """
        Load Natural Earth state/province border data (admin_1) with caching.
        
        Args:
            resolution: Natural Earth resolution ('10m', '50m', or '110m')
            force_reload: Force re-download even if cached
            
        Returns:
            GeoDataFrame with state/province borders
        """
        if not HAS_GEOPANDAS:
            raise ImportError("geopandas is required for border operations. Install with: pip install geopandas")
        
        cache_file = self.cache_dir / f"ne_{resolution}_admin_1.pkl"
        
        # Return cached data if available and not forcing reload
        if not force_reload and cache_file.exists():
            if self._state_data is not None and self._state_resolution == resolution:
                return self._state_data
            
            print(f"   - Loading state borders from cache: {cache_file}")
            with open(cache_file, 'rb') as f:
                self._state_data = pickle.load(f)
                self._state_resolution = resolution
                return self._state_data
        
        # Download from Natural Earth
        print(f"   - Downloading Natural Earth {resolution} admin_1 (states/provinces)...")
        ne_url = f"https://naciscdn.org/naturalearth/{resolution}/cultural/ne_{resolution}_admin_1_states_provinces.zip"
        self._state_data = gpd.read_file(ne_url)
        self._state_resolution = resolution
        
        # Cache for future use
        with open(cache_file, 'wb') as f:
            pickle.dump(self._state_data, f)
        print(f"   - Cached state borders to: {cache_file}")
        
        return self._state_data
    
    def get_state(self, country_name: str, state_name: str, resolution: str = '110m') -> Optional[gpd.GeoDataFrame]:
        """
        Get border data for a specific state/province.
        
        Args:
            country_name: Country name (e.g., 'United States of America')
            state_name: State/province name (e.g., 'Tennessee', 'California')
            resolution: Natural Earth resolution
            
        Returns:
            GeoDataFrame for the state, or None if not found
        """
        states = self.load_state_borders(resolution)
        
        # Try exact match first
        state = states[(states['admin'] == country_name) & (states['name'] == state_name)]
        
        # Try case-insensitive match if exact match fails
        if state.empty:
            state = states[
                (states['admin'].str.lower() == country_name.lower()) & 
                (states['name'].str.lower() == state_name.lower())
            ]
        
        if state.empty:
            # Show available states in this country
            available_states = states[states['admin'].str.contains(country_name, case=False, na=False)]['name'].tolist()
            if available_states:
                print(f"\n[!] State '{state_name}' not found in '{country_name}'.")
                print(f"    Available states: {', '.join(sorted(available_states)[:10])}...")
                print(f"    (showing first 10 of {len(available_states)} states)")
            else:
                print(f"\n[!] Country '{country_name}' not found in state database.")
            return None
        
        return state
    
    def list_states_in_country(self, country_name: str, resolution: str = '110m') -> List[str]:
        """
        List all states/provinces in a specific country.
        
        Args:
            country_name: Country name (e.g., 'United States of America')
            resolution: Natural Earth resolution
            
        Returns:
            Sorted list of state/province names
        """
        states = self.load_state_borders(resolution)
        
        # Filter by country (case-insensitive)
        country_states = states[states['admin'].str.lower() == country_name.lower()]
        
        return sorted(country_states['name'].unique())
    
    def mask_raster_to_state(self, raster_src: rasterio.DatasetReader, 
                            country_name: str, 
                            state_name: str,
                            resolution: str = '110m') -> Tuple[np.ndarray, rasterio.Affine]:
        """
        Mask a raster dataset to state/province boundaries.
        
        Args:
            raster_src: Open rasterio dataset
            country_name: Country name (e.g., 'United States of America')
            state_name: State/province name (e.g., 'Tennessee')
            resolution: Natural Earth resolution
            
        Returns:
            Tuple of (masked_array, transform)
        """
        # Get state geometry
        state = self.get_state(country_name, state_name, resolution)
        
        if state is None or state.empty:
            raise ValueError(f"State '{state_name}' not found in '{country_name}'")
        
        # Reproject to raster CRS
        state_reproj = state.to_crs(raster_src.crs)
        
        # Convert to geometries
        geoms = [mapping(geom) for geom in state_reproj.geometry]
        
        # Mask the raster and crop to actual state bounds
        out_image, out_transform = rasterio_mask(
            raster_src, 
            geoms, 
            crop=True,  # Crop to minimum bounding box containing the state
            nodata=np.nan,
            invert=False
        )
        
        return out_image[0], out_transform


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


# Convenience functions for easy access
def get_country_geometry(country_name: str, resolution: str = '110m'):
    """
    Get shapely geometry for a country (for use in clipping).
    
    Args:
        country_name: Country name (e.g., 'United States of America')
        resolution: Natural Earth resolution ('10m', '50m', '110m')
        
    Returns:
        Shapely geometry object, or None if not found
    """
    bm = get_border_manager()
    country = bm.get_country(country_name, resolution)
    
    if country is None or country.empty:
        return None
    
    # Return the unary union of all geometries (in case of multi-part countries)
    from shapely.ops import unary_union
    return unary_union(country.geometry)


def list_countries(resolution: str = '110m') -> List[str]:
    """
    List all available country names.
    
    Args:
        resolution: Natural Earth resolution
        
    Returns:
        List of country names
    """
    bm = get_border_manager()
    return bm.list_available(resolution)
