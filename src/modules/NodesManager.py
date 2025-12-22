"""
Nodes Management
Handles CRUD operations for nodes in multi-node architecture
"""
import uuid
import json
import secrets
from datetime import datetime
from typing import List, Optional, Tuple, Any
import sqlalchemy as db

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .Node import Node
    from .NodeAgent import AgentClient
except ImportError:
    from Node import Node
    from NodeAgent import AgentClient


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


class NodesManager:
    """Manager for node operations"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        self.nodesTable = DashboardConfig.nodesTable
    
    def getAllNodes(self) -> List[Node]:
        """Get all nodes from database"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(self.nodesTable.select()).mappings().fetchall()
                nodes = []
                for row in result:
                    nodes.append(Node(dict(row)))
                return nodes
        except Exception as e:
            _log_error(f"Error getting all nodes: {e}")
            return []
    
    def getNodeById(self, node_id: str) -> Optional[Node]:
        """Get node by ID"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodesTable.select().where(self.nodesTable.c.id == node_id)
                ).mappings().fetchone()
                if result:
                    return Node(dict(result))
                return None
        except Exception as e:
            _log_error(f"Error getting node {node_id}: {e}")
            return None
    
    def getEnabledNodes(self) -> List[Node]:
        """Get only enabled nodes"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    self.nodesTable.select().where(self.nodesTable.c.enabled == True)
                ).mappings().fetchall()
                nodes = []
                for row in result:
                    nodes.append(Node(dict(row)))
                return nodes
        except Exception as e:
            _log_error(f"Error getting enabled nodes: {e}")
            return []
    
    def getNodesByGroup(self, group_id: Optional[str]) -> List[Node]:
        """
        Get nodes in a specific group (Phase 5)
        
        Args:
            group_id: Group ID to filter by (None for ungrouped nodes)
        
        Returns:
            List of nodes in the group
        """
        try:
            with self.engine.connect() as conn:
                if group_id is None:
                    # Get ungrouped nodes
                    result = conn.execute(
                        self.nodesTable.select().where(self.nodesTable.c.group_id.is_(None))
                    ).mappings().fetchall()
                else:
                    # Get nodes in specific group
                    result = conn.execute(
                        self.nodesTable.select().where(self.nodesTable.c.group_id == group_id)
                    ).mappings().fetchall()
                nodes = []
                for row in result:
                    nodes.append(Node(dict(row)))
                return nodes
        except Exception as e:
            _log_error(f"Error getting nodes by group {group_id}: {e}")
            return []
    
    def getEnabledNodesByGroup(self, group_id: Optional[str]) -> List[Node]:
        """
        Get enabled nodes in a specific group (Phase 5)
        
        Args:
            group_id: Group ID to filter by (None for ungrouped nodes)
        
        Returns:
            List of enabled nodes in the group
        """
        try:
            with self.engine.connect() as conn:
                if group_id is None:
                    # Get ungrouped enabled nodes
                    result = conn.execute(
                        self.nodesTable.select().where(
                            (self.nodesTable.c.enabled == True) & 
                            (self.nodesTable.c.group_id.is_(None))
                        )
                    ).mappings().fetchall()
                else:
                    # Get enabled nodes in specific group
                    result = conn.execute(
                        self.nodesTable.select().where(
                            (self.nodesTable.c.enabled == True) & 
                            (self.nodesTable.c.group_id == group_id)
                        )
                    ).mappings().fetchall()
                nodes = []
                for row in result:
                    nodes.append(Node(dict(row)))
                return nodes
        except Exception as e:
            _log_error(f"Error getting enabled nodes by group {group_id}: {e}")
            return []
    
    def createNode(self, name: str, agent_url: str, wg_interface: str,
                   endpoint: str, ip_pool_cidr: str, 
                   secret: Optional[str] = None,
                   auth_type: str = "hmac",
                   weight: int = 100,
                   max_peers: int = 0,
                   enabled: bool = True) -> Tuple[bool, Any]:
        """
        Create a new node
        
        Returns:
            Tuple of (success: bool, node or error_message)
        """
        try:
            # Validate required fields
            if not name or not agent_url or not wg_interface:
                return False, "Name, agent URL, and WG interface are required"
            
            # Generate node ID and secret if not provided
            node_id = str(uuid.uuid4())
            if not secret:
                secret = secrets.token_urlsafe(32)
            
            # Store secret (in production, this should be encrypted)
            # TODO: Implement proper encryption for secrets at rest
            # Consider using Fernet (cryptography library) or similar
            secret_encrypted = secret
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodesTable.insert().values({
                        'id': node_id,
                        'name': name,
                        'agent_url': agent_url.rstrip('/'),
                        'auth_type': auth_type,
                        'secret_encrypted': secret_encrypted,
                        'wg_interface': wg_interface,
                        'endpoint': endpoint,
                        'ip_pool_cidr': ip_pool_cidr,
                        'enabled': enabled,
                        'weight': weight,
                        'max_peers': max_peers,
                        'health_json': json.dumps({})
                    })
                )
            
            node = self.getNodeById(node_id)
            _log_info(f"Created node: {name} ({node_id})")
            return True, node
            
        except Exception as e:
            _log_error(f"Error creating node: {e}")
            return False, str(e)
    
    def updateNode(self, node_id: str, data: dict) -> Tuple[bool, Any]:
        """
        Update node
        
        Returns:
            Tuple of (success: bool, node or error_message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            update_values = {}
            allowed_fields = ['name', 'agent_url', 'wg_interface', 'endpoint', 
                            'ip_pool_cidr', 'weight', 'max_peers', 'enabled',
                            'group_id',  # Phase 5
                            'override_listen_port', 'override_dns', 'override_mtu',
                            'override_keepalive', 'override_endpoint_allowed_ip',
                            # Phase 6 - Interface-level configuration
                            'private_key_encrypted', 'post_up', 'pre_down']
            
            for field in allowed_fields:
                if field in data:
                    update_values[field] = data[field]
            
            if 'agent_url' in update_values:
                update_values['agent_url'] = update_values['agent_url'].rstrip('/')
            
            if update_values:
                update_values['updated_at'] = datetime.now()
                
                with self.engine.begin() as conn:
                    conn.execute(
                        self.nodesTable.update()
                        .where(self.nodesTable.c.id == node_id)
                        .values(update_values)
                    )
            
            updated_node = self.getNodeById(node_id)
            _log_info(f"Updated node: {node_id}")
            return True, updated_node
            
        except Exception as e:
            _log_error(f"Error updating node {node_id}: {e}")
            return False, str(e)
    
    def deleteNode(self, node_id: str) -> Tuple[bool, str]:
        """
        Delete node
        
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodesTable.delete().where(self.nodesTable.c.id == node_id)
                )
            
            _log_info(f"Deleted node: {node_id}")
            return True, "Node deleted successfully"
            
        except Exception as e:
            _log_error(f"Error deleting node {node_id}: {e}")
            return False, str(e)
    
    def toggleNodeEnabled(self, node_id: str, enabled: bool) -> Tuple[bool, Any]:
        """
        Enable or disable node
        
        Returns:
            Tuple of (success: bool, node or error_message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodesTable.update()
                    .where(self.nodesTable.c.id == node_id)
                    .values(enabled=enabled, updated_at=datetime.now())
                )
            
            updated_node = self.getNodeById(node_id)
            status = "enabled" if enabled else "disabled"
            _log_info(f"Node {node_id} {status}")
            return True, updated_node
            
        except Exception as e:
            _log_error(f"Error toggling node {node_id}: {e}")
            return False, str(e)
    
    def testNodeConnection(self, node_id: str) -> Tuple[bool, str]:
        """
        Test connection to node agent
        
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            # Create agent client and test connection
            client = AgentClient(node.agent_url, node.secret_encrypted)
            success, message = client.test_connection()
            
            return success, message
            
        except Exception as e:
            _log_error(f"Error testing node connection {node_id}: {e}")
            return False, str(e)
    
    def updateNodeHealth(self, node_id: str, health_data: dict) -> bool:
        """
        Update node health data from polling
        
        Returns:
            bool: Success status
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    self.nodesTable.update()
                    .where(self.nodesTable.c.id == node_id)
                    .values(
                        last_seen=datetime.now(),
                        health_json=json.dumps(health_data),
                        updated_at=datetime.now()
                    )
                )
            return True
        except Exception as e:
            _log_error(f"Error updating node health {node_id}: {e}")
            return False
    
    def getNodeAgentClient(self, node_id: str) -> Optional[AgentClient]:
        """
        Get agent client for node
        
        Returns:
            AgentClient or None if node not found
        """
        node = self.getNodeById(node_id)
        if node:
            return AgentClient(node.agent_url, node.secret_encrypted)
        return None
    
    # Interface-Level Configuration Management (Phase 6)
    
    def syncNodeInterfaceConfig(self, node_id: str) -> Tuple[bool, str]:
        """
        Sync interface configuration to node (Phase 6)
        Pushes the node's interface-level configuration to the agent
        
        Args:
            node_id: Node ID to sync
            
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            if not node.wg_interface:
                return False, "Node has no WireGuard interface configured"
            
            # Build interface configuration
            config_data = {}
            
            # Private key is required
            if not node.private_key_encrypted:
                return False, "Node has no private key configured"
            
            config_data['private_key'] = node.private_key_encrypted
            
            # Add optional fields if they exist
            if node.override_listen_port:
                config_data['listen_port'] = node.override_listen_port
            
            if node.override_dns:
                config_data['dns'] = node.override_dns
            
            if node.override_mtu:
                config_data['mtu'] = node.override_mtu
            
            if node.post_up:
                config_data['post_up'] = node.post_up
            
            if node.pre_down:
                config_data['pre_down'] = node.pre_down
            
            # Note: Address will typically be set from ip_pool_cidr or similar
            # For now, we don't automatically set it from the model
            
            # Send to agent
            client = AgentClient(node.agent_url, node.secret_encrypted)
            success, response = client.set_interface_config(node.wg_interface, config_data)
            
            if success:
                _log_info(f"Successfully synced interface config for node {node_id}")
                return True, "Interface configuration synchronized successfully"
            else:
                _log_error(f"Failed to sync interface config for node {node_id}: {response}")
                return False, f"Failed to sync interface configuration: {response}"
                
        except Exception as e:
            _log_error(f"Error syncing interface config for node {node_id}: {e}")
            return False, str(e)
    
    def getNodeInterfaceConfig(self, node_id: str) -> Tuple[bool, Any]:
        """
        Get interface configuration from node (Phase 6)
        Fetches the current interface configuration from the agent
        
        Args:
            node_id: Node ID
            
        Returns:
            Tuple of (success: bool, config_data or error_message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            if not node.wg_interface:
                return False, "Node has no WireGuard interface configured"
            
            client = AgentClient(node.agent_url, node.secret_encrypted)
            success, response = client.get_interface_config(node.wg_interface)
            
            if success:
                _log_info(f"Successfully retrieved interface config for node {node_id}")
                return True, response
            else:
                _log_error(f"Failed to get interface config for node {node_id}: {response}")
                return False, response
                
        except Exception as e:
            _log_error(f"Error getting interface config for node {node_id}: {e}")
            return False, str(e)
    
    def enableNodeInterface(self, node_id: str) -> Tuple[bool, str]:
        """
        Enable (bring up) node interface (Phase 6)
        
        Args:
            node_id: Node ID
            
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            if not node.wg_interface:
                return False, "Node has no WireGuard interface configured"
            
            client = AgentClient(node.agent_url, node.secret_encrypted)
            success, response = client.enable_interface(node.wg_interface)
            
            if success:
                _log_info(f"Successfully enabled interface for node {node_id}")
                return True, "Interface enabled successfully"
            else:
                _log_error(f"Failed to enable interface for node {node_id}: {response}")
                return False, response
                
        except Exception as e:
            _log_error(f"Error enabling interface for node {node_id}: {e}")
            return False, str(e)
    
    def disableNodeInterface(self, node_id: str) -> Tuple[bool, str]:
        """
        Disable (bring down) node interface (Phase 6)
        
        Args:
            node_id: Node ID
            
        Returns:
            Tuple of (success: bool, message)
        """
        try:
            node = self.getNodeById(node_id)
            if not node:
                return False, "Node not found"
            
            if not node.wg_interface:
                return False, "Node has no WireGuard interface configured"
            
            client = AgentClient(node.agent_url, node.secret_encrypted)
            success, response = client.disable_interface(node.wg_interface)
            
            if success:
                _log_info(f"Successfully disabled interface for node {node_id}")
                return True, "Interface disabled successfully"
            else:
                _log_error(f"Failed to disable interface for node {node_id}: {response}")
                return False, response
                
        except Exception as e:
            _log_error(f"Error disabling interface for node {node_id}: {e}")
            return False, str(e)

