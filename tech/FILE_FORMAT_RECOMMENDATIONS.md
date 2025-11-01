# File Format Recommendations

## Data Hierarchy (CRITICAL)

**Raw upstream files are the source of truth - preserve these exactly as downloaded.**

```
data/raw/          ← CRITICAL: Preserve exactly as downloaded (never modify)
  ├── usa_3dep/    ← USGS 3DEP downloads (format as-provided)
  ├── srtm_30m/    ← OpenTopography SRTM downloads (format as-provided)
  └── srtm_90m/    ← Lower resolution fallback (format as-provided)

data/clipped/      ← Can regenerate from raw (optimize these)
data/processed/    ← Can regenerate from clipped (optimize these)
generated/regions/ ← Can regenerate from processed (JSON - already gzipped)
```

**Principle**: As long as raw files are preserved, everything else can be regenerated.

---

## File Format Strategy

### Raw Files (`data/raw/`)
**Format**: Preserve exactly as downloaded from upstream providers
- **No modification**: Keep provider's format (standard GeoTIFF, COG, etc.)
- **No recompression**: Preserve original byte-for-byte
- **Reason**: These are the source of truth - modifying risks data loss

**Current providers:**
- USGS 3DEP: Standard GeoTIFF (often uncompressed)
- OpenTopography SRTM: Standard GeoTIFF (compression varies)
- Copernicus DEM: Standard GeoTIFF or COG

---

### Our Generated Files (Clipped, Processed)

**Current State**: Standard GeoTIFF, no compression, no optimization
**Recommended**: Cloud Optimized GeoTIFF (COG) with compression

#### Recommended Settings

```python
{
    "driver": "GTiff",
    "compress": "DEFLATE",      # Lossless compression (60-70% typical reduction)
    "tiled": True,               # Internal tiling for efficient access
    "blockxsize": 512,           # Tile width
    "blockysize": 512,           # Tile height
    "interleave": "band",        # Band-interleaved
    "predictor": 2,              # Horizontal differencing predictor (better compression)
    "ZLEVEL": 6,                 # DEFLATE compression level (balance speed vs ratio)
    "COPY_SRC_OVERVIEWS": "YES", # Copy overviews from source if available
    "SPARSE_OK": True,           # Allow sparse files (nodata regions)
    "BIGTIFF": "IF_SAFER",       # Use BigTIFF if needed (>4GB)
}
```

#### COG Optimization (Additional)

For maximum efficiency, apply COG validation:
- Requires `rio-cogeo` package
- Validates/creates proper COG structure
- Ensures header-first layout for streaming

**Example:**
```python
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

cog_translate(
    source_path,
    dst_path,
    **cog_profiles.get("deflate")  # Pre-configured COG profile
)
```

---

## Compression Comparison

For elevation data (float32, relatively smooth):

| Compression | Ratio | Speed | Lossless | Notes |
|------------|-------|-------|----------|-------|
| None | 0% | Fastest | Yes | Not recommended |
| LZW | 40-50% | Fast | Yes | Good compatibility |
| **DEFLATE** | **60-70%** | **Medium** | **Yes** | **Recommended** |
| ZSTD | 65-75% | Medium | Yes | Best compression |
| JPEG | 80-90% | Fast | No | Lossy - don't use |

**Recommendation**: DEFLATE (good balance of compression and speed)

---

## File Size Estimates

For float32 elevation data:

| Stage | Compression | Typical Size | Notes |
|-------|------------|-------------|-------|
| Raw (uncompressed) | None | 100 MB | USGS 3DEP example |
| Raw (compressed) | Provider | 40-60 MB | Varies by provider |
| Clipped (DEFLATE) | 60-70% | 25-35 MB | Our optimization |
| Processed (DEFLATE) | 60-70% | 15-25 MB | Downsampled |
| JSON (gzipped) | 85-95% | 1-2 MB | Already optimized |

---

## Implementation Priority

1. **Now**: Add DEFLATE compression to clipped/processed files
   - Quick win, significant size reduction (60-70%)
   - No format change required
   - Standard GeoTIFF compression

2. **Now**: Add internal tiling (along with compression)
   - Improves read performance (random access)
   - Works with DEFLATE for better compression
   - Required for future COG migration

3. **Future (not now)**: Full COG validation
   - Optimal for web/cloud delivery
   - Requires `rio-cogeo` dependency
   - DEFLATE + tiling gives us most of the benefit already
   - Can add later as enhancement

4. **Future**: Consider ZSTD compression (if GDAL 3.4+)
   - Best compression ratio (65-75%)
   - Requires newer GDAL version

---

## Code Changes Required

### 1. Update `clip_to_boundary()` (src/pipeline.py)
Add compression to clipped file writes:
```python
out_meta.update({
    "compress": "DEFLATE",
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
    "predictor": 2,
    "ZLEVEL": 6,
})
```

### 2. Update `downsample_for_viewer()` (src/pipeline.py)
Add compression to processed file writes:
```python
out_meta.update({
    "compress": "DEFLATE",
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
    "predictor": 2,
    "ZLEVEL": 6,
})
```

### 3. Update `reproject_to_metric_crs()` (ensure_region.py)
Add compression to reprojected file writes (same settings)

---

## Migration Strategy

**For existing files:**
- Raw files: **Don't touch** - preserve as-is
- Clipped/Processed: Can be regenerated with new format
- Next `--force-reprocess` will create optimized versions

**Cache invalidation:**
- Format change = version bump for clipped/processed stages
- Old uncompressed files will be replaced on next processing

---

## Notes

1. **Raw files must never be modified** - they're the source of truth
2. **Compression is lossless** - no data loss with DEFLATE/LZW
3. **COG is backwards compatible** - standard GeoTIFF readers work
4. **File size savings**: Typically 60-70% for elevation data
5. **Performance**: Tiled files read faster (random access patterns)

---

## Testing

After implementation, verify:
- Files are ~60-70% smaller
- Files still readable with standard tools
- No data loss (compare statistics)
- Performance improved for web delivery

