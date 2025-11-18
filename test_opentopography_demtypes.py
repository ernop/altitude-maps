"""Test OpenTopography API for available demtypes."""
import json
import requests
from pathlib import Path

settings = json.load(open('settings.json'))
api_key = settings['opentopography']['api_key']

# Test bbox (small region around Morro Bay)
bbox = {
    'south': 35.25,
    'north': 35.4,
    'west': -120.9,
    'east': -120.8
}

# Demtypes to test
demtypes = [
    'SRTMGL1',  # 30m
    'SRTMGL3',  # 90m
    'GTOPO30',  # 1km
    'ETOPO1',   # 1 arc-minute (~1.8km)
    'ETOPO5',   # 5 arc-minute (~9km)
    'AW3D30',   # 30m
    'COP30',    # Copernicus 30m
    'COP90',    # Copernicus 90m
]

print("Testing OpenTopography API demtypes:")
print("=" * 60)

for demtype in demtypes:
    params = {
        'demtype': demtype,
        'south': bbox['south'],
        'north': bbox['north'],
        'west': bbox['west'],
        'east': bbox['east'],
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }
    
    try:
        r = requests.get('https://portal.opentopography.org/API/globaldem', 
                        params=params, timeout=30)
        if r.status_code == 200:
            size_kb = len(r.content) / 1024
            print(f"OK {demtype:10s} - ({size_kb:.1f} KB)")
        else:
            print(f"FAIL {demtype:10s} - {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"ERROR {demtype:10s} - {str(e)[:50]}")

print("\n" + "=" * 60)
print("Note: Only demtypes that return 200 OK can be used for bbox downloads")

