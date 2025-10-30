"""
Test if the production server at fuseki.net compresses JSON files.
"""
import urllib.request
import ssl

def test_production():
    """Test compression on production server."""
    print("Testing PRODUCTION server: fuseki.net")
    print("=" * 70)
    
    # Test with a likely JSON file (Oregon)
    url = "https://fuseki.net/altitude-maps/generated/regions/oregon_srtm_30m_2048px_v2.json"
    
    print(f"\nTesting: {url}")
    print("-" * 70)
    
    try:
        # Create SSL context (ignore cert issues for testing)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # Test WITH gzip support (like a browser)
        print("\n[TEST 1] WITH Accept-Encoding: gzip (browser behavior)")
        req = urllib.request.Request(url, headers={
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': 'Mozilla/5.0 (Test Script)'
        })
        
        with urllib.request.urlopen(req, context=ctx) as response:
            data = response.read()
            
            print(f"  Status: {response.status}")
            print(f"  Content-Encoding: {response.getheader('Content-Encoding', '(none)')}")
            print(f"  Content-Type: {response.getheader('Content-Type', '(unknown)')}")
            print(f"  Content-Length header: {response.getheader('Content-Length', '(not set)')}")
            print(f"  Actual bytes received: {len(data):,} bytes ({len(data)/1024:.1f} KB)")
            
            encoding = response.getheader('Content-Encoding')
            if encoding in ('gzip', 'br', 'deflate'):
                print(f"  [SUCCESS] Server IS using {encoding} compression!")
                
                # Try to decompress to see original size
                if encoding == 'gzip':
                    import gzip
                    import io
                    try:
                        decompressed = gzip.decompress(data)
                        ratio = (1 - len(data) / len(decompressed)) * 100
                        print(f"  Original size: {len(decompressed):,} bytes ({len(decompressed)/1024:.1f} KB)")
                        print(f"  Compression ratio: {ratio:.1f}%")
                    except:
                        print("  (Unable to decompress for size comparison)")
            else:
                print(f"  [WARNING] Server NOT compressing (or already decompressed by urllib)")
                print(f"  Full {len(data)/1024:.1f} KB transferred")
        
        # Test WITHOUT gzip (baseline)
        print("\n[TEST 2] WITHOUT Accept-Encoding (no compression request)")
        req2 = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Test Script)'
        })
        
        with urllib.request.urlopen(req2, context=ctx) as response:
            data2 = response.read()
            
            print(f"  Status: {response.status}")
            print(f"  Content-Encoding: {response.getheader('Content-Encoding', '(none)')}")
            print(f"  Actual bytes received: {len(data2):,} bytes ({len(data2)/1024:.1f} KB)")
        
        # Analysis
        print("\n" + "=" * 70)
        print("ANALYSIS:")
        
        # Check if urllib auto-decompressed (it does by default)
        if len(data) == len(data2):
            print("[INFO] urllib auto-decompressed the response.")
            print("       Browsers see compressed data, this is normal.")
            print("       The server IS likely compressing correctly.")
        elif len(data) < len(data2):
            ratio = (1 - len(data) / len(data2)) * 100
            print(f"[SUCCESS] Compression working: {ratio:.1f}% reduction")
            print(f"          {len(data2)/1024:.1f} KB -> {len(data)/1024:.1f} KB")
        
        # Check response headers for compression hints
        print("\n[TIP] To verify browser sees compression:")
        print("      Open browser DevTools -> Network tab")
        print("      Load the page, find the JSON file")
        print("      Check 'Size' column: shows 'XX KB / YY KB' if compressed")
        print("      Check Response Headers for 'content-encoding: gzip'")
        
    except urllib.error.HTTPError as e:
        print(f"\n[ERROR] HTTP {e.code}: {e.reason}")
        if e.code == 404:
            print("       File not found - trying to list available files...")
            # Try the manifest
            try:
                manifest_url = "https://fuseki.net/altitude-maps/generated/regions/manifest.json"
                req = urllib.request.Request(manifest_url)
                with urllib.request.urlopen(req, context=ctx) as resp:
                    import json
                    manifest = json.loads(resp.read())
                    print(f"\n       Available regions: {', '.join(list(manifest.get('regions', {}).keys())[:10])}...")
            except:
                pass
        return 1
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Connection failed: {e.reason}")
        print("        Server may be down or URL incorrect")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1
    
    print("=" * 70)
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(test_production())

