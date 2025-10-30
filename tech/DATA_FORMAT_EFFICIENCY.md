# Data Format Efficiency

## Current Format Analysis

### The Format: Rectangular 2D Arrays with Nulls

Our elevation JSON files store data as **full rectangular 2D arrays**, including `null` values for areas outside the region boundary (ocean, neighboring states, etc.).

**Example: Oregon (1374x1453 pixels, downsampled to fit 2048px target)**
- File size: **12.5 MB** (uncompressed)
- Valid elevation data: **81.4%** (1,625,770 pixels)
- Null values: **18.6%** (370,370 pixels - coastline, rivers, borders)
- This is **not excessive** - Oregon is nearly rectangular with some coastal irregularity

### Why Nulls Exist

When we clip elevation data to state/country boundaries:
1. We mask pixels outside the boundary -> `NaN` in the array
2. Export converts `NaN` -> `null` in JSON
3. JSON stores the full rectangular bounding box containing the region

**Typical null percentages:**
- Rectangular states (Colorado, Wyoming): 5-10% nulls
- Coastal states (Oregon, California): 15-25% nulls  
- Island/complex coastlines (Alaska, Hawaii): 30-50% nulls
- Irregular inland (Tennessee, Oklahoma): 10-20% nulls

**From `src/pipeline.py` line 407:**
```python
for val in row:
    if np.isnan(val):  # Filter bad values (already marked as NaN)
        row_list.append(None)  # <- Stores 'null' in JSON
    else:
        row_list.append(float(val))
```

### Current Mitigations

####  1. GZIP Compression (NEW - October 2025)

**Development Server (`serve_viewer.py`):**
- Automatically gzips JSON files during transfer
- Typical compression: **85-95% reduction** for sparse data
- Oregon: 12.5 MB -> ~1.5 MB over the wire

**Production Deployment:**
- Configure nginx/Apache to enable gzip compression
- Add to nginx config:
  ```nginx
  gzip on;
  gzip_types application/json;
  gzip_comp_level 6;
  ```

####  2. Downsampling During Export

Target pixels set to reasonable defaults:
- States: 2048x2048 max (or auto-calculated based on size)
- Small regions: Lower resolution

This limits file sizes but doesn't eliminate the sparse data problem.

### Potential Future Improvements

If file sizes become a serious issue, consider:

#### Option A: Sparse Array Format
Store only non-null values with coordinates:
```json
{
  "format": "sparse",
  "width": 2048,
  "height": 2048,
  "data": [
    {"x": 0, "y": 0, "z": 1234.5},
    {"x": 0, "y": 1, "z": 1235.2},
    ...
  ]
}
```

**Pros:** Massive size reduction for sparse data  
**Cons:** More complex viewer code, slower to render

#### Option B: Run-Length Encoding
Compress consecutive null runs:
```json
{
  "format": "rle",
  "elevation": [
    [null, 75],  // 75 consecutive nulls
    [1234.5, 1], // 1 value
    [1235.2, 1], // 1 value
    ...
  ]
}
```

**Pros:** Good compression, relatively simple  
**Cons:** Still more complex than current format

#### Option C: Binary Format
Use binary format instead of JSON (e.g., MessagePack, Protocol Buffers)

**Pros:** Smaller size, faster parsing  
**Cons:** Not human-readable, requires decoder library

### Recommendation: Status Quo + GZIP

**Current approach (2D array + GZIP) is good enough because:**

1. **GZIP is extremely effective** on sparse data (85-95% compression)
2. **Simple format** means simple viewer code (easier maintenance)
3. **JSON is debuggable** (can open files and inspect)
4. **No breaking changes needed**

The "null spam" looks inefficient when you open the raw file, but with GZIP compression it's actually fine. Focus optimization efforts elsewhere (rendering performance, user experience, camera controls) rather than micro-optimizing data format.

### Validation: File Size Expectations

**With GZIP compression enabled:**
- Small states (Rhode Island, Delaware): 50-200 KB transferred
- Medium states (Ohio, Kentucky): 200-800 KB transferred
- Large states (California, Texas): 1-3 MB transferred
- Complex coastlines (Oregon, Alaska): Higher due to detail

**Total for all US states:** ~50 MB raw -> ~5-10 MB transferred with gzip

### Monitoring

When loading regions in the viewer, console shows:
```
[GZIP] oregon_srtm_30m_2048px_v2.json: 12234.5 KB -> 1456.7 KB (88.1% saved)
```

If compression ratios drop below 80%, investigate why (may indicate already-compressed data or binary content).

## Related Documentation

- `tech/TECHNICAL_REFERENCE.md` - Data format specification
- `DEPLOY_README.md` - Production compression configuration
- `.cursorrules` - Data format versioning rules

