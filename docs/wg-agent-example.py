#!/usr/bin/env python3
"""
WGDashboard Node Agent - Example Implementation

This is a reference implementation of a WireGuard node agent that works
with WGDashboard's multi-node architecture.

WARNING: This is a basic example. For production use, add:
- Proper error handling
- Logging
- Input validation
- Rate limiting
- TLS/HTTPS support
- Process management
"""

import os
import sys
import json
import hmac
import hashlib
import time
import subprocess
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, List, Any

# Configuration
AGENT_PORT = 8080
SHARED_SECRET = os.getenv('WG_AGENT_SECRET', 'change-me-in-production')
MAX_TIMESTAMP_AGE = 300  # 5 minutes


class WGAgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for WireGuard agent"""

    def log_message(self, format, *args):
        """Override to customize logging"""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def verify_signature(self) -> bool:
        """Verify HMAC signature of the request"""
        signature = self.headers.get('X-Signature')
        timestamp = self.headers.get('X-Timestamp')
        
        if not signature or not timestamp:
            return False
        
        # Check timestamp to prevent replay attacks
        try:
            req_time = int(timestamp)
            now = int(time.time())
            if abs(now - req_time) > MAX_TIMESTAMP_AGE:
                return False
        except ValueError:
            return False
        
        # Read body for signature verification
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
        
        # Store body for later use
        self.body = body
        
        # Compute expected signature
        message = f"{self.command}|{self.path}|{body}|{timestamp}"
        expected_sig = hmac.new(
            SHARED_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_sig)

    def send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        """Handle GET requests"""
        if not self.verify_signature():
            self.send_json_response(401, {'error': 'Unauthorized'})
            return
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/health':
            self.handle_health()
        elif path.startswith('/wg/') and path.endswith('/dump'):
            # Extract interface name from path like /wg/wg0/dump
            parts = path.split('/')
            if len(parts) == 4:
                interface = parts[2]
                self.handle_wg_dump(interface)
            else:
                self.send_json_response(400, {'error': 'Invalid path'})
        else:
            self.send_json_response(404, {'error': 'Not found'})

    def do_POST(self):
        """Handle POST requests"""
        if not self.verify_signature():
            self.send_json_response(401, {'error': 'Unauthorized'})
            return
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path.startswith('/wg/') and path.endswith('/peers'):
            # Extract interface from path like /wg/wg0/peers
            parts = path.split('/')
            if len(parts) == 4:
                interface = parts[2]
                try:
                    data = json.loads(self.body)
                    self.handle_add_peer(interface, data)
                except json.JSONDecodeError:
                    self.send_json_response(400, {'error': 'Invalid JSON'})
            else:
                self.send_json_response(400, {'error': 'Invalid path'})
        else:
            self.send_json_response(404, {'error': 'Not found'})

    def do_PUT(self):
        """Handle PUT requests"""
        if not self.verify_signature():
            self.send_json_response(401, {'error': 'Unauthorized'})
            return
        
        # Path like /wg/wg0/peers/{public_key}
        parsed_path = urlparse(self.path)
        path_parts = parsed_path.path.split('/')
        
        if len(path_parts) == 5 and path_parts[1] == 'wg' and path_parts[3] == 'peers':
            interface = path_parts[2]
            public_key = path_parts[4]
            try:
                data = json.loads(self.body)
                self.handle_update_peer(interface, public_key, data)
            except json.JSONDecodeError:
                self.send_json_response(400, {'error': 'Invalid JSON'})
        else:
            self.send_json_response(404, {'error': 'Not found'})

    def do_DELETE(self):
        """Handle DELETE requests"""
        if not self.verify_signature():
            self.send_json_response(401, {'error': 'Unauthorized'})
            return
        
        # Path like /wg/wg0/peers/{public_key}
        parsed_path = urlparse(self.path)
        path_parts = parsed_path.path.split('/')
        
        if len(path_parts) == 5 and path_parts[1] == 'wg' and path_parts[3] == 'peers':
            interface = path_parts[2]
            public_key = path_parts[4]
            self.handle_delete_peer(interface, public_key)
        else:
            self.send_json_response(404, {'error': 'Not found'})

    def handle_health(self):
        """Handle health check"""
        # Get system uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime = float(f.readline().split()[0])
        except:
            uptime = 0
        
        self.send_json_response(200, {
            'status': 'ok',
            'timestamp': int(time.time()),
            'uptime': int(uptime),
            'version': '1.0.0'
        })

    def handle_wg_dump(self, interface: str):
        """Get WireGuard peer dump"""
        try:
            output = subprocess.check_output(
                ['wg', 'show', interface, 'dump'],
                stderr=subprocess.STDOUT
            ).decode('utf-8')
            
            peers = []
            for line in output.strip().split('\n')[1:]:  # Skip header
                parts = line.split('\t')
                if len(parts) >= 8:
                    peers.append({
                        'public_key': parts[0],
                        'preshared_key': parts[1] if parts[1] != '(none)' else None,
                        'endpoint': parts[2] if parts[2] != '(none)' else None,
                        'allowed_ips': parts[3].split(',') if parts[3] else [],
                        'latest_handshake': int(parts[4]) if parts[4] != '0' else None,
                        'transfer_rx': int(parts[5]),
                        'transfer_tx': int(parts[6]),
                        'persistent_keepalive': int(parts[7]) if parts[7] != 'off' else 0
                    })
            
            self.send_json_response(200, {
                'interface': interface,
                'peers': peers
            })
        except subprocess.CalledProcessError as e:
            self.send_json_response(500, {
                'error': f'WireGuard command failed: {e.output.decode()}'
            })
        except Exception as e:
            self.send_json_response(500, {'error': str(e)})

    def handle_add_peer(self, interface: str, data: Dict[str, Any]):
        """Add peer to WireGuard interface"""
        try:
            public_key = data.get('public_key')
            allowed_ips = data.get('allowed_ips', [])
            preshared_key = data.get('preshared_key')
            keepalive = data.get('persistent_keepalive', 0)
            
            if not public_key:
                self.send_json_response(400, {'error': 'public_key required'})
                return
            
            # Build wg command
            cmd = ['wg', 'set', interface, 'peer', public_key]
            
            if allowed_ips:
                cmd.extend(['allowed-ips', ','.join(allowed_ips)])
            
            if preshared_key:
                # In production, use a temporary file for preshared key
                cmd.extend(['preshared-key', '/dev/stdin'])
                subprocess.run(cmd, input=preshared_key.encode(), check=True)
            else:
                subprocess.run(cmd, check=True)
            
            if keepalive > 0:
                subprocess.run([
                    'wg', 'set', interface, 'peer', public_key,
                    'persistent-keepalive', str(keepalive)
                ], check=True)
            
            # Save config
            subprocess.run(['wg-quick', 'save', interface], check=True)
            
            self.send_json_response(200, {
                'status': 'success',
                'message': 'Peer added successfully',
                'peer': {'public_key': public_key, 'allowed_ips': allowed_ips}
            })
        except subprocess.CalledProcessError as e:
            self.send_json_response(500, {'error': f'Failed to add peer: {str(e)}'})
        except Exception as e:
            self.send_json_response(500, {'error': str(e)})

    def handle_update_peer(self, interface: str, public_key: str, data: Dict[str, Any]):
        """Update peer configuration"""
        try:
            cmd = ['wg', 'set', interface, 'peer', public_key]
            
            if 'allowed_ips' in data:
                cmd.extend(['allowed-ips', ','.join(data['allowed_ips'])])
            
            if 'persistent_keepalive' in data:
                cmd.extend(['persistent-keepalive', str(data['persistent_keepalive'])])
            
            subprocess.run(cmd, check=True)
            subprocess.run(['wg-quick', 'save', interface], check=True)
            
            self.send_json_response(200, {
                'status': 'success',
                'message': 'Peer updated successfully'
            })
        except subprocess.CalledProcessError as e:
            self.send_json_response(500, {'error': f'Failed to update peer: {str(e)}'})
        except Exception as e:
            self.send_json_response(500, {'error': str(e)})

    def handle_delete_peer(self, interface: str, public_key: str):
        """Remove peer from WireGuard interface"""
        try:
            subprocess.run([
                'wg', 'set', interface, 'peer', public_key, 'remove'
            ], check=True)
            subprocess.run(['wg-quick', 'save', interface], check=True)
            
            self.send_json_response(200, {
                'status': 'success',
                'message': 'Peer removed successfully'
            })
        except subprocess.CalledProcessError as e:
            self.send_json_response(500, {'error': f'Failed to remove peer: {str(e)}'})
        except Exception as e:
            self.send_json_response(500, {'error': str(e)})


def main():
    """Start the agent server"""
    if SHARED_SECRET == 'change-me-in-production':
        print("WARNING: Using default shared secret. Set WG_AGENT_SECRET environment variable!")
    
    server_address = ('', AGENT_PORT)
    httpd = HTTPServer(server_address, WGAgentHandler)
    
    print(f"WireGuard Agent starting on port {AGENT_PORT}")
    print("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == '__main__':
    main()
