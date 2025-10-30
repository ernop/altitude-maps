# Download Guide

**Quick reference for downloading and processing regions.**

For complete pipeline specification, see **[DATA_PIPELINE.md](DATA_PIPELINE.md)**.

---

## Quick Start

### Activate Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### Download and Process a Region (One Command)
```powershell
# US state
python ensure_region.py ohio

# International region
python ensure_region.py iceland

# High resolution
python ensure_region.py california --target-pixels 4096

# Force reprocess
python ensure_region.py tennessee --force-reprocess
```

**That's it!** The `ensure_region.py` script handles:
- Region validation
- Data source selection (USGS 3DEP for US, OpenTopography for international)
- Automatic tiling for large areas
- Boundary clipping
- Reprojection and downsampling
- JSON export and compression
- Manifest updates

---

## List Available Regions

```powershell
python ensure_region.py --list-regions
```

Shows all configured regions: US states, countries, and special regions.

---

## Check Status Only

```powershell
python ensure_region.py ohio --check-only
```

Shows current pipeline status without downloading or processing.

---

## Command Options

- `--target-pixels N`: Target resolution (default: 800)
- `--border-resolution 10m|50m|110m`: Border detail level (default: 10m, use 10m for production)
- `--force-reprocess`: Force full rebuild from raw data
- `--check-only`: Check status only, don't modify files
- `--list-regions`: List all available regions

---

## Adding New Regions

1. Edit `src/regions_config.py`
2. Add `RegionConfig` to appropriate category:
   - `US_STATES` - US states (always uses USGS 3DEP 10m)
   - `COUNTRIES` - Countries (uses OpenTopography SRTMGL1/COP30)
   - `REGIONS` - Islands, peninsulas, mountain ranges
3. Run `python ensure_region.py --list-regions` to verify

Example:
```python
"iceland": RegionConfig(
    id="iceland",
    name="Iceland",
    bounds=(-24.5, 63.4, -13.5, 66.6),
    description="Iceland - volcanic terrain",
    category="region",
    clip_boundary=True,  # Iceland has known boundaries
),
```

---

## Viewer Integration

After processing, regions automatically appear in the viewer:

1. Start viewer: `python serve_viewer.py`
2. Open: http://localhost:8001/interactive_viewer_advanced.html
3. Select region from dropdown

The manifest (`generated/regions/regions_manifest.json`) is automatically updated after each successful export.

---

## Troubleshooting

### "Unknown region"
- Check spelling: `python ensure_region.py --list-regions`
- Ensure region is defined in `src/regions_config.py`

### "API key required"
Add OpenTopography API key to `settings.json`:
```json
{
  "opentopography_api_key": "your_key_here"
}
```
Get free key: https://portal.opentopography.org/

### Region downloads but doesn't show in viewer
Manifest may be stale. Processing automatically updates it, but you can regenerate:
```powershell
python regenerate_manifest.py
```

### Download fails (timeout, too large)
- Large regions are automatically tiled (invisible to user)
- If still failing, check API limits or try a smaller region

---

## Complete Pipeline Specification

For detailed information about:
- Exact file paths and naming conventions
- Pipeline stages (download → clip → process → export)
- Region classes and their requirements
- Versioning and cache management

See **[DATA_PIPELINE.md](DATA_PIPELINE.md)** - the canonical reference.

---

## Related Documentation

- **Complete Pipeline**: `tech/DATA_PIPELINE.md` - Full specification
- **Data Principles**: `tech/DATA_PRINCIPLES.md` - Aspect ratios, rendering
- **Technical Reference**: `tech/TECHNICAL_REFERENCE.md` - API reference
