"""
Test if Nebraska JSON file is compressed on production server.
Simulates Firefox downloading the file.
"""
import urllib.request
import ssl
import sys

def test_production_compression():
    """Test Nebraska file compression on fuseki.net."""
    url = 'https://fuseki.net/altitude-maps/generated/regions/nebraska_srtm_30m_2048px_v2.json'
    
    print('Testing PRODUCTION Server Compression')
    print('=' * 70)
    print(f'URL: {url}')
    print()
    
    try:
        # Create SSL context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # Make request WITH gzip support (like Firefox)
        print('[TEST] Simulating Firefox request with Accept-Encoding: gzip')
        print('-' * 70)
        req = urllib.request.Request(url, headers={
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
        })
        
        response = urllib.request.urlopen(req, context=ctx)
        data = response.read()
        
        # Display results
        print(f'\nStatus: {response.status}')
        print(f'Content-Type: {response.getheader("Content-Type")}')
        
        encoding = response.getheader('Content-Encoding')
        print(f'Content-Encoding: {encoding if encoding else "(NONE - NOT COMPRESSED)"}')
        
        content_length = response.getheader('Content-Length')
        print(f'Content-Length header: {content_length if content_length else "(not set)"}')
        print(f'Actual bytes received: {len(data):,} bytes ({len(data)/1024/1024:.2f} MB)')
        
        print()
        print('=' * 70)
        
        # Analyze results
        if encoding in ('gzip', 'br', 'deflate'):
            print(f'[SUCCESS] Server IS using {encoding} compression!')
            print(f'Firefox receives compressed data over the wire.')
            print(f'Transfer size: ~{len(data)/1024:.1f} KB')
        else:
            print('[PROBLEM] NO Content-Encoding header!')
            print()
            print('This means server is NOT compressing JSON files.')
            print(f'Firefox will download the full {len(data)/1024/1024:.2f} MB uncompressed.')
            print()
            print('RECOMMENDATION: Enable gzip in your web server config')
            print('(nginx, Apache, or whatever serves fuseki.net)')
        
        return 0 if encoding else 1
        
    except Exception as e:
        print(f'\n[ERROR] {e}')
        return 1

if __name__ == '__main__':
    sys.exit(test_production_compression())

