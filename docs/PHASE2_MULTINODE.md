# Phase 2: Multi-Node Peer Management

This document describes the Phase 2 multi-node features that enable functional peer management across multiple nodes.

## Features

### 1. Node Selection & Load Balancing

When creating a peer, you can now select which node should host it:

- **Auto (Load Balanced)**: Automatically selects the best available node based on current load
- **Specific Node**: Manually select a specific node
- **Local**: Create the peer on the local dashboard server (legacy mode)

#### Auto Selection Algorithm

The auto-selection algorithm considers:

1. **Only enabled nodes**: Disabled nodes are excluded
2. **Capacity limits**: Nodes at or over `max_peers` cap are skipped
3. **Load score**: Calculated as `(active_peers / max_peers) / weight`
   - Lower score = better candidate
   - For unlimited capacity (max_peers=0), uses `active_peers / weight`
4. **Graceful fallback**: If no nodes are configured, falls back to local mode

**Example Scenario:**
```
Node A: 50/100 peers, weight=100 → score = 0.5/100 = 0.005
Node B: 25/100 peers, weight=100 → score = 0.25/100 = 0.0025 ✓ Selected
Node C: 48/50 peers, weight=100  → score = 0.96/100 = 0.0096
```

### 2. IP Address Allocation Management (IPAM)

Each node has its own IP pool defined by `ip_pool_cidr`. The IPAM system:

- **Reserves first usable IP** (typically `.1`) for the server/gateway
- **Allocates unique IPs** within the node's pool for each peer
- **Enforces uniqueness** via database constraints
- **Handles conflicts** with retry logic (up to 3 attempts)
- **Tracks allocations** in the `IPAllocations` table

**Example:**
```
Node pool: 10.0.1.0/24
Reserved: 10.0.1.1/24 (server)
Available: 10.0.1.2/24 to 10.0.1.254/24
First allocation: 10.0.1.2/24
Second allocation: 10.0.1.3/24
...
```

### 3. Peer Lifecycle via Agent

When a peer is created on a remote node:

1. **IP Allocation**: IPAM allocates an IP from the node's pool
2. **Agent Call**: Controller calls node agent to create the peer
3. **Database Record**: Peer is stored with `node_id` and `iface` fields
4. **Rollback on Failure**: If agent call fails, IP allocation is rolled back

When a peer is deleted from a remote node:

1. **Agent Call**: Controller calls node agent to delete the peer
2. **IP Deallocation**: IPAM releases the IP back to the pool
3. **Database Cleanup**: Peer record is removed

**Peer Data Stored:**
- Standard peer fields (name, keys, DNS, etc.)
- `node_id`: Which node hosts this peer
- `iface`: Interface name on the node (e.g., `wg0`)
- `handshake_obs`, `rx_obs`, `tx_obs`: Observed statistics from node

### 4. User Interface Changes

#### Peer Creation
- New **Node Selection** dropdown with three options:
  - Auto (Load Balanced)
  - Local (This Server)
  - [List of enabled nodes]
- IP address field is optional when using node selection (auto-allocated)
- Clear messaging when no nodes are configured

#### Peer Display
- Peer cards now show which node they're hosted on
- Node badge displayed with node ID
- Icon indicator for remote vs local peers

## API Endpoints

### Get Enabled Nodes
```http
GET /api/nodes/enabled
```

Returns list of enabled nodes for peer creation dropdown.

**Response:**
```json
{
  "status": true,
  "data": [
    {
      "id": "node-uuid",
      "name": "Node 1",
      "enabled": true,
      "endpoint": "vpn1.example.com:51820",
      "wg_interface": "wg0",
      "ip_pool_cidr": "10.0.1.0/24",
      "max_peers": 100,
      "weight": 100
    }
  ]
}
```

### Create Peer with Node Selection
```http
POST /api/addPeers/{configName}
Content-Type: application/json

{
  "name": "My Peer",
  "node_selection": "auto",  // or node_id, or empty for local
  "private_key": "...",
  "public_key": "...",
  "DNS": "1.1.1.1",
  "endpoint_allowed_ip": "0.0.0.0/0",
  "keepalive": 25,
  "mtu": 1420,
  "preshared_key": ""
}
```

**Note:** When `node_selection` is set to "auto" or a specific node ID, the `allowed_ips` field is optional (will be auto-allocated).

## Database Schema

### IPAllocations Table
```sql
CREATE TABLE IPAllocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id VARCHAR(255) NOT NULL,
  peer_id VARCHAR(255) NOT NULL,
  ip_address VARCHAR(50) NOT NULL,
  allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(node_id, ip_address)
);
```

### Peers Table Extensions
Existing peer tables now include:
- `node_id VARCHAR(255)` - NULL for local peers, node ID for remote peers
- `iface VARCHAR(50)` - Interface name on the node
- `handshake_obs VARCHAR(255)` - Observed handshake timestamp
- `rx_obs FLOAT` - Observed RX bytes
- `tx_obs FLOAT` - Observed TX bytes

## Backward Compatibility

**Zero Breaking Changes:**
- Existing single-node deployments continue to work without any nodes configured
- API endpoints accept `node_selection` as optional parameter
- When `node_selection` is empty/null, behaves exactly as before (local mode)
- Peers without `node_id` are managed locally as before
- UI gracefully handles absence of nodes

## Usage Examples

### Example 1: First Remote Peer

1. Add a node in the Nodes management page
2. Navigate to a configuration and click "Add Peers"
3. Select "Auto (Load Balanced)" from Node Selection dropdown
4. Fill in peer name and other settings
5. Click Add - IP will be auto-allocated from node's pool

### Example 2: Manual Node Selection

1. In peer creation, select specific node from dropdown
2. System will use that node regardless of load
3. Useful for testing or specific routing requirements

### Example 3: Load Balancing

With multiple nodes configured:
```
Node A: 30/100 peers, weight=100
Node B: 60/100 peers, weight=150
Node C: 20/50 peers, weight=100

Auto-selection will pick Node A (lowest score)
```

## Troubleshooting

### "No available IPs in node's pool"
- Check node's `ip_pool_cidr` configuration
- Verify IP pool is large enough for expected peer count
- Check for IP allocation leaks in database

### "Failed to add peer to node"
- Verify node agent is running
- Check agent URL is correct
- Verify shared secret matches
- Review agent logs for errors

### "Node at capacity"
- Node has reached `max_peers` limit
- Use different node or increase `max_peers`
- Auto-selection will skip full nodes

### Peer shows on wrong node
- Only happens if manually moved in database
- Delete and recreate peer to fix
- Check node health and connectivity

## Security Considerations

1. **HMAC Authentication**: All agent communication is authenticated
2. **IP Uniqueness**: Database constraints prevent IP conflicts
3. **Transactional Safety**: Failed operations roll back changes
4. **Input Validation**: All inputs validated before agent calls

## Performance

- **IP Allocation**: O(n) where n = allocated IPs in node
- **Node Selection**: O(m) where m = enabled nodes
- **Agent Calls**: Network latency dependent
- **Rollback**: Atomic database transactions

## Testing

Run Phase 2 tests:
```bash
python3 test_phase2_multinode.py
```

Tests cover:
- Node selection scoring algorithm
- IP allocation boundaries (first host reservation)
- IP pool exhaustion handling
- Agent communication mocking
- Backward compatibility

All tests should pass (6/6).
