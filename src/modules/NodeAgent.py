"""
Node Agent Client
Handles communication with WireGuard node agents via HMAC-signed requests
"""
import hashlib
import hmac
import json
import time
import requests
from typing import Optional, Dict, Any, Tuple


class AgentClient:
    """Client for communicating with WireGuard node agents"""

    def __init__(self, agent_url: str, secret: str, timeout: int = 10):
        """
        Initialize agent client
        
        Args:
            agent_url: Base URL of the node agent (e.g., http://node1.example.com:8080)
            secret: Shared secret for HMAC signing
            timeout: Request timeout in seconds
        """
        self.agent_url = agent_url.rstrip('/')
        self.secret = secret
        self.timeout = timeout

    def _generate_hmac(self, method: str, path: str, body: str, timestamp: str) -> str:
        """
        Generate HMAC signature for request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            body: Request body (empty string for GET)
            timestamp: Unix timestamp as string
            
        Returns:
            HMAC signature as hex string
        """
        message = f"{method}|{path}|{body}|{timestamp}"
        signature = hmac.new(
            self.secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_request(self, method: str, path: str, data: Optional[Dict] = None) -> Tuple[bool, Any]:
        """
        Make authenticated request to agent
        
        Args:
            method: HTTP method
            path: Request path (relative to agent_url)
            data: Optional request body data
            
        Returns:
            Tuple of (success: bool, response_data: dict or error_message: str)
        """
        url = f"{self.agent_url}{path}"
        timestamp = str(int(time.time()))
        body = json.dumps(data) if data else ""
        
        signature = self._generate_hmac(method, path, body, timestamp)
        
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature,
            'X-Timestamp': timestamp
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=self.timeout)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=self.timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=self.timeout)
            else:
                return False, f"Unsupported HTTP method: {method}"
            
            if response.status_code >= 200 and response.status_code < 300:
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            return False, "Request timed out"
        except requests.exceptions.ConnectionError:
            return False, "Connection failed"
        except Exception as e:
            return False, f"Request failed: {str(e)}"

    def get_health(self) -> Tuple[bool, Any]:
        """
        Get node health status
        
        Returns:
            Tuple of (success: bool, health_data or error_message)
        """
        return self._make_request('GET', '/health')

    def get_status(self) -> Tuple[bool, Any]:
        """
        Get detailed status report including peer counts, memory, CPU usage, and interface statuses (Phase 5)
        
        Returns:
            Tuple of (success: bool, status_data or error_message)
        """
        return self._make_request('GET', '/v1/status')
    
    def get_metrics(self) -> Tuple[bool, Any]:
        """
        Get Prometheus-compatible metrics for observability systems (Phase 5)
        
        Returns:
            Tuple of (success: bool, metrics_text or error_message)
        """
        return self._make_request('GET', '/v1/metrics')

    def get_wg_dump(self, iface: str) -> Tuple[bool, Any]:
        """
        Get WireGuard interface dump (peer stats)
        
        Args:
            iface: WireGuard interface name
            
        Returns:
            Tuple of (success: bool, dump_data or error_message)
        """
        return self._make_request('GET', f'/wg/{iface}/dump')

    def add_peer(self, iface: str, peer_data: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Add peer to WireGuard interface
        
        Args:
            iface: WireGuard interface name
            peer_data: Peer configuration data
            
        Returns:
            Tuple of (success: bool, response_data or error_message)
        """
        return self._make_request('POST', f'/wg/{iface}/peers', peer_data)

    def update_peer(self, iface: str, public_key: str, peer_data: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Update peer configuration
        
        Args:
            iface: WireGuard interface name
            public_key: Peer public key
            peer_data: Updated peer configuration
            
        Returns:
            Tuple of (success: bool, response_data or error_message)
        """
        return self._make_request('PUT', f'/wg/{iface}/peers/{public_key}', peer_data)

    def delete_peer(self, iface: str, public_key: str) -> Tuple[bool, Any]:
        """
        Remove peer from WireGuard interface
        
        Args:
            iface: WireGuard interface name
            public_key: Peer public key
            
        Returns:
            Tuple of (success: bool, response_data or error_message)
        """
        return self._make_request('DELETE', f'/wg/{iface}/peers/{public_key}')
    
    def syncconf(self, iface: str, config_base64: str) -> Tuple[bool, Any]:
        """
        Apply configuration using wg syncconf for atomic updates (Phase 4)
        
        Args:
            iface: WireGuard interface name
            config_base64: Base64-encoded WireGuard configuration
            
        Returns:
            Tuple of (success: bool, response_data or error_message)
        """
        return self._make_request('POST', f'/v1/wg/{iface}/syncconf', {'config': config_base64})

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to agent
        
        Returns:
            Tuple of (success: bool, message)
        """
        success, result = self.get_health()
        if success:
            return True, "Connection successful"
        else:
            return False, f"Connection failed: {result}"
