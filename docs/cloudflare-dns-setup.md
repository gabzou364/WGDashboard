# Cloudflare DNS-Only Cluster Setup Guide

Complete guide for setting up WireGuard cluster endpoints using Cloudflare DNS (DNS-only mode, no proxy).

## Table of Contents

1. [Overview](#overview)
2. [DNS-Only Requirement](#dns-only-requirement)
3. [Prerequisites](#prerequisites)
4. [Cloudflare API Token Setup](#cloudflare-api-token-setup)
5. [Panel Configuration](#panel-configuration)
6. [Endpoint Group Creation](#endpoint-group-creation)
7. [TTL Recommendations](#ttl-recommendations)
8. [Troubleshooting](#troubleshooting)

---

## Overview

### What is Cluster Mode?

Cluster mode (Mode A) allows multiple WireGuard nodes to serve the same configuration using a single domain endpoint. Clients connect to one domain (e.g., `vpn.example.com`), and DNS returns multiple IP addresses for load distribution.

```
Client downloads ONE config with endpoint: vpn.example.com:51820
                        ↓
              DNS query for vpn.example.com
                        ↓
        ┌───────────────┴───────────────┐
        ↓                               ↓
   192.0.2.100 (Node 1)            192.0.2.101 (Node 2)
   
Client connects to one of these IPs (sticky connection)
```

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                 Cloudflare DNS                        │
│                                                       │
│  vpn.example.com → 192.0.2.100 (A record, DNS-only)  │
│  vpn.example.com → 192.0.2.101 (A record, DNS-only)  │
│  vpn.example.com → 2001:db8::1 (AAAA, DNS-only)      │
│                                                       │
│  ⚠️  Proxied = OFF (Orange Cloud = OFF)               │
└──────────────────────────────────────────────────────┘
                        ↓
        WireGuard clients connect directly to node IPs
                        ↓
        ┌───────────────┴───────────────┐
        ↓                               ↓
   Node 1 (192.0.2.100)            Node 2 (192.0.2.101)
   WireGuard UDP :51820            WireGuard UDP :51820
```

**Key Features:**
- Single domain for all nodes
- Automatic DNS record management
- Round-robin load distribution
- Client "stickiness" (UDP connection stays with one node)
- Failover to other nodes if primary unreachable
- Low TTL for fast updates

---

## DNS-Only Requirement

### Why DNS-Only Mode is Required

**Critical:** WireGuard **REQUIRES** DNS-only mode. Cloudflare proxy mode **WILL NOT WORK**.

**Reason:** WireGuard uses **UDP protocol** which requires direct IP access. Cloudflare's proxy:
- Terminates connections at Cloudflare's edge
- Only supports HTTP/HTTPS (TCP)
- Cannot proxy UDP traffic
- Will break WireGuard connectivity completely

**Implementation:** The system automatically enforces `proxied=false` in three locations:
1. When creating endpoint groups
2. When creating DNS records
3. When updating DNS records

**Visual Indicator:**
- ✅ **DNS only** - Orange cloud OFF (correct)
- ❌ **Proxied** - Orange cloud ON (will not work)

### WireGuard Client Behavior

**Important:** WireGuard clients are "sticky" - this is not perfect load balancing:

1. **Initial Connection:**
   - Client performs DNS query
   - Receives multiple IP addresses
   - Selects one IP (typically first in list)
   - Establishes UDP connection

2. **Ongoing Connection:**
   - Client keeps using same IP
   - Connection persists until:
     - Client reconnects
     - Handshake fails
     - Keepalive timeout
   - Does NOT switch IPs during active session

3. **Failover Behavior:**
   - If handshake fails, client may try next IP
   - Behavior varies by client implementation
   - Some clients retry same IP
   - Manual reconnection may be required

**What This Means:**
- Not true "load balancing" (no active switching)
- More like "distribution at connection time"
- Good for: Spreading new connections across nodes
- Good for: Failover when node goes down
- Not good for: Real-time load balancing

**Use Case:** Best for scenarios with:
- Many clients connecting at different times
- Failover/redundancy requirements
- Geographic distribution
- Planned maintenance (remove node, clients reconnect)

---

## Prerequisites

Before starting, ensure you have:

- [ ] Domain registered and using Cloudflare nameservers
- [ ] Cloudflare account with access to domain
- [ ] WGDashboard installed and running
- [ ] At least one node registered in panel
- [ ] Node(s) assigned to a configuration
- [ ] Nodes have public IPv4 addresses (IPv6 optional)

**Verify Cloudflare DNS Management:**

1. Log into [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your domain
3. Go to **DNS** tab
4. Ensure nameservers are active (not pending)

---

## Cloudflare API Token Setup

### Step 1: Create API Token

1. Log into [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Click your profile icon (top right) → **My Profile**
3. Navigate to **API Tokens** tab
4. Click **Create Token**

### Step 2: Configure Token Permissions

**Option 1: Use Template (Recommended)**

1. Find **Edit zone DNS** template
2. Click **Use template**
3. Configure zone resources:
   - **Zone Resources**
   - **Include** → **Specific zone** → Select your domain (e.g., `example.com`)
4. Click **Continue to summary**
5. Review permissions:
   - Zone - DNS - Edit ✓
6. Click **Create Token**

**Option 2: Custom Token (Advanced)**

1. Click **Create Custom Token**
2. **Token name:** `WGDashboard DNS Management`
3. **Permissions:**
   ```
   Zone - DNS - Edit
   ```
4. **Zone Resources:**
   ```
   Include - Specific zone - example.com
   ```
5. **IP Address Filtering:** (optional but recommended)
   ```
   Is in - Your panel server IP
   ```
6. **TTL:** Set expiration (e.g., 1 year, or never)
7. Click **Continue to summary** → **Create Token**

### Step 3: Save Token

**Important:** Token is shown only once!

```
Token: 1234567890abcdefghijklmnopqrstuvwxyzABCDEFGH
```

**Securely save this token** - you'll need it for panel configuration.

### Token Security Best Practices

1. **Restrict by IP:** Limit token use to panel server IP only
2. **Use specific zone:** Don't use "All zones" permission
3. **Set expiration:** Use 1-year expiration and rotate regularly
4. **Store securely:** Use secrets management system (Vault, AWS Secrets Manager)
5. **Monitor usage:** Review API usage in Cloudflare dashboard
6. **Rotate regularly:** Update token every 90-365 days

**Test Token:**

```bash
# Replace with your token and zone ID
curl -X GET "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/dns_records" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected:** List of DNS records (200 OK)

---

## Finding Zone ID

### Method 1: Cloudflare Dashboard (Easiest)

1. Log into [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your domain
3. Scroll down on **Overview** page
4. Find **Zone ID** in right sidebar (under API section)
5. Copy the Zone ID

**Example:**
```
Zone ID: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

### Method 2: API Call

```bash
curl -X GET "https://api.cloudflare.com/client/v4/zones?name=example.com" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "result": [
    {
      "id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
      "name": "example.com",
      ...
    }
  ]
}
```

Zone ID is the `id` field.

---

## Panel Configuration

### Method 1: Via Configuration File

Edit `wg-dashboard.ini`:

```bash
sudo nano /opt/wgdashboard/wg-dashboard.ini
```

Add or update the Cloudflare section:

```ini
[Cloudflare]
api_token = YOUR_CLOUDFLARE_API_TOKEN_HERE
```

**Example:**
```ini
[Cloudflare]
api_token = 1234567890abcdefghijklmnopqrstuvwxyzABCDEFGH
```

**Restart panel:**
```bash
sudo systemctl restart wgdashboard
```

### Method 2: Via Web Interface (if available)

1. Log into WGDashboard
2. Navigate to **Settings** → **Advanced** or **Integrations**
3. Find **Cloudflare Configuration** section
4. Paste API token
5. Click **Save**

**Note:** Web interface for Cloudflare settings may not be available in all versions. Use configuration file method if not present.

### Verify Configuration

Check configuration was loaded:

```bash
# Check if token is configured
grep -A1 "\[Cloudflare\]" /opt/wgdashboard/wg-dashboard.ini

# Check panel logs for Cloudflare initialization
sudo tail -f /var/log/wgdashboard/dashboard.log | grep -i cloudflare
```

---

## Endpoint Group Creation

### Prerequisites

Before creating an endpoint group:

1. **Assign nodes to configuration:**
   ```bash
   curl -X POST http://localhost:10086/api/configs/wg0/nodes \
     -H "Content-Type: application/json" \
     -d '{"node_id": "node1"}'
   
   curl -X POST http://localhost:10086/api/configs/wg0/nodes \
     -H "Content-Type: application/json" \
     -d '{"node_id": "node2"}'
   ```

2. **Verify nodes are healthy:**
   ```bash
   curl http://localhost:10086/api/configs/wg0/nodes
   ```

### Create Endpoint Group

**API Endpoint:** `POST /api/configs/{config_name}/endpoint-group`

**Request:**

```bash
curl -X POST http://localhost:10086/api/configs/wg0/endpoint-group \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "vpn.example.com",
    "port": 51820,
    "cloudflare_zone_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "cloudflare_record_name": "vpn.example.com",
    "ttl": 60,
    "auto_migrate": true,
    "publish_only_healthy": true,
    "min_nodes": 1
  }'
```

**Parameters Explained:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain` | string | Yes | Full domain for WireGuard endpoint (e.g., `vpn.example.com`) |
| `port` | integer | Yes | WireGuard UDP port (typically 51820) |
| `cloudflare_zone_id` | string | Yes | Zone ID from Cloudflare (see above) |
| `cloudflare_record_name` | string | Yes | DNS record name (usually same as domain) |
| `ttl` | integer | No | DNS TTL in seconds (default: 60, recommended: 60-300) |
| `auto_migrate` | boolean | No | Enable automatic peer migration (default: true) |
| `publish_only_healthy` | boolean | No | Only include healthy nodes in DNS (default: true) |
| `min_nodes` | integer | No | Minimum nodes required (default: 1) |

**Response:**

```json
{
  "status": true,
  "message": "Endpoint group created successfully",
  "data": {
    "id": 1,
    "config_name": "wg0",
    "domain": "vpn.example.com",
    "port": 51820,
    "proxied": false
  }
}
```

**Note:** `proxied` is automatically set to `false` and cannot be changed.

### What Happens Next

After endpoint group creation, the system automatically:

1. ✅ Queries all nodes assigned to the configuration
2. ✅ Filters to healthy nodes (if `publish_only_healthy: true`)
3. ✅ Extracts IP addresses from node endpoints
4. ✅ Creates DNS A records for IPv4 addresses
5. ✅ Creates DNS AAAA records for IPv6 addresses (if present)
6. ✅ Sets TTL to specified value (default: 60 seconds)
7. ✅ Enforces `proxied=false` (DNS-only)
8. ✅ Creates audit log entry

**Verify DNS Records:**

1. Go to Cloudflare Dashboard → DNS
2. Look for records with name `vpn.example.com`
3. Verify:
   - Multiple A/AAAA records exist (one per node)
   - **Proxy status** is OFF (gray cloud, not orange)
   - TTL matches your configuration

**Command-line verification:**

```bash
# Query DNS records
dig vpn.example.com A
dig vpn.example.com AAAA

# Should return multiple IP addresses
```

### Update Endpoint Group

**Use same endpoint** to update settings:

```bash
curl -X POST http://localhost:10086/api/configs/wg0/endpoint-group \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "vpn.example.com",
    "port": 51820,
    "cloudflare_zone_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "cloudflare_record_name": "vpn.example.com",
    "ttl": 300,
    "auto_migrate": true,
    "publish_only_healthy": true,
    "min_nodes": 2
  }'
```

**Changes take effect immediately** and DNS records are automatically updated.

### Get Endpoint Group

**API Endpoint:** `GET /api/configs/{config_name}/endpoint-group`

```bash
curl http://localhost:10086/api/configs/wg0/endpoint-group
```

**Response:**

```json
{
  "status": true,
  "message": "Endpoint group retrieved successfully",
  "data": {
    "id": 1,
    "config_name": "wg0",
    "domain": "vpn.example.com",
    "port": 51820,
    "cloudflare_zone_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "cloudflare_record_name": "vpn.example.com",
    "ttl": 60,
    "proxied": false,
    "auto_migrate": true,
    "publish_only_healthy": true,
    "min_nodes": 1,
    "created_at": "2024-12-22T10:00:00Z",
    "updated_at": "2024-12-22T10:00:00Z"
  }
}
```

---

## TTL Recommendations

### What is TTL?

**TTL (Time To Live)** determines how long DNS resolvers cache the record before querying again.

**How it works:**
1. Client queries DNS for `vpn.example.com`
2. DNS resolver returns IP addresses with TTL=60
3. Client caches IPs for 60 seconds
4. After 60 seconds, client queries again for fresh IPs

### Recommended TTL Values

| Scenario | TTL | Reasoning |
|----------|-----|-----------|
| **Production (Recommended)** | 60-120s | Balance between freshness and DNS load |
| **Testing/Development** | 30-60s | Faster updates during testing |
| **Stable Infrastructure** | 300-600s | Lower DNS query load |
| **Frequent Changes** | 30-60s | Faster propagation of node changes |
| **Large Scale** | 120-300s | Reduce Cloudflare API calls |

### Implications of Different TTL Values

#### Low TTL (30-60 seconds)

**Advantages:**
- Faster failover when nodes go down
- Quick propagation of node additions/removals
- Clients get updated IP list more frequently

**Disadvantages:**
- Higher DNS query volume
- More Cloudflare API calls
- Potential for rate limiting
- Increased DNS resolver load

#### Medium TTL (60-300 seconds) - Recommended

**Advantages:**
- Good balance of freshness and performance
- Reasonable failover time (1-5 minutes)
- Lower API usage
- Sufficient for most use cases

**Disadvantages:**
- Slightly slower failover
- 1-5 minute delay for node changes to propagate

#### High TTL (300-600 seconds)

**Advantages:**
- Minimal DNS load
- Very low API usage
- Best for stable infrastructure

**Disadvantages:**
- Slow failover (5-10 minutes)
- Long propagation time for changes
- Clients may use stale IPs longer

### Best Practices

1. **Start with 60 seconds** - Good default for most deployments
2. **Monitor query volume** - Increase TTL if DNS queries are excessive
3. **Consider client reconnection patterns** - WireGuard clients reconnect rarely
4. **Plan for failures** - Lower TTL = faster failover
5. **Test before going live** - Verify clients handle multiple IPs correctly

**Formula:**
```
TTL = (Average time between client reconnections) / 4
```

**Example:**
- Clients reconnect every 4 hours on average
- TTL = (4 hours × 3600 seconds) / 4 = 3600 seconds (1 hour)
- **Recommendation:** Use 300-600 seconds for this scenario

### Changing TTL

**Update endpoint group with new TTL:**

```bash
curl -X POST http://localhost:10086/api/configs/wg0/endpoint-group \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "vpn.example.com",
    "port": 51820,
    "cloudflare_zone_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "cloudflare_record_name": "vpn.example.com",
    "ttl": 120
  }'
```

**Note:** Old TTL will still apply to cached records until they expire. Full propagation takes: `old_ttl + new_ttl` seconds.

---

## Troubleshooting

### DNS Records Not Created

**Symptom:** No DNS records appear in Cloudflare after creating endpoint group

**Troubleshooting:**

1. **Check API token permissions:**
   ```bash
   curl -X GET "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/dns_records" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
   
   **Expected:** 200 OK with record list
   **If fails:** Token lacks permissions or is invalid

2. **Verify zone ID:**
   ```bash
   curl -X GET "https://api.cloudflare.com/client/v4/zones" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
   
   Ensure your zone ID matches the domain.

3. **Check panel logs:**
   ```bash
   sudo tail -f /var/log/wgdashboard/dashboard.log | grep -i cloudflare
   ```
   
   Look for API errors:
   - `Authentication error` - Invalid token
   - `Zone not found` - Wrong zone ID
   - `Permission denied` - Token lacks DNS edit permission

4. **Check nodes have valid IPs:**
   ```bash
   curl http://localhost:10086/api/configs/wg0/nodes
   ```
   
   Verify each node has valid endpoint with IP address.

5. **Manually test API:**
   ```bash
   curl -X POST "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/dns_records" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "type": "A",
       "name": "vpn.example.com",
       "content": "192.0.2.100",
       "ttl": 60,
       "proxied": false
     }'
   ```

**Common Causes:**
- Invalid or expired API token
- Incorrect zone ID
- Token lacks DNS edit permission
- Domain not active on Cloudflare
- Rate limiting (see below)

### DNS Records Created but Proxied

**Symptom:** DNS records exist but orange cloud is ON (proxied)

**This should NOT happen** - system enforces `proxied=false` in 3 places.

**If it does happen:**

1. **Manually disable proxy in Cloudflare:**
   - Go to Cloudflare Dashboard → DNS
   - Find the record
   - Click orange cloud icon to turn it OFF (gray cloud)

2. **Report as bug:**
   - This indicates a code defect
   - Check system logs for errors
   - Contact WGDashboard support

3. **Verify enforcement in code:**
   ```bash
   grep -r "proxied.*false" /opt/wgdashboard/src/modules/
   ```
   
   Should show enforcements in:
   - `EndpointGroupsManager.py`
   - `CloudflareDNSManager.py`

### Rate Limit Errors

**Symptom:** DNS updates fail with rate limit errors

**Cloudflare Rate Limits:**
- Free plan: ~1200 requests/5 minutes
- Pro plan: ~6000 requests/5 minutes
- Business+: Higher limits

**Troubleshooting:**

1. **Check retry queue:**
   ```bash
   curl http://localhost:10086/api/cloudflare/retry-queue
   ```
   
   If queue is growing, rate limiting is occurring.

2. **Increase TTL:**
   - Higher TTL = fewer DNS updates needed
   - Update endpoint group with TTL 300-600

3. **Check update frequency:**
   ```bash
   sudo journalctl -u wgdashboard | grep "DNS update"
   ```
   
   If updates are too frequent, adjust health check intervals.

4. **Review audit logs:**
   ```bash
   curl "http://localhost:10086/api/audit-logs?action=dns_updated&limit=50"
   ```
   
   Identify what's triggering excessive updates.

5. **Implement debouncing:**
   - System includes debouncing mechanism
   - Batches multiple changes within 30-second window
   - Prevents rapid-fire updates

**Solution:**
- Wait for rate limit to reset (5 minutes)
- System will automatically retry queued operations
- Consider upgrading Cloudflare plan for higher limits

### Retry Queue Growing

**Symptom:** Failed DNS operations accumulating in retry queue

**Check queue size:**

System logs show retry queue activity:
```bash
sudo journalctl -u wgdashboard | grep "retry queue"
```

**Causes:**

1. **Cloudflare API unavailable:**
   - Check Cloudflare status: https://www.cloudflarestatus.com/
   - Wait for service restoration

2. **Network connectivity issues:**
   ```bash
   # Test from panel server
   ping -c 4 api.cloudflare.com
   curl -I https://api.cloudflare.com
   ```

3. **Expired or invalid token:**
   - Check token in Cloudflare dashboard
   - Regenerate if expired
   - Update panel configuration

4. **Rate limiting:**
   - See rate limit troubleshooting above

**Resolution:**

System automatically retries failed operations:
- Every 30 seconds
- Maximum 5 attempts
- After 5 failures, operation is dropped and logged

**Manual intervention:**
```bash
# Restart panel to clear queue and retry
sudo systemctl restart wgdashboard

# Or manually sync DNS
curl -X POST http://localhost:10086/api/configs/wg0/endpoint-group/sync-dns
```

### Missing or Incorrect DNS Records

**Symptom:** Some node IPs not in DNS, or wrong IPs listed

**Troubleshooting:**

1. **Check node health status:**
   ```bash
   curl http://localhost:10086/api/configs/wg0/nodes
   ```
   
   If `publish_only_healthy: true`, unhealthy nodes are excluded.

2. **Verify node endpoints:**
   ```bash
   curl http://localhost:10086/api/nodes
   ```
   
   Ensure each node has valid endpoint with correct IP.

3. **Check DNS record in Cloudflare:**
   ```bash
   curl -X GET "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records?name=vpn.example.com" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

4. **Force DNS sync:**
   ```bash
   # Remove and re-add node to trigger DNS update
   curl -X DELETE http://localhost:10086/api/configs/wg0/nodes/node1
   curl -X POST http://localhost:10086/api/configs/wg0/nodes \
     -d '{"node_id": "node1"}'
   ```

5. **Manual DNS cleanup:**
   - Go to Cloudflare Dashboard → DNS
   - Delete stale records
   - Update endpoint group to recreate

### Clients Not Connecting

**Symptom:** Clients can't establish WireGuard connection

**Troubleshooting:**

1. **Verify DNS resolution:**
   ```bash
   dig vpn.example.com A
   nslookup vpn.example.com
   ```
   
   Should return multiple IP addresses.

2. **Check proxy status:**
   - Go to Cloudflare Dashboard → DNS
   - **Ensure orange cloud is OFF** (gray cloud = DNS only)
   - If orange, turn off and wait for TTL to expire

3. **Test direct IP connection:**
   - Get IP from DNS query
   - Update client config temporarily with IP instead of domain
   - If works with IP but not domain, DNS issue
   - If doesn't work with IP, WireGuard issue

4. **Verify WireGuard port accessible:**
   ```bash
   nc -zvu NODE_IP 51820
   ```

5. **Check client logs:**
   ```bash
   # Linux
   sudo wg show
   sudo journalctl -u wg-quick@wg0
   
   # macOS (WireGuard app)
   # View logs in app interface
   
   # Windows (WireGuard app)
   # View logs in app interface
   ```

6. **Common client errors:**
   - `handshake did not complete` - Firewall or proxy blocking
   - `endpoint unreachable` - DNS or routing issue
   - `invalid public key` - Key mismatch

### Stale Records Not Cleaning Up

**Symptom:** Old node IPs remain in DNS after node removal

**The system automatically cleans up stale records** during DNS sync.

**Manual cleanup:**

1. **List all DNS records:**
   ```bash
   curl -X GET "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records?name=vpn.example.com" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

2. **Delete specific record:**
   ```bash
   curl -X DELETE "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records/RECORD_ID" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Force full DNS sync:**
   ```bash
   # Update endpoint group (triggers full sync)
   curl -X POST http://localhost:10086/api/configs/wg0/endpoint-group \
     -H "Content-Type: application/json" \
     -d '{ ... existing settings ... }'
   ```

---

## Additional Resources

- [Node Setup Guide](node-setup.md)
- [Multi-Node Architecture](MULTI_NODE_ARCHITECTURE.md)
- [Phase 8 Implementation Summary](../PHASE8_IMPLEMENTATION_SUMMARY.md)
- [Cloudflare API Documentation](https://developers.cloudflare.com/api/)
- [WireGuard Official Documentation](https://www.wireguard.com/quickstart/)

---

## Quick Reference

### Create Endpoint Group

```bash
curl -X POST http://localhost:10086/api/configs/wg0/endpoint-group \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "vpn.example.com",
    "port": 51820,
    "cloudflare_zone_id": "YOUR_ZONE_ID",
    "cloudflare_record_name": "vpn.example.com",
    "ttl": 60
  }'
```

### Get Endpoint Group

```bash
curl http://localhost:10086/api/configs/wg0/endpoint-group
```

### Test Cloudflare Token

```bash
curl -X GET "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/dns_records" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Query DNS Records

```bash
dig vpn.example.com A
dig vpn.example.com AAAA
```

### Check Audit Logs

```bash
curl "http://localhost:10086/api/audit-logs?action=dns_updated"
```

---

## Checklist

Before going live with Cloudflare DNS cluster:

- [ ] Domain using Cloudflare nameservers
- [ ] Cloudflare API token created with DNS edit permissions
- [ ] Zone ID identified and saved
- [ ] API token configured in panel (`wg-dashboard.ini`)
- [ ] Multiple nodes registered and healthy
- [ ] Nodes assigned to configuration
- [ ] Endpoint group created successfully
- [ ] DNS records visible in Cloudflare dashboard
- [ ] **Orange cloud is OFF (DNS-only mode)**
- [ ] DNS query returns multiple IPs
- [ ] TTL set to appropriate value (60-300 seconds)
- [ ] Test client can connect successfully
- [ ] Monitor panel logs for DNS errors
- [ ] Audit logs show DNS updates

---

*Last updated: December 2024 | Phase 9 Documentation*
