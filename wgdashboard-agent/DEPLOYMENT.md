# WGDashboard Agent - Production Deployment Guide

This guide covers deploying the WGDashboard Agent in production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Deployment Methods](#deployment-methods)
3. [Docker Deployment](#docker-deployment)
4. [Systemd Service Deployment](#systemd-service-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Configuration](#configuration)
7. [Security Best Practices](#security-best-practices)
8. [Monitoring & Observability](#monitoring--observability)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

- Linux server with WireGuard installed
- Python 3.7+ (for non-Docker deployments)
- Docker and Docker Compose (for Docker deployments)
- Root or sudo access (WireGuard requires privileged operations)
- Network connectivity between agent and panel

## Deployment Methods

Choose the deployment method that best fits your infrastructure:

- **Docker** - Recommended for containerized environments
- **Systemd Service** - Traditional Linux service deployment
- **Kubernetes** - For orchestrated container deployments

## Docker Deployment

### Quick Start

```bash
# Clone or copy agent files
cd /opt
git clone https://github.com/yourusername/WGDashboard.git
cd WGDashboard/wgdashboard-agent

# Generate a secure secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Create .env file
cat > .env << EOF
WG_AGENT_SECRET=your-generated-secret-here
WG_AGENT_PORT=8080
WG_AGENT_HOST=0.0.0.0
WG_AGENT_LOG_LEVEL=INFO
MAX_TIMESTAMP_AGE=300
EOF

# Build and start
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

### Building the Image

```bash
# Build locally
docker build -t wgdashboard-agent:latest .

# Or use docker-compose
docker-compose build
```

### Running the Container

```bash
# Using docker-compose (recommended)
docker-compose up -d

# Or using docker run
docker run -d \
  --name wgdashboard-agent \
  --cap-add=NET_ADMIN \
  --cap-add=SYS_MODULE \
  --network host \
  -v /etc/wireguard:/etc/wireguard:rw \
  -e WG_AGENT_SECRET=your-secret-here \
  -e WG_AGENT_PORT=8080 \
  wgdashboard-agent:latest
```

### Docker Configuration Options

**Network Mode:**
- `host` - Required for WireGuard interface management (recommended)
- Bridge mode not supported for WireGuard operations

**Capabilities:**
- `NET_ADMIN` - Required for network interface operations
- `SYS_MODULE` - Required for loading WireGuard kernel module

**Volumes:**
- `/etc/wireguard` - WireGuard configuration directory (required)
- `/app/logs` - Application logs (optional)

## Systemd Service Deployment

### Installation

```bash
# Create installation directory
sudo mkdir -p /opt/wgdashboard-agent
cd /opt/wgdashboard-agent

# Copy agent files
sudo cp /path/to/wgdashboard-agent/* /opt/wgdashboard-agent/

# Install Python dependencies
sudo pip3 install -r requirements.txt

# Generate shared secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Create .env file
sudo nano /opt/wgdashboard-agent/.env
```

**.env file:**
```env
WG_AGENT_SECRET=your-generated-secret-here
WG_AGENT_PORT=8080
WG_AGENT_HOST=0.0.0.0
WG_AGENT_LOG_LEVEL=INFO
MAX_TIMESTAMP_AGE=300
```

### Systemd Service Setup

```bash
# Copy service file
sudo cp wgdashboard-agent.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable wgdashboard-agent
sudo systemctl start wgdashboard-agent

# Check status
sudo systemctl status wgdashboard-agent

# View logs
sudo journalctl -u wgdashboard-agent -f
```

### Service Management

```bash
# Start service
sudo systemctl start wgdashboard-agent

# Stop service
sudo systemctl stop wgdashboard-agent

# Restart service
sudo systemctl restart wgdashboard-agent

# Reload configuration
sudo systemctl reload wgdashboard-agent

# View logs
sudo journalctl -u wgdashboard-agent -n 100

# Follow logs
sudo journalctl -u wgdashboard-agent -f
```

## Kubernetes Deployment

### Deployment YAML

Save as `wgdashboard-agent-deployment.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: wgdashboard
---
apiVersion: v1
kind: Secret
metadata:
  name: wgdashboard-agent-secret
  namespace: wgdashboard
type: Opaque
stringData:
  WG_AGENT_SECRET: "your-generated-secret-here"
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: wgdashboard-agent
  namespace: wgdashboard
spec:
  selector:
    matchLabels:
      app: wgdashboard-agent
  template:
    metadata:
      labels:
        app: wgdashboard-agent
    spec:
      hostNetwork: true
      containers:
      - name: agent
        image: wgdashboard-agent:latest
        imagePullPolicy: IfNotPresent
        securityContext:
          privileged: true
          capabilities:
            add:
              - NET_ADMIN
              - SYS_MODULE
        env:
        - name: WG_AGENT_SECRET
          valueFrom:
            secretKeyRef:
              name: wgdashboard-agent-secret
              key: WG_AGENT_SECRET
        - name: WG_AGENT_HOST
          value: "0.0.0.0"
        - name: WG_AGENT_PORT
          value: "8080"
        - name: WG_AGENT_LOG_LEVEL
          value: "INFO"
        ports:
        - containerPort: 8080
          protocol: TCP
        volumeMounts:
        - name: wireguard-config
          mountPath: /etc/wireguard
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: wireguard-config
        hostPath:
          path: /etc/wireguard
          type: Directory
```

Apply the deployment:

```bash
kubectl apply -f wgdashboard-agent-deployment.yaml
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `WG_AGENT_SECRET` | Shared secret for HMAC authentication | - | Yes |
| `WG_AGENT_HOST` | Host to bind to | `0.0.0.0` | No |
| `WG_AGENT_PORT` | Port to listen on | `8080` | No |
| `WG_AGENT_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `MAX_TIMESTAMP_AGE` | Maximum age of request timestamps (seconds) | `300` | No |

### Generating Secrets

```bash
# Generate a strong shared secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Or using OpenSSL
openssl rand -base64 32
```

**Important:** Use the same secret on both the agent and panel!

## Security Best Practices

### 1. Secret Management

- **Never** commit secrets to version control
- Use environment variables or secret management systems
- Rotate secrets periodically
- Use different secrets for each node

### 2. Network Security

```bash
# Firewall configuration (example using ufw)
sudo ufw allow 8080/tcp  # Agent API
sudo ufw allow 51820/udp # WireGuard VPN
sudo ufw enable

# Or using iptables
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

### 3. TLS/SSL (Recommended)

Use a reverse proxy (nginx, caddy) for TLS termination:

```nginx
# Nginx configuration
server {
    listen 443 ssl http2;
    server_name node1.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 4. Access Control

- Restrict agent API access to panel IPs only
- Use VPN or private network for panel-agent communication
- Implement network segmentation

## Monitoring & Observability

### Health Check

```bash
# Basic health check
curl http://localhost:8080/health

# Expected response
{
  "status": "ok",
  "timestamp": 1234567890,
  "uptime": 3600,
  "version": "2.1.0"
}
```

### Status Endpoint

```bash
# Get detailed status
curl http://localhost:8080/v1/status

# Includes:
# - System metrics (CPU, memory, disk)
# - WireGuard interface status
# - Peer counts and activity
```

### Prometheus Metrics

```bash
# Scrape metrics
curl http://localhost:8080/v1/metrics

# Configure Prometheus scraper
# prometheus.yml:
scrape_configs:
  - job_name: 'wgdashboard-agents'
    static_configs:
      - targets: ['node1.example.com:8080', 'node2.example.com:8080']
```

### Grafana Dashboard

Import the WGDashboard Agent dashboard (coming soon) or create custom panels:

**Useful Metrics:**
- `wgdashboard_agent_cpu_percent` - CPU usage
- `wgdashboard_agent_memory_percent` - Memory usage
- `wireguard_peers_total` - Total peer count
- `wireguard_peers_active` - Active peer count
- `wireguard_interface_receive_bytes_total` - RX bytes
- `wireguard_interface_transmit_bytes_total` - TX bytes

### Log Management

**View logs:**
```bash
# Docker
docker-compose logs -f

# Systemd
sudo journalctl -u wgdashboard-agent -f

# Log files (if configured)
tail -f /app/logs/agent.log
```

**Log levels:**
- `DEBUG` - Detailed debug information
- `INFO` - General information (default)
- `WARNING` - Warning messages
- `ERROR` - Error messages only

## Troubleshooting

### Common Issues

#### 1. Agent won't start

**Check logs:**
```bash
# Docker
docker-compose logs

# Systemd
sudo journalctl -u wgdashboard-agent -n 50
```

**Common causes:**
- Missing or invalid `WG_AGENT_SECRET`
- Port 8080 already in use
- Insufficient permissions
- Missing WireGuard installation

#### 2. Connection refused from panel

**Verify agent is running:**
```bash
curl http://localhost:8080/health
```

**Check firewall:**
```bash
sudo ufw status
sudo iptables -L -n
```

**Verify network connectivity:**
```bash
# From panel server
telnet agent-ip 8080
nc -zv agent-ip 8080
```

#### 3. Authentication failures

**Symptoms:**
- "Invalid signature" errors in logs
- 401 Unauthorized responses

**Solutions:**
- Verify secrets match on panel and agent
- Check system clock synchronization (NTP)
- Verify `MAX_TIMESTAMP_AGE` setting

```bash
# Check time sync
timedatectl status

# Sync time
sudo ntpdate pool.ntp.org
# or
sudo systemctl restart systemd-timesyncd
```

#### 4. WireGuard operations fail

**Check WireGuard installation:**
```bash
which wg
wg version
sudo wg show
```

**Verify permissions:**
```bash
# Agent needs root/CAP_NET_ADMIN
ps aux | grep main.py

# Docker - check capabilities
docker inspect wgdashboard-agent | grep -A 10 CapAdd
```

#### 5. High memory/CPU usage

**Check resource usage:**
```bash
# Docker
docker stats wgdashboard-agent

# System
top -p $(pgrep -f "python.*main.py")
```

**Common causes:**
- Too many concurrent requests
- Large number of peers
- Inefficient metrics collection

**Solutions:**
- Increase request timeout
- Reduce metrics scrape frequency
- Scale horizontally (more nodes)

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set environment variable
export WG_AGENT_LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart wgdashboard-agent

# Or for Docker
docker-compose down
docker-compose up -d
```

### Testing Connection

```bash
# Test from panel server
curl -X GET \
  -H "X-Signature: test" \
  -H "X-Timestamp: $(date +%s)" \
  http://agent-ip:8080/health

# Test authenticated endpoint (requires proper HMAC signature)
# Use the panel's node testing feature or AgentClient
```

### Performance Tuning

**For high-load scenarios:**

```env
# Increase worker processes
WORKERS=4

# Adjust timeout
TIMEOUT=120

# Optimize database connections
DB_POOL_SIZE=20
```

**Systemd service limits:**
```ini
[Service]
LimitNOFILE=65536
LimitNPROC=4096
```

## Support

For issues, feature requests, or questions:

- GitHub Issues: [WGDashboard/WGDashboard](https://github.com/donaldzou/WGDashboard/issues)
- Discord: [WGDashboard Community](https://discord.gg/72TwzjeuWm)
- Documentation: [wgdashboard.dev](https://wgdashboard.dev)

## Version History

- **v2.1.0** - Phase 5: Added `/v1/status` and `/v1/metrics` endpoints
- **v2.0.0** - Phase 4: Production-ready agent with FastAPI
- **v1.0.0** - Initial multi-node agent implementation
