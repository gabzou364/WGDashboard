#!/usr/bin/env python3
"""
WGDashboard Agent - Production-grade WireGuard node agent
Main entry point for FastAPI-based agent
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('WG_AGENT_LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import after logging configuration
from app import app
import uvicorn

def main():
    """Start the agent server"""
    # Get configuration from environment
    host = os.getenv('WG_AGENT_HOST', '0.0.0.0')
    port = int(os.getenv('WG_AGENT_PORT', '8080'))
    secret = os.getenv('WG_AGENT_SECRET')
    
    # Validate required configuration
    if not secret or secret == 'change-me-in-production':
        logger.warning("WARNING: Using default or no shared secret. Set WG_AGENT_SECRET environment variable!")
        logger.warning("Generate one with: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'")
    
    logger.info(f"Starting WGDashboard Agent on {host}:{port}")
    logger.info(f"Log level: {LOG_LEVEL}")
    logger.info("Press Ctrl+C to stop")
    
    # Run uvicorn server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=LOG_LEVEL.lower(),
        access_log=True
    )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
