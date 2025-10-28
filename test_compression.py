"""
Test if the dev server properly compresses JSON files.
Run this while serve_viewer.py is running.
"""
import http.client
import sys

def test_compression():
    """Test if server compresses JSON responses."""
    print("Testing GZIP compression on dev server...")
    print("=" * 70)
    
    # Test with gzip support
    conn = http.client.HTTPConnection('localhost', 8001)
    try:
        # Request with Accept-Encoding
        print("\n[TEST 1] Request WITH Accept-Encoding: gzip")
        conn.request('GET', '/generated/regions/oregon_srtm_30m_2048px_v2.json', 
                     headers={'Accept-Encoding': 'gzip'})
        resp = conn.getresponse()
        data = resp.read()
        
        print(f"  Status: {resp.status}")
        print(f"  Content-Encoding: {resp.getheader('Content-Encoding', '(none)')}")
        print(f"  Content-Length: {resp.getheader('Content-Length', '(unknown)')}")
        print(f"  Actual bytes received: {len(data):,}")
        
        if resp.getheader('Content-Encoding') == 'gzip':
            print("  [OK] GZIP compression IS working!")
            print(f"  Compression: ~{len(data)/1024:.1f} KB transferred")
        else:
            print("  [FAIL] GZIP compression NOT applied")
            print(f"  Full size: ~{len(data)/1024:.1f} KB transferred")
        
        conn.close()
        
        # Test without gzip support (should get uncompressed)
        print("\n[TEST 2] Request WITHOUT Accept-Encoding (baseline)")
        conn = http.client.HTTPConnection('localhost', 8001)
        conn.request('GET', '/generated/regions/oregon_srtm_30m_2048px_v2.json')
        resp = conn.getresponse()
        data2 = resp.read()
        
        print(f"  Status: {resp.status}")
        print(f"  Content-Encoding: {resp.getheader('Content-Encoding', '(none)')}")
        print(f"  Actual bytes received: {len(data2):,}")
        print(f"  Uncompressed: ~{len(data2)/1024:.1f} KB")
        
        # Compare
        if len(data) < len(data2):
            ratio = (1 - len(data)/len(data2)) * 100
            print(f"\n[SUCCESS] Compression reduced transfer by {ratio:.1f}%")
            print(f"   {len(data2)/1024:.1f} KB -> {len(data)/1024:.1f} KB")
        else:
            print("\n[WARNING] No compression detected!")
        
    except ConnectionRefusedError:
        print("\n[ERROR] Server not running!")
        print("   Start with: python serve_viewer.py")
        return 1
    except FileNotFoundError:
        print("\n[ERROR] Test file not found!")
        print("   Make sure Oregon data exists: generated/regions/oregon_srtm_30m_2048px_v2.json")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1
    finally:
        conn.close()
    
    print("\n" + "=" * 70)
    return 0

if __name__ == '__main__':
    sys.exit(test_compression())

