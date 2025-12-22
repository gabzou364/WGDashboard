# WGDashboard Agent

Production-grade WireGuard node agent for WGDashboard multi-node architecture.

## Features

- **FastAPI-based** - Modern, high-performance async Python web framework
- **HMAC Authentication** - Secure request signing and verification
- **Health Checks** - Built-in health check endpoint for monitoring
- **Logging** - Structured logging with configurable levels
- **Security** - Replay attack prevention with timestamp validation
- **Drift Reconciliation** - Support for syncconf operations
- **Production Ready** - Systemd service, proper error handling, and configuration management

## Requirements

- Python 3.7+
- WireGuard installed and configured
- Root or sudo access (for WireGuard operations)

## Installation

### Quick Install

```bash
# Clone or copy the agent files
sudo mkdir -p /opt/wgdashboard-agent
sudo cp -r wgdashboard-agent/* /opt/wgdashboard-agent/

# Install Python dependencies
cd /opt/wgdashboard-agent
sudo pip3 install -r requirements.txt

# Generate a secure shared secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Create environment file
sudo nano /opt/wgdashboard-agent/.env
```

### Environment Configuration

Create `/opt/wgdashboard-agent/.env`:

```env
WG_AGENT_SECRET=your-generated-secret-here
WG_AGENT_PORT=8080
WG_AGENT_HOST=0.0.0.0
WG_AGENT_LOG_LEVEL=INFO
MAX_TIMESTAMP_AGE=300
```

### Systemd Service

```bash
# Copy service file
sudo cp wgdashboard-agent.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable wgdashboard-agent
sudo systemctl start wgdashboard-agent

# Check status
sudo systemctl status wgdashboard-agent

# View logs
sudo journalctl -u wgdashboard-agent -f
```

## API Endpoints

### Health Check

**GET /health**

Returns agent health status.

### WireGuard Operations

- **GET /v1/wg/{interface}/dump** - Get current peer state
- **POST /v1/wg/{interface}/peers** - Add a peer
- **PUT /v1/wg/{interface}/peers/{public_key}** - Update a peer
- **DELETE /v1/wg/{interface}/peers/{public_key}** - Delete a peer
- **POST /v1/wg/{interface}/syncconf** - Apply configuration atomically (Phase 4)

## Security

All requests require HMAC-SHA256 signatures via `X-Signature` and `X-Timestamp` headers.

See full documentation in main README.
