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
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Path, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Configuration
SHARED_SECRET = os.getenv('WG_AGENT_SECRET', 'change-me-in-production')
MAX_TIMESTAMP_AGE = int(os.getenv('MAX_TIMESTAMP_AGE', '300'))

# FastAPI app
app = FastAPI(
    title="WGDashboard Agent",
    description="Production-grade WireGuard node agent for WGDashboard multi-node architecture",
    version="2.0.0"
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


# Middleware for HMAC authentication
@app.middleware("http")
async def verify_hmac_signature(request: Request, call_next):
    """Verify HMAC signature on all requests except health check"""
    
    # Skip auth for health check
    if request.url.path == "/health":
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
        "version": "2.0.0"
    }


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
