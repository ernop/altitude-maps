"""
Quick test to see if the site is up or broken by .htaccess.
"""
import urllib.request
import ssl
import sys

def test_site():
    """Test if site loads at all."""
    url = 'https://fuseki.net/altitude-maps/interactive_viewer_advanced.html'
    
    print('Testing if site is accessible...')
    print(f'URL: {url}')
    print()
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, context=ctx)
        
        print(f'[SUCCESS] Status: {resp.status}')
        print('Site is UP and accessible')
        return 0
        
    except urllib.error.HTTPError as e:
        print(f'[ERROR] HTTP {e.code}: {e.reason}')
        
        if e.code == 500:
            print()
            print('500 = Internal Server Error')
            print('This usually means .htaccess has a syntax error or uses')
            print('an Apache module that is not enabled.')
            print()
            print('ACTION REQUIRED:')
            print('  1. Delete .htaccess from server OR')
            print('  2. Replace with .htaccess.minimal (very simple version)')
        
        return 1
    except Exception as e:
        print(f'[ERROR] {e}')
        return 1

if __name__ == '__main__':
    sys.exit(test_site())

