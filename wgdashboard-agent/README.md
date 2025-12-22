# WGDashboard Agent

Production-grade WireGuard node agent for WGDashboard multi-node architecture.

## Features

- **FastAPI-based** - Modern, high-performance async Python web framework
- **HMAC Authentication** - Secure request signing and verification
- **Health Checks** - Built-in health check endpoint for monitoring
- **Observability** - Prometheus metrics and detailed status reporting (Phase 5)
- **Interface Management** - Full WireGuard interface configuration control (Phase 6)
- **Logging** - Structured logging with configurable levels
- **Security** - Replay attack prevention with timestamp validation
- **Drift Reconciliation** - Support for syncconf operations
- **Production Ready** - Docker support, systemd service, proper error handling
- **System Metrics** - CPU, memory, disk, and network monitoring
- **WireGuard Metrics** - Per-interface and per-peer statistics

## Requirements

- Python 3.7+
- WireGuard installed and configured
- Root or sudo access (for WireGuard operations)

## Quick Start

### Docker Deployment (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/WGDashboard.git
cd WGDashboard/wgdashboard-agent

# Generate a secure secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Create .env file
cat > .env << EOF
WG_AGENT_SECRET=your-generated-secret-here
WG_AGENT_PORT=8080
EOF

# Start with Docker Compose
docker-compose up -d

# Check status
docker-compose logs -f
```

### Systemd Service Deployment

```bash
# Install dependencies
sudo mkdir -p /opt/wgdashboard-agent
cd /opt/wgdashboard-agent
sudo pip3 install -r requirements.txt

# Generate secret and create .env file
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
sudo nano .env

# Install and start service
sudo cp wgdashboard-agent.service /etc/systemd/system/
sudo systemctl enable --now wgdashboard-agent
sudo systemctl status wgdashboard-agent
```

## API Endpoints

### Health & Monitoring

- **GET /health** - Health check (no auth required)
- **GET /v1/status** - Detailed status with system and WireGuard metrics (Phase 5)
- **GET /v1/metrics** - Prometheus-compatible metrics (Phase 5)

### WireGuard Operations

- **GET /v1/wg/{interface}/dump** - Get current peer state
- **POST /v1/wg/{interface}/peers** - Add a peer
- **PUT /v1/wg/{interface}/peers/{public_key}** - Update a peer
- **DELETE /v1/wg/{interface}/peers/{public_key}** - Delete a peer
- **POST /v1/wg/{interface}/syncconf** - Apply configuration atomically (Phase 4)

### Interface Management (Phase 6)

- **GET /v1/wg/{interface}/config** - Get full interface configuration
- **PUT /v1/wg/{interface}/config** - Replace interface configuration
- **POST /v1/wg/{interface}/enable** - Bring interface up
- **POST /v1/wg/{interface}/disable** - Bring interface down

## Configuration

Environment variables:

```env
WG_AGENT_SECRET=your-secret-here        # Required: Shared secret for HMAC
WG_AGENT_PORT=8080                      # Port to listen on
WG_AGENT_HOST=0.0.0.0                   # Host to bind to
WG_AGENT_LOG_LEVEL=INFO                 # Log level (DEBUG, INFO, WARNING, ERROR)
MAX_TIMESTAMP_AGE=300                   # Max request age in seconds
```

## Deployment Guide

For complete production deployment instructions, see **[DEPLOYMENT.md](DEPLOYMENT.md)**

Topics covered:
- Docker deployment
- Systemd service setup
- Kubernetes deployment
- Security best practices
- Monitoring & observability
- Troubleshooting guide
- Performance tuning

## Security

All requests (except `/health` and `/v1/metrics`) require HMAC-SHA256 signatures via `X-Signature` and `X-Timestamp` headers.

**Generate a secure secret:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Use the same secret on both agent and panel!**

## Observability

### Prometheus Metrics

The agent exposes Prometheus-compatible metrics at `/v1/metrics`:

- System metrics: CPU, memory, disk usage
- WireGuard metrics: interface count, peer counts, active peers
- Per-peer metrics: RX/TX bytes, last handshake time

**Example Prometheus config:**
```yaml
scrape_configs:
  - job_name: 'wgdashboard-agents'
    static_configs:
      - targets: ['node1.example.com:8080', 'node2.example.com:8080']
```

### Status Endpoint

Get detailed status at `/v1/status`:

```bash
curl http://localhost:8080/v1/status
```

Returns:
- System metrics (CPU, memory, disk)
- WireGuard interface status
- Peer counts (total and active)
- Network I/O statistics
- Uptime and version

## Interface Configuration Management (Phase 6)

### Overview

Phase 6 adds full interface-level configuration management, allowing the panel to control all aspects of a node's WireGuard interface including private keys, listen ports, and firewall rules.

### GET /v1/wg/{interface}/config

Fetch the complete interface configuration from `/etc/wireguard/{interface}.conf`.

**Response:**
```json
{
  "interface": "wg0",
  "config": {
    "private_key": "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789=",
    "listen_port": 51820,
    "address": "10.0.0.1/24",
    "post_up": "iptables -A FORWARD -i wg0 -j ACCEPT",
    "pre_down": "iptables -D FORWARD -i wg0 -j ACCEPT",
    "mtu": 1420,
    "dns": "1.1.1.1",
    "table": "auto",
    "raw_config": "[Interface]\nPrivateKey = ...\n..."
  }
}
```

### PUT /v1/wg/{interface}/config

Replace the interface configuration with new settings. Includes dry-run validation and automatic backup/restore.

**Request:**
```json
{
  "private_key": "new-private-key-here",
  "listen_port": 51820,
  "address": "10.0.0.1/24",
  "post_up": "iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
  "pre_down": "iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE",
  "mtu": 1420,
  "dns": "1.1.1.1"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Interface configuration updated successfully",
  "reloaded": true
}
```

**Features:**
- **Dry-run validation** - Config validated before applying
- **Backup/restore** - Automatic rollback on failure
- **Peer preservation** - Existing peers are kept
- **Atomic update** - Interface reloaded if it was up

### POST /v1/wg/{interface}/enable

Bring the WireGuard interface up using `wg-quick up`.

**Response:**
```json
{
  "status": "success",
  "message": "Interface wg0 enabled successfully",
  "was_down": true
}
```

### POST /v1/wg/{interface}/disable

Bring the WireGuard interface down using `wg-quick down`.

**Response:**
```json
{
  "status": "success",
  "message": "Interface wg0 disabled successfully",
  "was_up": true
}
```

### PostUp/PreDown Examples

**NAT and Masquerading:**
```bash
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PreDown = iptables -D FORWARD -i wg0 -j ACCEPT
PreDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
```

**Port Forwarding:**
```bash
PostUp = iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 8080 -j DNAT --to-destination 10.0.0.2:80
PreDown = iptables -t nat -D PREROUTING -i eth0 -p tcp --dport 8080 -j DNAT --to-destination 10.0.0.2:80
```

**DNS Configuration:**
```bash
PostUp = resolvectl dns wg0 1.1.1.1 8.8.8.8
PostUp = resolvectl domain wg0 ~.
PreDown = resolvectl revert wg0
```

## Development

### Running locally

```bash
# Install dependencies
pip3 install -r requirements.txt

# Set environment variables
export WG_AGENT_SECRET=test-secret
export WG_AGENT_LOG_LEVEL=DEBUG

# Run the agent
python3 main.py
```

### Testing

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test status endpoint
curl http://localhost:8080/v1/status

# Test metrics endpoint
curl http://localhost:8080/v1/metrics
```

## Support

- **Documentation**: [wgdashboard.dev](https://wgdashboard.dev)
- **GitHub Issues**: [WGDashboard/WGDashboard](https://github.com/donaldzou/WGDashboard/issues)
- **Discord**: [WGDashboard Community](https://discord.gg/72TwzjeuWm)

## Version History

- **v2.2.0** (Phase 6) - Interface-level configuration management with PostUp/PreDown support
- **v2.1.0** (Phase 5) - Added `/v1/status` and `/v1/metrics` endpoints for observability
- **v2.0.0** (Phase 4) - Production-ready FastAPI agent with syncconf support
- **v1.0.0** - Initial multi-node agent implementation

## License

Apache License 2.0 - See LICENSE file for details
