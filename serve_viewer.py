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
import signal
import threading

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
        
        # Check if requesting a .json.gz file (pre-compressed)
        if path.endswith('.json.gz'):
            if not Path(path).exists():
                # File doesn't exist - let default handler return 404
                super().do_GET()
                return
            
            try:
                # Serve pre-compressed .json.gz file directly
                with open(path, 'rb') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/gzip')  # Changed to gzip
                # DO NOT send Content-Encoding: gzip header
                # This would make browser auto-decompress, breaking our JS DecompressionStream
                self.send_header('Content-Length', len(content))
                # In development, avoid stale JSON by disabling caching
                self.send_header('Cache-Control', 'no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(content)
                
                print(f"[GZIP] Served pre-compressed (binary): {Path(path).name} ({len(content)/1024:.1f} KB)")
                return
            except Exception as e:
                # Fall back to standard handler if serving fails
                print(f"[WARN] Failed to serve {path}: {e}")
        
        # Check if it's a JSON file and client accepts gzip (on-the-fly compression)
        if path.endswith('.json') and 'gzip' in self.headers.get('Accept-Encoding', ''):
            # Check if file exists before attempting compression
            if not Path(path).exists():
                # File doesn't exist - let default handler return 404
                super().do_GET()
                return
            
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
        
        # Use default handler for other files
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
    
    # Global reference for signal handler
    httpd_server = None
    shutdown_event = threading.Event()
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n\n[-] Shutdown signal received, stopping server...")
        shutdown_event.set()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination request
    
    try:
        # Create server with socket reuse enabled
        socketserver.TCPServer.allow_reuse_address = True
        httpd_server = socketserver.TCPServer(("", PORT), Handler)
        
        # Set socket timeout to allow periodic interrupt checking
        httpd_server.timeout = 0.5
        
        print(f"\n[+] Server started successfully!")
        print(f"\n[>] Opening viewer in browser...")
        
        # Open browser after short delay
        def open_browser():
            import time
            time.sleep(1)
            if not shutdown_event.is_set():
                webbrowser.open(f"http://localhost:{PORT}/interactive_viewer_advanced.html")
        
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Serve with periodic checking for shutdown
        print(f"\n[*] Server running (Ctrl+C to stop)...")
        while not shutdown_event.is_set():
            httpd_server.handle_request()
        
        print("[-] Server stopped cleanly")
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
    finally:
        # Ensure cleanup
        if httpd_server:
            try:
                httpd_server.server_close()
            except:
                pass

if __name__ == "__main__":
    sys.exit(main())

