"""
Handles the data loading, caching, and processing for the elevation visualization.
"""
import time
import pickle
import numpy as np
from pathlib import Path

try:
    import rasterio
    from rasterio.mask import mask
    import geopandas as gpd
    from shapely.geometry import mapping
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

def prepare_visualization_data(tif_path: str):
    """
    Loads, processes, and transforms all data needed for the visualization.

    Args:
        tif_path: Path to the GeoTIFF elevation file.

    Returns:
        A dictionary containing all the processed data required for rendering.
    """
    overall_start = time.time()
    print("\n" + "=" * 70)
    print("  STEP 1: DATA PROCESSING")
    print("=" * 70)

    # --- 1. Load Elevation Data ---
    step_start = time.time()
    print(f"\n📂 Loading GeoTIFF: {tif_path}")
    with rasterio.open(tif_path) as src:
        elevation = src.read(1)
        bounds = src.bounds
        crs = src.crs
        
        if src.nodata is not None:
            elevation = np.where(elevation == src.nodata, np.nan, elevation)
        
        print(f"   - Shape: {elevation.shape}")
        print(f"   - Elevation: {np.nanmin(elevation):.0f}m to {np.nanmax(elevation):.0f}m")
        print(f"   ⏱️  Time: {time.time() - step_start:.2f}s")

        # --- 2. Load Borders & Mask Data (with Caching) ---
        step_start = time.time()
        
        cache_dir = Path("data/.cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{Path(tif_path).stem}_masked.pkl"
        
        if cache_file.exists():
            print("\n🗺️  Loading masked data from cache...")
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            elevation = cached_data['elevation']
            print(f"   - Loaded from: {cache_file}")
            print(f"   ⏱️  Cache load time: {time.time() - step_start:.2f}s")
        elif HAS_GEOPANDAS:
            print("\n🗺️  Loading USA borders and masking data (first run)...")
            border_start = time.time()
            ne_url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
            world = gpd.read_file(ne_url)
            print(f"   - Natural Earth download/load: {time.time() - border_start:.2f}s")
            
            usa = world[world.ADMIN == 'United States of America']
            if not usa.empty:
                usa = usa.to_crs(crs)
                
                mask_start = time.time()
                geoms = [mapping(usa.geometry.iloc[0])]
                out_image, _ = mask(src, geoms, crop=False, nodata=np.nan)
                elevation_masked = out_image[0]
                
                if np.any(~np.isnan(elevation_masked)):
                    elevation = elevation_masked
                    print(f"   - Masked data to USA boundaries: {time.time() - mask_start:.2f}s")

                print("   - Saving to cache...")
                with open(cache_file, 'wb') as f:
                    pickle.dump({'elevation': elevation}, f)
                print(f"   - Cache saved to: {cache_file}")
            print(f"   ⏱️  Total border/mask time: {time.time() - step_start:.2f}s")
        else:
            print("\n⚠️ Geopandas not found. Skipping masking. Install with: pip install geopandas")

    # --- 3. Prepare Data for Visualization ---
    step_start = time.time()
    print("\n⚙️  Preparing data for visualization...")
    original_shape = elevation.shape

    # Transformations
    elevation_viz = np.fliplr(elevation)
    elevation_viz = np.rot90(elevation_viz, k=-1)
    elevation_viz = np.rot90(elevation_viz, k=2)
    
    z_min, z_max = np.nanmin(elevation_viz), np.nanmax(elevation_viz)
    
    print(f"   - Applied flip and 2 rotations")
    print(f"   ⏱️  Preparation time: {time.time() - step_start:.2f}s")
    
    print("\n" + "=" * 70)
    print(f"  DATA PROCESSING COMPLETE. Total time: {time.time() - overall_start:.2f}s")
    print("=" * 70)

    return {
        "elevation_viz": elevation_viz,
        "bounds": bounds,
        "z_min": z_min,
        "z_max": z_max,
        "original_shape": original_shape
    }
