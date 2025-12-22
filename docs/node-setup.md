# Node Setup Guide

Complete guide for setting up WGDashboard nodes including panel-side configuration and node server deployment.

## Table of Contents

1. [Prerequisites and Network Topology](#prerequisites-and-network-topology)
2. [Panel-Side Setup](#panel-side-setup)
3. [Node Server Setup](#node-server-setup)
4. [Firewall and Security](#firewall-and-security)
5. [Verification Steps](#verification-steps)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites and Network Topology

### Network Topology Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     WGDashboard Panel                        │
│  (Controller - Web UI + API)                                 │
│  • Web Interface: Port 10086 (configurable)                  │
│  • Manages all nodes via agent API                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
    ┌────────┐     ┌────────┐     ┌────────┐
    │ Node 1 │     │ Node 2 │     │ Node 3 │
    │        │     │        │     │        │
    │ Agent  │     │ Agent  │     │ Agent  │
    │ :8080  │     │ :8080  │     │ :8080  │
    │        │     │        │     │        │
    │ WG UDP │     │ WG UDP │     │ WG UDP │
    │ :51820 │     │ :51820 │     │ :51820 │
    └────────┘     └────────┘     └────────┘
```

### Required Ports

**Panel Server:**
- **10086/TCP** (default) - Web interface and API
- **8080/TCP** - Agent API (if panel is also a node)
- **51820/UDP** (or custom) - WireGuard UDP traffic (if panel is also a node)

**Node Servers:**
- **8080/TCP** (default) - Agent API (must be accessible from panel)
- **51820/UDP** (or custom) - WireGuard UDP traffic (must be publicly accessible)

### Prerequisites

**Panel Server:**
- WGDashboard installed and running
- Network access to all node servers (TCP 8080)
- Python 3.7+
- PostgreSQL or SQLite database

**Node Servers:**
- Linux server (Ubuntu 20.04+, Debian 10+, CentOS 8+, etc.)
- WireGuard installed (`wg` and `wg-quick` commands available)
- Python 3.7+ (for systemd deployment) or Docker (for container deployment)
- Root or sudo access
- Public IP address or domain name
- Network access from panel server

---

## Panel-Side Setup

### Step 1: Understanding Panel Node vs Remote Node

**Panel Node (is_panel_node=true):**
- The panel server itself runs WireGuard
- Uses local WireGuard commands instead of agent API
- Ideal for small deployments or testing
- Set `is_panel_node=true` when creating the node

**Remote Node (is_panel_node=false):**
- Separate server running the agent
- Panel communicates via agent API over HTTP
- Required for multi-node architecture
- Set `is_panel_node=false` (default)

### Step 2: Generate Shared Secret

Each node requires a shared secret for HMAC authentication:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Example output:**
```
Xg7kP2mN9qR4tY6wZ8xC1vB5nM3jK0lH7fG2dS4aQ9eU8iO6pL3mK1
```

Save this secret securely - you'll need it for both node configuration and panel registration.

### Step 3: Register Node in Panel

#### Via Web Interface

1. Navigate to **Settings** → **Nodes** in WGDashboard
2. Click **Add Node**
3. Fill in the form:

**Required Fields:**
- **Node ID**: Unique identifier (e.g., `node-us-east-1`, `node-eu-west-1`)
- **Node Name**: Human-readable name (e.g., "US East 1", "Europe West 1")
- **Agent URL**: Full URL to agent API (e.g., `http://192.0.2.100:8080`)
- **Agent Secret**: The shared secret generated above
- **WireGuard Interface**: Interface name on the node (e.g., `wg0`)
- **Endpoint**: Public IP/domain and port (e.g., `vpn.example.com:51820`)
- **Is Panel Node**: Check if this is the panel server itself

**Optional Fields:**
- **Enabled**: Enable/disable the node (default: enabled)
- **Weight**: Load balancing weight (higher = more peers, default: 1)
- **IP Pool CIDR**: IP address pool for this node (e.g., `10.0.1.0/24`)

4. Click **Test Connection** to verify connectivity
5. Click **Create** to save the node

#### Via API (Alternative)

```bash
curl -X POST http://localhost:10086/api/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "id": "node-us-east-1",
    "name": "US East 1",
    "agent_url": "http://192.0.2.100:8080",
    "agent_secret": "Xg7kP2mN9qR4tY6wZ8xC1vB5nM3jK0lH7fG2dS4aQ9eU8iO6pL3mK1",
    "interface": "wg0",
    "endpoint": "vpn.example.com:51820",
    "is_panel_node": false,
    "enabled": true,
    "weight": 1,
    "ip_pool_cidr": "10.0.1.0/24"
  }'
```

### Step 4: Assign Node to Configuration

After registering a node, assign it to one or more WireGuard configurations.

#### Assign Node to Config via API

```bash
# Assign node1 to wg0 configuration
curl -X POST http://localhost:10086/api/configs/wg0/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-us-east-1"
  }'
```

**Response:**
```json
{
  "status": true,
  "message": "Node assigned to configuration successfully"
}
```

#### List Nodes for Configuration

```bash
# Get all nodes assigned to wg0
curl http://localhost:10086/api/configs/wg0/nodes
```

**Response:**
```json
{
  "status": true,
  "message": "Nodes retrieved successfully",
  "data": [
    {
      "id": "node-us-east-1",
      "name": "US East 1",
      "endpoint": "vpn.example.com:51820",
      "is_healthy": true,
      "config_node_id": 1,
      "enabled": true,
      "weight": 1
    }
  ]
}
```

#### Remove Node from Configuration (Triggers Migration)

**Warning:** This will migrate all peers from the removed node to other healthy nodes.

```bash
# Remove node from configuration
curl -X DELETE http://localhost:10086/api/configs/wg0/nodes/node-us-east-1
```

**Response:**
```json
{
  "status": true,
  "message": "Node removed successfully",
  "data": {
    "peers_migrated": 15
  }
}
```

**What happens during removal:**
1. Panel backs up the interface configuration
2. All peers are migrated to other healthy nodes
3. Node assignment is removed from database
4. Interface is deleted on the node (via agent API)
5. DNS records are updated (if Cloudflare is configured)
6. Audit log entry is created

### Step 5: Enable Panel as a Node (Optional)

If you want the panel server to also serve peers:

1. Install WireGuard on the panel server
2. Create a WireGuard interface (e.g., `wg0`)
3. Register the panel as a node with `is_panel_node=true`

```bash
curl -X POST http://localhost:10086/api/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "id": "panel-node",
    "name": "Panel Node",
    "agent_url": "http://localhost:8080",
    "agent_secret": "not-used-for-panel-node",
    "interface": "wg0",
    "endpoint": "panel.example.com:51820",
    "is_panel_node": true,
    "enabled": true
  }'
```

**Note:** For panel nodes, the agent API is not used. Panel executes WireGuard commands locally.

### Validation Checklist

Before proceeding to node deployment, verify:

- [ ] Node is registered in panel
- [ ] Shared secret is saved securely
- [ ] Node is assigned to at least one configuration
- [ ] Test connection succeeded (green status)
- [ ] Endpoint is publicly accessible
- [ ] Agent port (8080) is reachable from panel

---

## Node Server Setup

Deploy the WireGuard node agent using either Docker (recommended) or systemd.

### A) Docker Deployment

Docker deployment is recommended for production as it provides isolation, easy updates, and consistent environments.

#### Prerequisites

- Docker installed (`docker --version`)
- Docker Compose installed (optional, for easier management)

#### Option 1: Docker Run Command

```bash
# Generate secret first
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Generated secret: $SECRET"
echo "Save this secret for panel registration!"

# Run agent container
docker run -d \
  --name wgdashboard-agent \
  --restart unless-stopped \
  --cap-add NET_ADMIN \
  --cap-add SYS_MODULE \
  --sysctl net.ipv4.ip_forward=1 \
  --sysctl net.ipv4.conf.all.src_valid_mark=1 \
  -v /etc/wireguard:/etc/wireguard \
  -v /lib/modules:/lib/modules:ro \
  -e WG_AGENT_SECRET="$SECRET" \
  -e WG_AGENT_PORT=8080 \
  -e WG_AGENT_LOG_LEVEL=INFO \
  -p 8080:8080 \
  -p 51820:51820/udp \
  donaldzou/wgdashboard-agent:latest
```

**Explanation:**
- `--cap-add NET_ADMIN` - Required for WireGuard interface management
- `--cap-add SYS_MODULE` - Required for loading WireGuard kernel module
- `--sysctl net.ipv4.ip_forward=1` - Enable IP forwarding
- `-v /etc/wireguard:/etc/wireguard` - Mount WireGuard config directory
- `-v /lib/modules:/lib/modules:ro` - Mount kernel modules (read-only)
- `-p 8080:8080` - Expose agent API port
- `-p 51820:51820/udp` - Expose WireGuard port (adjust if different)

#### Option 2: Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  wgdashboard-agent:
    image: donaldzou/wgdashboard-agent:latest
    container_name: wgdashboard-agent
    restart: unless-stopped
    
    # Required Linux capabilities
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    
    # System configuration
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
    
    # Environment variables
    environment:
      - WG_AGENT_SECRET=${WG_AGENT_SECRET}
      - WG_AGENT_PORT=8080
      - WG_AGENT_HOST=0.0.0.0
      - WG_AGENT_LOG_LEVEL=INFO
      - MAX_TIMESTAMP_AGE=300
    
    # Volume mounts
    volumes:
      - /etc/wireguard:/etc/wireguard
      - /lib/modules:/lib/modules:ro
    
    # Port mappings
    ports:
      - "8080:8080"
      - "51820:51820/udp"
    
    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

Create `.env` file:

```bash
# Generate and save secret
WG_AGENT_SECRET=Xg7kP2mN9qR4tY6wZ8xC1vB5nM3jK0lH7fG2dS4aQ9eU8iO6pL3mK1
```

**Deploy:**

```bash
# Start agent
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Stop agent
docker-compose down
```

#### Docker Security Notes

**DO NOT use `--privileged` mode** unless absolutely necessary. The `NET_ADMIN` and `SYS_MODULE` capabilities are sufficient for WireGuard operations.

If you must use privileged mode:
```bash
docker run -d --privileged ...
```

**Best practices:**
- Use specific capability grants instead of privileged mode
- Run container with read-only root filesystem when possible
- Limit resource usage with `--memory` and `--cpus` flags
- Use Docker secrets for production deployments

### B) Systemd Deployment

Systemd deployment runs the agent as a native system service.

#### Step 1: Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip wireguard-tools

# Install Python dependencies
sudo pip3 install fastapi uvicorn pydantic python-dotenv requests
```

**CentOS/RHEL:**
```bash
sudo yum install -y python3 python3-pip wireguard-tools

# Install Python dependencies
sudo pip3 install fastapi uvicorn pydantic python-dotenv requests
```

#### Step 2: Install Agent Files

```bash
# Create directory
sudo mkdir -p /opt/wgdashboard-agent
cd /opt/wgdashboard-agent

# Download agent files (adjust URL to match your setup)
sudo wget https://raw.githubusercontent.com/donaldzou/WGDashboard/main/wgdashboard-agent/app.py
sudo wget https://raw.githubusercontent.com/donaldzou/WGDashboard/main/wgdashboard-agent/requirements.txt

# Or copy from cloned repository
# sudo cp -r /path/to/WGDashboard/wgdashboard-agent/* /opt/wgdashboard-agent/

# Install requirements
sudo pip3 install -r requirements.txt
```

#### Step 3: Configure Environment

```bash
# Generate secret
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create .env file
sudo tee /opt/wgdashboard-agent/.env > /dev/null <<EOF
WG_AGENT_SECRET=$SECRET
WG_AGENT_PORT=8080
WG_AGENT_HOST=0.0.0.0
WG_AGENT_LOG_LEVEL=INFO
MAX_TIMESTAMP_AGE=300
EOF

# Secure the file
sudo chmod 600 /opt/wgdashboard-agent/.env

echo "Generated secret: $SECRET"
echo "Save this for panel registration!"
```

#### Step 4: Create Systemd Service

Create `/etc/systemd/system/wgdashboard-agent.service`:

```ini
[Unit]
Description=WGDashboard Node Agent
After=network-online.target wg-quick.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wgdashboard-agent
EnvironmentFile=/opt/wgdashboard-agent/.env

# Main service command
ExecStart=/usr/bin/python3 -m uvicorn app:app \
    --host ${WG_AGENT_HOST} \
    --port ${WG_AGENT_PORT} \
    --log-level info

# Restart policy
Restart=always
RestartSec=10s

# Security hardening (optional but recommended)
NoNewPrivileges=false
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/wireguard
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wgdashboard-agent

[Install]
WantedBy=multi-user.target
```

#### Step 5: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable wgdashboard-agent

# Start service
sudo systemctl start wgdashboard-agent

# Check status
sudo systemctl status wgdashboard-agent

# View logs
sudo journalctl -u wgdashboard-agent -f
```

#### Systemd Management Commands

```bash
# Stop service
sudo systemctl stop wgdashboard-agent

# Restart service
sudo systemctl restart wgdashboard-agent

# Disable service (prevent auto-start)
sudo systemctl disable wgdashboard-agent

# View recent logs
sudo journalctl -u wgdashboard-agent -n 100

# Follow logs in real-time
sudo journalctl -u wgdashboard-agent -f
```

#### Running as Root Safely

The agent **must run as root** to manage WireGuard interfaces. Security considerations:

**Why root is required:**
- WireGuard interface creation/deletion requires root
- Network configuration changes require root
- iptables rules (PostUp/PreDown) require root

**Security best practices:**
1. **Restrict agent port access** - Use firewall to allow only panel IP
2. **Use strong secrets** - Generate with `secrets.token_urlsafe(32)`
3. **Enable audit logging** - Monitor agent access via panel logs
4. **Keep software updated** - Regularly update agent and dependencies
5. **Limit network exposure** - Don't expose agent port publicly
6. **Use TLS/reverse proxy** - Consider nginx with TLS for production

---

## Firewall and Security

### Node Server Firewall Rules

**Allow agent API from panel only:**

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow from PANEL_IP to any port 8080 proto tcp
sudo ufw allow 51820/udp  # WireGuard port (adjust if different)

# iptables (all distributions)
sudo iptables -A INPUT -p tcp -s PANEL_IP --dport 8080 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j DROP
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

**Example:**
```bash
# Panel IP: 203.0.113.50
# WireGuard port: 51820
sudo ufw allow from 203.0.113.50 to any port 8080 proto tcp
sudo ufw allow 51820/udp
sudo ufw enable
```

### TLS/Reverse Proxy (Optional but Recommended)

For production deployments, consider using nginx as a reverse proxy with TLS:

**nginx configuration:**

```nginx
server {
    listen 443 ssl http2;
    server_name agent.example.com;
    
    ssl_certificate /etc/ssl/certs/agent.crt;
    ssl_certificate_key /etc/ssl/private/agent.key;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    
    # Restrict to panel IP
    allow 203.0.113.50;
    deny all;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Update agent URL in panel to: `https://agent.example.com`

### Secret Management Best Practices

1. **Generate strong secrets:**
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Store securely:**
   - Use environment files with restricted permissions (600)
   - Consider secrets management tools (Vault, AWS Secrets Manager)
   - Never commit secrets to version control

3. **Rotate regularly:**
   - Update secrets every 90 days
   - Update both node and panel configurations
   - Test connectivity after rotation

4. **Monitor access:**
   - Review panel audit logs regularly
   - Monitor failed authentication attempts
   - Set up alerts for suspicious activity

---

## Verification Steps

### 1. Verify Agent is Running

**Docker:**
```bash
docker ps | grep wgdashboard-agent
docker logs wgdashboard-agent --tail 50
```

**Systemd:**
```bash
sudo systemctl status wgdashboard-agent
sudo ss -tlnp | grep 8080
```

### 2. Test Agent Health Endpoint

```bash
# From node server
curl http://localhost:8080/health

# Expected response:
{"status": "ok"}
```

### 3. Test HMAC Authentication

Create test script `test_agent.py`:

```python
#!/usr/bin/env python3
import hmac
import hashlib
import time
import requests
import sys

AGENT_URL = "http://localhost:8080"
SECRET = "your-secret-here"  # Replace with your secret

def make_signed_request(method, path, body=""):
    timestamp = str(int(time.time()))
    message = f"{method}|{path}|{body}|{timestamp}"
    signature = hmac.new(
        SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'X-Signature': signature,
        'X-Timestamp': timestamp,
        'Content-Type': 'application/json'
    }
    
    url = f"{AGENT_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            resp = requests.post(url, headers=headers, data=body)
        
        print(f"{method} {path}")
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

# Test status endpoint
if not make_signed_request("GET", "/v1/status"):
    sys.exit(1)

print("✓ Agent authentication working!")
```

Run test:
```bash
chmod +x test_agent.py
python3 test_agent.py
```

### 4. Test from Panel Server

```bash
# Replace with your panel IP and node agent IP
PANEL_IP="203.0.113.50"
NODE_IP="192.0.2.100"

# SSH to panel server and test
ssh user@$PANEL_IP
curl http://$NODE_IP:8080/health
```

### 5. Validate WireGuard Configuration

```bash
# Check WireGuard is installed
wg version

# Check interface status
sudo wg show

# Check interface configuration
sudo cat /etc/wireguard/wg0.conf
```

### 6. Verify Panel Connectivity

1. Log into WGDashboard panel
2. Navigate to **Settings** → **Nodes**
3. Find your node and click **Test Connection**
4. Should show green status with response time

### 7. Test Peer Creation

Create a test peer through the panel:

1. Navigate to **Configurations** → Select config → **Add Peer**
2. Select your node from the dropdown
3. Create the peer
4. SSH to node and verify:
   ```bash
   sudo wg show wg0
   ```
5. Should see the new peer listed

---

## Troubleshooting

### Agent Authentication Errors

**Symptom:** Panel shows "Authentication failed" or 401 errors

**Causes and Solutions:**

1. **Mismatched secrets:**
   ```bash
   # Verify secret on node
   sudo cat /opt/wgdashboard-agent/.env | grep SECRET
   
   # Compare with panel configuration
   # Settings → Nodes → Edit Node → Check secret field
   ```

2. **Time drift between panel and node:**
   ```bash
   # Check time on both servers
   date
   
   # Sync time (Ubuntu/Debian)
   sudo timedatectl set-ntp true
   sudo systemctl restart systemd-timesyncd
   
   # Verify NTP sync
   timedatectl status
   ```
   
   **Note:** HMAC signatures include timestamps. Clock drift >5 minutes will cause authentication to fail.

3. **Firewall blocking requests:**
   ```bash
   # Test connectivity from panel
   telnet NODE_IP 8080
   
   # If fails, check firewall rules on node
   sudo ufw status
   sudo iptables -L -n | grep 8080
   ```

### Interface Deletion Endpoint Issues

**Symptom:** Error when removing node from configuration

**Troubleshooting:**

1. **Check agent logs:**
   ```bash
   # Docker
   docker logs wgdashboard-agent --tail 100
   
   # Systemd
   sudo journalctl -u wgdashboard-agent -n 100
   ```

2. **Verify DELETE endpoint exists:**
   ```bash
   # Check agent version
   curl http://NODE_IP:8080/health
   
   # Test DELETE endpoint manually
   curl -X DELETE http://localhost:8080/v1/wg/wg0 \
     -H "X-Signature: test" \
     -H "X-Timestamp: $(date +%s)"
   ```

3. **Interface busy/in use:**
   ```bash
   # Check what's using the interface
   sudo lsof | grep wg0
   
   # Force down interface
   sudo wg-quick down wg0
   
   # Remove config file
   sudo rm /etc/wireguard/wg0.conf
   ```

### WireGuard Config File Permissions

**Symptom:** Agent can't read/write WireGuard configuration files

**Solution:**

```bash
# Fix permissions on config directory
sudo chmod 700 /etc/wireguard
sudo chmod 600 /etc/wireguard/*.conf

# For Docker, ensure volume mount has correct permissions
docker exec wgdashboard-agent ls -la /etc/wireguard

# If permission denied, recreate container with correct user mapping
```

### Panel Cannot Reach Agent

**Symptom:** Panel shows "Connection refused" or "Timeout"

**Checklist:**

1. **Verify agent is running:**
   ```bash
   # Docker
   docker ps | grep wgdashboard-agent
   
   # Systemd
   sudo systemctl status wgdashboard-agent
   ```

2. **Check agent is listening:**
   ```bash
   sudo ss -tlnp | grep 8080
   # Should show process listening on 0.0.0.0:8080 or :::8080
   ```

3. **Test local connectivity:**
   ```bash
   curl http://localhost:8080/health
   # Should return: {"status": "ok"}
   ```

4. **Check firewall rules:**
   ```bash
   # UFW
   sudo ufw status | grep 8080
   
   # iptables
   sudo iptables -L -n | grep 8080
   
   # Allow panel IP if blocked
   sudo ufw allow from PANEL_IP to any port 8080 proto tcp
   ```

5. **Test from panel server:**
   ```bash
   # From panel server
   telnet NODE_IP 8080
   curl http://NODE_IP:8080/health
   ```

6. **Check network path:**
   ```bash
   # Trace route from panel to node
   traceroute NODE_IP
   
   # Test specific port
   nc -zv NODE_IP 8080
   ```

### Agent Not Starting

**Docker:**

```bash
# Check container status
docker ps -a | grep wgdashboard-agent

# View container logs
docker logs wgdashboard-agent

# Common issues:
# 1. Missing capabilities - add --cap-add NET_ADMIN
# 2. Port already in use - check with: sudo ss -tlnp | grep 8080
# 3. Invalid secret - verify .env file or environment variables
```

**Systemd:**

```bash
# Check service status
sudo systemctl status wgdashboard-agent

# View full logs
sudo journalctl -u wgdashboard-agent -xe

# Common issues:
# 1. Python dependencies missing - reinstall: pip3 install -r requirements.txt
# 2. Permission denied - service must run as root
# 3. Port conflict - change WG_AGENT_PORT in .env
```

### Peer Migration Failures

**Symptom:** Peers not migrated when node removed

**Troubleshooting:**

1. **Check panel logs:**
   ```bash
   # Check for migration errors
   grep "migration" /var/log/wgdashboard/dashboard.log
   ```

2. **Verify destination nodes available:**
   ```bash
   # List nodes for configuration
   curl http://localhost:10086/api/configs/wg0/nodes
   
   # Ensure at least one other healthy node exists
   ```

3. **Check agent connectivity:**
   ```bash
   # Test destination node agent
   curl http://DESTINATION_NODE_IP:8080/health
   ```

4. **Manual migration (if automatic fails):**
   ```bash
   # Get peer list from source node
   curl http://localhost:10086/api/configs/wg0/peers
   
   # Manually create peers on destination node through panel UI
   # Then remove source node
   ```

### High Memory Usage (Docker)

**Symptom:** Agent container using excessive memory

**Solution:**

```bash
# Limit container resources
docker run -d \
  --memory="512m" \
  --memory-swap="1g" \
  --cpus="1.0" \
  ...

# Or in docker-compose.yml:
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
```

### DNS Resolution Issues

**Symptom:** Agent can't resolve domain names for API calls

**Solution:**

```bash
# Add custom DNS to container
docker run -d \
  --dns 8.8.8.8 \
  --dns 1.1.1.1 \
  ...

# Or in docker-compose.yml:
dns:
  - 8.8.8.8
  - 1.1.1.1
```

---

## Additional Resources

- [Multi-Node Architecture Documentation](MULTI_NODE_ARCHITECTURE.md)
- [Phase 4 Multi-Node Features](PHASE4_MULTINODE.md)
- [Phase 8 Implementation Summary](../PHASE8_IMPLEMENTATION_SUMMARY.md)
- [Cloudflare DNS Setup Guide](cloudflare-dns-setup.md)
- [Agent Deployment Guide](AGENT_DEPLOYMENT.md)

---

## Quick Reference

### Essential Commands

**Check agent status:**
```bash
# Docker
docker ps | grep wgdashboard-agent

# Systemd
sudo systemctl status wgdashboard-agent
```

**View agent logs:**
```bash
# Docker
docker logs wgdashboard-agent -f

# Systemd
sudo journalctl -u wgdashboard-agent -f
```

**Test agent connectivity:**
```bash
curl http://NODE_IP:8080/health
```

**Assign node to config:**
```bash
curl -X POST http://localhost:10086/api/configs/wg0/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node1"}'
```

**Remove node from config:**
```bash
curl -X DELETE http://localhost:10086/api/configs/wg0/nodes/node1
```

**List config nodes:**
```bash
curl http://localhost:10086/api/configs/wg0/nodes
```

---

*Last updated: December 2024 | Phase 9 Documentation*
