"""
Start a local HTTP server for the interactive 3D elevation viewer.
"""
import http.server
import socketserver
import webbrowser
from pathlib import Path
import sys
import gzip
import io

class GzipHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that supports gzip compression for JSON files."""
    
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    
    def do_GET(self):
        """Handle GET requests with gzip compression for JSON files."""
        # Get the path
        path = self.translate_path(self.path)
        
        # Check if it's a JSON file and client accepts gzip
        if path.endswith('.json') and 'gzip' in self.headers.get('Accept-Encoding', ''):
            try:
                with open(path, 'rb') as f:
                    content = f.read()
                
                # Compress content
                gzip_buffer = io.BytesIO()
                with gzip.GzipFile(fileobj=gzip_buffer, mode='wb', compresslevel=6) as gzip_file:
                    gzip_file.write(content)
                compressed = gzip_buffer.getvalue()
                
                # Send response with compressed content
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Encoding', 'gzip')
                self.send_header('Content-Length', len(compressed))
                # In development, avoid stale JSON by disabling caching
                self.send_header('Cache-Control', 'no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(compressed)
                
                # Log compression ratio
                ratio = (1 - len(compressed) / len(content)) * 100 if content else 0
                print(f"[GZIP] {Path(path).name}: {len(content)/1024:.1f} KB -> {len(compressed)/1024:.1f} KB ({ratio:.1f}% saved)")
                return
            except Exception as e:
                # Fall back to standard handler if compression fails
                print(f"[WARN] Compression failed for {path}: {e}")
        
        # Use default handler for non-JSON or non-gzip requests
        super().do_GET()

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
    print(f"[OK] GZIP compression enabled for JSON files")
    print("=" * 70)
    
    # Create HTTP request handler with gzip support
    Handler = GzipHTTPRequestHandler
    
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

