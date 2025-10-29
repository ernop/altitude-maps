"""
Test different .htaccess configurations to see what works on Dreamhost.
This helps incrementally add features without breaking the site.
"""
import urllib.request
import ssl
import sys
from datetime import datetime

def test_config(config_name, test_caching=False, test_headers=False):
    """
    Test if a configuration works and what features it enables.
    
    Args:
        config_name: Name of the .htaccess file being tested
        test_caching: If True, check for cache headers
        test_headers: If True, check for security headers
    """
    print(f'Testing: {config_name}')
    print('=' * 70)
    
    # Test if site loads
    html_url = 'https://fuseki.net/altitude-maps/interactive_viewer_advanced.html'
    json_url = 'https://fuseki.net/altitude-maps/generated/regions/nebraska_srtm_30m_2048px_v2.json'
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        # Test HTML page
        print('\n[1] Testing HTML page loads...')
        req = urllib.request.Request(html_url)
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        print(f'    Status: {resp.status} - OK')
        
        # Test JSON with compression
        print('\n[2] Testing JSON compression...')
        req = urllib.request.Request(json_url, headers={
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'Mozilla/5.0'
        })
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        data = resp.read()
        
        encoding = resp.getheader('Content-Encoding')
        print(f'    Status: {resp.status}')
        print(f'    Content-Encoding: {encoding or "(none)"}')
        print(f'    Transfer size: {len(data)/1024/1024:.2f} MB')
        
        if encoding == 'gzip':
            print('    ✓ Compression WORKING')
        else:
            print('    ✗ Compression NOT working')
        
        # Test caching headers if requested
        if test_caching:
            print('\n[3] Testing cache headers...')
            expires = resp.getheader('Expires')
            cache_control = resp.getheader('Cache-Control')
            
            if expires or cache_control:
                print(f'    Expires: {expires or "(not set)"}')
                print(f'    Cache-Control: {cache_control or "(not set)"}')
                print('    ✓ Caching headers present')
            else:
                print('    ✗ No caching headers (mod_expires may not be working)')
        
        # Test security headers if requested
        if test_headers:
            print('\n[4] Testing security headers...')
            cors = resp.getheader('Access-Control-Allow-Origin')
            
            if cors:
                print(f'    Access-Control-Allow-Origin: {cors}')
                print('    ✓ CORS header present')
            else:
                print('    ✗ No CORS header (mod_headers may not be working)')
        
        print('\n' + '=' * 70)
        print('[SUCCESS] Configuration is working!')
        return 0
        
    except urllib.error.HTTPError as e:
        print(f'\n[ERROR] HTTP {e.code}: {e.reason}')
        
        if e.code == 500:
            print('\n500 = Configuration has errors!')
            print('This .htaccess file breaks the server.')
        
        print('\n' + '=' * 70)
        print('[FAILED] Configuration does NOT work')
        return 1
        
    except Exception as e:
        print(f'\n[ERROR] {e}')
        print('\n' + '=' * 70)
        print('[FAILED] Test failed')
        return 1

def main():
    """Interactive testing."""
    print('Apache .htaccess Feature Testing')
    print('=' * 70)
    print()
    print('This script tests different .htaccess configurations.')
    print('Upload the test file, then run this script to verify it works.')
    print()
    
    print('Available test files:')
    print('  1. .htaccess.minimal       - Just compression (currently working)')
    print('  2. .htaccess.test_caching  - Compression + browser caching')
    print('  3. .htaccess.test_headers  - Compression + CORS headers')
    print('  4. .htaccess.test_full     - All features combined')
    print()
    
    choice = input('Which config did you upload? (1-4, or "current" to test current): ').strip()
    
    if choice == '1':
        return test_config('.htaccess.minimal', test_caching=False, test_headers=False)
    elif choice == '2':
        return test_config('.htaccess.test_caching', test_caching=True, test_headers=False)
    elif choice == '3':
        return test_config('.htaccess.test_headers', test_caching=False, test_headers=True)
    elif choice == '4':
        return test_config('.htaccess.test_full', test_caching=True, test_headers=True)
    elif choice.lower() == 'current':
        return test_config('current .htaccess', test_caching=True, test_headers=True)
    else:
        print('Invalid choice')
        return 1

if __name__ == '__main__':
    sys.exit(main())

