# Adjacency System Simplification

Date: 2025-11-07

## Problem

The adjacency computation system had unnecessary complexity:

1. **8-way direction calculation** → split diagonals into TWO cardinals → deduplicate
2. **Hardcoded adjacency data** in `src/us_state_adjacency.py` that could get out of sync
3. **Complex deduplication logic** with tie-breaking when borders had equal lengths

This caused issues like California-Nevada appearing in both "north" and "east" from California's perspective, requiring complex tie-breaking logic.

## Solution

### 1. Pure 4-Cardinal Direction System

Simplified `get_cardinal_direction()` to use only 4 directions with 90-degree sectors:
- **East**: -45° to 45° (0° = due east)
- **North**: 45° to 135° (90° = due north)
- **West**: 135° to 225° (180° = due west)
- **South**: 225° to 315° (270° = due south)

**Benefits:**
- Each neighbor appears in exactly ONE direction
- No deduplication needed
- No tie-breaking logic needed
- Diagonal borders (like California-Nevada) correctly classified based on centroid angle
- ~80 fewer lines of code

### 2. Remove Hardcoded Data

The hardcoded adjacency data in `src/us_state_adjacency.py` is deprecated in favor of computed adjacency from `compute_adjacency.py`. This:
- Eliminates maintenance burden
- Prevents data drift between two sources
- Uses actual geographic boundaries as single source of truth

## Example: California-Nevada

**Old system:**
1. Compute angle between centroids → ~60° (northeast)
2. Split into both "north" AND "east"
3. Try to deduplicate by border length
4. Border lengths equal → apply tie-breaking logic (dx vs dy)
5. Pick "east"

**New system:**
1. Compute angle between centroids → ~60°
2. Falls in 45°-135° sector → "east"
3. Done!

## Files Changed

- `compute_adjacency.py`: Simplified to 4-cardinal system, removed ~80 lines
- `src/us_state_adjacency.py`: Marked as deprecated (kept for reference)

## Results

Clean adjacency data with no duplicates:
```json
"california": {
  "north": "oregon",
  "east": ["arizona", "nevada"]
},
"nevada": {
  "west": "california"
}
```

