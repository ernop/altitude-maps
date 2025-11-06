# Obsolete Documentation

**These files are superseded by the canonical references and kept only for historical context.**

## Superseded by DATA_PIPELINE.md

The following implementation/planning docs are now obsolete since `DATA_PIPELINE.md` is the canonical reference:

- `IMPLEMENTATION_PLAN.md` - Original implementation plan (completed)
- `IMPLEMENTATION_STATUS.md` - Status tracking (completed)
- `CONSOLIDATION_PLAN.md` - Planning doc (completed)

## Superseded by TILE_SYSTEM.md (DELETED - consolidated)

The following tile-related docs have been **deleted** and consolidated into `TILE_SYSTEM.md`:

- `GRID_ALIGNMENT_STRATEGY.md` - Grid alignment details (DELETED)
- `90M_IMPLEMENTATION_SUMMARY.md` - 90m tile implementation (DELETED)
- `SRTM_90M_DOWNLOADER.md` - 90m downloader specifics (DELETED)
- `TESTING_90M_DOWNLOADER.md` - Testing notes (DELETED)
- `learnings/TILE_NAMING_DESIGN.md` - Tile naming design alternatives (DELETED)

**Why keep them?**: Historical context for future developers wondering "why was it done this way?"

**When to reference them?**: Never for current development. Use DATA_PIPELINE.md instead.

## Active Documentation (Single Source of Truth)

### Core References (MUST follow these)
1. **`DATA_PIPELINE.md`** - Complete pipeline specification (CANONICAL)
2. **`DATA_PRINCIPLES.md`** - Aspect ratios, rendering principles  
3. **`DOWNLOAD_GUIDE.md`** - Quick start guide (defers to DATA_PIPELINE.md)

### Implementation
4. **`src/types.py`** - RegionType enum definition (MUST use this)
5. **`src/pipeline.py`** - Pipeline implementation
6. **`ensure_region.py`** - CLI entry point

### Specialized Topics
7. **`TILE_SYSTEM.md`** - Complete tile strategy (CANONICAL for all tile operations)
8. **`RATE_LIMIT_COORDINATION.md`** - OpenTopography rate limiting
9. **`DATA_FORMAT_EFFICIENCY.md`** - JSON/GZIP compression

---

**Rule**: When documentation conflicts, DATA_PIPELINE.md wins. Update or delete the conflicting doc.

