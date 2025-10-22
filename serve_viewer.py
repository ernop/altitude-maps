"""
Start a local HTTP server for the interactive 3D elevation viewer.
"""
import http.server
import socketserver
import webbrowser
from pathlib import Path
import sys

def main():
    """Start the HTTP server."""
    PORT = 8001
    
    # Change to project directory
    project_dir = Path(__file__).parent
    
    print("=" * 70)
    print("Starting Altitude Maps Interactive Viewer")
    print("=" * 70)
    print(f"\n[*] Serving from: {project_dir}")
    print(f"[*] Server address: http://localhost:{PORT}")
    print(f"[*] Viewer URL: http://localhost:{PORT}/interactive_viewer_advanced.html")
    print("\n[!] Press Ctrl+C to stop the server")
    print("=" * 70)
    
    # Create HTTP request handler
    Handler = http.server.SimpleHTTPRequestHandler
    
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"\n[+] Server started successfully!")
            print(f"\n[>] Opening viewer in browser...")
            
            # Open browser after short delay
            import threading
            def open_browser():
                import time
                time.sleep(1)
                webbrowser.open(f"http://localhost:{PORT}/interactive_viewer_advanced.html")
            
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            
            # Serve forever
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\n[-] Server stopped by user")
        return 0
    except OSError as e:
        if "address already in use" in str(e).lower():
            print(f"\n[X] Error: Port {PORT} is already in use!")
            print(f"   Either:")
            print(f"   1. Stop the existing server on port {PORT}")
            print(f"   2. Change the PORT value in this script")
        else:
            print(f"\n[X] Error starting server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

