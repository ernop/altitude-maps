"""Research GMTED2010 download URLs."""
import requests
import re
from pathlib import Path

# Fetch GMTED2010 viewer page
print("Fetching GMTED2010 viewer page...")
try:
    r = requests.get('https://topotools.cr.usgs.gov/gmted_viewer/gmted2010_global_grids.php', timeout=30)
    content = r.text
    
    # Save for inspection
    Path('gmted2010_viewer.html').write_text(content, encoding='utf-8')
    print(f"Saved page content ({len(content)} bytes)")
    
    # Find URLs
    url_pattern = r'(https?://[^\s"<>]+|ftp://[^\s"<>]+)'
    urls = re.findall(url_pattern, content)
    
    print(f"\nFound {len(urls)} URLs:")
    unique_urls = sorted(set(urls))
    for url in unique_urls[:30]:  # Show first 30
        print(f"  {url}")
    
    # Look for GMTED2010-specific patterns
    gmted_urls = [u for u in unique_urls if 'gmted' in u.lower() or 'GMTED' in u]
    if gmted_urls:
        print(f"\nGMTED2010-specific URLs ({len(gmted_urls)}):")
        for url in gmted_urls:
            print(f"  {url}")
    
    # Look for download/data patterns
    download_urls = [u for u in unique_urls if any(x in u.lower() for x in ['download', 'data', 'tile', 'grid', '.tif', '.zip'])]
    if download_urls:
        print(f"\nPotential download URLs ({len(download_urls)}):")
        for url in download_urls[:20]:
            print(f"  {url}")
            
except Exception as e:
    print(f"Error: {e}")





