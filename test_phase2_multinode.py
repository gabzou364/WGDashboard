#!/usr/bin/env python3
"""
Test script for Phase 2 multi-node functionality
Tests node selection, IP allocation, and peer routing
"""

import sys
import os
import ipaddress
from unittest.mock import MagicMock, patch

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_node_selector_scoring():
    """Test node selection scoring algorithm"""
    print("\nTesting Node Selector scoring...")
    try:
        from NodeSelector import NodeSelector
        from Node import Node
        
        # Mock NodesManager
        mock_manager = MagicMock()
        selector = NodeSelector(mock_manager)
        
        # Create test nodes with different loads
        node1_data = {
            "id": "node-1",
            "name": "Node 1",
            "enabled": True,
            "max_peers": 100,
            "weight": 100,
            "health_json": '{"wg_dump": {"peers": [' + ','.join(['{}'] * 50) + ']}}'  # 50 peers
        }
        
        node2_data = {
            "id": "node-2",
            "name": "Node 2",
            "enabled": True,
            "max_peers": 100,
            "weight": 100,
            "health_json": '{"wg_dump": {"peers": [' + ','.join(['{}'] * 25) + ']}}'  # 25 peers
        }
        
        node3_data = {
            "id": "node-3",
            "name": "Node 3",
            "enabled": True,
            "max_peers": 50,
            "weight": 100,
            "health_json": '{"wg_dump": {"peers": [' + ','.join(['{}'] * 48) + ']}}'  # 48 peers
        }
        
        node1 = Node(node1_data)
        node2 = Node(node2_data)
        node3 = Node(node3_data)
        
        # Test _getNodeActivePeers
        assert selector._getNodeActivePeers(node1) == 50
        assert selector._getNodeActivePeers(node2) == 25
        assert selector._getNodeActivePeers(node3) == 48
        
        # Mock getEnabledNodes to return our test nodes
        mock_manager.getEnabledNodes.return_value = [node1, node2, node3]
        
        # Test auto selection - should pick node2 (lowest utilization)
        success, selected_node, message = selector._selectNodeAuto()
        assert success is True
        assert selected_node is not None
        assert selected_node.id == "node-2", f"Expected node-2, got {selected_node.id}"
        
        print("✓ Node selector scoring works correctly")
        return True
    except Exception as e:
        print(f"✗ Node selector scoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_node_selector_capacity():
    """Test node selection respects max_peers cap"""
    print("\nTesting Node Selector capacity limits...")
    try:
        from NodeSelector import NodeSelector
        from Node import Node
        
        mock_manager = MagicMock()
        selector = NodeSelector(mock_manager)
        
        # Node at capacity
        node1_data = {
            "id": "node-1",
            "name": "Node 1",
            "enabled": True,
            "max_peers": 50,
            "weight": 100,
            "health_json": '{"wg_dump": {"peers": [' + ','.join(['{}'] * 50) + ']}}'  # At capacity
        }
        
        # Node with space
        node2_data = {
            "id": "node-2",
            "name": "Node 2",
            "enabled": True,
            "max_peers": 50,
            "weight": 100,
            "health_json": '{"wg_dump": {"peers": [' + ','.join(['{}'] * 10) + ']}}'  # Has space
        }
        
        node1 = Node(node1_data)
        node2 = Node(node2_data)
        
        mock_manager.getEnabledNodes.return_value = [node1, node2]
        
        # Should select node2 since node1 is at capacity
        success, selected_node, message = selector._selectNodeAuto()
        assert success is True
        assert selected_node.id == "node-2"
        
        print("✓ Node selector respects capacity limits")
        return True
    except Exception as e:
        print(f"✗ Node selector capacity test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_node_selector_fallback():
    """Test graceful fallback when no nodes available"""
    print("\nTesting Node Selector fallback...")
    try:
        from NodeSelector import NodeSelector
        
        mock_manager = MagicMock()
        selector = NodeSelector(mock_manager)
        
        # No enabled nodes
        mock_manager.getEnabledNodes.return_value = []
        
        success, node, message = selector._selectNodeAuto()
        assert success is False
        assert node is None
        assert "legacy" in message.lower() or "no nodes" in message.lower()
        
        print("✓ Node selector falls back gracefully")
        return True
    except Exception as e:
        print(f"✗ Node selector fallback test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ip_allocation_boundaries():
    """Test IP allocation reserves first host for server"""
    print("\nTesting IP Allocation boundaries...")
    try:
        from IPAllocationManager import IPAllocationManager
        
        # Test _findAvailableIP reserves first usable host
        mock_config = MagicMock()
        manager = IPAllocationManager(mock_config)
        
        # Test with /24 network
        network = ipaddress.ip_network("10.0.1.0/24")
        allocated_ips = set()
        
        # First call should return .2 (skipping .1 which is reserved)
        first_ip = manager._findAvailableIP(network, allocated_ips)
        assert first_ip == "10.0.1.2/24", f"Expected 10.0.1.2/24, got {first_ip}"
        
        # Add .2 to allocated, next should be .3
        allocated_ips.add("10.0.1.2/24")
        second_ip = manager._findAvailableIP(network, allocated_ips)
        assert second_ip == "10.0.1.3/24", f"Expected 10.0.1.3/24, got {second_ip}"
        
        print("✓ IP allocation reserves first host correctly")
        return True
    except Exception as e:
        print(f"✗ IP allocation boundaries test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ip_allocation_exhaustion():
    """Test IP allocation handles pool exhaustion"""
    print("\nTesting IP Allocation exhaustion...")
    try:
        from IPAllocationManager import IPAllocationManager
        
        mock_config = MagicMock()
        manager = IPAllocationManager(mock_config)
        
        # Test with small /30 network (only 2 usable hosts after reserving .1)
        network = ipaddress.ip_network("10.0.1.0/30")
        
        # Allocate all available IPs
        allocated_ips = {"10.0.1.1/30", "10.0.1.2/30"}  # All usable IPs taken
        
        result = manager._findAvailableIP(network, allocated_ips)
        assert result is None, "Should return None when pool exhausted"
        
        print("✓ IP allocation handles exhaustion correctly")
        return True
    except Exception as e:
        print(f"✗ IP allocation exhaustion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_peer_creation_integration():
    """Test peer creation flow with mock agent"""
    print("\nTesting peer creation integration with mock agent...")
    try:
        from NodeAgent import AgentClient
        from Node import Node
        
        # Test that AgentClient can be instantiated
        client = AgentClient("http://test.example.com", "test-secret")
        assert client.agent_url == "http://test.example.com"
        
        # Test HMAC generation for add_peer
        sig = client._generate_hmac("POST", "/wg/wg0/peers", '{"public_key":"test"}', "1234567890")
        assert isinstance(sig, str)
        assert len(sig) == 64
        
        print("✓ Peer creation integration components work")
        return True
    except Exception as e:
        print(f"✗ Peer creation integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Phase 2 Multi-Node Functionality Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Node Selector Scoring", test_node_selector_scoring()))
    results.append(("Node Selector Capacity", test_node_selector_capacity()))
    results.append(("Node Selector Fallback", test_node_selector_fallback()))
    results.append(("IP Allocation Boundaries", test_ip_allocation_boundaries()))
    results.append(("IP Allocation Exhaustion", test_ip_allocation_exhaustion()))
    results.append(("Peer Creation Integration", test_peer_creation_integration()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 60)
    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
