"""
NodeInterfaces Manager
Handles CRUD operations for node interfaces in multi-node architecture
"""
import uuid
import json
from datetime import datetime
from typing import List, Optional, Tuple, Any
import sqlalchemy as db

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .NodeInterface import NodeInterface
except ImportError:
    from NodeInterface import NodeInterface


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


class NodeInterfacesManager:
    """Manager for node interface operations"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.nodeInterfacesTable = DashboardConfig.nodeInterfacesTable
    
    def getAllInterfaces(self) -> List[NodeInterface]:
        """Get all node interfaces from database"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(self.nodeInterfacesTable.select()).mappings().fetchall()
                interfaces = []
                for row in result:
                    interfaces.append(NodeInterface(dict(row)))
                return interfaces
        except Exception as e:
            _log_error(f"Error getting all interfaces: {e}")
            return []
    
    def getInterfaceById(self, interface_id: str) -> Optional[NodeInterface]:
        """Get interface by ID"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodeInterfacesTable.select().where(
                        self.nodeInterfacesTable.c.id == interface_id
                    )
                ).mappings().fetchone()
                if result:
                    return NodeInterface(dict(result))
                return None
        except Exception as e:
            _log_error(f"Error getting interface {interface_id}: {e}")
            return None
    
    def getInterfacesByNodeId(self, node_id: str) -> List[NodeInterface]:
        """Get all interfaces for a specific node"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodeInterfacesTable.select().where(
                        self.nodeInterfacesTable.c.node_id == node_id
                    )
                ).mappings().fetchall()
                interfaces = []
                for row in result:
                    interfaces.append(NodeInterface(dict(row)))
                return interfaces
        except Exception as e:
            _log_error(f"Error getting interfaces for node {node_id}: {e}")
            return []
    
    def getEnabledInterfacesByNodeId(self, node_id: str) -> List[NodeInterface]:
        """Get only enabled interfaces for a specific node"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodeInterfacesTable.select().where(
                        db.and_(
                            self.nodeInterfacesTable.c.node_id == node_id,
                            self.nodeInterfacesTable.c.enabled == True
                        )
                    )
                ).mappings().fetchall()
                interfaces = []
                for row in result:
                    interfaces.append(NodeInterface(dict(row)))
                return interfaces
        except Exception as e:
            _log_error(f"Error getting enabled interfaces for node {node_id}: {e}")
            return []
    
    def createInterface(self, node_id: str, interface_name: str, 
                       endpoint: Optional[str] = None,
                       ip_pool_cidr: Optional[str] = None,
                       listen_port: Optional[int] = None,
                       address: Optional[str] = None,
                       private_key_encrypted: Optional[str] = None,
                       post_up: Optional[str] = None,
                       pre_down: Optional[str] = None,
                       mtu: Optional[int] = None,
                       dns: Optional[str] = None,
                       table: Optional[str] = None,
                       enabled: bool = True) -> Tuple[bool, Any]:
        """
        Create a new interface for a node
        
        Returns:
            Tuple of (success: bool, interface or error_message)
        """
        try:
            # Validate required fields
            if not node_id or not interface_name:
                return False, "Node ID and interface name are required"
            
            # Check if interface already exists for this node using database query
            try:
                with self.engine.connect() as conn:
                    existing = conn.execute(
                        self.nodeInterfacesTable.select().where(
                            db.and_(
                                self.nodeInterfacesTable.c.node_id == node_id,
                                self.nodeInterfacesTable.c.interface_name == interface_name
                            )
                        )
                    ).fetchone()
                    
                    if existing:
                        return False, f"Interface {interface_name} already exists for this node"
            except Exception as e:
                _log_error(f"Error checking existing interface: {e}")
                return False, str(e)
            
            # Generate interface ID
            interface_id = str(uuid.uuid4())
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodeInterfacesTable.insert().values({
                        'id': interface_id,
                        'node_id': node_id,
                        'interface_name': interface_name,
                        'endpoint': endpoint,
                        'ip_pool_cidr': ip_pool_cidr,
                        'listen_port': listen_port,
                        'address': address,
                        'private_key_encrypted': private_key_encrypted,
                        'post_up': post_up,
                        'pre_down': pre_down,
                        'mtu': mtu,
                        'dns': dns,
                        'table': table,
                        'enabled': enabled
                    })
                )
            
            interface = self.getInterfaceById(interface_id)
            _log_info(f"Created interface: {interface_name} for node {node_id}")
            return True, interface
            
        except Exception as e:
            _log_error(f"Error creating interface: {e}")
            return False, str(e)
    
    def updateInterface(self, interface_id: str, data: dict) -> Tuple[bool, Any]:
        """
        Update interface
        
        Returns:
            Tuple of (success: bool, interface or error_message)
        """
        try:
            interface = self.getInterfaceById(interface_id)
            if not interface:
                return False, "Interface not found"
            
            update_values = {}
            allowed_fields = ['endpoint', 'ip_pool_cidr', 'listen_port', 'address',
                            'private_key_encrypted', 'post_up', 'pre_down', 'mtu',
                            'dns', 'table', 'enabled']
            
            for field in allowed_fields:
                if field in data:
                    update_values[field] = data[field]
            
            if update_values:
                update_values['updated_at'] = datetime.now()
                
                with self.engine.begin() as conn:
                    conn.execute(
                        self.nodeInterfacesTable.update()
                        .where(self.nodeInterfacesTable.c.id == interface_id)
                        .values(update_values)
                    )
            
            updated_interface = self.getInterfaceById(interface_id)
            _log_info(f"Updated interface: {interface_id}")
            return True, updated_interface
            
        except Exception as e:
            _log_error(f"Error updating interface {interface_id}: {e}")
            return False, str(e)
    
    def deleteInterface(self, interface_id: str) -> Tuple[bool, str]:
        """
        Delete interface
        
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            interface = self.getInterfaceById(interface_id)
            if not interface:
                return False, "Interface not found"
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodeInterfacesTable.delete().where(
                        self.nodeInterfacesTable.c.id == interface_id
                    )
                )
            
            _log_info(f"Deleted interface: {interface_id}")
            return True, "Interface deleted successfully"
            
        except Exception as e:
            _log_error(f"Error deleting interface {interface_id}: {e}")
            return False, str(e)
    
    def toggleInterfaceEnabled(self, interface_id: str, enabled: bool) -> Tuple[bool, Any]:
        """
        Enable or disable interface
        
        Returns:
            Tuple of (success: bool, interface or error_message)
        """
        try:
            interface = self.getInterfaceById(interface_id)
            if not interface:
                return False, "Interface not found"
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodeInterfacesTable.update()
                    .where(self.nodeInterfacesTable.c.id == interface_id)
                    .values(enabled=enabled, updated_at=datetime.now())
                )
            
            updated_interface = self.getInterfaceById(interface_id)
            status = "enabled" if enabled else "disabled"
            _log_info(f"Interface {interface_id} {status}")
            return True, updated_interface
            
        except Exception as e:
            _log_error(f"Error toggling interface {interface_id}: {e}")
            return False, str(e)
