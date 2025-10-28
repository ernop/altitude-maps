# Quick Reference Guide

## Multi-Word State Names

For states with multiple words (New Hampshire, North Dakota, etc.), you have **three options**:

### ✅ Option 1: Underscores (Recommended)
```powershell
python ensure_region.py new_hampshire
python check_region.py north_dakota
python reprocess_existing_states.py --states new_hampshire north_dakota
```

### ✅ Option 2: Quotes
```powershell
python ensure_region.py "new hampshire"
python check_region.py "north dakota"
python reprocess_existing_states.py --states "new hampshire" "north dakota"
```

### ✅ Option 3: Hyphens (converted to underscores)
```powershell
python ensure_region.py new-hampshire
python check_region.py north-dakota
```

All three formats work identically! The scripts automatically normalize them.

## Default Settings

All scripts now use **centralized defaults** from `src/config.py`:

- **Default target pixels:** 2048 (can override with `--target-pixels`)
- **Export format version:** export_v2
- **Minimum data coverage:** 20%

## Multi-Word States List

States requiring special formatting:
- New Hampshire → `new_hampshire` or `"new hampshire"`
- New Jersey → `new_jersey` or `"new jersey"`
- New Mexico → `new_mexico` or `"new mexico"`
- New York → `new_york` or `"new york"`
- North Carolina → `north_carolina` or `"north carolina"`
- North Dakota → `north_dakota` or `"north dakota"`
- Rhode Island → `rhode_island` or `"rhode island"`
- South Carolina → `south_carolina` or `"south carolina"`
- South Dakota → `south_dakota` or `"south dakota"`
- West Virginia → `west_virginia` or `"west virginia"`

## Common Commands

### One Command - Ensure Region Ready
```powershell
# Single word states
python ensure_region.py ohio
python ensure_region.py california --target-pixels 4096

# Multi-word states (use underscores)
python ensure_region.py new_hampshire
python ensure_region.py north_dakota --force-reprocess

# Multi-word states (use quotes)
python ensure_region.py "new hampshire"
python ensure_region.py "north dakota" --target-pixels 4096
```

### Check Region Status
```powershell
python check_region.py ohio
python check_region.py new_hampshire --verbose
python check_region.py "north dakota" --raw-only
```

### Reprocess Multiple States
```powershell
# Single command, multiple states
python reprocess_existing_states.py --states ohio kentucky tennessee

# Mix single and multi-word states
python reprocess_existing_states.py --states ohio new_hampshire california

# With quotes
python reprocess_existing_states.py --states ohio "new hampshire" california

# Force rebuild at specific resolution
python reprocess_existing_states.py --states ohio kentucky --target-pixels 4096 --force
```

## Resolution Guide

**Default: 2048 pixels** (good balance of quality and file size)

- **1024px** - Smaller files, faster loading, still good quality
- **2048px** - Default, recommended for most uses
- **4096px** - High detail, larger files (~4x size of 2048px)
- **8192px** - Very high detail, very large files (only for special cases)

Example file sizes for a typical state at 2048px: 5-20 MB JSON

## Pipeline Stages

Every region goes through 4 stages:

1. **Raw** - Downloaded bounding box data
2. **Clipped** - Masked to state/country boundary
3. **Processed** - Downsampled to target resolution
4. **Generated** - Exported as JSON for viewer

Use `check_region.py` to see status of all stages!

