"""
ConfigNodes Manager
Handles CRUD operations for config-node assignments (Phase 8)
"""
import json
from datetime import datetime
from typing import List, Optional, Tuple
import sqlalchemy as db

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .ConfigNode import ConfigNode
except ImportError:
    from ConfigNode import ConfigNode


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


class ConfigNodesManager:
    """Manager for config-node assignment operations"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.configNodesTable = DashboardConfig.configNodesTable
    
    def assignNodeToConfig(self, config_name: str, node_id: str) -> Tuple[bool, str]:
        """
        Assign a node to a configuration
        
        Args:
            config_name: Name of the WireGuard configuration
            node_id: ID of the node to assign
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.engine.begin() as conn:
                # Check if assignment already exists
                existing = conn.execute(
                    self.configNodesTable.select().where(
                        db.and_(
                            self.configNodesTable.c.config_name == config_name,
                            self.configNodesTable.c.node_id == node_id
                        )
                    )
                ).fetchone()
                
                if existing:
                    return False, "Node already assigned to this configuration"
                
                # Create new assignment
                conn.execute(
                    self.configNodesTable.insert().values(
                        config_name=config_name,
                        node_id=node_id,
                        is_healthy=True
                    )
                )
                
                _log_info(f"Assigned node {node_id} to config {config_name}")
                return True, "Node assigned successfully"
        except Exception as e:
            _log_error(f"Error assigning node to config: {e}")
            return False, str(e)
    
    def removeNodeFromConfig(self, config_name: str, node_id: str) -> Tuple[bool, str]:
        """
        Remove a node from a configuration
        
        Args:
            config_name: Name of the WireGuard configuration
            node_id: ID of the node to remove
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    self.configNodesTable.delete().where(
                        db.and_(
                            self.configNodesTable.c.config_name == config_name,
                            self.configNodesTable.c.node_id == node_id
                        )
                    )
                )
                
                if result.rowcount == 0:
                    return False, "Node assignment not found"
                
                _log_info(f"Removed node {node_id} from config {config_name}")
                return True, "Node removed successfully"
        except Exception as e:
            _log_error(f"Error removing node from config: {e}")
            return False, str(e)
    
    def getNodesForConfig(self, config_name: str) -> List[ConfigNode]:
        """
        Get all nodes assigned to a configuration
        
        Args:
            config_name: Name of the WireGuard configuration
            
        Returns:
            List of ConfigNode objects
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.configNodesTable.select().where(
                        self.configNodesTable.c.config_name == config_name
                    )
                ).mappings().fetchall()
                
                return [ConfigNode(dict(row)) for row in result]
        except Exception as e:
            _log_error(f"Error getting nodes for config: {e}")
            return []
    
    def getHealthyNodesForConfig(self, config_name: str) -> List[ConfigNode]:
        """
        Get all healthy nodes assigned to a configuration
        
        Args:
            config_name: Name of the WireGuard configuration
            
        Returns:
            List of ConfigNode objects
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.configNodesTable.select().where(
                        db.and_(
                            self.configNodesTable.c.config_name == config_name,
                            self.configNodesTable.c.is_healthy == True
                        )
                    )
                ).mappings().fetchall()
                
                return [ConfigNode(dict(row)) for row in result]
        except Exception as e:
            _log_error(f"Error getting healthy nodes for config: {e}")
            return []
    
    def getConfigsForNode(self, node_id: str) -> List[ConfigNode]:
        """
        Get all configurations assigned to a node
        
        Args:
            node_id: ID of the node
            
        Returns:
            List of ConfigNode objects
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.configNodesTable.select().where(
                        self.configNodesTable.c.node_id == node_id
                    )
                ).mappings().fetchall()
                
                return [ConfigNode(dict(row)) for row in result]
        except Exception as e:
            _log_error(f"Error getting configs for node: {e}")
            return []
    
    def updateNodeHealth(self, config_name: str, node_id: str, is_healthy: bool) -> Tuple[bool, str]:
        """
        Update the health status of a node assignment
        
        Args:
            config_name: Name of the WireGuard configuration
            node_id: ID of the node
            is_healthy: New health status
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    self.configNodesTable.update().where(
                        db.and_(
                            self.configNodesTable.c.config_name == config_name,
                            self.configNodesTable.c.node_id == node_id
                        )
                    ).values(is_healthy=is_healthy)
                )
                
                if result.rowcount == 0:
                    return False, "Node assignment not found"
                
                _log_info(f"Updated health for node {node_id} in config {config_name}: {is_healthy}")
                return True, "Health status updated"
        except Exception as e:
            _log_error(f"Error updating node health: {e}")
            return False, str(e)
