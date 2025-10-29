"""Check which US states are affected by latitude distortion"""
import json
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# US state approximate center latitudes
us_states = {
    'alabama': 32.8, 'alaska': 64.0, 'arizona': 34.3, 'arkansas': 34.9,
    'california': 37.0, 'colorado': 39.0, 'connecticut': 41.6, 'delaware': 39.0,
    'florida': 28.0, 'georgia': 33.0, 'hawaii': 20.0, 'idaho': 44.5,
    'illinois': 40.0, 'indiana': 40.0, 'iowa': 42.0, 'kansas': 38.5,
    'kentucky': 37.5, 'louisiana': 31.0, 'maine': 45.5, 'maryland': 39.0,
    'massachusetts': 42.3, 'michigan': 44.5, 'minnesota': 46.0, 'mississippi': 33.0,
    'missouri': 38.5, 'montana': 47.0, 'nebraska': 41.5, 'nevada': 39.0,
    'new_hampshire': 43.5, 'new_jersey': 40.0, 'new_mexico': 34.5, 'new_york': 43.0,
    'north_carolina': 35.5, 'north_dakota': 47.5, 'ohio': 40.5, 'oklahoma': 35.5,
    'oregon': 44.0, 'pennsylvania': 41.0, 'rhode_island': 41.7, 'south_carolina': 34.0,
    'south_dakota': 44.5, 'tennessee': 36.0, 'texas': 31.5, 'utah': 39.5,
    'vermont': 44.0, 'virginia': 37.5, 'washington': 47.5, 'west_virginia': 38.5,
    'wisconsin': 44.5, 'wyoming': 43.0
}

# Check which states are currently processed
generated_dir = Path('generated/regions')
processed_states = []
for json_file in generated_dir.glob('*.json'):
    if not json_file.name.endswith('_meta.json') and 'manifest' not in json_file.name:
        for state in us_states.keys():
            if json_file.name.startswith(state + '_'):
                processed_states.append(state)
                break

# Categorize states
HIGH_LAT_THRESHOLD = 45.0

high_lat_states = {state: lat for state, lat in us_states.items() if lat >= HIGH_LAT_THRESHOLD}
mid_lat_states = {state: lat for state, lat in us_states.items() if lat < HIGH_LAT_THRESHOLD}

print("US STATES AND LATITUDE DISTORTION")
print("="*70)
print(f"\nReprojection threshold: {HIGH_LAT_THRESHOLD}°N")
print(f"\nSTATES THAT WILL BE REPROJECTED (>= {HIGH_LAT_THRESHOLD}°N):")
print("-"*70)
for state, lat in sorted(high_lat_states.items(), key=lambda x: -x[1]):
    processed = "✓ PROCESSED" if state in processed_states else "  (not yet processed)"
    import math
    distortion = 1.0 / math.cos(math.radians(lat))
    print(f"  {state:20s} {lat:5.1f}°N  distortion: {distortion:.2f}x  {processed}")

print(f"\nSTATES THAT WON'T BE REPROJECTED (< {HIGH_LAT_THRESHOLD}°N):")
print("-"*70)
sample_mid = sorted(mid_lat_states.items(), key=lambda x: -x[1])[:5]
for state, lat in sample_mid:
    processed = "✓ PROCESSED" if state in processed_states else ""
    import math
    distortion = 1.0 / math.cos(math.radians(lat))
    print(f"  {state:20s} {lat:5.1f}°N  distortion: {distortion:.2f}x  {processed}")
print(f"  ... and {len(mid_lat_states) - 5} more states")

print("\n" + "="*70)
print("\n⚠️  IMPORTANT:")
states_needing_reprocess = [s for s in high_lat_states.keys() if s in processed_states]
if states_needing_reprocess:
    print(f"These {len(states_needing_reprocess)} high-latitude states were processed BEFORE the fix:")
    print(f"  {', '.join(sorted(states_needing_reprocess))}")
    print(f"\nThey currently have DISTORTED aspect ratios and should be reprocessed!")
else:
    print("No high-latitude states have been processed yet - good!")

