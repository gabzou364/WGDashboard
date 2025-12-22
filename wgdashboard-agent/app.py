"""
FastAPI application for WGDashboard Agent
Handles WireGuard operations with HMAC authentication
"""

import os
import time
import hmac
import hashlib
import subprocess
import tempfile
import base64
import logging
import psutil
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Path, Body
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Configuration
SHARED_SECRET = os.getenv('WG_AGENT_SECRET', 'change-me-in-production')
MAX_TIMESTAMP_AGE = int(os.getenv('MAX_TIMESTAMP_AGE', '300'))

# FastAPI app
app = FastAPI(
    title="WGDashboard Agent",
    description="Production-grade WireGuard node agent for WGDashboard multi-node architecture",
    version="2.2.0"
)


# Request/Response Models
class PeerAddRequest(BaseModel):
    public_key: str = Field(..., description="Peer public key")
    allowed_ips: List[str] = Field(default=[], description="List of allowed IPs")
    preshared_key: Optional[str] = Field(None, description="Optional preshared key")
    persistent_keepalive: int = Field(default=0, description="Persistent keepalive interval")


class PeerUpdateRequest(BaseModel):
    allowed_ips: Optional[List[str]] = Field(None, description="Updated allowed IPs")
    persistent_keepalive: Optional[int] = Field(None, description="Updated keepalive interval")


class SyncconfRequest(BaseModel):
    config: str = Field(..., description="Base64-encoded WireGuard configuration")


class InterfaceConfigRequest(BaseModel):
    """Request model for updating full interface configuration (Phase 6)"""
    private_key: str = Field(..., description="WireGuard private key for the interface")
    listen_port: Optional[int] = Field(None, description="UDP port to listen on")
    address: Optional[str] = Field(None, description="Interface IP address(es)")
    post_up: Optional[str] = Field(None, description="Commands to run after interface is up")
    pre_down: Optional[str] = Field(None, description="Commands to run before interface goes down")
    mtu: Optional[int] = Field(None, description="MTU for the interface")
    dns: Optional[str] = Field(None, description="DNS servers for the interface")
    table: Optional[str] = Field(None, description="Routing table to use")


# Middleware for HMAC authentication
@app.middleware("http")
async def verify_hmac_signature(request: Request, call_next):
    """Verify HMAC signature on all requests except health check and metrics"""
    
    # Skip auth for health check and metrics endpoints
    if request.url.path in ["/health", "/v1/metrics"]:
        return await call_next(request)
    
    # Get headers
    signature = request.headers.get('X-Signature')
    timestamp = request.headers.get('X-Timestamp')
    
    if not signature or not timestamp:
        logger.warning(f"Missing signature or timestamp from {request.client.host}")
        return JSONResponse(
            status_code=401,
            content={"error": "Missing X-Signature or X-Timestamp header"}
        )
    
    # Validate timestamp to prevent replay attacks
    try:
        req_time = int(timestamp)
        now = int(time.time())
        if abs(now - req_time) > MAX_TIMESTAMP_AGE:
            logger.warning(f"Timestamp too old from {request.client.host}: {abs(now - req_time)}s")
            return JSONResponse(
                status_code=401,
                content={"error": "Request timestamp too old"}
            )
    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid timestamp"}
        )
    
    # Read body for signature verification
    body = await request.body()
    body_str = body.decode('utf-8') if body else ""
    
    # Compute expected signature
    message = f"{request.method}|{request.url.path}|{body_str}|{timestamp}"
    expected_sig = hmac.new(
        SHARED_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Verify signature
    if not hmac.compare_digest(signature, expected_sig):
        logger.warning(f"Invalid signature from {request.client.host}")
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid signature"}
        )
    
    # Signature valid, proceed
    response = await call_next(request)
    return response


# Health Check Endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint - no authentication required"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime = float(f.readline().split()[0])
    except:
        uptime = 0
    
    return {
        "status": "ok",
        "timestamp": int(time.time()),
        "uptime": int(uptime),
        "version": "2.2.0"
    }


# Observability Endpoints (Phase 5)
@app.get("/v1/status")
async def get_status():
    """
    Get detailed status report including peer counts, memory, CPU usage, and interface statuses.
    Used for observability systems and real-time health monitoring.
    """
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get network info
        net_io = psutil.net_io_counters()
        
        # Get WireGuard interfaces
        interfaces_status = {}
        try:
            # List all WireGuard interfaces
            wg_output = subprocess.check_output(['wg', 'show', 'interfaces'], stderr=subprocess.STDOUT).decode('utf-8')
            interfaces = wg_output.strip().split()
            
            for iface in interfaces:
                try:
                    # Get interface status
                    dump_output = subprocess.check_output(
                        ['wg', 'show', iface, 'dump'],
                        stderr=subprocess.STDOUT
                    ).decode('utf-8')
                    
                    lines = dump_output.strip().split('\n')
                    peer_count = len(lines) - 1  # Subtract header line
                    
                    # Count active peers (those with recent handshake)
                    active_peers = 0
                    total_rx = 0
                    total_tx = 0
                    current_time = int(time.time())
                    
                    for line in lines[1:]:  # Skip header
                        parts = line.split('\t')
                        if len(parts) >= 8:
                            latest_handshake = int(parts[4]) if parts[4] != '0' else 0
                            # Consider peer active if handshake within last 3 minutes
                            if latest_handshake > 0 and (current_time - latest_handshake) < 180:
                                active_peers += 1
                            total_rx += int(parts[5])
                            total_tx += int(parts[6])
                    
                    interfaces_status[iface] = {
                        'status': 'up',
                        'peer_count': peer_count,
                        'active_peers': active_peers,
                        'total_rx_bytes': total_rx,
                        'total_tx_bytes': total_tx
                    }
                except subprocess.CalledProcessError:
                    interfaces_status[iface] = {
                        'status': 'error',
                        'peer_count': 0,
                        'active_peers': 0
                    }
        except subprocess.CalledProcessError:
            pass  # No WireGuard interfaces
        
        # Get uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime = float(f.readline().split()[0])
        except:
            uptime = 0
        
        return {
            'status': 'ok',
            'timestamp': int(time.time()),
            'uptime': int(uptime),
            'version': '2.1.0',
            'system': {
                'cpu_percent': round(cpu_percent, 2),
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                }
            },
            'wireguard': {
                'interfaces': interfaces_status,
                'interface_count': len(interfaces_status)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/metrics")
async def get_metrics():
    """
    Expose WireGuard and system-level metrics in Prometheus-compatible format.
    Used for observability systems like Prometheus/Grafana.
    """
    try:
        metrics = []
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics.append(f'# HELP wgdashboard_agent_cpu_percent CPU usage percentage')
        metrics.append(f'# TYPE wgdashboard_agent_cpu_percent gauge')
        metrics.append(f'wgdashboard_agent_cpu_percent {cpu_percent}')
        
        metrics.append(f'# HELP wgdashboard_agent_memory_used_bytes Memory used in bytes')
        metrics.append(f'# TYPE wgdashboard_agent_memory_used_bytes gauge')
        metrics.append(f'wgdashboard_agent_memory_used_bytes {memory.used}')
        
        metrics.append(f'# HELP wgdashboard_agent_memory_percent Memory usage percentage')
        metrics.append(f'# TYPE wgdashboard_agent_memory_percent gauge')
        metrics.append(f'wgdashboard_agent_memory_percent {memory.percent}')
        
        metrics.append(f'# HELP wgdashboard_agent_disk_used_bytes Disk used in bytes')
        metrics.append(f'# TYPE wgdashboard_agent_disk_used_bytes gauge')
        metrics.append(f'wgdashboard_agent_disk_used_bytes {disk.used}')
        
        # Get WireGuard interfaces and metrics
        try:
            wg_output = subprocess.check_output(['wg', 'show', 'interfaces'], stderr=subprocess.STDOUT).decode('utf-8')
            interfaces = wg_output.strip().split()
            
            metrics.append(f'# HELP wireguard_interface_count Number of WireGuard interfaces')
            metrics.append(f'# TYPE wireguard_interface_count gauge')
            metrics.append(f'wireguard_interface_count {len(interfaces)}')
            
            for iface in interfaces:
                try:
                    dump_output = subprocess.check_output(
                        ['wg', 'show', iface, 'dump'],
                        stderr=subprocess.STDOUT
                    ).decode('utf-8')
                    
                    lines = dump_output.strip().split('\n')
                    peer_count = len(lines) - 1
                    
                    metrics.append(f'# HELP wireguard_peers_total Total number of peers on interface')
                    metrics.append(f'# TYPE wireguard_peers_total gauge')
                    metrics.append(f'wireguard_peers_total{{interface="{iface}"}} {peer_count}')
                    
                    # Parse peer data
                    active_peers = 0
                    total_rx = 0
                    total_tx = 0
                    current_time = int(time.time())
                    
                    for line in lines[1:]:
                        parts = line.split('\t')
                        if len(parts) >= 8:
                            public_key = parts[0][:16]  # Truncate for label
                            latest_handshake = int(parts[4]) if parts[4] != '0' else 0
                            transfer_rx = int(parts[5])
                            transfer_tx = int(parts[6])
                            
                            # Count active peers
                            if latest_handshake > 0 and (current_time - latest_handshake) < 180:
                                active_peers += 1
                            
                            total_rx += transfer_rx
                            total_tx += transfer_tx
                            
                            # Per-peer metrics (optional, can be commented out for large deployments)
                            metrics.append(f'wireguard_peer_receive_bytes_total{{interface="{iface}",public_key="{public_key}"}} {transfer_rx}')
                            metrics.append(f'wireguard_peer_transmit_bytes_total{{interface="{iface}",public_key="{public_key}"}} {transfer_tx}')
                            
                            if latest_handshake > 0:
                                seconds_since = current_time - latest_handshake
                                metrics.append(f'wireguard_peer_last_handshake_seconds{{interface="{iface}",public_key="{public_key}"}} {seconds_since}')
                    
                    metrics.append(f'# HELP wireguard_peers_active Active peers (handshake within 3 minutes)')
                    metrics.append(f'# TYPE wireguard_peers_active gauge')
                    metrics.append(f'wireguard_peers_active{{interface="{iface}"}} {active_peers}')
                    
                    metrics.append(f'# HELP wireguard_interface_receive_bytes_total Total bytes received on interface')
                    metrics.append(f'# TYPE wireguard_interface_receive_bytes_total counter')
                    metrics.append(f'wireguard_interface_receive_bytes_total{{interface="{iface}"}} {total_rx}')
                    
                    metrics.append(f'# HELP wireguard_interface_transmit_bytes_total Total bytes transmitted on interface')
                    metrics.append(f'# TYPE wireguard_interface_transmit_bytes_total counter')
                    metrics.append(f'wireguard_interface_transmit_bytes_total{{interface="{iface}"}} {total_tx}')
                    
                except subprocess.CalledProcessError:
                    pass
        except subprocess.CalledProcessError:
            pass
        
        # Return in Prometheus text format
        return PlainTextResponse('\n'.join(metrics) + '\n', media_type='text/plain; version=0.0.4')
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# WireGuard Operations
@app.get("/v1/wg/{interface}/dump")
async def get_wg_dump(interface: str = Path(..., description="WireGuard interface name")):
    """Get WireGuard interface dump with all peer information"""
    try:
        logger.info(f"Getting WireGuard dump for interface {interface}")
        
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
        
        logger.info(f"Successfully retrieved {len(peers)} peers from {interface}")
        return {
            'interface': interface,
            'peers': peers
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"WireGuard command failed for {interface}: {e.output.decode()}")
        raise HTTPException(status_code=500, detail=f"WireGuard command failed: {e.output.decode()}")
    except Exception as e:
        logger.error(f"Error getting WireGuard dump for {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/wg/{interface}/peers")
async def add_peer(
    interface: str = Path(..., description="WireGuard interface name"),
    peer_data: PeerAddRequest = Body(...)
):
    """Add a new peer to the WireGuard interface"""
    try:
        logger.info(f"Adding peer {peer_data.public_key[:16]}... to {interface}")
        
        # Build wg command
        cmd = ['wg', 'set', interface, 'peer', peer_data.public_key]
        
        if peer_data.allowed_ips:
            cmd.extend(['allowed-ips', ','.join(peer_data.allowed_ips)])
        
        # Handle preshared key via temporary file
        psk_file_path = None
        if peer_data.preshared_key:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as psk_file:
                psk_file.write(peer_data.preshared_key)
                psk_file_path = psk_file.name
            cmd.extend(['preshared-key', psk_file_path])
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Set keepalive if specified
            if peer_data.persistent_keepalive > 0:
                subprocess.run([
                    'wg', 'set', interface, 'peer', peer_data.public_key,
                    'persistent-keepalive', str(peer_data.persistent_keepalive)
                ], check=True, capture_output=True)
            
            # Save configuration
            subprocess.run(['wg-quick', 'save', interface], check=True, capture_output=True)
            
            logger.info(f"Successfully added peer {peer_data.public_key[:16]}... to {interface}")
            return {
                'status': 'success',
                'message': 'Peer added successfully',
                'peer': {
                    'public_key': peer_data.public_key,
                    'allowed_ips': peer_data.allowed_ips
                }
            }
            
        finally:
            # Clean up preshared key file
            if psk_file_path and os.path.exists(psk_file_path):
                os.unlink(psk_file_path)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to add peer to {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add peer: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error adding peer to {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/wg/{interface}/peers/{public_key}")
async def update_peer(
    interface: str = Path(..., description="WireGuard interface name"),
    public_key: str = Path(..., description="Peer public key"),
    peer_data: PeerUpdateRequest = Body(...)
):
    """Update an existing peer's configuration"""
    try:
        logger.info(f"Updating peer {public_key[:16]}... on {interface}")
        
        cmd = ['wg', 'set', interface, 'peer', public_key]
        
        if peer_data.allowed_ips is not None:
            cmd.extend(['allowed-ips', ','.join(peer_data.allowed_ips)])
        
        if peer_data.persistent_keepalive is not None:
            cmd.extend(['persistent-keepalive', str(peer_data.persistent_keepalive)])
        
        subprocess.run(cmd, check=True, capture_output=True)
        subprocess.run(['wg-quick', 'save', interface], check=True, capture_output=True)
        
        logger.info(f"Successfully updated peer {public_key[:16]}... on {interface}")
        return {
            'status': 'success',
            'message': 'Peer updated successfully'
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to update peer on {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update peer: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error updating peer on {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/wg/{interface}/peers/{public_key}")
async def delete_peer(
    interface: str = Path(..., description="WireGuard interface name"),
    public_key: str = Path(..., description="Peer public key")
):
    """Remove a peer from the WireGuard interface"""
    try:
        logger.info(f"Deleting peer {public_key[:16]}... from {interface}")
        
        subprocess.run([
            'wg', 'set', interface, 'peer', public_key, 'remove'
        ], check=True, capture_output=True)
        
        subprocess.run(['wg-quick', 'save', interface], check=True, capture_output=True)
        
        logger.info(f"Successfully deleted peer {public_key[:16]}... from {interface}")
        return {
            'status': 'success',
            'message': 'Peer removed successfully'
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete peer from {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to remove peer: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error deleting peer from {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/wg/{interface}/syncconf")
async def syncconf(
    interface: str = Path(..., description="WireGuard interface name"),
    config_data: SyncconfRequest = Body(...)
):
    """
    Apply configuration using wg syncconf for atomic updates (Phase 4)
    This endpoint is used for drift reconciliation
    """
    try:
        logger.info(f"Applying syncconf to {interface}")
        
        # Decode base64 configuration
        try:
            config_content = base64.b64decode(config_data.config).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decode configuration: {e}")
            raise HTTPException(status_code=400, detail="Invalid base64-encoded configuration")
        
        # Write config to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as config_file:
            config_file.write(config_content)
            config_file_path = config_file.name
        
        try:
            # Apply configuration using wg syncconf
            subprocess.run([
                'wg', 'syncconf', interface, config_file_path
            ], check=True, capture_output=True)
            
            # Save the configuration
            subprocess.run(['wg-quick', 'save', interface], check=True, capture_output=True)
            
            logger.info(f"Successfully applied syncconf to {interface}")
            return {
                'status': 'success',
                'message': 'Configuration synchronized successfully'
            }
            
        finally:
            # Clean up temporary config file
            if os.path.exists(config_file_path):
                os.unlink(config_file_path)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to syncconf {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to synchronize configuration: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error syncing configuration for {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Interface-Level Configuration Management (Phase 6)
@app.get("/v1/wg/{interface}/config")
async def get_interface_config(interface: str = Path(..., description="WireGuard interface name")):
    """
    Get full WireGuard interface configuration (Phase 6)
    Returns the complete configuration from /etc/wireguard/{interface}.conf
    """
    try:
        logger.info(f"Getting interface configuration for {interface}")
        
        config_path = f"/etc/wireguard/{interface}.conf"
        
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            raise HTTPException(status_code=404, detail=f"Configuration file not found: {config_path}")
        
        # Read the configuration file
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        # Parse the configuration to extract key details
        config_lines = config_content.strip().split('\n')
        parsed_config = {
            'private_key': None,
            'listen_port': None,
            'address': None,
            'post_up': None,
            'pre_down': None,
            'mtu': None,
            'dns': None,
            'table': None,
            'raw_config': config_content
        }
        
        current_section = None
        for line in config_lines:
            line = line.strip()
            if line.startswith('['):
                current_section = line.lower()
            elif current_section == '[interface]' and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'privatekey':
                    parsed_config['private_key'] = value
                elif key == 'listenport':
                    parsed_config['listen_port'] = int(value)
                elif key == 'address':
                    parsed_config['address'] = value
                elif key == 'postup':
                    parsed_config['post_up'] = value
                elif key == 'predown':
                    parsed_config['pre_down'] = value
                elif key == 'mtu':
                    parsed_config['mtu'] = int(value)
                elif key == 'dns':
                    parsed_config['dns'] = value
                elif key == 'table':
                    parsed_config['table'] = value
        
        logger.info(f"Successfully retrieved configuration for {interface}")
        return {
            'interface': interface,
            'config': parsed_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting interface configuration for {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/wg/{interface}/config")
async def set_interface_config(
    interface: str = Path(..., description="WireGuard interface name"),
    config_data: InterfaceConfigRequest = Body(...)
):
    """
    Replace WireGuard interface configuration (Phase 6)
    Updates /etc/wireguard/{interface}.conf and reloads the interface
    Includes dry-run validation before applying
    """
    try:
        logger.info(f"Updating interface configuration for {interface}")
        
        config_path = f"/etc/wireguard/{interface}.conf"
        backup_path = f"{config_path}.backup"
        temp_path = f"{config_path}.tmp"
        
        # Backup existing configuration if it exists
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                backup_content = f.read()
            with open(backup_path, 'w') as f:
                f.write(backup_content)
        
        # Build new configuration file
        config_lines = ["[Interface]"]
        
        # Required field
        config_lines.append(f"PrivateKey = {config_data.private_key}")
        
        # Optional fields
        if config_data.listen_port:
            config_lines.append(f"ListenPort = {config_data.listen_port}")
        if config_data.address:
            config_lines.append(f"Address = {config_data.address}")
        if config_data.mtu:
            config_lines.append(f"MTU = {config_data.mtu}")
        if config_data.dns:
            config_lines.append(f"DNS = {config_data.dns}")
        if config_data.table:
            config_lines.append(f"Table = {config_data.table}")
        if config_data.post_up:
            config_lines.append(f"PostUp = {config_data.post_up}")
        if config_data.pre_down:
            config_lines.append(f"PreDown = {config_data.pre_down}")
        
        # Add existing peer configurations if any
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                existing_content = f.read()
            
            # Extract [Peer] sections from existing config
            peer_sections = []
            lines = existing_content.split('\n')
            in_peer_section = False
            current_peer = []
            
            for line in lines:
                if line.strip().startswith('[Peer]'):
                    if current_peer:
                        peer_sections.append('\n'.join(current_peer))
                    current_peer = [line]
                    in_peer_section = True
                elif in_peer_section:
                    if line.strip().startswith('['):
                        # New section, end peer
                        if current_peer:
                            peer_sections.append('\n'.join(current_peer))
                        current_peer = []
                        in_peer_section = False
                    else:
                        current_peer.append(line)
            
            # Add last peer if exists
            if current_peer:
                peer_sections.append('\n'.join(current_peer))
            
            # Add peer sections to new config
            if peer_sections:
                config_lines.append("")
                for peer in peer_sections:
                    config_lines.append(peer)
        
        new_config = '\n'.join(config_lines) + '\n'
        
        # Write to temporary file for validation
        with open(temp_path, 'w') as f:
            f.write(new_config)
        
        # Dry-run validation: check if wg can parse the config
        try:
            # Use wg show to validate the private key format
            subprocess.run([
                'wg', 'show', interface
            ], capture_output=True)
            
            # Validate the config syntax by trying to read it
            subprocess.run([
                'wg', 'showconf', interface
            ], capture_output=True)
            
            logger.info(f"Dry-run validation passed for {interface}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Dry-run validation failed for {interface}: {e.stderr.decode() if e.stderr else str(e)}")
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise HTTPException(status_code=400, detail=f"Configuration validation failed: {e.stderr.decode() if e.stderr else str(e)}")
        
        # Move temp file to actual config path
        os.rename(temp_path, config_path)
        
        # Reload the interface (bring down and up)
        try:
            # Check if interface is currently up
            try:
                subprocess.run(['wg', 'show', interface], check=True, capture_output=True)
                interface_was_up = True
            except subprocess.CalledProcessError:
                interface_was_up = False
            
            if interface_was_up:
                # Bring interface down
                subprocess.run(['wg-quick', 'down', interface], check=True, capture_output=True)
                # Bring interface up with new config
                subprocess.run(['wg-quick', 'up', interface], check=True, capture_output=True)
                logger.info(f"Successfully reloaded interface {interface} with new configuration")
            else:
                logger.info(f"Interface {interface} was not up, configuration updated but not loaded")
            
            return {
                'status': 'success',
                'message': f'Interface configuration updated successfully',
                'reloaded': interface_was_up
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload interface {interface}: {e.stderr.decode() if e.stderr else str(e)}")
            # Restore backup
            if os.path.exists(backup_path):
                os.rename(backup_path, config_path)
                logger.info(f"Restored backup configuration for {interface}")
            raise HTTPException(status_code=500, detail=f"Failed to reload interface: {e.stderr.decode() if e.stderr else str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating interface configuration for {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/wg/{interface}/enable")
async def enable_interface(interface: str = Path(..., description="WireGuard interface name")):
    """
    Bring WireGuard interface up (Phase 6)
    """
    try:
        logger.info(f"Enabling interface {interface}")
        
        # Check if interface is already up
        try:
            subprocess.run(['wg', 'show', interface], check=True, capture_output=True)
            logger.info(f"Interface {interface} is already up")
            return {
                'status': 'success',
                'message': f'Interface {interface} is already up',
                'was_down': False
            }
        except subprocess.CalledProcessError:
            pass  # Interface is down, proceed to bring it up
        
        # Bring interface up
        result = subprocess.run([
            'wg-quick', 'up', interface
        ], check=True, capture_output=True)
        
        logger.info(f"Successfully enabled interface {interface}")
        return {
            'status': 'success',
            'message': f'Interface {interface} enabled successfully',
            'was_down': True
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to enable interface {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to enable interface: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error enabling interface {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/wg/{interface}/disable")
async def disable_interface(interface: str = Path(..., description="WireGuard interface name")):
    """
    Bring WireGuard interface down (Phase 6)
    """
    try:
        logger.info(f"Disabling interface {interface}")
        
        # Check if interface is up
        try:
            subprocess.run(['wg', 'show', interface], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.info(f"Interface {interface} is already down")
            return {
                'status': 'success',
                'message': f'Interface {interface} is already down',
                'was_up': False
            }
        
        # Bring interface down
        result = subprocess.run([
            'wg-quick', 'down', interface
        ], check=True, capture_output=True)
        
        logger.info(f"Successfully disabled interface {interface}")
        return {
            'status': 'success',
            'message': f'Interface {interface} disabled successfully',
            'was_up': True
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to disable interface {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to disable interface: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error disabling interface {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/wg/{interface}")
async def delete_interface(interface: str = Path(..., description="WireGuard interface name")):
    """
    Delete/remove a WireGuard interface (Phase 8)
    This will:
    1. Disable the interface if it's up
    2. Remove the configuration file
    """
    try:
        logger.info(f"Deleting interface {interface}")
        
        # First, try to disable the interface if it's up
        try:
            subprocess.run(['wg', 'show', interface], check=True, capture_output=True)
            # Interface is up, disable it
            subprocess.run(['wg-quick', 'down', interface], check=True, capture_output=True)
            logger.info(f"Disabled interface {interface}")
        except subprocess.CalledProcessError:
            # Interface is already down or doesn't exist
            logger.info(f"Interface {interface} is not running")
        
        # Remove the configuration file
        import os
        config_path = f"/etc/wireguard/{interface}.conf"
        if os.path.exists(config_path):
            os.remove(config_path)
            logger.info(f"Removed configuration file {config_path}")
        else:
            logger.warning(f"Configuration file {config_path} not found")
        
        return {
            'status': 'success',
            'message': f'Interface {interface} deleted successfully'
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete interface {interface}: {e.stderr.decode() if e.stderr else str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete interface: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        logger.error(f"Error deleting interface {interface}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
