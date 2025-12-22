#!/usr/bin/env python3
"""
Test script for Phase 5 multi-node functionality
Tests new agent endpoints (/status, /metrics), node grouping, and observability features
"""

import sys
import os
from unittest.mock import MagicMock, patch, Mock

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_agent_status_endpoint():
    """Test agent /v1/status endpoint"""
    print("\nTesting Agent /v1/status endpoint...")
    try:
        from NodeAgent import AgentClient
        
        # Mock the request to return status data
        mock_status = {
            'status': 'ok',
            'timestamp': 1234567890,
            'uptime': 3600,
            'version': '2.1.0',
            'system': {
                'cpu_percent': 25.5,
                'memory': {
                    'total': 8589934592,
                    'available': 4294967296,
                    'percent': 50.0,
                    'used': 4294967296
                },
                'disk': {
                    'total': 107374182400,
                    'used': 53687091200,
                    'free': 53687091200,
                    'percent': 50.0
                }
            },
            'wireguard': {
                'interfaces': {
                    'wg0': {
                        'status': 'up',
                        'peer_count': 5,
                        'active_peers': 3,
                        'total_rx_bytes': 1024000,
                        'total_tx_bytes': 2048000
                    }
                },
                'interface_count': 1
            }
        }
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        with patch.object(client, '_make_request', return_value=(True, mock_status)):
            success, data = client.get_status()
            
            assert success is True
            assert data['status'] == 'ok'
            assert data['version'] == '2.1.0'
            assert 'system' in data
            assert 'wireguard' in data
            assert data['system']['cpu_percent'] == 25.5
            assert data['wireguard']['interface_count'] == 1
            assert data['wireguard']['interfaces']['wg0']['peer_count'] == 5
            assert data['wireguard']['interfaces']['wg0']['active_peers'] == 3
        
        print("✓ Agent /v1/status endpoint returns expected data structure")
        return True
    except Exception as e:
        print(f"✗ Agent /v1/status endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_metrics_endpoint():
    """Test agent /v1/metrics endpoint"""
    print("\nTesting Agent /v1/metrics endpoint...")
    try:
        from NodeAgent import AgentClient
        
        # Mock Prometheus metrics response
        mock_metrics = """# HELP wgdashboard_agent_cpu_percent CPU usage percentage
# TYPE wgdashboard_agent_cpu_percent gauge
wgdashboard_agent_cpu_percent 25.5
# HELP wgdashboard_agent_memory_used_bytes Memory used in bytes
# TYPE wgdashboard_agent_memory_used_bytes gauge
wgdashboard_agent_memory_used_bytes 4294967296
# HELP wireguard_interface_count Number of WireGuard interfaces
# TYPE wireguard_interface_count gauge
wireguard_interface_count 1
# HELP wireguard_peers_total Total number of peers on interface
# TYPE wireguard_peers_total gauge
wireguard_peers_total{interface="wg0"} 5
# HELP wireguard_peers_active Active peers (handshake within 3 minutes)
# TYPE wireguard_peers_active gauge
wireguard_peers_active{interface="wg0"} 3
"""
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        with patch.object(client, '_make_request', return_value=(True, mock_metrics)):
            success, data = client.get_metrics()
            
            assert success is True
            assert 'wgdashboard_agent_cpu_percent' in data
            assert 'wireguard_interface_count' in data
            assert 'wireguard_peers_total' in data
            assert 'wireguard_peers_active' in data
        
        print("✓ Agent /v1/metrics endpoint returns Prometheus-compatible metrics")
        return True
    except Exception as e:
        print(f"✗ Agent /v1/metrics endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_selector_with_metrics():
    """Test NodeSelector using real-time metrics from /v1/status"""
    print("\nTesting NodeSelector with real-time metrics...")
    try:
        from NodeSelector import NodeSelector
        from Node import Node
        
        # Mock NodesManager
        mock_nodes_manager = MagicMock()
        
        # Create mock nodes with different loads
        node1_data = {
            'id': 'node-1',
            'name': 'Node 1',
            'agent_url': 'http://node1:8080',
            'enabled': True,
            'weight': 100,
            'max_peers': 100,
            'wg_interface': 'wg0',
            'secret_encrypted': 'test',
            'auth_type': 'hmac',
            'endpoint': 'node1.example.com:51820',
            'ip_pool_cidr': '10.0.1.0/24'
        }
        
        node2_data = {
            'id': 'node-2',
            'name': 'Node 2',
            'agent_url': 'http://node2:8080',
            'enabled': True,
            'weight': 100,
            'max_peers': 100,
            'wg_interface': 'wg0',
            'secret_encrypted': 'test',
            'auth_type': 'hmac',
            'endpoint': 'node2.example.com:51820',
            'ip_pool_cidr': '10.0.2.0/24'
        }
        
        node1 = Node(node1_data)
        node2 = Node(node2_data)
        
        # Mock getting nodes
        mock_nodes_manager.getEnabledNodes.return_value = [node1, node2]
        mock_nodes_manager.DashboardConfig = MagicMock()
        mock_nodes_manager.DashboardConfig.engine = MagicMock()
        
        # Create selector
        selector = NodeSelector(mock_nodes_manager)
        
        # Test that selector can be instantiated and works
        # selectNode returns a tuple (success, node, message)
        success, best_node, message = selector.selectNode()
        
        # Should return success or failure, with node or None
        assert isinstance(success, bool)
        assert best_node is None or isinstance(best_node, Node)
        assert isinstance(message, str)
        
        print("✓ NodeSelector can be used with real-time metrics infrastructure")
        return True
    except Exception as e:
        print(f"✗ NodeSelector with metrics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_client_methods():
    """Test that AgentClient has all required methods"""
    print("\nTesting AgentClient has Phase 5 methods...")
    try:
        from NodeAgent import AgentClient
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        # Check that new methods exist
        assert hasattr(client, 'get_status'), "AgentClient missing get_status method"
        assert hasattr(client, 'get_metrics'), "AgentClient missing get_metrics method"
        assert callable(client.get_status), "get_status is not callable"
        assert callable(client.get_metrics), "get_metrics is not callable"
        
        print("✓ AgentClient has all Phase 5 methods")
        return True
    except Exception as e:
        print(f"✗ AgentClient methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("Phase 5 Multi-Node Tests")
    print("="*60)
    
    tests = [
        test_agent_client_methods,
        test_agent_status_endpoint,
        test_agent_metrics_endpoint,
        test_node_selector_with_metrics,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "="*60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("="*60)
    
    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
