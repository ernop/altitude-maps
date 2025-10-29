# Pre-Deployment Testing Checklist

**Release Date:** TBD  
**Version:** October 2025 Camera Enhancements  
**Tester:** _____________

---

## Summary of Changes

This release includes major camera control enhancements:
- ✨ **WASD/QE keyboard movement** - Unity/Unreal-style flythrough
- 📱 **Touch/trackpad gestures** - Pinch zoom, pan (mobile & laptop support)
- 🎮 **Alt+Left rotate** - Maya/3ds Max style tumble
- 🎯 **F key reframe** - Quick reset to optimal view
- 🗺 **Google Earth style** - Right-drag rotation

---

## Critical Fixes Before This Test

###  Fixed: Keyboard Handler Conflicts
- **Issue:** F key was handled by both viewer and camera scheme (duplicate actions)
- **Issue:** No typing detection in main viewer (hotkeys active while typing)
- **Fix:** Added typing detection to `viewer-advanced.js` onKeyDown
- **Fix:** Removed F key handler from viewer (camera scheme handles it now)
- **Status:** Fixed in this session

---

## Testing Sections

### 1. Mouse Controls ✓ (Core Functionality)

**Basic Mouse Operations:**
- [ ] **Left drag** = Pan (grab and drag the map)
  - [ ] Drag up -> map moves up
  - [ ] Drag down -> map moves down
  - [ ] Drag left -> map moves left
  - [ ] Drag right -> map moves right
  - [ ] Movement is smooth and responsive

- [ ] **Shift+Left drag** = Tilt (adjust viewing angle)
  - [ ] Drag down -> tilt down (see more horizon)
  - [ ] Drag up -> tilt up (more overhead)
  - [ ] Angle limits prevent camera flip
  - [ ] Releasing Shift mid-drag cancels smoothly (no jank)

- [ ] **Alt+Left drag** = Rotate (Maya style)  NEW
  - [ ] Horizontal drag -> turn left/right
  - [ ] Vertical drag -> tilt up/down
  - [ ] Same behavior as Right drag
  - [ ] Releasing Alt mid-drag cancels smoothly

- [ ] **Right drag** = Rotate (Google Earth style)
  - [ ] Horizontal drag -> turn left/right
  - [ ] Vertical drag -> tilt up/down
  - [ ] Maintains distance from focus point
  - [ ] Smooth rotation at all angles

- [ ] **Mouse wheel** = Zoom
  - [ ] Scroll up -> zoom IN toward cursor
  - [ ] Scroll down -> zoom OUT from cursor
  - [ ] Point under cursor stays visually stable
  - [ ] Minimum distance limit prevents clipping (5 meters)
  - [ ] Focus point shifts bidirectionally (smooth zoom feel)

**Edge Cases:**
- [ ] Can combine operations (pan while keyboard moving)
- [ ] No jitter at any camera angle
- [ ] Camera doesn't flip or lose orientation
- [ ] Extreme zoom in/out works correctly

---

### 2. Keyboard Controls  (New Feature)

**WASD/QE Movement:**
- [ ] **W** = Move forward (in view direction)
- [ ] **S** = Move backward
- [ ] **A** = Strafe left
- [ ] **D** = Strafe right
- [ ] **Q** = Move down (descend)
- [ ] **E** = Move up (ascend)

**Combination Tests:**
- [ ] W+D moves diagonally forward-right
- [ ] W+E moves forward and up
- [ ] All 6 keys can be combined smoothly
- [ ] Can use mouse to look around while holding WASD

**F Key Reframe:**  NEW - CRITICAL TEST
- [ ] Press **F** -> Camera reframes to show full terrain
- [ ] View centers on terrain bounds
- [ ] Entire terrain visible with margins
- [ ] Works in bars mode
- [ ] Works in surface mode
- [ ] Works in points mode
- [ ] Works after changing bucket size
- [ ] Works after switching regions
- [ ] Console logs terrain center (debugging)

**R Key Reset:**
- [ ] Press **R** -> Camera resets to initial position
- [ ] Works as fallback if F key fails

**Space Bar:**
- [ ] Press **Space** -> Toggle auto-rotate on/off
- [ ] Auto-rotate checkbox updates
- [ ] Works correctly

**Typing Detection:**  CRITICAL - NEW FIX
- [ ] Type in region search box -> WASD/F/R keys don't affect camera
- [ ] Type in bucket size input -> Keys don't affect camera
- [ ] Type in exaggeration input -> Keys don't affect camera
- [ ] Click Select2 dropdown, search -> Keys don't affect camera
- [ ] Tab out of input -> Keys resume working
- [ ] No lag or delay in typing response

---

### 3. Touch/Trackpad Gestures  (New - Cannot fully test without device)

**Mobile Touch (Phone/Tablet):**
- [ ] Single finger drag = Pan
- [ ] Two-finger pinch = Zoom (pinch in = zoom, spread = zoom out)
- [ ] Pinch zooms toward center of fingers
- [ ] No page scrolling during gestures
- [ ] Smooth and responsive

**Laptop Trackpad:**
- [ ] Two-finger drag = Pan (Google Maps style)
- [ ] Two-finger pinch = Zoom
- [ ] Both gestures work simultaneously
- [ ] Sensitivity feels natural
- [ ] Works on MacBook trackpad
- [ ] Works on Windows precision trackpad

**Notes:**
- User reported they cannot test touch gestures (no touch device)
- Should be tested on actual mobile/tablet before production deploy
- Trackpad testing requires laptop with gesture support

---

### 4. UI and Visual Feedback

**Controls Help:**
- [ ] Controls help panel shows all shortcuts
- [ ] F key documented
- [ ] Alt+Left documented
- [ ] Touch gestures documented (if applicable)
- [ ] Panel toggles correctly

**Camera Scheme Selector:**
- [ ] Ground Plane Camera shows correct description
- [ ] Description mentions new features (F key, WASD, touch)
- [ ] Switching schemes works correctly
- [ ] Event listeners cleaned up on switch (no memory leaks)

**Console Output:**
- [ ] No errors in browser console
- [ ] No warnings about event listeners
- [ ] F key logs reframe action (debugging)
- [ ] Modifier cancellation logs correctly

**Performance:**
- [ ] 60 FPS maintained during movement
- [ ] No stuttering or frame drops
- [ ] Smooth transitions at all times
- [ ] Memory usage stable (no leaks after 5+ minutes)

---

### 5. Region and Data Loading

**Region Switching:**
- [ ] Load default region (USA if available)
- [ ] F key reframes correctly on initial load  NEW
- [ ] Switch to different region
- [ ] F key reframes to new region bounds  NEW
- [ ] Terrain bounds update correctly

**Bucket Size Changes:**
- [ ] Change bucket size to 1 (max detail)
- [ ] F key reframes correctly
- [ ] Change bucket size to 10
- [ ] F key still works

**Render Modes:**
- [ ] Test in bars mode
- [ ] F key reframes (bars coordinate system)
- [ ] Test in surface mode
- [ ] F key reframes (real-world scale)
- [ ] Test in points mode
- [ ] F key reframes (unit spacing)

**Vertical Exaggeration:**
- [ ] Change exaggeration to 10.0
- [ ] F key reframes correctly
- [ ] All controls still work

---

### 6. Cross-Browser Testing

**Chrome/Edge (Chromium):**
- [ ] All mouse controls work
- [ ] Keyboard controls work
- [ ] Typing detection works
- [ ] F key reframe works
- [ ] No console errors

**Firefox:**
- [ ] All mouse controls work
- [ ] Keyboard controls work
- [ ] Typing detection works
- [ ] F key reframe works
- [ ] No console errors

**Safari (if available):**
- [ ] All mouse controls work
- [ ] Keyboard controls work
- [ ] Touch gestures work (iPad/iPhone)
- [ ] No console errors

---

### 7. Documentation Updates Needed

- [ ] **README.md** - Brief mention of new camera features
  - [ ] F key reframe
  - [ ] Touch/trackpad support
  - [ ] Maya-style Alt+Left rotation

- [ ] **tech/USER_GUIDE.md** - Detailed usage guide
  - [ ] Full keyboard control table
  - [ ] Touch gesture descriptions
  - [ ] F key reframe explanation
  - [ ] Typing detection note

- [ ] **tech/CAMERA_CONTROLS.md** - Technical camera documentation
  - [ ] Updated control scheme summary
  - [ ] F key implementation details
  - [ ] Touch gesture architecture

---

### 8. Known Issues & Limitations

**Touch Gestures:**
-  NOT TESTED on actual touch devices (user has no touch device)
-  Should be tested on mobile/tablet before production
-  Trackpad testing needs laptop with gesture support

**Potential Issues to Watch For:**
- [ ] F key terrain bounds might be incorrect in some render modes
- [ ] Touch zoom sensitivity might need tuning
- [ ] Three-finger gestures not implemented (future enhancement)
- [ ] No visual mode indicators (pan/tilt/rotate)

---

### 9. Deployment Checklist

**Pre-Deploy:**
- [ ] All critical tests passed
- [ ] Documentation updated
- [ ] Known issues documented
- [ ] Git status clean (all changes committed)
- [ ] Version number/date updated in README

**Dry Run:**
- [ ] Run: `.\deploy.ps1 -RemoteHost example.com -RemotePath /var/www/maps -RemoteUser deploy -DryRun`
- [ ] Verify file list looks correct
- [ ] No unexpected files included
- [ ] No raw data (data/) being uploaded

**Actual Deploy:**
- [ ] Run: `.\deploy.ps1 -RemoteHost example.com -RemotePath /var/www/maps -RemoteUser deploy`
- [ ] Upload completes without errors
- [ ] Remote site accessible
- [ ] Test on remote: Mouse controls
- [ ] Test on remote: Keyboard controls
- [ ] Test on remote: F key reframe
- [ ] Test on remote: Region switching
- [ ] Browser console clean (no 404s, no errors)

---

### 10. Post-Deployment Validation

**Smoke Test (5 minutes):**
- [ ] Open viewer on production URL
- [ ] Load default region (should be USA)
- [ ] Press F -> reframe works
- [ ] Pan, rotate, zoom all work
- [ ] Switch to different region
- [ ] Press F again -> reframes to new region
- [ ] No console errors

**Full Test (15 minutes):**
- [ ] Run through sections 1-4 above on production site
- [ ] Test on mobile device (if available)
- [ ] Test on different browsers
- [ ] Performance check (60 FPS)

---

## Test Results Summary

**Date Tested:** _____________  
**Tester:** _____________  
**Environment:** _____________  

### Critical Issues Found
_List any blocking issues here_

### Minor Issues Found
_List non-blocking issues here_

### Recommendations
- [ ] Ready for production deployment
- [ ] Needs fixes before deployment
- [ ] Needs additional testing

---

## Sign-Off

- [ ] **Developer:** Code reviewed and tested locally
- [ ] **Tester:** All critical tests passed
- [ ] **Approver:** Ready for deployment

**Notes:**
_Add any additional notes, concerns, or follow-up items here_

