# Obsolete Documentation

**These files are superseded by the canonical references and kept only for historical context.**

## Superseded by DATA_PIPELINE.md

The following implementation/planning docs are now obsolete since `DATA_PIPELINE.md` is the canonical reference:

- `90M_IMPLEMENTATION_SUMMARY.md` - 90m implementation notes (completed, now in DATA_PIPELINE.md)
- `SRTM_90M_DOWNLOADER.md` - 90m downloader specifics (redundant with DATA_PIPELINE.md Stage 5)
- `TESTING_90M_DOWNLOADER.md` - Testing notes (completed)
- `IMPLEMENTATION_PLAN.md` - Original implementation plan (completed)
- `IMPLEMENTATION_STATUS.md` - Status tracking (completed)
- `CONSOLIDATION_PLAN.md` - Planning doc (completed)

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
7. **`RATE_LIMIT_COORDINATION.md`** - OpenTopography rate limiting
8. **`GRID_ALIGNMENT_STRATEGY.md`** - Tile naming and alignment
9. **`DATA_FORMAT_EFFICIENCY.md`** - JSON/GZIP compression

---

**Rule**: When documentation conflicts, DATA_PIPELINE.md wins. Update or delete the conflicting doc.

