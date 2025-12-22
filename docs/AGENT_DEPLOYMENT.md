# Node Agent Deployment Guide

This guide walks through deploying a WireGuard node agent for use with WGDashboard's multi-node architecture.

## Prerequisites

- Linux server with WireGuard installed
- Python 3.7+ installed
- Root or sudo access
- WireGuard interface configured (e.g., `wg0`)
- Network connectivity from controller to agent

## Quick Start

### 1. Install the Agent

```bash
# Create directory for agent
sudo mkdir -p /opt/wg-agent

# Copy agent script
sudo cp wg-agent-example.py /opt/wg-agent/wg-agent.py
sudo chmod +x /opt/wg-agent/wg-agent.py

# Test run
sudo WG_AGENT_SECRET="your-secret-here" python3 /opt/wg-agent/wg-agent.py
```

### 2. Generate Shared Secret

Generate a secure shared secret for HMAC authentication:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save this secret - you'll need it both on the agent and in the dashboard.

### 3. Configure Systemd Service

```bash
# Copy systemd unit file
sudo cp wg-agent.service /etc/systemd/system/

# Edit to set your secret
sudo nano /etc/systemd/system/wg-agent.service

# Update this line with your generated secret:
# Environment="WG_AGENT_SECRET=your-generated-secret-here"

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable wg-agent
sudo systemctl start wg-agent

# Check status
sudo systemctl status wg-agent
```

### 4. Verify Agent is Running

```bash
# Check if agent is listening
sudo ss -tlnp | grep 8080

# Check logs
sudo journalctl -u wg-agent -f
```

### 5. Test Agent Locally

Create a test script to verify agent responds correctly:

```python
#!/usr/bin/env python3
import hmac
import hashlib
import time
import requests

agent_url = "http://localhost:8080"
secret = "your-secret-here"

def make_signed_request(method, path, body=""):
    timestamp = str(int(time.time()))
    message = f"{method}|{path}|{body}|{timestamp}"
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'X-Signature': signature,
        'X-Timestamp': timestamp,
        'Content-Type': 'application/json'
    }
    
    url = f"{agent_url}{path}"
    if method == "GET":
        return requests.get(url, headers=headers)
    elif method == "POST":
        return requests.post(url, headers=headers, data=body)

# Test health endpoint
response = make_signed_request("GET", "/health")
print(f"Health check: {response.status_code}")
print(response.json())

# Test WireGuard dump
response = make_signed_request("GET", "/wg/wg0/dump")
print(f"\nWireGuard dump: {response.status_code}")
print(response.json())
```

Save as `test_agent.py` and run:
```bash
python3 test_agent.py
```

### 6. Configure Firewall

If using a firewall, allow traffic from the controller:

```bash
# UFW example
sudo ufw allow from CONTROLLER_IP to any port 8080 proto tcp

# Or iptables
sudo iptables -A INPUT -p tcp -s CONTROLLER_IP --dport 8080 -j ACCEPT
```

### 7. Add Node to Dashboard

1. Log into WGDashboard
2. Navigate to **Nodes** page
3. Click **Add Node**
4. Fill in details:
   - **Name**: `node-1` (or descriptive name)
   - **Agent URL**: `http://your-node-ip:8080`
   - **WireGuard Interface**: `wg0`
   - **Endpoint**: `your-node-public-ip:51820`
   - **Shared Secret**: (paste the generated secret)
5. Click **Test Connection** to verify
6. Click **Create**

## Production Deployment

### Use HTTPS

For production, use HTTPS with a reverse proxy:

```nginx
# Nginx example
server {
    listen 443 ssl;
    server_name node1.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Update agent URL in dashboard to `https://node1.example.com`

### Security Hardening

1. **Restrict access by IP**:
   ```bash
   # Only allow controller IP
   sudo iptables -A INPUT -p tcp ! -s CONTROLLER_IP --dport 8080 -j DROP
   ```

2. **Use systemd security features**:
   Edit `/etc/systemd/system/wg-agent.service`:
   ```ini
   [Service]
   # Hardening
   NoNewPrivileges=true
   PrivateTmp=true
   ProtectSystem=strict
   ProtectHome=true
   ReadWritePaths=/etc/wireguard
   ```

3. **Rotate secrets regularly**:
   - Generate new secret
   - Update agent service
   - Update node in dashboard
   - Restart agent

### Monitoring

Add monitoring for the agent:

```bash
# Check agent health
curl -f http://localhost:8080/health || echo "Agent down"

# Monitor with systemd
sudo systemctl status wg-agent

# View logs
sudo journalctl -u wg-agent --since "1 hour ago"
```

### Backup and Recovery

Agent state is minimal - configuration is in:
- `/etc/systemd/system/wg-agent.service` (systemd unit)
- `/opt/wg-agent/wg-agent.py` (agent script)

WireGuard configuration is in `/etc/wireguard/` (managed by WireGuard itself).

To backup:
```bash
sudo cp /etc/systemd/system/wg-agent.service /backup/
sudo cp /opt/wg-agent/wg-agent.py /backup/
```

## Troubleshooting

### Agent won't start

Check logs:
```bash
sudo journalctl -u wg-agent -n 50
```

Common issues:
- Port 8080 already in use: Change `WG_AGENT_PORT` in service file
- Python not found: Install Python 3 or adjust `ExecStart` path
- Permission denied: Ensure agent runs as root (needed for `wg` commands)

### Connection refused from dashboard

1. Check agent is running: `sudo systemctl status wg-agent`
2. Check firewall: `sudo ufw status` or `sudo iptables -L`
3. Verify network connectivity: `ping node-ip`
4. Check agent logs for errors

### Signature verification fails

1. Ensure shared secret matches in agent and dashboard
2. Check system time is synchronized (NTP)
3. Verify no trailing spaces in secret

### WireGuard commands fail

1. Check WireGuard is installed: `wg version`
2. Verify interface exists: `wg show`
3. Ensure agent runs as root: Check `User=root` in service file

## Updating the Agent

To update the agent:

```bash
# Stop service
sudo systemctl stop wg-agent

# Backup current version
sudo cp /opt/wg-agent/wg-agent.py /opt/wg-agent/wg-agent.py.bak

# Update script
sudo cp new-wg-agent.py /opt/wg-agent/wg-agent.py
sudo chmod +x /opt/wg-agent/wg-agent.py

# Restart service
sudo systemctl start wg-agent

# Check status
sudo systemctl status wg-agent
```

## Multiple Interfaces

To manage multiple WireGuard interfaces on one node:

Option 1: One agent handles all interfaces (recommended)
- Agent already supports multiple interfaces via path parameter
- Add multiple nodes in dashboard with same agent URL but different interfaces

Option 2: Multiple agents (one per interface)
- Run agents on different ports
- Use different systemd unit files (`wg-agent@wg0.service`, `wg-agent@wg1.service`)

## Docker Deployment

Example Dockerfile for containerized agent:

```dockerfile
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y wireguard-tools && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY wg-agent.py .

ENV WG_AGENT_SECRET=changeme
ENV WG_AGENT_PORT=8080

EXPOSE 8080

CMD ["python3", "wg-agent.py"]
```

Run with:
```bash
docker run -d \
  --name wg-agent \
  --cap-add NET_ADMIN \
  --network host \
  -v /etc/wireguard:/etc/wireguard \
  -e WG_AGENT_SECRET="your-secret" \
  wg-agent:latest
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/WGDashboard/WGDashboard/issues
- Documentation: See MULTI_NODE_ARCHITECTURE.md

## License

The example agent implementation is provided as-is for reference purposes.
See main WGDashboard license for details.
