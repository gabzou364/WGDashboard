"""
Node Selector
Implements load balancing and node selection logic for peer distribution
Phase 5: Added support for node groups and real-time metrics from /v1/status
"""
import json
from typing import Optional, List, Tuple

try:
    from flask import current_app
    _has_flask = True
except ImportError:
    _has_flask = False

try:
    from .Node import Node
except ImportError:
    from Node import Node


def _log_debug(msg):
    """Helper to log debug messages"""
    if _has_flask:
        try:
            current_app.logger.debug(msg)
        except RuntimeError:
            pass  # Not in app context

def _log_info(msg):
    """Helper to log info messages"""
    if _has_flask:
        try:
            current_app.logger.info(msg)
        except RuntimeError:
            pass  # Not in app context

def _log_error(msg):
    """Helper to log error messages"""
    if _has_flask:
        try:
            current_app.logger.error(msg)
        except RuntimeError:
            pass  # Not in app context


class NodeSelector:
    """Handles node selection for peer placement"""
    
    def __init__(self, NodesManager):
        self.NodesManager = NodesManager
    
    def selectNode(self, strategy: str = "auto", group_id: Optional[str] = None) -> Tuple[bool, Optional[Node], str]:
        """
        Select a node for peer placement
        
        Args:
            strategy: Selection strategy ("auto" or specific node_id)
            group_id: Optional group ID to limit selection to nodes in this group (Phase 5)
            
        Returns:
            Tuple of (success: bool, node or None, message)
        """
        if strategy == "auto":
            return self._selectNodeAuto(group_id)
        else:
            # Specific node ID provided
            node = self.NodesManager.getNodeById(strategy)
            if not node:
                return False, None, f"Node {strategy} not found"
            if not node.enabled:
                return False, None, f"Node {node.name} is disabled"
            
            # Check if node is in requested group (if specified)
            if group_id is not None and node.group_id != group_id:
                return False, None, f"Node {node.name} is not in the requested group"
            
            # Check if node is at capacity
            if node.max_peers > 0:
                active_peers = self._getNodeActivePeers(node)
                if active_peers >= node.max_peers:
                    return False, None, f"Node {node.name} is at capacity ({active_peers}/{node.max_peers})"
            
            return True, node, f"Selected node {node.name}"
    
    def _selectNodeAuto(self, group_id: Optional[str] = None) -> Tuple[bool, Optional[Node], str]:
        """
        Auto select best node using load balancing (Phase 5: with group support)
        
        Strategy:
        - Only consider enabled nodes (optionally filtered by group)
        - Skip nodes at or over max_peers cap
        - Incorporate real-time metrics from /v1/status if available (CPU, memory)
        - Score = (active_peers / max_peers) / weight
        - Lower score is better
        - If max_peers is 0 (unlimited), use active_peers / weight
        
        Args:
            group_id: Optional group ID to limit selection to nodes in this group
        
        Returns:
            Tuple of (success: bool, node or None, message)
        """
        try:
            # Get enabled nodes, optionally filtered by group
            if group_id is not None:
                enabled_nodes = self.NodesManager.getEnabledNodesByGroup(group_id)
                _log_debug(f"Selecting from {len(enabled_nodes)} enabled nodes in group {group_id}")
            else:
                enabled_nodes = self.NodesManager.getEnabledNodes()
                _log_debug(f"Selecting from {len(enabled_nodes)} enabled nodes (all groups)")
            
            if not enabled_nodes:
                if group_id:
                    return False, None, f"No enabled nodes in group {group_id}"
                else:
                    # No nodes configured - fallback to legacy mode
                    return False, None, "No nodes configured - using legacy local mode"
            
            candidates = []
            
            for node in enabled_nodes:
                # Get active peer count and system metrics
                active_peers = self._getNodeActivePeers(node)
                system_metrics = self._getNodeSystemMetrics(node)
                
                # Check max_peers soft cap
                if node.max_peers > 0 and active_peers >= node.max_peers:
                    _log_debug(f"Node {node.name} at capacity: {active_peers}/{node.max_peers}")
                    continue
                
                # Calculate base score from peer utilization
                if node.max_peers > 0:
                    # Use utilization percentage divided by weight
                    utilization = active_peers / node.max_peers
                    base_score = utilization / node.weight if node.weight > 0 else utilization
                else:
                    # Unlimited capacity - use raw peer count divided by weight
                    base_score = active_peers / node.weight if node.weight > 0 else active_peers
                
                # Adjust score based on real-time system metrics (Phase 5)
                # Higher CPU/memory usage = higher penalty
                score = self._adjustScoreWithMetrics(base_score, system_metrics)
                
                candidates.append((score, node, active_peers, system_metrics))
                _log_debug(
                    f"Node {node.name}: active={active_peers}, "
                    f"max={node.max_peers}, weight={node.weight}, "
                    f"cpu={system_metrics.get('cpu_percent', 'N/A')}%, "
                    f"mem={system_metrics.get('memory_percent', 'N/A')}%, "
                    f"score={score:.4f}"
                )
            
            if not candidates:
                if group_id:
                    return False, None, f"No available nodes in group {group_id} (all at capacity)"
                else:
                    return False, None, "No available nodes (all at capacity)"
            
            # Sort by score (lower is better) and pick first
            candidates.sort(key=lambda x: x[0])
            selected_node = candidates[0][1]
            
            _log_info(f"Auto-selected node: {selected_node.name} (score: {candidates[0][0]:.4f})")
            return True, selected_node, f"Auto-selected node {selected_node.name}"
            
        except Exception as e:
            _log_error(f"Error in node selection: {e}")
            return False, None, str(e)
    
    def _getNodeActivePeers(self, node: Node) -> int:
        """
        Get count of active peers on a node from health data
        
        Returns:
            Number of active peers (0 if unknown)
        """
        try:
            if node.health_json:
                health_data = json.loads(node.health_json) if isinstance(node.health_json, str) else node.health_json
                
                # Check if we have WireGuard dump data
                if 'wg_dump' in health_data and isinstance(health_data['wg_dump'], dict):
                    peers = health_data['wg_dump'].get('peers', [])
                    return len(peers) if isinstance(peers, list) else 0
                
                # Fallback: check if health data has peer count
                if 'peer_count' in health_data:
                    return int(health_data['peer_count'])
            
            # Default to 0 if no health data
            return 0
            
        except Exception as e:
            _log_error(f"Error getting active peers for node {node.id}: {e}")
            return 0
    
    def _getNodeSystemMetrics(self, node: Node) -> dict:
        """
        Get system metrics from node /v1/status endpoint (Phase 5)
        
        Returns:
            Dict with cpu_percent, memory_percent, and other metrics (empty if unavailable)
        """
        try:
            if node.health_json:
                health_data = json.loads(node.health_json) if isinstance(node.health_json, str) else node.health_json
                
                # Check if we have status data from /v1/status endpoint
                if 'status' in health_data and isinstance(health_data['status'], dict):
                    status = health_data['status']
                    system = status.get('system', {})
                    
                    metrics = {}
                    if 'cpu_percent' in system:
                        metrics['cpu_percent'] = float(system['cpu_percent'])
                    if 'memory' in system and 'percent' in system['memory']:
                        metrics['memory_percent'] = float(system['memory']['percent'])
                    
                    return metrics
            
            return {}
            
        except Exception as e:
            _log_error(f"Error getting system metrics for node {node.id}: {e}")
            return {}
    
    def _adjustScoreWithMetrics(self, base_score: float, system_metrics: dict) -> float:
        """
        Adjust node selection score based on real-time system metrics (Phase 5)
        
        Args:
            base_score: Base score from peer utilization
            system_metrics: Dict with cpu_percent and memory_percent
        
        Returns:
            Adjusted score (lower is better)
        """
        try:
            score = base_score
            
            # Add penalty for high CPU usage
            if 'cpu_percent' in system_metrics:
                cpu = system_metrics['cpu_percent']
                if cpu > 80:
                    # Heavy penalty for very high CPU
                    score += 0.5
                elif cpu > 60:
                    # Moderate penalty for high CPU
                    score += 0.2
                elif cpu > 40:
                    # Small penalty for elevated CPU
                    score += 0.05
            
            # Add penalty for high memory usage
            if 'memory_percent' in system_metrics:
                mem = system_metrics['memory_percent']
                if mem > 85:
                    # Heavy penalty for very high memory
                    score += 0.4
                elif mem > 70:
                    # Moderate penalty for high memory
                    score += 0.15
                elif mem > 50:
                    # Small penalty for elevated memory
                    score += 0.05
            
            return score
            
        except Exception as e:
            _log_error(f"Error adjusting score with metrics: {e}")
            return base_score

