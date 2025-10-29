"""
Temporary script to migrate all regions from download_regions.py to regions_config.py format.
"""
import sys
sys.path.insert(0, '.')

from download_regions import REGIONS

# Categorize regions
us_states = []
international = []

# Map region IDs to categories
for rid, data in REGIONS.items():
    name_lower = data['name'].lower()
    
    if rid in ['california', 'texas', 'colorado', 'washington', 'new_york', 'florida', 
               'arizona', 'alaska', 'hawaii']:
        category = 'usa_state'
        country = 'United States of America'
        clip = True
        group = us_states
    elif rid in ['usa_full']:
        category = 'usa_full'
        country = 'United States of America'
        clip = True
        group = international
    elif any(x in name_lower for x in ['island', 'peninsula']):
        category = 'island'
        country = None
        clip = data.get('clip_boundary', False)
        group = international
    elif rid in ['alps', 'rockies']:
        category = 'mountain_range'
        country = None
        clip = False
        group = international
    elif rid in ['nepal', 'kamchatka', 'yakutsk_area', 'yatusk_area', 'san_mateo', 'peninsula']:
        category = 'special'
        country = None
        clip = False
        group = international
    else:
        category = 'international'
        country = data['name'] if '/' not in data['name'] else None
        clip = data.get('clip_boundary', True)
        group = international
    
    group.append({
        'id': rid,
        'name': data['name'],
        'bounds': data['bounds'],
        'description': data['description'],
        'category': category,
        'country': country,
        'clip_boundary': clip
    })

# Sort
us_states.sort(key=lambda x: x['name'])
international.sort(key=lambda x: x['name'])

# Generate output
print("\n# US STATES:")
print("US_STATES: Dict[str, RegionConfig] = {")
for r in us_states:
    print(f'    "{r["id"]}": RegionConfig(')
    print(f'        id="{r["id"]}",')
    print(f'        name="{r["name"]}",')
    print(f'        bounds={r["bounds"]},')
    print(f'        description="{r["description"]}",')
    print(f'        category="{r["category"]}",')
    print(f'        country="{r["country"]}",')
    print(f'        clip_boundary={r["clip_boundary"]},')
    print(f'    ),')
print("}")

print("\n\n# INTERNATIONAL REGIONS:")
print("INTERNATIONAL_REGIONS: Dict[str, RegionConfig] = {")
for r in international:
    print(f'    "{r["id"]}": RegionConfig(')
    print(f'        id="{r["id"]}",')
    print(f'        name="{r["name"]}",')
    print(f'        bounds={r["bounds"]},')
    print(f'        description="{r["description"]}",')
    print(f'        category="{r["category"]}",')
    print(f'        country={repr(r["country"])},')
    print(f'        clip_boundary={r["clip_boundary"]},')
    print(f'    ),')
print("}")

print(f"\n\nTotal: {len(us_states)} US, {len(international)} international")

