"""
Drift Detection Module
Identifies mismatches between panel database and node agent state
"""
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

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
                current_app.logger.error(msg, exc_info=exc)
            else:
                current_app.logger.error(msg)
        except (RuntimeError, NameError):
            pass


class DriftDetector:
    """Detects configuration drift between panel and node agents"""
    
    def __init__(self, DashboardConfig):
        self.DashboardConfig = DashboardConfig
        self.engine = DashboardConfig.engine
        
    def detectDrift(self, node_id: str, wg_dump_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect drift between panel database and agent-reported WireGuard state
        
        Args:
            node_id: Node ID to check for drift
            wg_dump_data: WireGuard dump data from agent (result of /wg/{iface}/dump)
            
        Returns:
            Dictionary with drift information:
            {
                "has_drift": bool,
                "unknown_peers": [list of peers on node but not in panel],
                "missing_peers": [list of peers in panel but not on node],
                "mismatched_peers": [list of peers with config differences],
                "summary": {
                    "unknown_count": int,
                    "missing_count": int,
                    "mismatched_count": int,
                    "total_issues": int
                }
            }
        """
        try:
            # Get peers from agent dump
            agent_peers = {}
            if wg_dump_data and 'peers' in wg_dump_data:
                for peer in wg_dump_data['peers']:
                    public_key = peer.get('public_key')
                    if public_key:
                        agent_peers[public_key] = peer
            
            # Get peers from database for this node
            db_peers = self._getNodePeersFromDB(node_id)
            
            # Detect unknown peers (on agent but not in panel)
            unknown_peers = []
            for public_key, peer_data in agent_peers.items():
                if public_key not in db_peers:
                    unknown_peers.append({
                        "public_key": public_key,
                        "allowed_ips": peer_data.get('allowed_ips', []),
                        "endpoint": peer_data.get('endpoint'),
                        "persistent_keepalive": peer_data.get('persistent_keepalive', 0)
                    })
            
            # Detect missing peers (in panel but not on agent)
            missing_peers = []
            for public_key, db_peer in db_peers.items():
                if public_key not in agent_peers:
                    missing_peers.append({
                        "public_key": public_key,
                        "name": db_peer.get('name', ''),
                        "allowed_ips": db_peer.get('allowed_ips', []),
                        "peer_id": db_peer.get('id')
                    })
            
            # Detect mismatched peers (present in both but with differences)
            mismatched_peers = []
            for public_key in set(db_peers.keys()) & set(agent_peers.keys()):
                db_peer = db_peers[public_key]
                agent_peer = agent_peers[public_key]
                
                mismatches = self._compareConfiguration(db_peer, agent_peer)
                if mismatches:
                    mismatched_peers.append({
                        "public_key": public_key,
                        "name": db_peer.get('name', ''),
                        "peer_id": db_peer.get('id'),
                        "mismatches": mismatches
                    })
            
            # Build summary
            has_drift = len(unknown_peers) > 0 or len(missing_peers) > 0 or len(mismatched_peers) > 0
            
            result = {
                "has_drift": has_drift,
                "unknown_peers": unknown_peers,
                "missing_peers": missing_peers,
                "mismatched_peers": mismatched_peers,
                "summary": {
                    "unknown_count": len(unknown_peers),
                    "missing_count": len(missing_peers),
                    "mismatched_count": len(mismatched_peers),
                    "total_issues": len(unknown_peers) + len(missing_peers) + len(mismatched_peers)
                },
                "node_id": node_id,
                "detected_at": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            _log_error(f"Error detecting drift for node {node_id}: {e}", exc=e)
            return {
                "has_drift": False,
                "error": str(e),
                "unknown_peers": [],
                "missing_peers": [],
                "mismatched_peers": [],
                "summary": {
                    "unknown_count": 0,
                    "missing_count": 0,
                    "mismatched_count": 0,
                    "total_issues": 0
                }
            }
    
    def _getNodePeersFromDB(self, node_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all peers for a node from database
        
        Returns:
            Dictionary mapping public_key to peer data
        """
        peers_by_public_key = {}
        
        try:
            # Query all peer tables for peers with this node_id
            # Try to find WireGuardPeer table
            from .WireguardConfiguration import WireguardConfiguration
            
            with self.engine.connect() as conn:
                # Get all configuration names
                conf_path = self.DashboardConfig.GetConfig("Server", "wg_conf_path")[1]
                import os
                if not os.path.exists(conf_path):
                    return peers_by_public_key
                
                # Iterate through all configurations
                for filename in os.listdir(conf_path):
                    if filename.endswith('.conf'):
                        conf_name = filename[:-5]
                        
                        # Create configuration object to access peer table
                        try:
                            wg_conf = WireguardConfiguration(name=conf_name)
                            
                            # Query peers for this node
                            peer_query = wg_conf.peerTable.select().where(
                                wg_conf.peerTable.c.node_id == node_id
                            )
                            
                            result = conn.execute(peer_query).mappings().fetchall()
                            
                            for row in result:
                                peer_data = dict(row)
                                public_key = peer_data.get('public_key')
                                if public_key:
                                    # Parse allowed_ips if stored as string
                                    allowed_ips = peer_data.get('allowed_ip', '')
                                    if isinstance(allowed_ips, str):
                                        allowed_ips = [ip.strip() for ip in allowed_ips.split(',') if ip.strip()]
                                    
                                    peers_by_public_key[public_key] = {
                                        'id': peer_data.get('id'),
                                        'name': peer_data.get('name', ''),
                                        'public_key': public_key,
                                        'allowed_ips': allowed_ips,
                                        'persistent_keepalive': int(peer_data.get('keepalive', 0)),
                                        'preshared_key': peer_data.get('preshared_key', '')
                                    }
                        except Exception as e:
                            # Skip configurations that don't exist or have errors
                            continue
            
        except Exception as e:
            _log_error(f"Error getting peers from database for node {node_id}: {e}", exc=e)
        
        return peers_by_public_key
    
    def _compareConfiguration(self, db_peer: Dict[str, Any], agent_peer: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compare peer configurations and return list of mismatches
        
        Returns:
            List of mismatch dictionaries with field, expected, actual
        """
        mismatches = []
        
        # Compare allowed IPs
        db_allowed = set(db_peer.get('allowed_ips', []))
        agent_allowed = set(agent_peer.get('allowed_ips', []))
        
        if db_allowed != agent_allowed:
            mismatches.append({
                "field": "allowed_ips",
                "expected": sorted(list(db_allowed)),
                "actual": sorted(list(agent_allowed))
            })
        
        # Compare persistent keepalive
        db_keepalive = int(db_peer.get('persistent_keepalive', 0))
        agent_keepalive = int(agent_peer.get('persistent_keepalive', 0))
        
        if db_keepalive != agent_keepalive:
            mismatches.append({
                "field": "persistent_keepalive",
                "expected": db_keepalive,
                "actual": agent_keepalive
            })
        
        # Note: We don't compare preshared_key as it's not exposed in wg show dump
        # and endpoint is client-reported, not configuration
        
        return mismatches
    
    def detectDriftForAllNodes(self, nodes_manager) -> Dict[str, Any]:
        """
        Detect drift for all enabled nodes
        
        Args:
            nodes_manager: NodesManager instance
            
        Returns:
            Dictionary mapping node_id to drift report
        """
        results = {}
        
        try:
            enabled_nodes = nodes_manager.getEnabledNodes()
            
            for node in enabled_nodes:
                try:
                    # Get agent client
                    client = nodes_manager.getNodeAgentClient(node.id)
                    if not client:
                        results[node.id] = {
                            "error": "Failed to create agent client",
                            "has_drift": False
                        }
                        continue
                    
                    # Get WireGuard dump from agent
                    success, wg_data = client.get_wg_dump(node.wg_interface)
                    
                    if not success:
                        results[node.id] = {
                            "error": f"Failed to get WireGuard dump: {wg_data}",
                            "has_drift": False
                        }
                        continue
                    
                    # Detect drift
                    drift_report = self.detectDrift(node.id, wg_data)
                    results[node.id] = drift_report
                    
                except Exception as e:
                    _log_error(f"Error detecting drift for node {node.id}: {e}", exc=e)
                    results[node.id] = {
                        "error": str(e),
                        "has_drift": False
                    }
        
        except Exception as e:
            _log_error(f"Error detecting drift for all nodes: {e}", exc=e)
        
        return results
