# Resampling Quality Thresholds - Technical Analysis

**Date:** 2025-01-09  
**Updated:** 2025-01-09 (threshold changed from 135m to 180m)  
**Context:** Smart resolution selection for OpenTopography downloads  
**Final Decision:** 180m threshold (2.0x Nyquist) chosen for guaranteed quality

## The Problem

When downsampling elevation data (e.g., 30m input → 100m output), we need to understand:
1. What's the minimum input-to-output ratio to avoid artifacts?
2. At what point is 90m input "good enough" vs needing 30m input?

## Research Findings

### Resampling Method: Bilinear Interpolation

Our pipeline uses `Resampling.bilinear` from rasterio (see `ensure_region.py:1650` and `src/pipeline.py:269, 513`). This is appropriate for continuous elevation data and significantly reduces moiré artifacts compared to nearest-neighbor.

### Anti-Aliasing Theory

**Shannon-Nyquist Sampling Theorem**: To avoid aliasing when downsampling, you need **at least 2x oversampling** (output resolution / input resolution ≥ 2.0x).

This is the theoretical minimum. Practical guidelines:

- **Guaranteed quality**: 2.0x+ oversampling (Nyquist criterion met)
- **Risk of artifacts**: 1.5-2.0x oversampling (marginal)
- **High risk of artifacts**: 1.0-1.5x oversampling (below Nyquist)
- **Guaranteed artifacts**: <1.0x (undersampling)

### Bilinear Interpolation Impact

Bilinear interpolation uses a 2×2 kernel (4 input pixels) to compute each output pixel:
- **Pros**: Smooth transitions, reduces blockiness
- **Cons**: Still vulnerable to aliasing if input resolution is too low
- **Observation**: With bilinear interpolation, artifacts may not be visible immediately below 2x, but risk increases as you approach 1.0x. Without empirical testing, we cannot guarantee safety below Nyquist.

## Our Specific Context

We're considering two scenarios when final visible resolution is ~100m:

### Scenario 1: Use 90m input → undersampling
- **Input**: 90m pixel size
- **Output**: 100m visible pixel size  
- **Oversampling**: 100/90 = 1.1x
- **Risk**: HIGH - Below 2.0x Nyquist minimum. Moiré and aliasing artifacts likely.

### Scenario 2: Use 30m input → oversampling
- **Input**: 30m pixel size
- **Output**: 100m visible pixel size
- **Oversampling**: 100/30 = 3.3x
- **Risk**: LOW - Well above 2x threshold, excellent quality

## Decision Framework

### Current Implementation (Too Aggressive)

```python
if visible['avg_m_per_pixel'] > 90:
    suggest_90m()
```

**Problem**: When visible pixels are 100m, 90m input gives 1.11x oversampling (below Nyquist minimum!)

### Recommended Threshold

Use a **2.0x Nyquist safety margin**:

```
90m input sufficient if: visible_pixels ≥ (90 × 2.0) = 180m
```

Below 180m visible, use 30m input for quality.

**Rationale**:
- Meets strict Shannon-Nyquist sampling theorem requirement
- Guaranteed to avoid aliasing/moiré artifacts
- Proven by signal processing theory
- Conservative but theoretically sound

## Updated Decision Logic

**Proposed threshold:** 

```python
if visible_pixels >= 180m:
    # 90m input gives 2.0x+ oversampling → Nyquist safe
    suggest_90m_dataset()
elif visible_pixels >= 60m:
    # 30m input gives 2.0x+ oversampling → Nyquist safe
    suggest_30m_dataset()
else:
    # Very high resolution needed (might need 10m if available)
    suggest_highest_available()
```

**Boundary cases**:
- 180m+: Use 90m (180/90 = 2.0x oversampling; meets Nyquist criterion exactly)
- 60m-180m: Use 30m (60/30 = 2.0x to 180/30 = 6.0x oversampling)
- <60m: Higher resolution needed if available

## Validation Example

**Iceland (visible ~400m pixels):**
- 90m input: 400/90 = **4.4x oversampling** ✓ EXCELLENT
- 30m input: 400/30 = **13.3x oversampling** ✓ WASTED DETAIL
- **Decision**: 90m is optimal

**Alaska (visible ~1,800m pixels):**
- 90m input: 1800/90 = **20x oversampling** ✓ EXCELLENT  
- 30m input: 1800/30 = **60x oversampling** ✓ EXTREME WASTE
- **Decision**: 90m is optimal

**Medium Region (visible ~120m pixels):**
- 90m input: 120/90 = **1.33x oversampling** ⚠️ MARGINAL
- 30m input: 120/30 = **4x oversampling** ✓ GOOD
- **Decision**: 30m recommended for quality

**Small Region (visible ~50m pixels):**
- 90m input: 50/90 = **0.56x oversampling** ✗ BAD (undersampled!)
- 30m input: 50/30 = **1.67x oversampling** ⚠️ MARGINAL (below Nyquist)
- **Decision**: Need 10m or better if available, else 30m is acceptable for small regions

## Implementation Impact

Change one line in `ensure_region.py`:

```python
# OLD (too aggressive):
if visible['avg_m_per_pixel'] > 90:

# NEW (conservative, quality-focused):
if visible['avg_m_per_pixel'] >= 180:  # 90m × 2.0 Nyquist criterion
```

## Trade-offs

**180m threshold (2.0x Nyquist) - CHOSEN:**
- ✅ Theoretical Nyquist safety
- ✅ Maximum quality guarantee
- ✅ Proven by signal processing theory
- ⚠️ Downloads more 30m data for medium-sized regions (90m-180m range)
- ⚠️ Still saves bandwidth for very large regions (>180m)

**Rejected: 135m threshold (1.5x) - NOT RECOMMENDED:**
- ❌ No empirical research supporting 1.5x as safe
- ❌ Risk of aliasing artifacts near threshold
- ❌ Cannot guarantee artifact-free output
- ✅ Would save more bandwidth (lower threshold)

## Recommendation

**Use 180m threshold (2.0x Nyquist)** for guaranteed quality:
- Theoretical safety: Meets strict Nyquist criterion
- No artifacts expected
- Proven by signal processing theory

**The 135m threshold (1.5x) was investigated but rejected:**
- Claims of "pragmatic balance" were not empirically validated
- Found no real research supporting 1.5x as safe for bilinear interpolation
- Would risk artifacts for regions like Anticosti (139m visible pixels)
- Without visual testing, we cannot guarantee 1.5x is artifact-free

## References

- USGS Raster Data Resampling Best Practices (NRCS)
- Esri Feature Preserving Smoothing documentation
- Shannon-Nyquist Sampling Theorem for anti-aliasing
- Bilinear interpolation 2×2 kernel behavior
- Practical oversampling guidelines (1.5-2x typical for geographic data)

