# Multi-Node Architecture Documentation

## Overview

WGDashboard now supports managing multiple WireGuard nodes through a controller-agent architecture. This allows you to:

- Manage peers across multiple WireGuard nodes from a single dashboard
- Distribute peers across nodes for load balancing
- Monitor health and status of all nodes
- Keep configurations synchronized

## Architecture

### Components

1. **Controller (Panel)**: The main WGDashboard instance that manages all nodes
2. **Node Agent**: A lightweight service running on each WireGuard node that receives commands from the controller

### Communication

The controller communicates with node agents via HMAC-signed HTTP requests. Each request includes:
- HTTP method and path
- Request body (JSON)
- Timestamp
- HMAC-SHA256 signature

This ensures:
- Authentication: Only the controller with the shared secret can issue commands
- Integrity: Requests cannot be modified in transit
- Replay protection: Timestamps prevent replay attacks

## Node Agent Contract

### Authentication

All requests must include these headers:
- `X-Signature`: HMAC-SHA256 signature of `METHOD|PATH|BODY|TIMESTAMP`
- `X-Timestamp`: Unix timestamp (seconds since epoch)
- `Content-Type`: `application/json`

**Signature Generation:**
```python
import hmac
import hashlib
import time

method = "GET"
path = "/health"
body = ""  # Empty for GET requests
timestamp = str(int(time.time()))
secret = "your-shared-secret"

message = f"{method}|{path}|{body}|{timestamp}"
signature = hmac.new(
    secret.encode('utf-8'),
    message.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

### Endpoints

#### Health Check

**GET /health**

Returns the health status of the node.

Response:
```json
{
  "status": "ok",
  "timestamp": 1234567890,
  "uptime": 86400,
  "version": "1.0.0"
}
```

#### WireGuard Dump

**GET /wg/{interface}/dump**

Returns the current state of all peers on the specified interface.

Parameters:
- `interface`: WireGuard interface name (e.g., `wg0`)

Response:
```json
{
  "interface": "wg0",
  "peers": [
    {
      "public_key": "peer_public_key_here",
      "endpoint": "1.2.3.4:51820",
      "allowed_ips": ["10.0.1.2/32"],
      "latest_handshake": 1234567890,
      "transfer_rx": 1024000,
      "transfer_tx": 2048000,
      "persistent_keepalive": 25
    }
  ]
}
```

#### Add Peer

**POST /wg/{interface}/peers**

Adds a new peer to the specified interface.

Parameters:
- `interface`: WireGuard interface name

Request Body:
```json
{
  "public_key": "peer_public_key_here",
  "allowed_ips": ["10.0.1.2/32"],
  "preshared_key": "optional_preshared_key",
  "persistent_keepalive": 25
}
```

Response:
```json
{
  "status": "success",
  "message": "Peer added successfully",
  "peer": {
    "public_key": "peer_public_key_here",
    "allowed_ips": ["10.0.1.2/32"]
  }
}
```

#### Update Peer

**PUT /wg/{interface}/peers/{public_key}**

Updates an existing peer's configuration.

Parameters:
- `interface`: WireGuard interface name
- `public_key`: Peer's public key (URL encoded)

Request Body:
```json
{
  "allowed_ips": ["10.0.1.2/32", "10.0.1.3/32"],
  "persistent_keepalive": 30
}
```

Response:
```json
{
  "status": "success",
  "message": "Peer updated successfully"
}
```

#### Delete Peer

**DELETE /wg/{interface}/peers/{public_key}**

Removes a peer from the specified interface.

Parameters:
- `interface`: WireGuard interface name
- `public_key`: Peer's public key (URL encoded)

Response:
```json
{
  "status": "success",
  "message": "Peer removed successfully"
}
```

## Deployment Models

### Single Controller, Multiple Nodes

```
                    ┌──────────────┐
                    │  Controller  │
                    │ (Dashboard)  │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐    ┌────▼─────┐    ┌────▼─────┐
    │  Node 1   │    │  Node 2  │    │  Node 3  │
    │  (Agent)  │    │ (Agent)  │    │ (Agent)  │
    └───────────┘    └──────────┘    └──────────┘
```

- Controller manages all nodes
- Agents run on each WireGuard server
- Controller polls agents for health and peer stats
- Peer operations executed via agent API

### Recommended Setup

1. **Controller**: Central server running full WGDashboard
   - Stores all configurations and peer data
   - Provides web UI for management
   - Polls agents for health monitoring

2. **Agents**: Lightweight service on each WireGuard node
   - Minimal dependencies
   - Executes WireGuard commands locally
   - Returns peer statistics
   - Validates HMAC signatures

## Security Considerations

### Shared Secret Management

- **Generate strong secrets**: Use `secrets.token_urlsafe(32)` or similar
- **Store securely**: Secrets should be encrypted at rest
- **Rotate regularly**: Implement secret rotation procedures
- **Unique per node**: Each node should have its own secret

### Network Security

- **Use HTTPS**: Always use TLS for agent communication in production
- **Firewall rules**: Restrict agent API to controller IP only
- **VPN tunnel**: Consider running agent communication over WireGuard itself
- **Rate limiting**: Implement rate limiting on agent endpoints

### Authentication

- **HMAC verification**: Agent must verify all signatures
- **Timestamp validation**: Reject requests with old timestamps (>5min)
- **No API keys in URLs**: Always use headers for authentication

## Backward Compatibility

The multi-node architecture is fully backward compatible with single-node setups:

- Database schema extensions use nullable columns
- If no nodes are configured, system operates in legacy mode
- Existing peers continue to work without modification
- Node management is optional and can be enabled when needed

## Node Configuration in Dashboard

### Adding a Node

1. Navigate to **Nodes** page
2. Click **Add Node**
3. Fill in required fields:
   - **Name**: Descriptive name for the node
   - **Agent URL**: Full URL to agent API (e.g., `http://node1.example.com:8080`)
   - **WireGuard Interface**: Interface name on the node (e.g., `wg0`)
   - **Endpoint**: Public endpoint for clients (optional)
   - **IP Pool CIDR**: IP range for peer allocation (optional)
   - **Weight**: Load balancing weight (default: 100)
   - **Max Peers**: Maximum peers on this node (0 = unlimited)
   - **Shared Secret**: Auto-generated or provide your own

4. Click **Test Connection** to verify agent is reachable
5. Click **Create**

### Managing Nodes

- **Enable/Disable**: Toggle node availability
- **Edit**: Update node configuration
- **Test Connection**: Verify agent connectivity
- **Delete**: Remove node (warning: peers on this node must be migrated first)

### Node Status

Nodes display real-time status:
- **Online**: Agent responding to health checks
- **Offline**: Agent not responding
- **Disabled**: Node manually disabled
- **Error**: Communication error with agent

## Implementation Checklist

When deploying the multi-node architecture:

- [ ] Set up controller (WGDashboard) instance
- [ ] Deploy agent service on each node
- [ ] Configure shared secrets
- [ ] Add nodes to dashboard
- [ ] Test connectivity
- [ ] Verify peer operations
- [ ] Set up monitoring
- [ ] Document secrets securely
- [ ] Configure backups
- [ ] Plan disaster recovery

## Future Enhancements

Planned features for future releases:

- Automatic peer load balancing
- Drift detection and reconciliation
- Node failover and high availability
- Peer migration between nodes
- Advanced health metrics
- Agent auto-discovery
- Certificate-based authentication
- Multi-region support
