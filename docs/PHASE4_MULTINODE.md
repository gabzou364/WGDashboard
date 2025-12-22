# Phase 4: Drift Detection and Enhanced Multi-Node Features

This document describes the Phase 4 features that enable drift detection, configuration reconciliation, per-node overrides, and a production-grade agent worker.

## Overview

Phase 4 adds critical operational features for managing distributed WireGuard deployments:

1. **Drift Detection** - Identify configuration mismatches between panel and nodes
2. **Reconciliation** - Automated drift resolution with atomic updates
3. **Per-Node Overrides** - Node-specific configuration parameters
4. **Production Agent** - FastAPI-based agent with robust error handling

## Features

### 1. Drift Detection

Drift detection identifies three types of configuration issues:

#### Unknown Peers
Peers present on the WireGuard interface but not recorded in the panel database.

**Example:**
```
Panel DB: No record
Agent:    Peer ABC123 with IP 10.0.1.100/32
Result:   Unknown peer detected
```

#### Missing Peers
Peers recorded in the panel but absent from the WireGuard interface.

**Example:**
```
Panel DB: Peer XYZ789 should be at 10.0.1.2/32
Agent:    No such peer
Result:   Missing peer detected
```

#### Mismatched Configurations
Peers present in both but with different configurations (allowed IPs, keepalive).

**Example:**
```
Panel DB: Peer DEF456 with allowed_ips=['10.0.1.2/32', '10.0.1.3/32']
Agent:    Peer DEF456 with allowed_ips=['10.0.1.2/32']
Result:   Configuration mismatch detected
```

#### API Endpoints

**Get Drift Report for Node**
```http
GET /api/drift/nodes/{node_id}
```

Response:
```json
{
  "status": true,
  "message": "Drift detection completed",
  "data": {
    "has_drift": true,
    "unknown_peers": [
      {
        "public_key": "...",
        "allowed_ips": ["10.0.1.100/32"],
        "persistent_keepalive": 0
      }
    ],
    "missing_peers": [
      {
        "public_key": "...",
        "name": "Peer Name",
        "allowed_ips": ["10.0.1.2/32"],
        "peer_id": "peer-uuid"
      }
    ],
    "mismatched_peers": [
      {
        "public_key": "...",
        "name": "Peer Name",
        "peer_id": "peer-uuid",
        "mismatches": [
          {
            "field": "allowed_ips",
            "expected": ["10.0.1.2/32", "10.0.1.3/32"],
            "actual": ["10.0.1.2/32"]
          },
          {
            "field": "persistent_keepalive",
            "expected": 25,
            "actual": 30
          }
        ]
      }
    ],
    "summary": {
      "unknown_count": 1,
      "missing_count": 1,
      "mismatched_count": 1,
      "total_issues": 3
    },
    "node_id": "node-uuid",
    "detected_at": "2024-01-15T10:30:00"
  }
}
```

**Get Drift Report for All Nodes**
```http
GET /api/drift/nodes
```

Response:
```json
{
  "status": true,
  "message": "Drift detection completed for all nodes",
  "data": {
    "nodes": {
      "node-uuid-1": { /* drift report */ },
      "node-uuid-2": { /* drift report */ }
    },
    "summary": {
      "total_nodes": 2,
      "nodes_with_drift": 1,
      "total_issues": 5
    }
  }
}
```

### 2. Drift Reconciliation

Automated drift resolution applies the panel's intended configuration to the node.

#### API Endpoint

**Reconcile Drift for Node**
```http
POST /api/drift/nodes/{node_id}/reconcile
Content-Type: application/json

{
  "reconcile_missing": true,
  "reconcile_mismatched": true,
  "remove_unknown": false
}
```

**Parameters:**
- `reconcile_missing` (bool): Add missing peers to the node
- `reconcile_mismatched` (bool): Update mismatched peer configurations
- `remove_unknown` (bool): Remove unknown peers from the node

Response:
```json
{
  "status": true,
  "message": "Added 2 peers, Updated 1 peers, 0 errors",
  "data": {
    "added": ["peer_key_1", "peer_key_2"],
    "updated": ["peer_key_3"],
    "removed": [],
    "errors": []
  }
}
```

#### Reconciliation Process

1. **Detect drift** - Compare current state to expected state
2. **Add missing peers** - Create peers that should exist
3. **Update mismatched peers** - Fix configuration differences
4. **Remove unknown peers** - Delete unrecognized peers (optional)
5. **Return results** - Report actions taken and any errors

**Safety Features:**
- **Non-destructive by default** - Unknown peers are not removed unless explicitly requested
- **Modular updates** - Each peer operation is independent
- **Error isolation** - Failure to update one peer doesn't affect others
- **Detailed reporting** - Full breakdown of actions and errors

### 3. Per-Node Overrides

Override global defaults with node-specific configuration parameters.

#### Supported Overrides

| Override Field | Type | Description |
|----------------|------|-------------|
| `override_listen_port` | Integer | WireGuard listen port for this node |
| `override_dns` | String | DNS server for peers on this node |
| `override_mtu` | Integer | MTU for peers on this node |
| `override_keepalive` | Integer | Persistent keepalive for peers on this node |
| `override_endpoint_allowed_ip` | String | Allowed IP ranges for peers on this node |

#### API Updates

When creating or updating a node, include override fields:

```http
PUT /api/nodes/{node_id}
Content-Type: application/json

{
  "name": "Node 1",
  "override_listen_port": 51821,
  "override_dns": "8.8.8.8",
  "override_mtu": 1380,
  "override_keepalive": 30,
  "override_endpoint_allowed_ip": "0.0.0.0/0,::/0"
}
```

#### Database Schema

New columns added to `Nodes` table:
```sql
ALTER TABLE Nodes ADD COLUMN override_listen_port INTEGER NULL;
ALTER TABLE Nodes ADD COLUMN override_dns VARCHAR(255) NULL;
ALTER TABLE Nodes ADD COLUMN override_mtu INTEGER NULL;
ALTER TABLE Nodes ADD COLUMN override_keepalive INTEGER NULL;
ALTER TABLE Nodes ADD COLUMN override_endpoint_allowed_ip TEXT NULL;
```

#### Usage Example

**Scenario:** You have nodes in different regions with different MTU requirements:

```
Node US-East:  override_mtu = 1420 (standard)
Node EU-West:  override_mtu = 1380 (lower for problematic ISPs)
Node Asia:     override_mtu = 1500 (jumbo frames supported)
```

When creating peers on each node, the appropriate MTU is automatically applied based on the node's override setting.

### 4. Production-Grade Agent Worker

A robust, FastAPI-based agent with enterprise features.

#### Features

- **FastAPI Framework** - Modern, async Python web framework
- **Structured Logging** - JSON-formatted logs with configurable levels
- **HMAC Authentication** - Same security as example agent
- **Request Validation** - Pydantic models for type safety
- **Error Handling** - Comprehensive exception handling
- **Health Checks** - Built-in monitoring endpoint
- **Systemd Integration** - Service file for production deployment
- **Configuration Management** - Environment-based configuration

#### Installation

See [wgdashboard-agent/README.md](../wgdashboard-agent/README.md) for detailed installation instructions.

**Quick Start:**
```bash
# Copy agent files
sudo mkdir -p /opt/wgdashboard-agent
sudo cp -r wgdashboard-agent/* /opt/wgdashboard-agent/

# Install dependencies
cd /opt/wgdashboard-agent
sudo pip3 install -r requirements.txt

# Configure environment
sudo cp .env.example .env
sudo nano .env  # Set WG_AGENT_SECRET

# Install and start service
sudo cp wgdashboard-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wgdashboard-agent
sudo systemctl start wgdashboard-agent
```

#### New Endpoint: Syncconf

**POST /v1/wg/{interface}/syncconf**

Atomic configuration synchronization using WireGuard's `wg syncconf` command.

Request:
```json
{
  "config": "base64-encoded-wireguard-config"
}
```

**Benefits:**
- **Zero downtime** - Updates without bringing down interface
- **Atomic updates** - All changes applied together or none
- **Drift reconciliation** - Ideal for fixing multiple issues at once

**Example Usage:**
```python
import base64
from NodeAgent import AgentClient

client = AgentClient('http://node:8080', 'secret')

# Prepare WireGuard config
config = """
[Peer]
PublicKey = peer1_public_key
AllowedIPs = 10.0.1.2/32

[Peer]
PublicKey = peer2_public_key
AllowedIPs = 10.0.1.3/32
"""

# Encode and send
config_b64 = base64.b64encode(config.encode()).decode()
success, result = client.syncconf('wg0', config_b64)
```

## Backward Compatibility

All Phase 4 features are fully backward compatible:

- ✅ **Drift detection** - Optional feature, doesn't affect existing functionality
- ✅ **Reconciliation** - Explicit API calls, won't auto-reconcile
- ✅ **Per-node overrides** - Nullable columns, existing nodes unaffected
- ✅ **Production agent** - Drop-in replacement for example agent
- ✅ **Existing API endpoints** - Unchanged behavior

## Testing

Run Phase 4 tests:
```bash
python3 test_phase4_multinode.py
```

**Test Coverage:**
1. ✅ Drift detection with no drift
2. ✅ Drift detection with unknown peers
3. ✅ Drift detection with missing peers
4. ✅ Drift detection with mismatched configurations
5. ✅ Drift detection with combined issues
6. ✅ Per-node override fields
7. ✅ AgentClient syncconf method

All tests passing (7/7).

## Security Considerations

### Drift Detection
- **Read-only operation** - Detection doesn't modify state
- **Authenticated** - Requires valid session or API key
- **Rate limiting** - Should be implemented for production

### Reconciliation
- **Destructive operation** - Can add/remove/modify peers
- **Requires explicit request** - Not automatic
- **Logged** - All reconciliation actions are logged
- **Transactional** - Each peer operation is independent

### Per-Node Overrides
- **Validated** - Override values validated before storage
- **Audit trail** - Changes tracked via `updated_at` timestamp
- **Access control** - Same permissions as node management

### Production Agent
- **HMAC authentication** - All requests signed
- **Timestamp validation** - Replay attack prevention
- **Secure defaults** - Requires explicit secret configuration
- **Systemd hardening** - Service runs with security restrictions

## Performance

### Drift Detection
- **O(n)** where n = total peers across all nodes
- **Network latency** dependent on agent response time
- **Recommended frequency** - Every 5-15 minutes

### Reconciliation
- **O(m)** where m = number of drift issues
- **Sequential operations** - Peers updated one at a time
- **Atomic option** - Use syncconf for bulk updates

### Agent Performance
- **FastAPI** - Async request handling
- **Concurrent requests** - Multiple controllers supported
- **Resource usage** - Minimal CPU/memory overhead

## Troubleshooting

### Drift Detection Fails

**Issue:** API returns error or no drift data

**Solutions:**
1. Verify agent is reachable: `curl http://node:8080/health`
2. Check node is enabled in database
3. Verify WireGuard interface exists: `wg show`
4. Check panel logs for detailed errors

### Reconciliation Fails

**Issue:** Reconciliation completes but peers still have drift

**Solutions:**
1. Check `errors` array in response for specific failures
2. Verify agent has root permissions
3. Check WireGuard interface configuration
4. Re-run drift detection to verify current state

### Per-Node Overrides Not Applied

**Issue:** Peers created on node don't use override values

**Solutions:**
1. Verify overrides are set in node record
2. Check peer creation logic uses node overrides
3. Verify database migration applied override columns

### Agent Syncconf Fails

**Issue:** Syncconf endpoint returns error

**Solutions:**
1. Verify config is valid base64
2. Check decoded config is valid WireGuard format
3. Verify agent can write to WireGuard interface
4. Check agent logs: `journalctl -u wgdashboard-agent -f`

## Migration Guide

### From Example Agent to Production Agent

1. **Backup current agent configuration**
```bash
sudo systemctl stop wg-agent  # If using old agent
sudo cp /opt/wg-agent/.env /opt/wg-agent/.env.backup
```

2. **Install production agent**
```bash
sudo cp -r wgdashboard-agent/* /opt/wgdashboard-agent/
cd /opt/wgdashboard-agent
sudo pip3 install -r requirements.txt
```

3. **Migrate configuration**
```bash
# Copy secret from old agent if exists
grep WG_AGENT_SECRET /opt/wg-agent/.env >> /opt/wgdashboard-agent/.env
```

4. **Update systemd service**
```bash
sudo systemctl stop wg-agent  # Stop old agent
sudo cp wgdashboard-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wgdashboard-agent
sudo systemctl start wgdashboard-agent
```

5. **Verify functionality**
```bash
sudo systemctl status wgdashboard-agent
curl http://localhost:8080/health
```

### Adding Per-Node Overrides to Existing Nodes

Database migration is automatic - just update nodes via API:

```bash
curl -X PUT http://panel/api/nodes/node-uuid \
  -H "Content-Type: application/json" \
  -d '{
    "override_mtu": 1380,
    "override_dns": "8.8.8.8"
  }'
```

## Future Enhancements

Potential improvements for future phases:

- **Scheduled drift detection** - Automatic periodic checks
- **Drift notifications** - Email/webhook alerts on drift detection
- **Drift history** - Track drift over time
- **Bulk reconciliation** - Reconcile all nodes at once
- **Reconciliation preview** - Show changes before applying
- **Advanced overrides** - More node-specific parameters
- **Agent clustering** - Multi-agent high availability
- **Configuration templates** - Reusable node configurations

## Conclusion

Phase 4 delivers critical operational features for production WireGuard deployments:

✅ **Drift Detection** - Identify configuration inconsistencies  
✅ **Reconciliation** - Automated drift resolution  
✅ **Per-Node Overrides** - Flexible node configuration  
✅ **Production Agent** - Robust, enterprise-ready agent  

These features enable reliable, scalable multi-node WireGuard management with confidence in configuration correctness and the ability to quickly detect and resolve issues.
