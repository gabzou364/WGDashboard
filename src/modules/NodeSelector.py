"""
Node Selector
Implements load balancing and node selection logic for peer distribution
"""
import json
from typing import Optional, List, Tuple
from flask import current_app
from .Node import Node


class NodeSelector:
    """Handles node selection for peer placement"""
    
    def __init__(self, NodesManager):
        self.NodesManager = NodesManager
    
    def selectNode(self, strategy: str = "auto") -> Tuple[bool, Optional[Node], str]:
        """
        Select a node for peer placement
        
        Args:
            strategy: Selection strategy ("auto" or specific node_id)
            
        Returns:
            Tuple of (success: bool, node or None, message)
        """
        if strategy == "auto":
            return self._selectNodeAuto()
        else:
            # Specific node ID provided
            node = self.NodesManager.getNodeById(strategy)
            if not node:
                return False, None, f"Node {strategy} not found"
            if not node.enabled:
                return False, None, f"Node {node.name} is disabled"
            
            # Check if node is at capacity
            if node.max_peers > 0:
                active_peers = self._getNodeActivePeers(node)
                if active_peers >= node.max_peers:
                    return False, None, f"Node {node.name} is at capacity ({active_peers}/{node.max_peers})"
            
            return True, node, f"Selected node {node.name}"
    
    def _selectNodeAuto(self) -> Tuple[bool, Optional[Node], str]:
        """
        Auto select best node using load balancing
        
        Strategy:
        - Only consider enabled nodes
        - Skip nodes at or over max_peers cap
        - Score = (active_peers / max_peers) / weight
        - Lower score is better
        - If max_peers is 0 (unlimited), use active_peers / weight
        
        Returns:
            Tuple of (success: bool, node or None, message)
        """
        try:
            enabled_nodes = self.NodesManager.getEnabledNodes()
            
            if not enabled_nodes:
                # No nodes configured - fallback to legacy mode
                return False, None, "No nodes configured - using legacy local mode"
            
            candidates = []
            
            for node in enabled_nodes:
                # Get active peer count from health data
                active_peers = self._getNodeActivePeers(node)
                
                # Check max_peers soft cap
                if node.max_peers > 0 and active_peers >= node.max_peers:
                    current_app.logger.debug(f"Node {node.name} at capacity: {active_peers}/{node.max_peers}")
                    continue
                
                # Calculate score
                if node.max_peers > 0:
                    # Use utilization percentage divided by weight
                    utilization = active_peers / node.max_peers
                    score = utilization / node.weight if node.weight > 0 else utilization
                else:
                    # Unlimited capacity - use raw peer count divided by weight
                    score = active_peers / node.weight if node.weight > 0 else active_peers
                
                candidates.append((score, node))
                current_app.logger.debug(
                    f"Node {node.name}: active={active_peers}, "
                    f"max={node.max_peers}, weight={node.weight}, score={score:.4f}"
                )
            
            if not candidates:
                return False, None, "No available nodes (all at capacity)"
            
            # Sort by score (lower is better) and pick first
            candidates.sort(key=lambda x: x[0])
            selected_node = candidates[0][1]
            
            current_app.logger.info(f"Auto-selected node: {selected_node.name}")
            return True, selected_node, f"Auto-selected node {selected_node.name}"
            
        except Exception as e:
            current_app.logger.error(f"Error in node selection: {e}")
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
            current_app.logger.error(f"Error getting active peers for node {node.id}: {e}")
            return 0
