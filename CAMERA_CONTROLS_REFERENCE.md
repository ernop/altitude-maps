# Camera Controls Reference - Precise Input-to-Action Mapping

## Ground Plane Camera (Custom Default) - Primary Scheme

### Mouse Operations

#### Left Button Drag (Pan)

| Input Direction | Mouse Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | `.x` component | INCREASES (moves RIGHT) | Mouse LEFT → camera.position.x INCREASES → camera moves RIGHT | `movement.addScaledVector(right, -deltaX * moveSpeed)` where `right` is camera's right vector |
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | `.z` component | Changes based on camera orientation | Camera moves RIGHT along right vector | Right vector calculated from `forward.cross(worldUp)` |
| **Mouse LEFT** | `deltaX < 0` (negative) | `focusPoint` | `.x` component | INCREASES (moves RIGHT) | Focus point moves RIGHT with camera | `focusPoint.add(movement)` |
| **Mouse LEFT** | `deltaX < 0` (negative) | `focusPoint` | `.z` component | Changes based on camera orientation | Focus point moves RIGHT along right vector | Same movement vector as camera |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | `.x` component | DECREASES (moves LEFT) | Mouse RIGHT → camera.position.x DECREASES → camera moves LEFT | Same formula, reversed sign |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | `.z` component | Changes based on camera orientation | Camera moves LEFT along right vector | Reversed direction |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `focusPoint` | `.x` component | DECREASES (moves LEFT) | Focus point moves LEFT with camera | Same movement vector |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `focusPoint` | `.z` component | Changes based on camera orientation | Focus point moves LEFT along right vector | Same movement vector |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | `.x` component | Changes based on camera orientation | Camera moves FORWARD along forwardHorizontal vector | `movement.addScaledVector(forwardHorizontal, deltaY * moveSpeed)` |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | `.z` component | Changes based on camera orientation | Camera moves FORWARD along forwardHorizontal vector | forwardHorizontal = forward projected onto XZ plane |
| **Mouse UP** | `deltaY < 0` (negative) | `focusPoint` | `.x` component | Changes based on camera orientation | Focus point moves FORWARD with camera | Same movement vector |
| **Mouse UP** | `deltaY < 0` (negative) | `focusPoint` | `.z` component | Changes based on camera orientation | Focus point moves FORWARD along forwardHorizontal | Same movement vector |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | `.x` component | Changes based on camera orientation | Camera moves BACKWARD along forwardHorizontal vector | Reversed direction |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | `.z` component | Changes based on camera orientation | Camera moves BACKWARD along forwardHorizontal vector | Reversed direction |
| **Mouse DOWN** | `deltaY > 0` (positive) | `focusPoint` | `.x` component | Changes based on camera orientation | Focus point moves BACKWARD with camera | Same movement vector |
| **Mouse DOWN** | `deltaY > 0` (positive) | `focusPoint` | `.z` component | Changes based on camera orientation | Focus point moves BACKWARD along forwardHorizontal | Same movement vector |
| **All movements** | Any | `camera.position` | `.y` component | CONSTANT (0) | Movement constrained to ground plane | `movement.y = 0` |
| **All movements** | Any | `focusPoint` | `.y` component | CONSTANT (0) | Focus point stays on ground plane | `focusPoint.y = 0` |
| **All movements** | Any | `camera.up` | Vector | CONSTANT `(0, 1, 0)` | Prevents roll accumulation | `camera.up.copy(worldUp)` |

**Speed Calculation**: `moveSpeed = distance * 0.0005` where `distance = camera.position.distanceTo(focusPoint)`

---

#### Shift + Left Button Drag (Tilt)

| Input Direction | Mouse Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | Spherical `.phi` angle | DECREASES | Mouse UP → phi DECREASES → camera moves UP → more overhead view | `spherical.phi = spherical.phi + deltaY * 0.005` (clamped 0.1 to π/2-0.01) |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | `.x` component | Changes based on spherical coordinates | Camera position recalculated from spherical | `offset.setFromSpherical(spherical)` then `camera.position = focusStart + offset` |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | `.y` component | INCREASES | Camera moves UP (away from ground) | Spherical coordinate conversion |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | `.z` component | Changes based on spherical coordinates | Camera position recalculated from spherical | Spherical coordinate conversion |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | Spherical `.phi` angle | INCREASES | Mouse DOWN → phi INCREASES → camera moves DOWN → tilt DOWN (see more terrain) | Same formula, positive deltaY |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | `.x` component | Changes based on spherical coordinates | Camera position recalculated from spherical | Same conversion |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | `.y` component | DECREASES | Camera moves DOWN (toward ground) | Spherical coordinate conversion |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | `.z` component | Changes based on spherical coordinates | Camera position recalculated from spherical | Same conversion |
| **Mouse LEFT/RIGHT** | `deltaX` (any) | N/A | N/A | NO EFFECT | Horizontal movement ignored | Only `deltaY` is used |
| **All movements** | Any | `focusPoint` | All components | CONSTANT | Focus point stays locked at `focusStart` | `this.state.focusStart` (locked pivot point) |
| **All movements** | Any | `camera.quaternion` | Orientation | Updates via `lookAt()` | Camera always looks at focus point | `camera.lookAt(focusStart)` |

**Speed**: `0.005` radians per pixel  
**Limits**: `phi` clamped between `0.1` and `π/2 - 0.01` radians

---

#### Alt + Left Button Drag (Rotate View Around Focus Point)

| Input Direction | Mouse Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | Rotation around Y-axis (theta) | INCREASES | Mouse LEFT → horizontalAngle INCREASES → camera orbits LEFT around focus | `horizontalAngle = -deltaX * 0.005` → `pos.applyAxisAngle(Y-axis, horizontalAngle)` |
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | `.x` component | Changes based on orbit | Camera position rotates around Y-axis through focus | Spherical coordinate rotation |
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | `.z` component | Changes based on orbit | Camera position rotates around Y-axis through focus | Spherical coordinate rotation |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | Rotation around Y-axis (theta) | DECREASES | Mouse RIGHT → horizontalAngle DECREASES → camera orbits RIGHT around focus | Same formula, reversed sign |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | `.x` component | Changes based on orbit | Camera position rotates around Y-axis through focus | Reversed rotation |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | `.z` component | Changes based on orbit | Camera position rotates around Y-axis through focus | Reversed rotation |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | Rotation around horizontal axis (phi) | INCREASES | Mouse UP → verticalAngle INCREASES → camera orbits UP around focus | `verticalAngle = -deltaY * 0.005` → `pos.applyAxisAngle(right, verticalAngle)` |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | `.y` component | INCREASES | Camera moves UP (away from focus) | Vertical rotation around horizontal axis |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | Rotation around horizontal axis (phi) | DECREASES | Mouse DOWN → verticalAngle DECREASES → camera orbits DOWN around focus | Same formula, reversed sign |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | `.y` component | DECREASES | Camera moves DOWN (toward focus) | Vertical rotation around horizontal axis |
| **All movements** | Any | `focusPoint` | All components | CONSTANT | Focus point stays locked at `focusStart` | `this.state.focusStart` (locked pivot point) |
| **All movements** | Any | `camera.quaternion` | Orientation | Updates via `lookAt()` | Camera always looks at focus point | `camera.lookAt(focusStart)` |

**Speed**: `0.005` radians per pixel  
**Limits**: Vertical angle clamped between `0.1` and `π - 0.1` radians to prevent camera flip

---

#### Middle Button Drag (Rotate Head - Camera Orientation Only)

| Input Direction | Mouse Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.quaternion` | Yaw (rotation around Y-axis) | INCREASES | Mouse LEFT → yaw INCREASES → camera turns LEFT | `yaw = startYaw + (-deltaX * 0.005)` |
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | All components | CONSTANT | Camera position does NOT move | Position stays completely fixed |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.quaternion` | Yaw (rotation around Y-axis) | DECREASES | Mouse RIGHT → yaw DECREASES → camera turns RIGHT | Same formula, reversed sign |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | All components | CONSTANT | Camera position does NOT move | Position stays completely fixed |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.quaternion` | Pitch (rotation around X-axis) | INCREASES | Mouse UP → pitch INCREASES → camera looks UP | `pitch = startPitch + (-deltaY * 0.005)` |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | All components | CONSTANT | Camera position does NOT move | Position stays completely fixed |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.quaternion` | Pitch (rotation around X-axis) | DECREASES | Mouse DOWN → pitch DECREASES → camera looks DOWN | Same formula, reversed sign |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | All components | CONSTANT | Camera position does NOT move | Position stays completely fixed |
| **All movements** | Any | `camera.up` | Vector | CONSTANT `(0, 1, 0)` | Prevents roll | `camera.up.set(0, 1, 0)` |
| **All movements** | Any | `focusPoint` | All components | CONSTANT | Focus point stays locked | Not recalculated (prevents drift) |

**Speed**: `0.005` radians per pixel  
**Pitch Limits**: Clamped between `-π/2 + 0.01` and `π/2 - 0.01` radians  
**Euler Order**: `YXZ` (prevents roll)

---

#### Right Button Drag (Rotate Terrain)

| Input Direction | Mouse Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Mouse LEFT** | `deltaX < 0` (negative) | `terrainGroup.quaternion` | Rotation around world Y-axis | INCREASES | Mouse LEFT → angleY INCREASES → terrain spins LEFT (counter-clockwise) | `angleY = -deltaX * 0.005` → `rotationY.setFromAxisAngle(Y-axis, angleY)` |
| **Mouse LEFT** | `deltaX < 0` (negative) | `camera.position` | All components | CONSTANT | Camera does NOT move | Only terrain rotates |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `terrainGroup.quaternion` | Rotation around world Y-axis | DECREASES | Mouse RIGHT → angleY DECREASES → terrain spins RIGHT (clockwise) | Same formula, reversed sign |
| **Mouse RIGHT** | `deltaX > 0` (positive) | `camera.position` | All components | CONSTANT | Camera does NOT move | Only terrain rotates |
| **Mouse UP** | `deltaY < 0` (negative) | `terrainGroup.quaternion` | Rotation around camera-relative horizontal axis | DECREASES | Mouse UP → angleH DECREASES → terrain tilts BACKWARD (far edge up) | `angleH = deltaY * 0.005` → `rotationH.setFromAxisAngle(horizontalAxis, angleH)` |
| **Mouse UP** | `deltaY < 0` (negative) | `camera.position` | All components | CONSTANT | Camera does NOT move | Only terrain rotates |
| **Mouse DOWN** | `deltaY > 0` (positive) | `terrainGroup.quaternion` | Rotation around camera-relative horizontal axis | INCREASES | Mouse DOWN → angleH INCREASES → terrain tilts FORWARD (near edge up) | Same formula, reversed sign |
| **Mouse DOWN** | `deltaY > 0` (positive) | `camera.position` | All components | CONSTANT | Camera does NOT move | Only terrain rotates |

**Speed**: `0.005` radians per pixel  
**Horizontal Axis Calculation**: `horizontalAxis = cross(viewDir, Y-axis)` where `viewDir` is from camera to terrain center

---

#### Wheel Scroll (Zoom)

| Input Direction | Wheel Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Scroll UP** | `deltaY < 0` (negative) | `camera.position` | Distance to cursor point | DECREASES | Scroll UP → factor < 1 → newDistance DECREASES → camera moves CLOSER to cursor | `factor = 1 - 0.1` → `newDistance = distance * factor` → `moveAmount = distance * (1 - factor)` |
| **Scroll UP** | `deltaY < 0` (negative) | `camera.position` | `.x` component | Moves toward cursor.x | Camera moves along direction vector toward cursor | `camera.position.addScaledVector(direction, moveAmount)` |
| **Scroll UP** | `deltaY < 0` (negative) | `camera.position` | `.y` component | Moves toward cursor.y | Camera moves along direction vector toward cursor | Direction vector from camera to cursor point |
| **Scroll UP** | `deltaY < 0` (negative) | `camera.position` | `.z` component | Moves toward cursor.z | Camera moves along direction vector toward cursor | Same direction vector |
| **Scroll UP** | `deltaY < 0` (negative) | `focusPoint` | All components | Moves TOWARD cursor | Focus shifts toward cursor point | `focusShift = -0.1` → `focusPoint.addScaledVector(towardsCursor, focusShift)` |
| **Scroll DOWN** | `deltaY > 0` (positive) | `camera.position` | Distance to cursor point | INCREASES | Scroll DOWN → factor > 1 → newDistance INCREASES → camera moves AWAY from cursor | `factor = 1 + 0.1` → same calculation |
| **Scroll DOWN** | `deltaY > 0` (positive) | `camera.position` | `.x` component | Moves away from cursor.x | Camera moves along direction vector away from cursor | Reversed direction |
| **Scroll DOWN** | `deltaY > 0` (positive) | `camera.position` | `.y` component | Moves away from cursor.y | Camera moves along direction vector away from cursor | Reversed direction |
| **Scroll DOWN** | `deltaY > 0` (positive) | `camera.position` | `.z` component | Moves away from cursor.z | Camera moves along direction vector away from cursor | Reversed direction |
| **Scroll DOWN** | `deltaY > 0` (positive) | `focusPoint` | All components | Moves AWAY from cursor | Focus shifts away from cursor point | `focusShift = 0.1` → same calculation |
| **All scroll** | Any | `focusPoint` | `.y` component | CONSTANT (0) | Focus point stays on ground plane | `focusPoint.y = 0` |

**Zoom Speed**: `0.1` (10% per scroll tick)  
**Min Distance**: `5` meters  
**Max Distance**: `50,000` meters  
**Direction Vector**: `direction = normalize(cursorPoint - camera.position)`

---

### Keyboard Operations

| Key | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|-----|--------------|----------------|--------|-----------------|----------------------|
| **W** | `camera.position` | Forward component | INCREASES | Move FORWARD along camera forward vector | `movement.addScaledVector(forward, currentMoveSpeed)` |
| **S** | `camera.position` | Forward component | DECREASES | Move BACKWARD along camera forward vector | `movement.addScaledVector(forward, -currentMoveSpeed)` |
| **A** | `camera.position` | Right component | DECREASES | Strafe LEFT along camera right vector | `movement.addScaledVector(right, -currentMoveSpeed)` |
| **D** | `camera.position` | Right component | INCREASES | Strafe RIGHT along camera right vector | `movement.addScaledVector(right, currentMoveSpeed)` |
| **Q** | `camera.position` | `.y` component | DECREASES | Move DOWN (descend) | `movement.y -= currentMoveSpeed` |
| **E** | `camera.position` | `.y` component | INCREASES | Move UP (ascend) | `movement.y += currentMoveSpeed` |
| **F** | `camera.position` | All components | RESET | Set to `(0, 1320, zOffset)` | `camera.position.set(0, 1320, zOffset)` where `zOffset = 1320 * tan(45°)` |
| **F** | `focusPoint` | All components | RESET | Set to `(0, 0, 0)` | `focusPoint.set(0, 0, 0)` |
| **F** | `terrainGroup.rotation` | All components | RESET | Set to `(0, 0, 0)` | `terrainGroup.rotation.set(0, 0, 0)` |
| **F** | `camera.quaternion` | Orientation | RESET | Set to identity | `camera.quaternion.set(0, 0, 0, 1)` |

**Base Speed**: `4.0` units/frame  
**Max Speed**: `8.0` units/frame (with acceleration)  
**Acceleration**: `0.05` per frame while moving

---

### Touch/Trackpad Gestures

#### Single Finger Drag (Pan)

| Input Direction | Touch Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Touch LEFT** | `deltaX < 0` (negative) | `camera.position` | Right component | INCREASES | Touch LEFT → camera moves RIGHT | `movement.addScaledVector(right, -deltaX * moveSpeed)` |
| **Touch RIGHT** | `deltaX > 0` (positive) | `camera.position` | Right component | DECREASES | Touch RIGHT → camera moves LEFT | Same formula, reversed sign |
| **Touch UP** | `deltaY < 0` (negative) | `camera.position` | Forward component | INCREASES | Touch UP → camera moves FORWARD | `movement.addScaledVector(forward, deltaY * moveSpeed)` |
| **Touch DOWN** | `deltaY > 0` (positive) | `camera.position` | Forward component | DECREASES | Touch DOWN → camera moves BACKWARD | Same formula, reversed sign |
| **All movements** | Any | `camera.position` | `.y` component | CONSTANT (0) | Movement constrained to ground plane | `movement.y = 0` |
| **All movements** | Any | `focusPoint` | All components | Moves with camera | Focus point moves with same movement vector | `focusPoint.add(movement)` |

**Speed**: `distance * 0.002` (faster than mouse pan)

---

#### Two-Finger Pinch (Zoom)

| Input Direction | Pinch Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Pinch IN** | `pinchDelta < 0` (distance decreases) | `camera.position` | Distance to center point | DECREASES | Pinch together → zoomFactor < 1 → camera moves CLOSER | `zoomFactor = 1 - (pinchDelta * 0.01)` → `newDistance = distance * zoomFactor` |
| **Pinch OUT** | `pinchDelta > 0` (distance increases) | `camera.position` | Distance to center point | INCREASES | Spread apart → zoomFactor > 1 → camera moves AWAY | Same calculation, reversed |
| **Pinch IN** | `pinchDelta < 0` | `focusPoint` | All components | Moves TOWARD center | Focus shifts toward center point | `focusShift = -0.05` |
| **Pinch OUT** | `pinchDelta > 0` | `focusPoint` | All components | Moves AWAY from center | Focus shifts away from center point | `focusShift = 0.05` |

**Sensitivity**: `0.01` per pixel of pinch distance change

---

#### Two-Finger Twist (Rotate Camera)

| Input Direction | Twist Movement | Target Object | Target Property | Effect | Precise Mapping | Formula/Code Reference |
|----------------|----------------|--------------|----------------|--------|-----------------|----------------------|
| **Counter-clockwise** | `deltaAngle < 0` (angle decreases) | `camera.position` | Spherical theta | INCREASES | Twist left → theta INCREASES → camera orbits LEFT | `spherical.theta -= deltaAngle` (note: subtraction because deltaAngle is negative) |
| **Clockwise** | `deltaAngle > 0` (angle increases) | `camera.position` | Spherical theta | DECREASES | Twist right → theta DECREASES → camera orbits RIGHT | Same calculation, reversed |

**Angle Calculation**: `deltaAngle = currentAngle - lastTouchAngle` where angles are `atan2(dy, dx)` between two touch points

---

## Other Camera Schemes - Precise Mappings

### Google Maps Style Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Left Drag** | Mouse LEFT | `camera.position` + `controls.target` | World position | Moves RIGHT | Raycast difference: `delta = panStart - current` → camera/target move by delta |
| **Left Drag** | Mouse RIGHT | `camera.position` + `controls.target` | World position | Moves LEFT | Same calculation, reversed |
| **Left Drag** | Mouse UP | `camera.position` + `controls.target` | World position | Moves DOWN | Same calculation |
| **Left Drag** | Mouse DOWN | `camera.position` + `controls.target` | World position | Moves UP | Same calculation |
| **Right Drag** | Mouse LEFT | `camera.position` | Spherical theta | INCREASES | `theta = -deltaX * 0.005` → camera orbits LEFT |
| **Right Drag** | Mouse RIGHT | `camera.position` | Spherical theta | DECREASES | Same calculation, reversed |
| **Right Drag** | Mouse UP | `camera.position` | Spherical phi | DECREASES | `phi = -deltaY * 0.005` → camera orbits UP |
| **Right Drag** | Mouse DOWN | `camera.position` | Spherical phi | INCREASES | Same calculation, reversed |
| **Wheel UP** | Scroll UP | `camera.position` | Distance to cursor | DECREASES | Zoom IN → camera moves CLOSER |
| **Wheel DOWN** | Scroll DOWN | `camera.position` | Distance to cursor | INCREASES | Zoom OUT → camera moves AWAY |

---

### Google Earth Style Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Left Drag** | Mouse LEFT | `camera.position` | Spherical theta | INCREASES | Orbit around clicked point → camera orbits LEFT |
| **Left Drag** | Mouse RIGHT | `camera.position` | Spherical theta | DECREASES | Same calculation, reversed |
| **Left Drag** | Mouse UP | `camera.position` | Spherical phi | DECREASES | Camera orbits UP |
| **Left Drag** | Mouse DOWN | `camera.position` | Spherical phi | INCREASES | Camera orbits DOWN |
| **Ctrl+Left Drag** | Mouse LEFT | `camera.position` + `controls.target` | Right component | INCREASES | Pan RIGHT | `movement.addScaledVector(right, -deltaX * moveSpeed)` |
| **Ctrl+Left Drag** | Mouse RIGHT | `camera.position` + `controls.target` | Right component | DECREASES | Pan LEFT | Reversed |
| **Ctrl+Left Drag** | Mouse UP | `camera.position` + `controls.target` | Y component | INCREASES | Pan UP | `movement.addScaledVector(up, deltaY * moveSpeed)` |
| **Ctrl+Left Drag** | Mouse DOWN | `camera.position` + `controls.target` | Y component | DECREASES | Pan DOWN | Reversed |

---

### Blender Style Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Middle Drag** | Mouse LEFT | `camera.position` | Spherical theta | INCREASES | Orbit LEFT around target |
| **Middle Drag** | Mouse RIGHT | `camera.position` | Spherical theta | DECREASES | Orbit RIGHT around target |
| **Middle Drag** | Mouse UP | `camera.position` | Spherical phi | DECREASES | Orbit UP around target |
| **Middle Drag** | Mouse DOWN | `camera.position` | Spherical phi | INCREASES | Orbit DOWN around target |
| **Shift+Middle Drag** | Mouse LEFT | `camera.position` + `controls.target` | Right component | INCREASES | Pan RIGHT |
| **Shift+Middle Drag** | Mouse RIGHT | `camera.position` + `controls.target` | Right component | DECREASES | Pan LEFT |
| **Shift+Middle Drag** | Mouse UP | `camera.position` + `controls.target` | Y component | INCREASES | Pan UP |
| **Shift+Middle Drag** | Mouse DOWN | `camera.position` + `controls.target` | Y component | DECREASES | Pan DOWN |
| **Wheel UP** | Scroll UP | `camera.position` | Forward component | INCREASES | Zoom IN along view direction |
| **Wheel DOWN** | Scroll DOWN | `camera.position` | Forward component | DECREASES | Zoom OUT along view direction |

---

### Roblox Studio Style Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Right Drag** | Mouse LEFT | `camera.position` | Spherical theta | INCREASES | Orbit LEFT around target |
| **Right Drag** | Mouse RIGHT | `camera.position` | Spherical theta | DECREASES | Orbit RIGHT around target |
| **Right Drag** | Mouse UP | `camera.position` | Spherical phi | DECREASES | Orbit UP around target |
| **Right Drag** | Mouse DOWN | `camera.position` | Spherical phi | INCREASES | Orbit DOWN around target |
| **Middle Drag** | Mouse LEFT | `camera.position` + `controls.target` | Right component | INCREASES | Pan RIGHT (fixed speed 0.5) |
| **Middle Drag** | Mouse RIGHT | `camera.position` + `controls.target` | Right component | DECREASES | Pan LEFT |
| **Middle Drag** | Mouse UP | `camera.position` + `controls.target` | Y component | INCREASES | Pan UP |
| **Middle Drag** | Mouse DOWN | `camera.position` + `controls.target` | Y component | DECREASES | Pan DOWN |
| **Wheel UP** | Scroll UP | `camera.position` + `controls.target` | Forward component | INCREASES | Zoom IN (20 units) |
| **Wheel DOWN** | Scroll DOWN | `camera.position` + `controls.target` | Forward component | DECREASES | Zoom OUT (20 units) |
| **W/A/S/D** | - | `camera.position` + `controls.target` | View-relative components | Movement | W=forward, S=back, A=left, D=right (2.0 units/frame) |
| **Q/E** | - | `camera.position` + `controls.target` | Y component | Q=down, E=up | Vertical movement (2.0 units/frame) |

---

### Unity Editor Style Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Alt+Left Drag** | Mouse LEFT | `camera.position` | Spherical theta | INCREASES | Orbit LEFT around target |
| **Alt+Left Drag** | Mouse RIGHT | `camera.position` | Spherical theta | DECREASES | Orbit RIGHT around target |
| **Alt+Left Drag** | Mouse UP | `camera.position` | Spherical phi | DECREASES | Orbit UP around target |
| **Alt+Left Drag** | Mouse DOWN | `camera.position` | Spherical phi | INCREASES | Orbit DOWN around target |
| **Alt+Middle Drag** | Mouse LEFT | `camera.position` + `controls.target` | Right component | INCREASES | Pan RIGHT (fixed speed 0.5) |
| **Alt+Middle Drag** | Mouse RIGHT | `camera.position` + `controls.target` | Right component | DECREASES | Pan LEFT |
| **Alt+Middle Drag** | Mouse UP | `camera.position` + `controls.target` | Y component | INCREASES | Pan UP |
| **Alt+Middle Drag** | Mouse DOWN | `camera.position` + `controls.target` | Y component | DECREASES | Pan DOWN |
| **Alt+Right Drag** | Mouse UP | `camera.position` | Forward component | INCREASES | Zoom IN (0.5 units per pixel) |
| **Alt+Right Drag** | Mouse DOWN | `camera.position` | Forward component | DECREASES | Zoom OUT |
| **Wheel UP** | Scroll UP | `camera.position` | Forward component | INCREASES | Zoom IN (distance * 0.1) |
| **Wheel DOWN** | Scroll DOWN | `camera.position` | Forward component | DECREASES | Zoom OUT |

---

### Flying Mode Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Mouse Move** (Pointer Lock) | Mouse RIGHT (movementX > 0) | `camera.quaternion` | Yaw | DECREASES | Turn RIGHT | `yaw -= movementX * 0.002` |
| **Mouse Move** (Pointer Lock) | Mouse LEFT (movementX < 0) | `camera.quaternion` | Yaw | INCREASES | Turn LEFT | Same calculation, reversed |
| **Mouse Move** (Pointer Lock) | Mouse DOWN (movementY > 0) | `camera.quaternion` | Pitch | DECREASES | Look DOWN | `pitch -= movementY * 0.002` |
| **Mouse Move** (Pointer Lock) | Mouse UP (movementY < 0) | `camera.quaternion` | Pitch | INCREASES | Look UP | Same calculation, reversed |
| **W/A/S/D** | - | `camera.position` | View-relative components | Movement | W=forward, S=back, A=left, D=right (5.0 normal, 15.0 with Shift) |
| **Q/E** | - | `camera.position` | Y component | Q=down, E=up | Vertical movement |

**Sensitivity**: `0.002` radians per pixel  
**Pitch Limits**: Clamped between `-π/2` and `π/2`

---

### Jumping Mode (Map-Grandpa) Scheme

| Input Combination | Mouse Direction | Target Object | Target Property | Effect | Precise Mapping |
|-------------------|----------------|--------------|----------------|--------|-----------------|
| **Right Drag** | Mouse LEFT | `cameraAngle.theta` | Horizontal angle | INCREASES | Camera orbits LEFT around character | `theta -= deltaX * 0.003` |
| **Right Drag** | Mouse RIGHT | `cameraAngle.theta` | Horizontal angle | DECREASES | Camera orbits RIGHT around character | Same calculation, reversed |
| **Right Drag** | Mouse UP | `cameraAngle.phi` | Vertical angle | DECREASES | Camera angle UP | `phi += deltaY * 0.003` |
| **Right Drag** | Mouse DOWN | `cameraAngle.phi` | Vertical angle | INCREASES | Camera angle DOWN | Same calculation, reversed |
| **W/A/S/D** | - | `character.position` | World position | Movement | W=forward, S=back, A=left, D=right (15.0 walk, 40.0 run) |
| **Space** | - | `character.velocity.y` | Vertical velocity | INCREASES | Jump upward (25.0 units) | Only when on ground |

**Sensitivity**: `0.003` radians per pixel  
**Phi Limits**: Clamped between `0.1` and `π/2`

---

## Coordinate System Reference

### Three.js Coordinate System
- **X-axis**: Right (positive) / Left (negative)
- **Y-axis**: Up (positive) / Down (negative)  
- **Z-axis**: Toward camera (positive) / Away from camera (negative) in default setup

### Spherical Coordinates (used for orbit operations)
- **theta (θ)**: Horizontal angle around Y-axis (azimuth)
  - 0° = +Z direction
  - Increases counter-clockwise when viewed from above
- **phi (φ)**: Vertical angle from Y-axis (elevation)
  - 0° = straight up (+Y)
  - π/2 = horizontal (on XZ plane)
  - π = straight down (-Y)

### Euler Angles (used for camera orientation)
- **Yaw**: Rotation around Y-axis (left/right)
- **Pitch**: Rotation around X-axis (up/down)
- **Roll**: Rotation around Z-axis (tilt) - NOT used in these schemes (prevents roll)
