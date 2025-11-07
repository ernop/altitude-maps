# Multiple Data Sources - Quick Start Guide

## What's New?

The system now tries multiple elevation data sources automatically. If one source fails or is rate-limited, others are tried until data is obtained.

**No configuration needed** - it just works out of the box.

---

## How It Works

### Before (Single Source)
```
Download iceland.tif
  → OpenTopography SRTM...
  → FAILED (rate limited)
  → STOP, user must wait
```

### Now (Multiple Sources)
```
Download iceland.tif
  → OpenTopography SRTM...FAILED (rate limited)
  → Copernicus S3...SUCCESS ✓
  → Continue processing
```

---

## Available Sources

### 10m Resolution
- **USGS 3DEP** (US only) - No API key needed
- **Copernicus GLO-10** (Europe) - Direct S3, no auth

### 30m Resolution
- **SRTM via OpenTopography** - Requires API key
- **Copernicus via OpenTopography** - Requires API key
- **Copernicus S3** - Direct download, no auth, no rate limits
- **ALOS AW3D30** - Via OpenTopography, requires API key

### 90m Resolution
- **SRTM via OpenTopography** - Requires API key
- **Copernicus via OpenTopography** - Requires API key
- **Copernicus S3** - Direct download, no auth, no rate limits

---

## Basic Usage (No Configuration)

Just use the system normally:

```bash
# Works exactly as before
python ensure_region.py iceland

# System will:
# 1. Try OpenTopography first (fastest if not rate-limited)
# 2. If that fails, try Copernicus S3 (no rate limits)
# 3. If that fails, try AW3D30 (different sensor, often high quality)
# 4. Continue until data is obtained
```

**Output example:**
```
[Tile 1/6] N63_W025_30m.tif
  → Trying SRTM 30m (OpenTopography)...✗
  → Trying Copernicus GLO-30 (S3)...✓

Download complete: 6/6 tiles
Sources used:
  - Copernicus GLO-30 (S3): 6 tiles
```

---

## Optional Configuration

### Configure Source Priority

If you want to prefer certain sources, edit `settings.json`:

```json
{
  "opentopography": {
    "api_key": "your_key_here"
  },
  "data_sources": {
    "priority": [
      "copernicus_s3_30m",
      "opentopo_copernicus_30m",
      "opentopo_srtm_30m",
      "aw3d30"
    ]
  }
}
```

Now Copernicus S3 is tried first (no rate limits).

### Why Configure Priority?

**Prefer S3 sources to avoid rate limits:**
```json
"priority": [
  "copernicus_s3_30m",
  "copernicus_s3_90m",
  "opentopo_copernicus_30m",
  "opentopo_copernicus_90m"
]
```

**Prefer high-quality sources:**
```json
"priority": [
  "usgs_3dep",
  "aw3d30",
  "opentopo_copernicus_30m"
]
```

---

## Common Scenarios

### Scenario 1: OpenTopography Rate Limited

**Old behavior:**
- Download fails
- User must wait (check `python check_rate_limit.py`)
- Come back later

**New behavior:**
- OpenTopography fails
- Copernicus S3 automatically tried
- Download succeeds
- No user intervention needed

### Scenario 2: Mixed Sources

**What happens:**
```
[Tile 1/15] N40_W080_30m.tif
  → Trying SRTM 30m (OpenTopography)...✓

[Tile 2/15] N40_W081_30m.tif
  → Trying SRTM 30m (OpenTopography)...✗ (rate limit hit)
  → Trying Copernicus GLO-30 (S3)...✓

[continues with Copernicus S3 for remaining tiles]

Download complete: 15/15 tiles
Sources used:
  - SRTM 30m (OpenTopography): 1 tile
  - Copernicus GLO-30 (S3): 14 tiles
```

**Is this OK?** Yes! Both are 30m sources with comparable quality. Tiles merge seamlessly.

### Scenario 3: No Configuration

**What's the default order?**

For 30m:
1. OpenTopography SRTM/Copernicus (fastest if working)
2. Copernicus S3 (no rate limits)
3. ALOS AW3D30 (high quality, different sensor)

For 90m:
1. OpenTopography SRTM/Copernicus
2. Copernicus S3 (no rate limits)

For 10m:
1. USGS 3DEP (US only)
2. Copernicus GLO-10 (Europe only)

---

## Troubleshooting

### "No sources available for resolution"

**Cause:** No sources provide the resolution or cover the region.

**Solution:** Check resolution requirement makes sense. Verify region bounds are correct.

### "All sources failed for tile"

**Cause:** 
- Tile is over ocean (no elevation data)
- Network issues
- All sources temporarily unavailable

**What happens:**
- Warning printed
- Tile skipped
- Download continues for other tiles
- Merge uses whatever tiles succeeded

**If many tiles fail:**
- Check internet connection
- Verify region actually has land
- Try again later

### OpenTopography Still Rate Limited

**If you see:**
```
→ Trying SRTM 30m (OpenTopography)...✗ (rate limited)
→ Trying Copernicus GLO-30 (S3)...✓
```

This is **expected and fine**. The system is working correctly - it tried OpenTopography first, got rate limited, automatically switched to S3, and succeeded.

**To completely avoid OpenTopography:**

Configure S3 sources first in priority:
```json
"priority": [
  "copernicus_s3_30m",
  "copernicus_s3_90m"
]
```

---

## Data Storage

### Where Tiles Are Stored

Each source gets its own directory:

```
data/raw/
  srtm_30m/tiles/          # OpenTopography SRTM/Copernicus
  copernicus_s3_30m/tiles/ # Copernicus S3 direct download
  aw3d30/tiles/            # ALOS AW3D30
  srtm_90m/tiles/          # 90m sources
  copernicus_s3_90m/tiles/ # Copernicus S3 90m
  usa_3dep/tiles/          # USGS 3DEP 10m
```

**Why separate?** Different sources may have slightly different data. Keeping them separate:
- Allows redownloading from specific source if needed
- Makes it clear which source each tile came from
- Enables mixing sources when needed

### Tile Naming (Same Across Sources)

All tiles use standard resolution-based names:
```
N40_W080_30m.tif
N40_W080_90m.tif
N40_W080_10m.tif
```

**Not source-specific names** - this allows tiles from different sources (same resolution) to be used interchangeably.

---

## Advanced

### Adding New Sources

See `tech/DATA_SOURCES.md` section "Adding New Sources" for how to add new elevation datasets to the system.

### Understanding Source Capabilities

Each source declares:
- Resolution it provides
- Geographic coverage
- Whether authentication needed
- Storage locations

See `src/downloaders/source_registry.py` for complete source definitions.

### Parallel Downloads

Copernicus S3 buckets have no rate limits. Future enhancement could download multiple tiles in parallel for faster completion.

For now: Sequential downloads are simple and reasonably fast.

---

## Summary

**Key points:**

1. **No configuration needed** - works out of the box
2. **Tries sources automatically** - keeps going until data obtained
3. **OpenTopography + S3** - best of both (speed + no rate limits)
4. **User can configure priority** - optional, not required
5. **Transparent** - logs show which sources succeeded
6. **Same pipeline** - processing unchanged, works with any source

**The goal:** Get elevation data reliably, regardless of which source provides it.

---

## See Also

- **`tech/DATA_SOURCES.md`** - Complete reference of all data sources
- **`tech/SOURCE_EXPANSION_SUMMARY.md`** - Technical implementation details
- **`README.md`** - Updated with multi-source info
- **`settings.example.json`** - Example priority configuration

