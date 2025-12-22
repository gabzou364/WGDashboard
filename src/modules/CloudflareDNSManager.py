"""
Cloudflare DNS Manager
Handles Cloudflare DNS API operations with retry queue (Phase 8)
"""
import json
import time
import threading
import requests
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from collections import deque

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False


def _log_info(msg):
    """Helper to log info messages"""
    if _has_flask:
        try:
            current_app.logger.info(msg)
        except (RuntimeError, NameError):
            pass


def _log_error(msg, exc=None):
    """Helper to log error messages"""
    if _has_flask:
        try:
            if exc:
                current_app.logger.error(msg, exc)
            else:
                current_app.logger.error(msg)
        except (RuntimeError, NameError):
            pass


class CloudflareDNSManager:
    """
    Manager for Cloudflare DNS operations with automatic retry queue
    
    Features:
    - Create/update/delete A and AAAA records
    - Enforce proxied=false (DNS-only)
    - Retry queue for failed operations
    - Debouncing/batching of updates
    """
    
    def __init__(self, api_token: str = None):
        """
        Initialize Cloudflare DNS Manager
        
        Args:
            api_token: Cloudflare API token with DNS edit permissions
        """
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.retry_queue = deque()
        self.pending_operations = {}  # For debouncing
        self.debounce_delay = 5  # seconds
        self._retry_thread = None
        self._stop_retry_thread = False
    
    def set_api_token(self, api_token: str):
        """Update the API token"""
        self.api_token = api_token
    
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> Tuple[bool, Any]:
        """
        Make a request to Cloudflare API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            
        Returns:
            Tuple of (success, response_data or error_message)
        """
        if not self.api_token:
            return False, "Cloudflare API token not configured"
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return False, f"Unsupported method: {method}"
            
            response_data = response.json()
            
            if response.status_code in [200, 201]:
                if response_data.get("success"):
                    return True, response_data.get("result")
                else:
                    errors = response_data.get("errors", [])
                    return False, errors[0].get("message") if errors else "Unknown error"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except requests.exceptions.RequestException as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)
    
    def list_dns_records(self, zone_id: str, name: str = None, record_type: str = None) -> Tuple[bool, Any]:
        """
        List DNS records in a zone
        
        Args:
            zone_id: Cloudflare zone ID
            name: Filter by record name (optional)
            record_type: Filter by record type (A, AAAA, etc.) (optional)
            
        Returns:
            Tuple of (success, list of records or error message)
        """
        endpoint = f"zones/{zone_id}/dns_records"
        params = []
        if name:
            params.append(f"name={name}")
        if record_type:
            params.append(f"type={record_type}")
        
        if params:
            endpoint += "?" + "&".join(params)
        
        return self._make_request("GET", endpoint)
    
    def create_dns_record(self, zone_id: str, record_type: str, name: str, 
                         content: str, ttl: int = 60, proxied: bool = False) -> Tuple[bool, Any]:
        """
        Create a DNS record
        
        Args:
            zone_id: Cloudflare zone ID
            record_type: Record type (A or AAAA)
            name: Record name (e.g., vpn.example.com)
            content: IP address
            ttl: TTL in seconds (default 60)
            proxied: Whether to proxy through Cloudflare (MUST be False for Phase 8)
            
        Returns:
            Tuple of (success, record data or error message)
        """
        # Enforce DNS-only (no proxy)
        proxied = False
        
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied
        }
        
        endpoint = f"zones/{zone_id}/dns_records"
        success, result = self._make_request("POST", endpoint, data)
        
        if success:
            _log_info(f"Created DNS record: {record_type} {name} -> {content}")
        else:
            _log_error(f"Failed to create DNS record: {result}")
        
        return success, result
    
    def update_dns_record(self, zone_id: str, record_id: str, record_type: str, 
                         name: str, content: str, ttl: int = 60, 
                         proxied: bool = False) -> Tuple[bool, Any]:
        """
        Update a DNS record
        
        Args:
            zone_id: Cloudflare zone ID
            record_id: DNS record ID
            record_type: Record type (A or AAAA)
            name: Record name
            content: IP address
            ttl: TTL in seconds
            proxied: Whether to proxy (MUST be False)
            
        Returns:
            Tuple of (success, record data or error message)
        """
        # Enforce DNS-only (no proxy)
        proxied = False
        
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied
        }
        
        endpoint = f"zones/{zone_id}/dns_records/{record_id}"
        success, result = self._make_request("PUT", endpoint, data)
        
        if success:
            _log_info(f"Updated DNS record: {record_type} {name} -> {content}")
        else:
            _log_error(f"Failed to update DNS record: {result}")
        
        return success, result
    
    def delete_dns_record(self, zone_id: str, record_id: str) -> Tuple[bool, Any]:
        """
        Delete a DNS record
        
        Args:
            zone_id: Cloudflare zone ID
            record_id: DNS record ID
            
        Returns:
            Tuple of (success, result or error message)
        """
        endpoint = f"zones/{zone_id}/dns_records/{record_id}"
        success, result = self._make_request("DELETE", endpoint)
        
        if success:
            _log_info(f"Deleted DNS record: {record_id}")
        else:
            _log_error(f"Failed to delete DNS record: {result}")
        
        return success, result
    
    def sync_node_ips_to_dns(self, zone_id: str, record_name: str, node_ips: List[str], 
                            ttl: int = 60) -> Tuple[bool, str]:
        """
        Sync node IPs to DNS records (A and AAAA)
        Creates/updates records to match the provided list of IPs
        Removes records that are not in the list
        All records are created with proxied=False (DNS-only)
        
        Args:
            zone_id: Cloudflare zone ID
            record_name: DNS record name (e.g., vpn.example.com)
            node_ips: List of IP addresses (IPv4 and IPv6)
            ttl: TTL in seconds
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Enforce DNS-only (no proxy)
            proxied = False
            
            # Separate IPv4 and IPv6
            ipv4_addresses = [ip for ip in node_ips if ':' not in ip]
            ipv6_addresses = [ip for ip in node_ips if ':' in ip]
            
            # Get existing A records
            success_a, existing_a = self.list_dns_records(zone_id, record_name, "A")
            if not success_a:
                existing_a = []
            
            # Get existing AAAA records
            success_aaaa, existing_aaaa = self.list_dns_records(zone_id, record_name, "AAAA")
            if not success_aaaa:
                existing_aaaa = []
            
            # Process A records
            existing_a_ips = {record['content']: record['id'] for record in existing_a} if isinstance(existing_a, list) else {}
            
            for ip in ipv4_addresses:
                if ip in existing_a_ips:
                    # Record exists, update if needed
                    record_id = existing_a_ips[ip]
                    existing_a_ips.pop(ip)  # Remove from list to track deletions
                else:
                    # Create new record
                    success, result = self.create_dns_record(zone_id, "A", record_name, ip, ttl, False)
                    if not success:
                        self._queue_retry("create", zone_id, "A", record_name, ip, ttl)
            
            # Delete A records that are no longer needed
            for ip, record_id in existing_a_ips.items():
                success, result = self.delete_dns_record(zone_id, record_id)
                if not success:
                    self._queue_retry("delete", zone_id, None, None, None, None, record_id)
            
            # Process AAAA records
            existing_aaaa_ips = {record['content']: record['id'] for record in existing_aaaa} if isinstance(existing_aaaa, list) else {}
            
            for ip in ipv6_addresses:
                if ip in existing_aaaa_ips:
                    # Record exists
                    existing_aaaa_ips.pop(ip)  # Remove from list to track deletions
                else:
                    # Create new record
                    success, result = self.create_dns_record(zone_id, "AAAA", record_name, ip, ttl, False)
                    if not success:
                        self._queue_retry("create", zone_id, "AAAA", record_name, ip, ttl)
            
            # Delete AAAA records that are no longer needed
            for ip, record_id in existing_aaaa_ips.items():
                success, result = self.delete_dns_record(zone_id, record_id)
                if not success:
                    self._queue_retry("delete", zone_id, None, None, None, None, record_id)
            
            return True, "DNS records synced successfully"
        
        except Exception as e:
            _log_error(f"Error syncing DNS records: {e}")
            return False, str(e)
    
    def _queue_retry(self, operation: str, zone_id: str, record_type: str = None, 
                    name: str = None, content: str = None, ttl: int = None, 
                    record_id: str = None):
        """Queue a failed operation for retry"""
        retry_item = {
            "operation": operation,
            "zone_id": zone_id,
            "record_type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "record_id": record_id,
            "timestamp": time.time(),
            "retry_count": 0
        }
        self.retry_queue.append(retry_item)
        _log_info(f"Queued {operation} operation for retry")
        
        # Start retry thread if not running
        if not self._retry_thread or not self._retry_thread.is_alive():
            self._start_retry_thread()
    
    def _start_retry_thread(self):
        """Start the retry thread"""
        self._stop_retry_thread = False
        self._retry_thread = threading.Thread(target=self._retry_worker, daemon=True)
        self._retry_thread.start()
    
    def _retry_worker(self):
        """Worker thread that processes retry queue"""
        while not self._stop_retry_thread:
            if self.retry_queue:
                item = self.retry_queue.popleft()
                
                # Attempt retry
                success = False
                if item["operation"] == "create":
                    success, _ = self.create_dns_record(
                        item["zone_id"], item["record_type"], item["name"],
                        item["content"], item["ttl"], False
                    )
                elif item["operation"] == "delete":
                    success, _ = self.delete_dns_record(item["zone_id"], item["record_id"])
                
                if not success:
                    item["retry_count"] += 1
                    if item["retry_count"] < 5:  # Max 5 retries
                        self.retry_queue.append(item)
                        _log_info(f"Retry {item['retry_count']}/5 for {item['operation']}")
                    else:
                        _log_error(f"Max retries reached for {item['operation']}, giving up")
            
            time.sleep(30)  # Wait 30 seconds between retries
    
    def stop_retry_thread(self):
        """Stop the retry thread"""
        self._stop_retry_thread = True
        if self._retry_thread:
            self._retry_thread.join(timeout=5)
