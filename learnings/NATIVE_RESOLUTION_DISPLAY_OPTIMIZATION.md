# Native Resolution Display Optimization - Future Consideration

**Date:** 2025-01-XX  
**Status:** Design Note - Not Implemented  
**Related:** `ensure_region.py` resolution selection logic

## The Question

When we have 10m source data, why can't we display at 10m visible pixel resolution?

Current logic requires >=2.0x oversampling (Nyquist criterion):
- 10m source -> requires visible pixels >=20m
- 30m source -> requires visible pixels >=60m  
- 90m source -> requires visible pixels >=180m

But if we have 10m source data, couldn't we display at 10m visible resolution (1.0x = native resolution)?

## The Current Limitation

**Nyquist Sampling Rule:** To avoid aliasing when downsampling, we need >=2.0x oversampling.

**The Pipeline Process:**
1. We download raw source data (e.g., 10m GeoTIFF)
2. We reproject/clip/process it
3. We downsample using bilinear interpolation to target resolution
4. The resampling process requires >=2.0x oversampling to avoid aliasing

**Problem:** At 1.0x oversampling (10m visible / 10m source), we're at the Nyquist limit. Any resampling/interpolation risks aliasing because we're not providing enough samples for proper filtering.

## The Potential Optimization

**Idea:** If visible pixels ≈ source pixels (close to 1:1), skip downsampling entirely and use the raw data directly.

**When This Could Work:**
- Source: 10m resolution
- Visible: 10-15m resolution (1.0x - 1.5x oversampling)
- Instead of: Resampling 10m source -> 10m output (risky)
- Do: Use 10m source directly without resampling (no interpolation = no aliasing risk)

**Benefits:**
- Display native resolution data without quality loss
- Avoid resampling artifacts when at or near 1:1 ratio
- Better quality for small regions that need high detail

**Challenges:**
1. **Coordinate system alignment:** Raw data must align exactly with desired output bounds/pixels
2. **Metadata handling:** Output format must preserve source resolution metadata
3. **Pipeline changes:** Need to detect "native resolution" case and skip resampling step
4. **Edge cases:** What if visible = 11m but source = 10m? (1.1x - close but not exact)
5. **Reprojection:** Raw data may still need reprojection (EPSG:4326 -> EPSG:3857) - can we skip resampling after reprojection?

## Technical Consideration

**Nyquist applies to resampling operations**, not to using raw data directly.

- **If resampling:** Need >=2.0x oversampling (current requirement)
- **If no resampling:** Can use at native resolution (1.0x) or slightly below (1.0x-1.5x) if we're just using raw pixels directly

**Implementation Approach:**
1. Detect when `visible_pixels ≈ source_resolution` (e.g., within 10-20%)
2. In pipeline, check if we can skip downsampling step
3. Use reprojected/clipped data directly without bilinear resampling
4. This would require changes to `src/pipeline.py` downsample logic

## Current Status

**Not implemented** - This is a potential future optimization.

**Current behavior:** Requires >=2.0x oversampling for all cases, even when we have native resolution data available. This is conservative and safe, but may be unnecessarily restrictive for very small, high-detail regions.

## Related Code

- `ensure_region.py::determine_min_required_resolution()` - Current resolution selection (requires >=2.0x)
- `src/pipeline.py::downsample_for_viewer()` - Downsampling logic using bilinear interpolation
- `learnings/RESAMPLING_QUALITY_THRESHOLDS.md` - Background on Nyquist requirements

## Questions to Answer (If Implementing)

1. What's the threshold? (e.g., use native when 0.9x - 1.1x ratio?)
2. Do we still need reprojection? (Probably yes - EPSG:4326 -> EPSG:3857)
3. How do we handle aspect ratio preservation? (Raw data may have different aspect than target)
4. What about clipping/boundaries? (Must still apply geographic masks)
5. Performance impact? (Skipping resampling should be faster)

## Recommendation

**Document this for future consideration** but don't implement now:
- Current 2.0x requirement is conservative and safe
- Edge case (very small regions needing native 10m) is rare
- Implementation complexity is significant
- Would need thorough testing to ensure quality
- Better to optimize after validating current pipeline more thoroughly

