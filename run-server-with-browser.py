#!/usr/bin/env python3
"""
HTTP Server with automatic browser opening
"""

import http.server
import socketserver
import webbrowser
import threading
import time
import os

# Configuration
HTML_OUTPUT_FILE = 'mapdata.html'

def open_browser():
    """Open browser after a short delay"""
    time.sleep(2)  # Wait for server to start
    try:
        webbrowser.open(f'http://localhost:8000/{HTML_OUTPUT_FILE}')
        print(f"Opened {HTML_OUTPUT_FILE} in your browser")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print(f"Please open http://localhost:8000/{HTML_OUTPUT_FILE} manually")

def main():
    PORT = 8000
    
    # Check if HTML file exists
    if not os.path.exists(HTML_OUTPUT_FILE):
        print(f"Error: {HTML_OUTPUT_FILE} not found!")
        return
    
    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start HTTP server
    with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        print(f"{HTML_OUTPUT_FILE} should open automatically in your browser")
        print("Press Ctrl+C to stop the server")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    main() 