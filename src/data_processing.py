"""
Handles the data loading, caching, and processing for the elevation visualization.
"""
import time
import pickle
import numpy as np
from pathlib import Path
import rasterio
from rasterio.mask import mask

try:
    import geopandas as gpd
    from shapely.geometry import mapping
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

from src.borders import get_border_manager

def prepare_visualization_data(tif_path: str, square_bucket_miles: float = None, 
                             square_bucket_pixels: int = None, mask_usa: bool = True,
                             mask_country: str = None, border_resolution: str = '110m'):
    """
    Loads, processes, and transforms all data needed for the visualization.

    Args:
        tif_path: Path to the GeoTIFF elevation file.
        square_bucket_miles: If set, divides the map into square buckets of this size (in miles)
                           and takes the MAX elevation within each bucket. E.g., 10 for 10x10 mile squares.
                           Accounts for Earth's curvature (latitude affects longitude spacing).
        square_bucket_pixels: If set, divides the map into square buckets of this size (in pixels)
                            and takes the MAX elevation within each bucket. Simpler method that ignores
                            geographic distances. E.g., 100 for 100x100 pixel buckets.
        mask_usa: If True, applies USA border masking (legacy, use mask_country='United States of America' instead).
        mask_country: If set, masks data to this country's borders (e.g., 'Canada', 'Mexico'). 
                     Can also be a list of countries for multi-country regions.
        border_resolution: Natural Earth border resolution ('10m', '50m', or '110m'). Default: '110m'
        Note: Only one of square_bucket_miles or square_bucket_pixels should be set.
              If both are set, square_bucket_miles takes precedence.
              None (default) means no bucketing - use all data points.

    Returns:
        A dictionary containing all the processed data required for rendering.
    """
    overall_start = time.time()
    print("\n" + "=" * 70, flush=True)
    print("  STEP 1: DATA PROCESSING", flush=True)
    print("=" * 70, flush=True)

    # --- 1. Load Elevation Data ---
    step_start = time.time()
    print(f"\n[*] Loading GeoTIFF: {tif_path}", flush=True)
    with rasterio.open(tif_path) as src:
        elevation = src.read(1)
        bounds = src.bounds
        crs = src.crs
        
        if src.nodata is not None:
            elevation = np.where(elevation == src.nodata, np.nan, elevation)
        
        print(f"   - Shape: {elevation.shape}", flush=True)
        print(f"   - Elevation: {np.nanmin(elevation):.0f}m to {np.nanmax(elevation):.0f}m", flush=True)
        print(f"   Time: {time.time() - step_start:.2f}s", flush=True)

        # --- 2. Load Borders & Mask Data (with Caching) ---
        # Convert legacy mask_usa parameter
        if mask_usa and mask_country is None:
            mask_country = 'United States of America'
        
        if mask_country:
            step_start = time.time()
            
            # Create country-specific cache filename
            if isinstance(mask_country, list):
                country_str = "_".join([c.replace(' ', '_') for c in mask_country])
            else:
                country_str = mask_country.replace(' ', '_')
            
            cache_dir = Path("data/.cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / f"{Path(tif_path).stem}_masked_{country_str}_{border_resolution}.pkl"
            
            if cache_file.exists():
                print(f"\n[*] Loading masked data from cache...", flush=True)
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                elevation = cached_data['elevation']
                print(f"   - Loaded from: {cache_file}", flush=True)
                print(f"   Time: {time.time() - step_start:.2f}s", flush=True)
            elif HAS_GEOPANDAS:
                country_display = mask_country if isinstance(mask_country, str) else ', '.join(mask_country)
                print(f"\n[*] Loading {country_display} borders and masking data (first run)...", flush=True)
                
                border_start = time.time()
                border_manager = get_border_manager()
                
                try:
                    mask_start = time.time()
                    elevation_masked, _ = border_manager.mask_raster_to_country(
                        src, mask_country, resolution=border_resolution
                    )
                    
                    if np.any(~np.isnan(elevation_masked)):
                        elevation = elevation_masked
                        print(f"   - Masked data to {country_display} boundaries: {time.time() - mask_start:.2f}s")
                        
                        print("   - Saving to cache...")
                        with open(cache_file, 'wb') as f:
                            pickle.dump({'elevation': elevation}, f)
                        print(f"   - Cache saved to: {cache_file}")
                    else:
                        print(f"   - WARNING: Masking resulted in no valid data. Using unmasked data.")
                    
                    print(f"   Time: {time.time() - step_start:.2f}s")
                except Exception as e:
                    print(f"   - ERROR during masking: {e}")
                    print(f"   - Continuing with unmasked data")
            else:
                print("\n[!] Geopandas not found. Skipping masking. Install with: pip install geopandas")
        else:
            print("\n[*] No country masking applied", flush=True)

    # --- 3. Square Bucketing (Optional) ---
    if square_bucket_miles is not None or square_bucket_pixels is not None:
        step_start = time.time()
        
        # Determine bucket size in pixels
        if square_bucket_miles is not None:
            # Geographic bucketing (accounts for Earth's curvature)
            print(f"\n[*] Applying {square_bucket_miles}x{square_bucket_miles} mile square bucketing (MAX, geographic)...", flush=True)
            
            # Calculate approximate degrees per mile (at mid-latitude ~39degN for continental USA)
            # At 39degN: 1 degree latitude ~ 69 miles, 1 degree longitude ~ 54 miles
            miles_per_deg_lat = 69.0
            miles_per_deg_lon = 54.0  # Approximate for central USA
            
            # Calculate pixel resolution from bounds
            height_px, width_px = elevation.shape
            height_deg = bounds.top - bounds.bottom
            width_deg = bounds.right - bounds.left
            
            deg_per_pixel_lat = height_deg / height_px
            deg_per_pixel_lon = width_deg / width_px
            
            miles_per_pixel_lat = deg_per_pixel_lat * miles_per_deg_lat
            miles_per_pixel_lon = deg_per_pixel_lon * miles_per_deg_lon
            
            # Calculate bucket size in pixels
            bucket_size_px_lat = int(np.ceil(square_bucket_miles / miles_per_pixel_lat))
            bucket_size_px_lon = int(np.ceil(square_bucket_miles / miles_per_pixel_lon))
            
            print(f"   - Original shape: {elevation.shape}")
            print(f"   - Resolution: {miles_per_pixel_lat:.3f} miles/px (lat), {miles_per_pixel_lon:.3f} miles/px (lon)")
            print(f"   - Bucket size: {bucket_size_px_lat}x{bucket_size_px_lon} pixels")
        else:
            # Simple pixel-based bucketing (ignores geographic distances)
            print(f"\n[*] Applying {square_bucket_pixels}x{square_bucket_pixels} pixel square bucketing (MAX, simple)...")
            bucket_size_px_lat = square_bucket_pixels
            bucket_size_px_lon = square_bucket_pixels
            print(f"   - Original shape: {elevation.shape}")
            print(f"   - Bucket size: {bucket_size_px_lat}x{bucket_size_px_lon} pixels")
        
        # Perform bucketing using max pooling
        height_px, width_px = elevation.shape
        bucketed_height = elevation.shape[0] // bucket_size_px_lat
        bucketed_width = elevation.shape[1] // bucket_size_px_lon
        
        # Trim edges to fit exact buckets
        trimmed_height = bucketed_height * bucket_size_px_lat
        trimmed_width = bucketed_width * bucket_size_px_lon
        elevation_trimmed = elevation[:trimmed_height, :trimmed_width]
        
        # Reshape and take max over each bucket
        bucketed = elevation_trimmed.reshape(
            bucketed_height, bucket_size_px_lat,
            bucketed_width, bucket_size_px_lon
        )
        
        # Take max along bucket dimensions (axis 1 and 3)
        elevation = np.nanmax(bucketed, axis=(1, 3))
        
        print(f"   - Bucketed shape: {elevation.shape} ({bucketed_height}x{bucketed_width} buckets)")
        print(f"   - Data reduction: {(1 - elevation.size / (height_px * width_px)) * 100:.1f}%")
        print(f"   Time: {time.time() - step_start:.2f}s")

    # --- 4. Prepare Data for Visualization ---
    step_start = time.time()
    print("\n[*] Preparing data for visualization...")
    original_shape = elevation.shape

    # Use data as-is from GeoTIFF (it's already in correct geographic orientation)
    # GeoTIFF standard: rows go North to South, columns go West to East
    elevation_viz = elevation
    
    z_min, z_max = np.nanmin(elevation_viz), np.nanmax(elevation_viz)
    
    print(f"   - Using natural GeoTIFF orientation (North up, East right)")
    print(f"   Time: {time.time() - step_start:.2f}s")
    
    print("\n" + "=" * 70)
    print(f"  DATA PROCESSING COMPLETE. Total time: {time.time() - overall_start:.2f}s")
    print("=" * 70)

    return {
        "elevation_viz": elevation_viz,
        "bounds": bounds,
        "z_min": z_min,
        "z_max": z_max,
        "original_shape": original_shape,
        "bucketed": square_bucket_miles is not None or square_bucket_pixels is not None,
        "bucket_size_miles": square_bucket_miles,
        "bucket_size_pixels": square_bucket_pixels
    }
