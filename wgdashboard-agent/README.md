# WGDashboard Agent

Production-grade WireGuard node agent for WGDashboard multi-node architecture.

## Features

- **FastAPI-based** - Modern, high-performance async Python web framework
- **HMAC Authentication** - Secure request signing and verification
- **Health Checks** - Built-in health check endpoint for monitoring
- **Observability** - Prometheus metrics and detailed status reporting (Phase 5)
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

- **v2.1.0** (Phase 5) - Added `/v1/status` and `/v1/metrics` endpoints for observability
- **v2.0.0** (Phase 4) - Production-ready FastAPI agent with syncconf support
- **v1.0.0** - Initial multi-node agent implementation

## License

Apache License 2.0 - See LICENSE file for details
