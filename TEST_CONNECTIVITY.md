# Testing the State Connectivity Feature

## Quick Test

1. **Start the viewer**:
   ```bash
   python serve_viewer.py
   ```

2. **Open in browser**: http://localhost:8001

3. **Test with California**:
   - Select "California" from the region dropdown
   - Look for the compass markers (N, S, E, W colored balls)
   - Near the **N** marker: Should see "Oregon" label
   - Near the **NE** marker: Should see "Nevada" label  
   - Near the **E** marker: Should see "Arizona" label
   - Click any label → should jump to that state

4. **Test with Tennessee** (8 neighbors - good stress test):
   - Select "Tennessee" from dropdown
   - Should see labels in all 8 directions:
     - N: Kentucky
     - NE: Virginia
     - E: North Carolina
     - SE: Georgia
     - S: Alabama
     - SW: Mississippi
     - W: Arkansas
     - NW: Missouri
   - Click any → jumps to that state

5. **Test with Ohio** (5 neighbors):
   - N: Michigan
   - NE: Pennsylvania
   - SE: West Virginia
   - S: Kentucky
   - W: Indiana

6. **Verify non-US regions don't show connectivity**:
   - Select "Iceland" → No connectivity labels (correct)
   - Select "Tasmania" → No connectivity labels (correct)

## Expected Behavior

### Visual Appearance
- Labels are rectangular with semi-transparent black background
- Colored border matches compass direction (N=red, S=blue, E=green, W=yellow)
- White text with state name
- Positioned near but not overlapping compass markers
- Multiple neighbors in same direction stack vertically

### Interaction
- **Hover**: Cursor changes to pointer
- **Click**: Immediately loads the neighboring state
- **Camera movement**: Labels stay fixed relative to terrain

### Console Output
- On init: "Loaded state adjacency data"
- Per state: "Created N connectivity labels for state_id"
- If no data: "No adjacency data for state_id"

## Troubleshooting

**Labels don't appear**:
- Check console for "Loaded state adjacency data"
- Verify `generated/us_state_adjacency.json` exists
- Make sure you're viewing a US state (not a country/region)

**Click doesn't work**:
- Check console for errors
- Verify the neighbor state exists in the manifest
- Try clicking center of label (not edges)

**Labels overlap compass markers**:
- This is intentional - they're positioned near the markers
- Labels are offset to minimize overlap

**Wrong neighbors shown**:
- Check `src/us_state_adjacency.py` data
- Re-run `python export_state_adjacency.py`
- Hard refresh browser (Ctrl+Shift+R)

## Performance Notes

- Labels are lightweight Three.js sprites
- Typical state has 3-5 neighbors (3-5 labels)
- Maximum is 8 neighbors (Tennessee, Missouri)
- No performance impact on rendering or camera controls


