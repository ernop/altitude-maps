"""Calculate correct bounds for test regions."""
import math
from src.tile_geometry import calculate_visible_pixel_size

# For 10m: need visible <= 20m/pixel
# For 30m: need 60m <= visible < 180m/pixel  
# For 90m: need visible >= 180m/pixel

target_pixels = 1024

# Test current bounds
print("Current bounds:")
bounds_10m = (-106.09, 39.43, -105.91, 39.57)
visible = calculate_visible_pixel_size(bounds_10m, target_pixels)
print(f"  10m test: visible={visible['avg_m_per_pixel']:.2f}m/pixel, width={visible['real_world_width_km']:.2f}km")

bounds_30m = (-110.905, 40.14, -109.695, 41.06)
visible = calculate_visible_pixel_size(bounds_30m, target_pixels)
print(f"  30m test: visible={visible['avg_m_per_pixel']:.2f}m/pixel, width={visible['real_world_width_km']:.2f}km")

bounds_90m = (-110.76, 42.08, -108.24, 43.92)
visible = calculate_visible_pixel_size(bounds_90m, target_pixels)
print(f"  90m test: visible={visible['avg_m_per_pixel']:.2f}m/pixel, width={visible['real_world_width_km']:.2f}km")

print("\nRequired ranges:")
print(f"  10m: visible <= 20m -> width <= {20 * target_pixels / 1000:.2f}km")
print(f"  30m: 60m <= visible < 180m -> width between {60 * target_pixels / 1000:.2f}km and {180 * target_pixels / 1000:.2f}km")
print(f"  90m: visible >= 180m -> width >= {180 * target_pixels / 1000:.2f}km")

# Calculate correct bounds
print("\nCalculating correct bounds:")

# 10m: visible = 20m (exactly meets Nyquist: 20/10 = 2.0x)
lat = 39.5
lon_per_deg = 111320 * math.cos(math.radians(lat))
lat_per_deg = 111320
width_m = 20 * target_pixels  # 20m/pixel (exactly meets Nyquist)
width_deg = width_m / lon_per_deg
height_deg = width_m / lat_per_deg
center_lon = -106.0
center_lat = 39.5
bounds_10m_new = (
    center_lon - width_deg/2,
    center_lat - height_deg/2,
    center_lon + width_deg/2,
    center_lat + height_deg/2
)
print(f"  10m: bounds={bounds_10m_new}, width={width_deg:.4f}deg x {height_deg:.4f}deg")
visible = calculate_visible_pixel_size(bounds_10m_new, target_pixels)
print(f"       visible={visible['avg_m_per_pixel']:.2f}m/pixel OK")

# 30m: visible = 100m (safe, between 60m and 180m)
lat = 40.6
lon_per_deg = 111320 * math.cos(math.radians(lat))
lat_per_deg = 111320
width_m = 100 * target_pixels  # 100m/pixel
width_deg = width_m / lon_per_deg
height_deg = width_m / lat_per_deg
center_lon = -110.3
center_lat = 40.6
bounds_30m_new = (
    center_lon - width_deg/2,
    center_lat - height_deg/2,
    center_lon + width_deg/2,
    center_lat + height_deg/2
)
print(f"  30m: bounds={bounds_30m_new}, width={width_deg:.4f}deg x {height_deg:.4f}deg")
visible = calculate_visible_pixel_size(bounds_30m_new, target_pixels)
print(f"       visible={visible['avg_m_per_pixel']:.2f}m/pixel OK")

# 90m: visible = 200m (safe, above 180m threshold)
lat = 43.0
lon_per_deg = 111320 * math.cos(math.radians(lat))
lat_per_deg = 111320
width_m = 200 * target_pixels  # 200m/pixel
width_deg = width_m / lon_per_deg
height_deg = width_m / lat_per_deg
center_lon = -109.5
center_lat = 43.0
bounds_90m_new = (
    center_lon - width_deg/2,
    center_lat - height_deg/2,
    center_lon + width_deg/2,
    center_lat + height_deg/2
)
print(f"  90m: bounds={bounds_90m_new}, width={width_deg:.4f}deg x {height_deg:.4f}deg")
visible = calculate_visible_pixel_size(bounds_90m_new, target_pixels)
print(f"       visible={visible['avg_m_per_pixel']:.2f}m/pixel OK")

