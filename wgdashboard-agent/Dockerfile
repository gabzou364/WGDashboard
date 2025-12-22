# Production Dockerfile for WGDashboard Agent
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wireguard-tools \
    iproute2 \
    iptables \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY app.py .
COPY .env.example .

# Create non-root user for running the application
RUN useradd -m -u 1000 wgagent && \
    chown -R wgagent:wgagent /app

# Switch to non-root user (but note: WireGuard operations require root/CAP_NET_ADMIN)
# In production, run with --cap-add=NET_ADMIN and potentially --privileged
# USER wgagent

# Expose default port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set environment variables
ENV WG_AGENT_HOST=0.0.0.0
ENV WG_AGENT_PORT=8080
ENV WG_AGENT_LOG_LEVEL=INFO

# Run the agent
CMD ["python3", "main.py"]
