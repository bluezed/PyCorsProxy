"""
PyCorsProxy - A simple CORS proxy with SQLite caching.

Copyright (c) 2025, Thomas Geppert
SPDX-License-Identifier: BSD-3-Clause
"""

import argparse
import os
import sqlite3
import time
from urllib.parse import urlparse, unquote
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DB_PATH = 'cache.db'
LOG_FILE = None
LOG_MAX_SIZE = 1 * 1024 * 1024  # 1 MB
CACHE_TTL = 10 * 60 * 60  # 10 hours in seconds
PURGE_INTERVAL = 3600  # Purge old entries every hour

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            url TEXT PRIMARY KEY,
            content BLOB,
            content_type TEXT,
            timestamp INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_cached(url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        'SELECT content, content_type, timestamp FROM cache WHERE url = ? AND content IS NOT NULL',
        (url,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        content, content_type, timestamp = row
        if content and time.time() - timestamp < CACHE_TTL:
            return content, content_type
    return None, None


def purge_old_cache():
    """Remove cache entries older than CACHE_TTL."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM cache WHERE timestamp < ?', (int(time.time()) - CACHE_TTL,))
    conn.commit()
    conn.close()

def cache_response(url, content, content_type):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT OR REPLACE INTO cache (url, content, content_type, timestamp) VALUES (?, ?, ?, ?)',
        (url, content, content_type, int(time.time()))
    )
    conn.commit()
    conn.close()

def log_to_file(message):
    if LOG_FILE:
        try:
            # Check file size and rotate if needed
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_SIZE:
                os.rename(LOG_FILE, LOG_FILE + '.old')
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            with open(LOG_FILE, 'a') as f:
                f.write(f'[{timestamp}] {message}\n')
        except OSError:
            pass

class ProxyHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(f'{{"error": "{message}"}}'.encode())

    def do_GET(self):
        # Reject malformed requests (non-GET methods or malformed request lines)
        if self.command != 'GET':
            return
        if not self.path.startswith('/proxy'):
            return

        parsed_path = urlparse(self.path)
        query = parsed_path.query
        if not query or '=' not in query:
            self.send_error_response(400, 'Missing url parameter')
            return

        url = unquote(query.split('=', 1)[1])
        parsed_url = urlparse(url)

        if not parsed_url.scheme or not parsed_url.netloc:
            self.send_error_response(400, 'Invalid URL')
            return

        cached = get_cached(url)
        if cached and cached[0] is not None:
            content, content_type = cached
            content_bytes = bytes(content) if content else b''
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('X-Cache', 'HIT')
            self.send_cors_headers()
            self.send_header('Content-Length', str(len(content_bytes)))
            self.end_headers()
            self.wfile.write(content_bytes)
            log_to_file(f'HIT - {url}')
            return

        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as response:
                content = response.read()
                content_type = response.headers.get('Content-Type', 'application/octet-stream')

                cache_response(url, sqlite3.Binary(content), content_type)

                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('X-Cache', 'MISS')
                self.send_cors_headers()
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                log_to_file(f'MISS - {url}')
        except HTTPError as e:
            self.send_error_response(502, f'HTTP Error: {e.code} {e.reason}')
        except URLError as e:
            self.send_error_response(502, f'URL Error: {e.reason}')
        except Exception as e:
            self.send_error_response(502, str(e))

    def do_OPTIONS(self):
        # Reject malformed requests (non-OPTIONS methods or malformed request lines)
        if self.command != 'OPTIONS':
            return
        if self.path.startswith('/proxy'):
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.send_header('Access-Control-Max-Age', '86400')
            self.end_headers()

    def log_message(self, format, *args):
        msg = f"{self.address_string()} - {format % args}"
        log_to_file(msg)
        if not LOG_FILE:
            print(msg)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PyCorsProxy - A simple CORS proxy with SQLite caching.')
    parser.add_argument('--log', type=str, help='Log file path')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    args = parser.parse_args()

    LOG_FILE = args.log

    if LOG_FILE:
        log_to_file(f'Starting PyCorsProxy on {args.host}:{args.port}')

    init_db()
    purge_old_cache()  # Clean old entries on startup

    last_purge_time = time.time()
    server = HTTPServer((args.host, args.port), ProxyHandler)
    print(f'Proxy server running on http://{args.host}:{args.port}')

    try:
        while True:
            server.handle_request()  # Handle one request at a time
            # Check if it's time to purge old cache entries
            if time.time() - last_purge_time >= PURGE_INTERVAL:
                purge_old_cache()
                last_purge_time = time.time()
    except KeyboardInterrupt:
        pass
    server.server_close()
