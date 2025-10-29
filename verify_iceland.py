"""Verify Iceland aspect ratio is now correct"""
import json
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('generated/regions/iceland_srtm_30m_2048px_v2.json') as f:
    d = json.load(f)

data_aspect = d['width'] / d['height']
real_aspect = 504 / 337  # Real Iceland dimensions in km

print(f" ICELAND ASPECT RATIO FIX VERIFICATION")
print(f"="*50)
print(f"Data aspect:  {d['width']}px × {d['height']}px = {data_aspect:.2f}:1")
print(f"Real aspect:  ~504km × 337km = {real_aspect:.2f}:1")
print(f"")
if abs(data_aspect - real_aspect) < 0.05:
    print(f" PERFECT MATCH! Aspect ratio is now correct!")
    print(f"   Difference: {abs(data_aspect - real_aspect):.3f} (< 0.05 threshold)")
else:
    print(f" Still off by {abs(data_aspect - real_aspect):.2f}")
print(f"="*50)

