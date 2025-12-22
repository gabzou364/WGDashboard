# API Documentation - Phase 4 Endpoints

This document describes the new API endpoints added in Phase 4 for drift detection, reconciliation, and per-node management.

## Drift Detection Endpoints

### Get Drift Report for Node

Detect configuration drift between panel database and a specific node's actual state.

**Endpoint:** `GET /api/drift/nodes/{node_id}`

**Authentication:** Required

**Path Parameters:**
- `node_id` (string, required): UUID of the node to check

**Response:**
```json
{
  "status": true,
  "message": "Drift detection completed",
  "data": {
    "has_drift": true,
    "unknown_peers": [
      {
        "public_key": "peer_public_key_here",
        "allowed_ips": ["10.0.1.100/32"],
        "endpoint": "1.2.3.4:51820",
        "persistent_keepalive": 0
      }
    ],
    "missing_peers": [
      {
        "public_key": "peer_public_key_here",
        "name": "Peer Name",
        "allowed_ips": ["10.0.1.2/32"],
        "peer_id": "peer-uuid"
      }
    ],
    "mismatched_peers": [
      {
        "public_key": "peer_public_key_here",
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

**Error Responses:**
- `404`: Node not found
- `500`: Failed to get WireGuard dump or detect drift

**Example:**
```bash
curl -X GET http://localhost:10086/api/drift/nodes/abc-123-def \
  -H "Authorization: Bearer your-api-key"
```

---

### Get Drift Report for All Nodes

Detect configuration drift for all enabled nodes.

**Endpoint:** `GET /api/drift/nodes`

**Authentication:** Required

**Response:**
```json
{
  "status": true,
  "message": "Drift detection completed for all nodes",
  "data": {
    "nodes": {
      "node-uuid-1": {
        "has_drift": true,
        "unknown_peers": [],
        "missing_peers": [{"public_key": "...", "name": "Peer 1"}],
        "mismatched_peers": [],
        "summary": {"total_issues": 1}
      },
      "node-uuid-2": {
        "has_drift": false,
        "unknown_peers": [],
        "missing_peers": [],
        "mismatched_peers": [],
        "summary": {"total_issues": 0}
      }
    },
    "summary": {
      "total_nodes": 2,
      "nodes_with_drift": 1,
      "total_issues": 1
    }
  }
}
```

**Example:**
```bash
curl -X GET http://localhost:10086/api/drift/nodes \
  -H "Authorization: Bearer your-api-key"
```

---

## Drift Reconciliation Endpoint

### Reconcile Node Drift

Automatically fix detected drift by applying panel configuration to the node.

**Endpoint:** `POST /api/drift/nodes/{node_id}/reconcile`

**Authentication:** Required

**Path Parameters:**
- `node_id` (string, required): UUID of the node to reconcile

**Request Body:**
```json
{
  "reconcile_missing": true,
  "reconcile_mismatched": true,
  "remove_unknown": false
}
```

**Request Parameters:**
- `reconcile_missing` (boolean, default: true): Add missing peers to the node
- `reconcile_mismatched` (boolean, default: true): Update peers with mismatched configurations
- `remove_unknown` (boolean, default: false): Remove unknown peers from the node (⚠️ destructive)

**Response:**
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

**Error Response with Failures:**
```json
{
  "status": true,
  "message": "Added 1 peers, 2 errors",
  "data": {
    "added": ["peer_key_1"],
    "updated": [],
    "removed": [],
    "errors": [
      {
        "peer": "peer_key_2",
        "action": "add",
        "error": "WireGuard command failed: invalid public key"
      },
      {
        "peer": "peer_key_3",
        "action": "update",
        "error": "Connection timeout"
      }
    ]
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:10086/api/drift/nodes/abc-123-def/reconcile \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "reconcile_missing": true,
    "reconcile_mismatched": true,
    "remove_unknown": false
  }'
```

**Safety Notes:**
- **Non-destructive by default**: `remove_unknown` defaults to `false`
- **Modular**: Each peer operation is independent
- **Error isolation**: One failure doesn't stop other operations
- **Detailed reporting**: Full breakdown of actions and errors

---

## Node Management Updates

The existing node management endpoints now support per-node override fields.

### Update Node (Enhanced)

**Endpoint:** `PUT /api/nodes/{node_id}`

**New Override Fields:**
- `override_listen_port` (integer, optional): WireGuard listen port
- `override_dns` (string, optional): DNS server for peers
- `override_mtu` (integer, optional): MTU for peers
- `override_keepalive` (integer, optional): Persistent keepalive interval
- `override_endpoint_allowed_ip` (string, optional): Allowed IP ranges

**Request Body:**
```json
{
  "name": "Node 1 - US East",
  "agent_url": "http://node1.example.com:8080",
  "wg_interface": "wg0",
  "endpoint": "node1.example.com:51820",
  "ip_pool_cidr": "10.0.1.0/24",
  "enabled": true,
  "weight": 100,
  "max_peers": 100,
  "override_listen_port": 51821,
  "override_dns": "8.8.8.8",
  "override_mtu": 1380,
  "override_keepalive": 30,
  "override_endpoint_allowed_ip": "0.0.0.0/0,::/0"
}
```

**Response:**
```json
{
  "status": true,
  "message": "Node updated successfully",
  "data": {
    "id": "node-uuid",
    "name": "Node 1 - US East",
    "agent_url": "http://node1.example.com:8080",
    "wg_interface": "wg0",
    "endpoint": "node1.example.com:51820",
    "ip_pool_cidr": "10.0.1.0/24",
    "enabled": true,
    "weight": 100,
    "max_peers": 100,
    "override_listen_port": 51821,
    "override_dns": "8.8.8.8",
    "override_mtu": 1380,
    "override_keepalive": 30,
    "override_endpoint_allowed_ip": "0.0.0.0/0,::/0",
    "last_seen": "2024-01-15 10:30:00",
    "created_at": "2024-01-01 00:00:00",
    "updated_at": "2024-01-15 10:30:00"
  }
}
```

**Example:**
```bash
curl -X PUT http://localhost:10086/api/nodes/abc-123-def \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "override_mtu": 1380,
    "override_dns": "1.1.1.1"
  }'
```

---

## Agent Endpoints (New in Phase 4)

The production agent includes a new syncconf endpoint for atomic configuration updates.

### Syncconf

Apply WireGuard configuration atomically using `wg syncconf`.

**Endpoint:** `POST /v1/wg/{interface}/syncconf`

**Authentication:** HMAC signature required

**Headers:**
- `X-Signature`: HMAC-SHA256 signature
- `X-Timestamp`: Unix timestamp
- `Content-Type`: application/json

**Path Parameters:**
- `interface` (string, required): WireGuard interface name (e.g., "wg0")

**Request Body:**
```json
{
  "config": "base64-encoded-wireguard-configuration"
}
```

**Configuration Format (before base64 encoding):**
```ini
[Peer]
PublicKey = peer1_public_key_here
AllowedIPs = 10.0.1.2/32
PersistentKeepalive = 25

[Peer]
PublicKey = peer2_public_key_here
AllowedIPs = 10.0.1.3/32
PersistentKeepalive = 25
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration synchronized successfully"
}
```

**Error Response:**
```json
{
  "error": "Failed to synchronize configuration: invalid peer public key"
}
```

**Example (Python):**
```python
import base64
import hmac
import hashlib
import time
import requests

# Prepare config
config = """
[Peer]
PublicKey = peer1_key
AllowedIPs = 10.0.1.2/32

[Peer]
PublicKey = peer2_key
AllowedIPs = 10.0.1.3/32
"""

# Encode
config_b64 = base64.b64encode(config.encode()).decode()

# Build request
agent_url = "http://node:8080"
secret = "your-shared-secret"
path = "/v1/wg/wg0/syncconf"
body = f'{{"config": "{config_b64}"}}'
timestamp = str(int(time.time()))

# Sign request
message = f"POST|{path}|{body}|{timestamp}"
signature = hmac.new(
    secret.encode(),
    message.encode(),
    hashlib.sha256
).hexdigest()

# Make request
response = requests.post(
    f"{agent_url}{path}",
    headers={
        'X-Signature': signature,
        'X-Timestamp': timestamp,
        'Content-Type': 'application/json'
    },
    json={'config': config_b64}
)

print(response.json())
```

**Benefits:**
- **Zero downtime**: Updates without interface restart
- **Atomic**: All changes applied together or none
- **Safe**: Uses WireGuard's built-in syncconf command

---

## Rate Limiting Recommendations

For production deployments, implement rate limiting:

| Endpoint | Recommended Limit |
|----------|-------------------|
| `GET /api/drift/nodes/{id}` | 10 requests/minute per node |
| `GET /api/drift/nodes` | 2 requests/minute |
| `POST /api/drift/nodes/{id}/reconcile` | 5 requests/hour per node |
| `PUT /api/nodes/{id}` | 10 requests/minute |

## Security Considerations

### Drift Detection
- **Authentication required**: All endpoints require valid session or API key
- **Read-only**: Detection doesn't modify any state
- **Audit logging**: All drift checks should be logged

### Drift Reconciliation
- **Destructive operation**: Can modify node configuration
- **Requires explicit request**: Not automatic
- **Logged operations**: All reconciliation actions logged
- **Transactional**: Each peer operation is independent

### Per-Node Overrides
- **Input validation**: Override values validated before storage
- **Audit trail**: Changes tracked via `updated_at` timestamp
- **Access control**: Same permissions as node management

### Agent Syncconf
- **HMAC authentication**: All requests must be signed
- **Timestamp validation**: Prevents replay attacks
- **Configuration validation**: Invalid configs rejected
- **Privilege required**: Agent must have WireGuard permissions

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid request (malformed JSON, invalid parameters) |
| 401 | Unauthorized (missing or invalid authentication) |
| 404 | Not found (node doesn't exist) |
| 500 | Internal server error (agent unavailable, WireGuard error) |

## Changelog

### Phase 4 (2024)
- Added drift detection endpoints
- Added drift reconciliation endpoint
- Added per-node override fields to node management
- Added syncconf endpoint to production agent

### Phase 2 (2024)
- Added node selection for peer creation
- Added IP allocation management
- Added load balancing

### Phase 1 (2024)
- Initial multi-node architecture
- Node CRUD operations
- Agent health monitoring
