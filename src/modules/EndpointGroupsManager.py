"""
EndpointGroups Manager
Handles CRUD operations for endpoint groups (Mode A / Cluster configuration) (Phase 8)
"""
import json
from datetime import datetime
from typing import Optional, Tuple, Any
import sqlalchemy as db

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .EndpointGroup import EndpointGroup
except ImportError:
    from EndpointGroup import EndpointGroup


def _log_info(msg):
    """Helper to log info messages"""
    if _has_flask:
        try:
            current_app.logger.info(msg)
        except (RuntimeError, NameError):
            pass


def _log_error(msg, exc=None):
    """Helper to log error messages"""
    if _has_flask:
        try:
            if exc:
                current_app.logger.error(msg, exc)
            else:
                current_app.logger.error(msg)
        except (RuntimeError, NameError):
            pass


class EndpointGroupsManager:
    """Manager for endpoint group operations"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.endpointGroupsTable = DashboardConfig.endpointGroupsTable
    
    def createOrUpdateEndpointGroup(self, config_name: str, data: dict) -> Tuple[bool, str]:
        """
        Create or update an endpoint group for a configuration
        
        Args:
            config_name: Name of the WireGuard configuration
            data: Dictionary containing endpoint group fields
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.engine.begin() as conn:
                # Check if endpoint group exists
                existing = conn.execute(
                    self.endpointGroupsTable.select().where(
                        self.endpointGroupsTable.c.config_name == config_name
                    )
                ).fetchone()
                
                # Ensure proxied is always false (DNS-only)
                data['proxied'] = False
                
                if existing:
                    # Update existing
                    conn.execute(
                        self.endpointGroupsTable.update().where(
                            self.endpointGroupsTable.c.config_name == config_name
                        ).values(**data)
                    )
                    _log_info(f"Updated endpoint group for config {config_name}")
                    return True, "Endpoint group updated successfully"
                else:
                    # Create new
                    data['config_name'] = config_name
                    conn.execute(
                        self.endpointGroupsTable.insert().values(**data)
                    )
                    _log_info(f"Created endpoint group for config {config_name}")
                    return True, "Endpoint group created successfully"
        except Exception as e:
            _log_error(f"Error creating/updating endpoint group: {e}")
            return False, str(e)
    
    def getEndpointGroup(self, config_name: str) -> Optional[EndpointGroup]:
        """
        Get endpoint group for a configuration
        
        Args:
            config_name: Name of the WireGuard configuration
            
        Returns:
            EndpointGroup object or None
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.endpointGroupsTable.select().where(
                        self.endpointGroupsTable.c.config_name == config_name
                    )
                ).mappings().fetchone()
                
                if result:
                    return EndpointGroup(dict(result))
                return None
        except Exception as e:
            _log_error(f"Error getting endpoint group: {e}")
            return None
    
    def deleteEndpointGroup(self, config_name: str) -> Tuple[bool, str]:
        """
        Delete an endpoint group
        
        Args:
            config_name: Name of the WireGuard configuration
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    self.endpointGroupsTable.delete().where(
                        self.endpointGroupsTable.c.config_name == config_name
                    )
                )
                
                if result.rowcount == 0:
                    return False, "Endpoint group not found"
                
                _log_info(f"Deleted endpoint group for config {config_name}")
                return True, "Endpoint group deleted successfully"
        except Exception as e:
            _log_error(f"Error deleting endpoint group: {e}")
            return False, str(e)
