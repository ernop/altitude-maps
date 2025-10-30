"""
Test if ANY JSON file on production server uses compression.
Will try several common patterns.
"""
import urllib.request
import ssl
import sys

def test_url(url):
    """Test a single URL for compression."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # Simulate browser with Accept-Encoding
        req = urllib.request.Request(url, headers={
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': 'Mozilla/5.0'
        })
        
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            # Get the raw response object to check headers before decompression
            encoding = response.getheader('Content-Encoding')
            content_length = response.getheader('Content-Length')
            data = response.read()
            
            return {
                'status': response.status,
                'encoding': encoding,
                'content_length_header': content_length,
                'bytes_received': len(data),
                'success': True
            }
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'success': False, 'error': str(e.reason)}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def main():
    print("Testing PRODUCTION compression: fuseki.net/altitude-maps")
    print("=" * 70)
    
    # Try various possible file patterns
    base_url = "https://fuseki.net/altitude-maps/generated/regions"
    
    test_files = [
        "manifest.json",
        "california_srtm_30m_2048px_v2.json",
        "texas_srtm_30m_2048px_v2.json", 
        "ohio_srtm_30m_2048px_v2.json",
    ]
    
    found_any = False
    
    for filename in test_files:
        url = f"{base_url}/{filename}"
        print(f"\nTrying: {filename}")
        print("-" * 50)
        
        result = test_url(url)
        
        if result['success']:
            found_any = True
            print(f"  [FOUND] Status: {result['status']}")
            print(f"  Content-Encoding: {result['encoding'] or '(none)'}")
            print(f"  Content-Length header: {result['content_length_header'] or '(not set)'}")
            print(f"  Bytes received: {result['bytes_received']:,} ({result['bytes_received']/1024:.1f} KB)")
            
            if result['encoding'] in ('gzip', 'br', 'deflate'):
                print(f"  [SUCCESS] Server IS using {result['encoding']} compression!")
            else:
                print(f"  [INFO] No Content-Encoding header (may be auto-decompressed by urllib)")
                print(f"        Check browser DevTools to confirm actual transfer size")
            
            # Only test first found file
            break
        else:
            print(f"  [SKIP] {result.get('error', 'Not found')}")
    
    if not found_any:
        print("\n" + "=" * 70)
        print("[INFO] No test files found on production server.")
        print("       Files may not be deployed yet, or use different naming.")
        print("\nTo test manually:")
        print("  1. Open: https://fuseki.net/altitude-maps/interactive_viewer_advanced.html")
        print("  2. Open browser DevTools (F12) -> Network tab")
        print("  3. Load a region in the viewer")
        print("  4. Find the .json file in Network tab")
        print("  5. Check:")
        print("     - Size column: shows 'XX KB / YY KB' if compressed")
        print("     - Response Headers: look for 'content-encoding: gzip'")
        return 1
    
    print("\n" + "=" * 70)
    print("[RECOMMENDATION]")
    print("Best way to verify compression in production:")
    print("  1. Open your viewer in browser with DevTools (F12)")
    print("  2. Go to Network tab")
    print("  3. Load a region (e.g., select 'California')")
    print("  4. Find the JSON file request")
    print("  5. Check 'Size' column:")
    print("     - If shows '1.2 MB / 8.5 MB' -> COMPRESSION WORKING")
    print("     - If shows '8.5 MB / 8.5 MB' -> NO COMPRESSION")
    print("  6. Click file -> Headers tab -> Response Headers")
    print("     - Look for 'content-encoding: gzip'")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

