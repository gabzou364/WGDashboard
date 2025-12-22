"""
Peer Migration Manager
Handles automatic peer migration between nodes (Phase 8)
"""
import json
from typing import List, Optional, Tuple
import sqlalchemy as db

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False


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


class PeerMigrationManager:
    """
    Manager for automatic peer migration between nodes
    
    Features:
    - Migrate peers when node is removed from config
    - Migrate peers when node becomes unhealthy
    - Least-loaded node selection
    - Update peers via agent APIs
    """
    
    def __init__(self, DashboardConfig, NodesManager, ConfigNodesManager):
        """
        Initialize Peer Migration Manager
        
        Args:
            DashboardConfig: Dashboard configuration instance
            NodesManager: Nodes manager instance
            ConfigNodesManager: Config nodes manager instance
        """
        self.DashboardConfig = DashboardConfig
        self.NodesManager = NodesManager
        self.ConfigNodesManager = ConfigNodesManager
        self.engine = DashboardConfig.engine
        
        # Get peer table reference from a WireguardConfiguration
        # We'll need to access the peer table directly
        self.dbMetadata = db.MetaData()
    
    def migrate_peers_from_node(self, config_name: str, source_node_id: str, 
                               destination_node_id: str = None) -> Tuple[bool, str, int]:
        """
        Migrate all peers from source node to destination node(s)
        
        Args:
            config_name: Name of the WireGuard configuration
            source_node_id: Node to migrate peers from
            destination_node_id: Specific destination node (optional, will auto-select if None)
            
        Returns:
            Tuple of (success, message, number of peers migrated)
        """
        try:
            # Get peers assigned to the source node for this config
            peers = self._get_peers_for_node(config_name, source_node_id)
            
            if not peers:
                _log_info(f"No peers to migrate from node {source_node_id}")
                return True, "No peers to migrate", 0
            
            _log_info(f"Found {len(peers)} peers to migrate from node {source_node_id}")
            
            # Get destination nodes
            if destination_node_id:
                dest_nodes = [self.NodesManager.getNodeById(destination_node_id)]
                if not dest_nodes[0]:
                    return False, "Destination node not found", 0
            else:
                # Get healthy nodes for this config (excluding source)
                config_nodes = self.ConfigNodesManager.getHealthyNodesForConfig(config_name)
                dest_node_ids = [cn.node_id for cn in config_nodes if cn.node_id != source_node_id]
                
                if not dest_node_ids:
                    return False, "No healthy destination nodes available", 0
                
                dest_nodes = [self.NodesManager.getNodeById(nid) for nid in dest_node_ids]
                dest_nodes = [n for n in dest_nodes if n and n.enabled]
                
                if not dest_nodes:
                    return False, "No enabled destination nodes available", 0
            
            # Migrate each peer
            migrated_count = 0
            for peer in peers:
                # Select destination node (least loaded)
                dest_node = self._select_destination_node(dest_nodes, config_name)
                
                if not dest_node:
                    _log_error(f"Could not select destination node for peer {peer['id']}")
                    continue
                
                # Migrate the peer
                success = self._migrate_single_peer(config_name, peer, source_node_id, dest_node.id)
                
                if success:
                    migrated_count += 1
                    _log_info(f"Migrated peer {peer['id']} from {source_node_id} to {dest_node.id}")
                else:
                    _log_error(f"Failed to migrate peer {peer['id']}")
            
            if migrated_count == len(peers):
                return True, f"Successfully migrated {migrated_count} peers", migrated_count
            else:
                return False, f"Migrated {migrated_count}/{len(peers)} peers", migrated_count
        
        except Exception as e:
            _log_error(f"Error migrating peers: {e}")
            return False, str(e), 0
    
    def _get_peers_for_node(self, config_name: str, node_id: str) -> List[dict]:
        """
        Get all peers assigned to a specific node for a config
        
        Args:
            config_name: Configuration name
            node_id: Node ID
            
        Returns:
            List of peer dictionaries
        """
        try:
            # Access the peer table
            # The peer table name is based on the config name
            peer_table_name = f"{config_name}"
            
            with self.engine.connect() as conn:
                # Check if table exists
                if not db.inspect(self.engine).has_table(peer_table_name):
                    return []
                
                # Reflect the peer table
                peer_table = db.Table(peer_table_name, self.dbMetadata, autoload_with=self.engine)
                
                # Query peers for this node
                result = conn.execute(
                    peer_table.select().where(peer_table.c.node_id == node_id)
                ).mappings().fetchall()
                
                return [dict(row) for row in result]
        
        except Exception as e:
            _log_error(f"Error getting peers for node: {e}")
            return []
    
    def _select_destination_node(self, dest_nodes: List, config_name: str):
        """
        Select the best destination node based on load
        
        Args:
            dest_nodes: List of available destination nodes
            config_name: Configuration name
            
        Returns:
            Selected node or None
        """
        if not dest_nodes:
            return None
        
        # Simple selection: choose node with fewest peers for this config
        node_loads = []
        for node in dest_nodes:
            peer_count = len(self._get_peers_for_node(config_name, node.id))
            node_loads.append((node, peer_count))
        
        # Sort by peer count (ascending)
        node_loads.sort(key=lambda x: x[1])
        
        return node_loads[0][0]
    
    def _migrate_single_peer(self, config_name: str, peer: dict, 
                            source_node_id: str, dest_node_id: str) -> bool:
        """
        Migrate a single peer from source to destination node
        
        Args:
            config_name: Configuration name
            peer: Peer data dictionary
            source_node_id: Source node ID
            dest_node_id: Destination node ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get source and destination nodes
            source_node = self.NodesManager.getNodeById(source_node_id)
            dest_node = self.NodesManager.getNodeById(dest_node_id)
            
            if not source_node or not dest_node:
                return False
            
            # Add peer to destination node via agent API
            from .NodeAgent import AgentClient
            dest_agent = AgentClient(dest_node.agent_url, dest_node.secret_encrypted)
            
            # Prepare peer data for agent
            peer_data = {
                "public_key": peer.get("publicKey"),
                "allowed_ips": peer.get("allowed_ip", "").split(",") if peer.get("allowed_ip") else [],
                "preshared_key": peer.get("preshared_key"),
                "persistent_keepalive": peer.get("keepalive", 0)
            }
            
            # Add peer to destination
            success_add, _ = dest_agent.add_peer(dest_node.wg_interface, peer_data)
            
            if not success_add:
                _log_error(f"Failed to add peer to destination node {dest_node_id}")
                return False
            
            # Update peer node_id in database
            peer_table_name = f"{config_name}"
            peer_table = db.Table(peer_table_name, self.dbMetadata, autoload_with=self.engine)
            
            with self.engine.begin() as conn:
                conn.execute(
                    peer_table.update().where(
                        peer_table.c.id == peer["id"]
                    ).values(node_id=dest_node_id)
                )
            
            # Remove peer from source node via agent API
            source_agent = AgentClient(source_node.agent_url, source_node.secret_encrypted)
            success_del, _ = source_agent.delete_peer(source_node.wg_interface, peer.get("publicKey"))
            
            if not success_del:
                _log_error(f"Failed to delete peer from source node {source_node_id}")
                # Note: Peer is already on destination and DB is updated, so this is not critical
            
            return True
        
        except Exception as e:
            _log_error(f"Error migrating single peer: {e}")
            return False
