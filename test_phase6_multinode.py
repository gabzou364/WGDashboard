#!/usr/bin/env python3
"""
Test script for Phase 6 multi-node functionality
Tests interface-level configuration management including agent endpoints, 
panel integration, and synchronization workflows
"""

import sys
import os
from unittest.mock import MagicMock, patch, Mock

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_agent_client_interface_methods():
    """Test that AgentClient has new Phase 6 methods"""
    print("\nTesting AgentClient interface methods...")
    try:
        from NodeAgent import AgentClient
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        # Check that all Phase 6 methods exist
        assert hasattr(client, 'get_interface_config'), "Missing get_interface_config method"
        assert hasattr(client, 'set_interface_config'), "Missing set_interface_config method"
        assert hasattr(client, 'enable_interface'), "Missing enable_interface method"
        assert hasattr(client, 'disable_interface'), "Missing disable_interface method"
        
        # Verify methods are callable
        assert callable(client.get_interface_config), "get_interface_config not callable"
        assert callable(client.set_interface_config), "set_interface_config not callable"
        assert callable(client.enable_interface), "enable_interface not callable"
        assert callable(client.disable_interface), "disable_interface not callable"
        
        print("✓ AgentClient has all Phase 6 interface management methods")
        return True
    except Exception as e:
        print(f"✗ AgentClient interface methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_model_interface_fields():
    """Test that Node model includes Phase 6 fields"""
    print("\nTesting Node model interface fields...")
    try:
        from Node import Node
        
        # Create a node with Phase 6 fields
        node_data = {
            'id': 'test-node-1',
            'name': 'Test Node',
            'agent_url': 'http://test:8080',
            'secret_encrypted': 'test-secret',
            'wg_interface': 'wg0',
            'private_key_encrypted': 'test-private-key-encrypted',
            'post_up': 'iptables -A FORWARD -i wg0 -j ACCEPT',
            'pre_down': 'iptables -D FORWARD -i wg0 -j ACCEPT',
            'override_listen_port': 51820
        }
        
        node = Node(node_data)
        
        # Check that Phase 6 fields are set
        assert node.private_key_encrypted == 'test-private-key-encrypted', "private_key_encrypted not set"
        assert node.post_up == 'iptables -A FORWARD -i wg0 -j ACCEPT', "post_up not set"
        assert node.pre_down == 'iptables -D FORWARD -i wg0 -j ACCEPT', "pre_down not set"
        
        # Check JSON serialization includes Phase 6 fields
        json_data = node.toJson()
        assert 'private_key_encrypted' in json_data, "private_key_encrypted not in JSON"
        assert 'post_up' in json_data, "post_up not in JSON"
        assert 'pre_down' in json_data, "pre_down not in JSON"
        assert json_data['private_key_encrypted'] == 'test-private-key-encrypted'
        assert json_data['post_up'] == 'iptables -A FORWARD -i wg0 -j ACCEPT'
        assert json_data['pre_down'] == 'iptables -D FORWARD -i wg0 -j ACCEPT'
        
        print("✓ Node model includes all Phase 6 interface fields")
        return True
    except Exception as e:
        print(f"✗ Node model interface fields test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nodes_manager_interface_methods():
    """Test that NodesManager has Phase 6 interface management methods"""
    print("\nTesting NodesManager interface management methods...")
    try:
        from NodesManager import NodesManager
        
        # Create a mock DashboardConfig
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.nodesTable = MagicMock()
        
        manager = NodesManager(mock_config)
        
        # Check that all Phase 6 methods exist
        assert hasattr(manager, 'syncNodeInterfaceConfig'), "Missing syncNodeInterfaceConfig method"
        assert hasattr(manager, 'getNodeInterfaceConfig'), "Missing getNodeInterfaceConfig method"
        assert hasattr(manager, 'enableNodeInterface'), "Missing enableNodeInterface method"
        assert hasattr(manager, 'disableNodeInterface'), "Missing disableNodeInterface method"
        
        # Verify methods are callable
        assert callable(manager.syncNodeInterfaceConfig), "syncNodeInterfaceConfig not callable"
        assert callable(manager.getNodeInterfaceConfig), "getNodeInterfaceConfig not callable"
        assert callable(manager.enableNodeInterface), "enableNodeInterface not callable"
        assert callable(manager.disableNodeInterface), "disableNodeInterface not callable"
        
        print("✓ NodesManager has all Phase 6 interface management methods")
        return True
    except Exception as e:
        print(f"✗ NodesManager interface management methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_get_interface_config_endpoint():
    """Test agent GET /v1/wg/{interface}/config endpoint structure"""
    print("\nTesting Agent GET /v1/wg/{interface}/config endpoint...")
    try:
        from NodeAgent import AgentClient
        
        # Mock response from agent
        mock_config = {
            'interface': 'wg0',
            'config': {
                'private_key': 'test-private-key',
                'listen_port': 51820,
                'address': '10.0.0.1/24',
                'post_up': 'iptables -A FORWARD -i wg0 -j ACCEPT',
                'pre_down': 'iptables -D FORWARD -i wg0 -j ACCEPT',
                'mtu': 1420,
                'dns': '1.1.1.1',
                'table': 'auto',
                'raw_config': '[Interface]\nPrivateKey = test-private-key\n...'
            }
        }
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        with patch.object(client, '_make_request', return_value=(True, mock_config)):
            success, data = client.get_interface_config('wg0')
            
            assert success is True, "Request failed"
            assert 'interface' in data, "Missing 'interface' field"
            assert 'config' in data, "Missing 'config' field"
            assert data['interface'] == 'wg0', "Incorrect interface name"
            
            config = data['config']
            assert 'private_key' in config, "Missing private_key"
            assert 'listen_port' in config, "Missing listen_port"
            assert 'address' in config, "Missing address"
            assert 'post_up' in config, "Missing post_up"
            assert 'pre_down' in config, "Missing pre_down"
            assert 'raw_config' in config, "Missing raw_config"
            assert config['listen_port'] == 51820, "Incorrect listen_port"
        
        print("✓ Agent GET /v1/wg/{interface}/config endpoint returns expected structure")
        return True
    except Exception as e:
        print(f"✗ Agent GET /v1/wg/{interface}/config endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_set_interface_config_endpoint():
    """Test agent PUT /v1/wg/{interface}/config endpoint structure"""
    print("\nTesting Agent PUT /v1/wg/{interface}/config endpoint...")
    try:
        from NodeAgent import AgentClient
        
        # Mock response from agent
        mock_response = {
            'status': 'success',
            'message': 'Interface configuration updated successfully',
            'reloaded': True
        }
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        config_data = {
            'private_key': 'new-private-key',
            'listen_port': 51821,
            'address': '10.0.0.1/24',
            'post_up': 'iptables -A FORWARD -i wg0 -j ACCEPT',
            'pre_down': 'iptables -D FORWARD -i wg0 -j ACCEPT'
        }
        
        with patch.object(client, '_make_request', return_value=(True, mock_response)):
            success, data = client.set_interface_config('wg0', config_data)
            
            assert success is True, "Request failed"
            assert 'status' in data, "Missing 'status' field"
            assert 'message' in data, "Missing 'message' field"
            assert data['status'] == 'success', "Status not success"
            assert 'reloaded' in data, "Missing 'reloaded' field"
        
        print("✓ Agent PUT /v1/wg/{interface}/config endpoint works correctly")
        return True
    except Exception as e:
        print(f"✗ Agent PUT /v1/wg/{interface}/config endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_enable_disable_interface():
    """Test agent enable/disable interface endpoints"""
    print("\nTesting Agent enable/disable interface endpoints...")
    try:
        from NodeAgent import AgentClient
        
        client = AgentClient('http://test-node:8080', 'test-secret')
        
        # Test enable endpoint
        mock_enable_response = {
            'status': 'success',
            'message': 'Interface wg0 enabled successfully',
            'was_down': True
        }
        
        with patch.object(client, '_make_request', return_value=(True, mock_enable_response)):
            success, data = client.enable_interface('wg0')
            
            assert success is True, "Enable request failed"
            assert data['status'] == 'success', "Enable status not success"
            assert 'was_down' in data, "Missing was_down field"
        
        # Test disable endpoint
        mock_disable_response = {
            'status': 'success',
            'message': 'Interface wg0 disabled successfully',
            'was_up': True
        }
        
        with patch.object(client, '_make_request', return_value=(True, mock_disable_response)):
            success, data = client.disable_interface('wg0')
            
            assert success is True, "Disable request failed"
            assert data['status'] == 'success', "Disable status not success"
            assert 'was_up' in data, "Missing was_up field"
        
        print("✓ Agent enable/disable interface endpoints work correctly")
        return True
    except Exception as e:
        print(f"✗ Agent enable/disable interface endpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_interface_sync_workflow():
    """Test complete interface sync workflow from panel to agent"""
    print("\nTesting node interface sync workflow...")
    try:
        from NodesManager import NodesManager
        from Node import Node
        
        # Create a mock DashboardConfig
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.nodesTable = MagicMock()
        
        manager = NodesManager(mock_config)
        
        # Mock node with interface configuration
        mock_node = Node({
            'id': 'test-node-1',
            'name': 'Test Node',
            'agent_url': 'http://test:8080',
            'secret_encrypted': 'test-secret',
            'wg_interface': 'wg0',
            'private_key_encrypted': 'test-private-key',
            'override_listen_port': 51820,
            'post_up': 'iptables -A FORWARD -i wg0 -j ACCEPT',
            'pre_down': 'iptables -D FORWARD -i wg0 -j ACCEPT',
            'override_dns': '1.1.1.1',
            'override_mtu': 1420
        })
        
        # Mock getNodeById to return our test node
        with patch.object(manager, 'getNodeById', return_value=mock_node):
            # Mock AgentClient
            with patch('NodesManager.AgentClient') as MockAgentClient:
                mock_client_instance = MagicMock()
                mock_client_instance.set_interface_config.return_value = (True, {
                    'status': 'success',
                    'message': 'Interface configuration synchronized successfully'
                })
                MockAgentClient.return_value = mock_client_instance
                
                # Test sync
                success, message = manager.syncNodeInterfaceConfig('test-node-1')
                
                assert success is True, f"Sync failed: {message}"
                assert "synchronized successfully" in message.lower(), f"Unexpected message: {message}"
                
                # Verify that set_interface_config was called with correct data
                mock_client_instance.set_interface_config.assert_called_once()
                call_args = mock_client_instance.set_interface_config.call_args
                assert call_args[0][0] == 'wg0', "Wrong interface name"
                
                config_data = call_args[0][1]
                assert config_data['private_key'] == 'test-private-key', "Wrong private key"
                assert config_data['listen_port'] == 51820, "Wrong listen port"
                assert config_data['post_up'] == 'iptables -A FORWARD -i wg0 -j ACCEPT', "Wrong post_up"
                assert config_data['pre_down'] == 'iptables -D FORWARD -i wg0 -j ACCEPT', "Wrong pre_down"
                assert config_data['dns'] == '1.1.1.1', "Wrong DNS"
                assert config_data['mtu'] == 1420, "Wrong MTU"
        
        print("✓ Node interface sync workflow works correctly")
        return True
    except Exception as e:
        print(f"✗ Node interface sync workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_schema_updates():
    """Test that database schema includes Phase 6 columns"""
    print("\nTesting database schema updates...")
    try:
        # This is a structural test - just verify the columns are defined in DashboardConfig
        import importlib.util
        
        spec = importlib.util.spec_from_file_location(
            "DashboardConfig",
            os.path.join(os.path.dirname(__file__), 'src', 'modules', 'DashboardConfig.py')
        )
        config_module = importlib.util.module_from_spec(spec)
        
        # Read the file and check for Phase 6 columns
        config_file_path = os.path.join(os.path.dirname(__file__), 'src', 'modules', 'DashboardConfig.py')
        with open(config_file_path, 'r') as f:
            config_content = f.read()
        
        # Check for Phase 6 columns
        assert 'private_key_encrypted' in config_content, "Missing private_key_encrypted column"
        assert 'post_up' in config_content, "Missing post_up column"
        assert 'pre_down' in config_content, "Missing pre_down column"
        assert '# Interface-level configuration (Phase 6)' in config_content, "Missing Phase 6 comment"
        
        print("✓ Database schema includes all Phase 6 columns")
        return True
    except Exception as e:
        print(f"✗ Database schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 6 tests"""
    print("=" * 60)
    print("Phase 6 Multi-Node Interface Replication Tests")
    print("=" * 60)
    
    tests = [
        test_agent_client_interface_methods,
        test_node_model_interface_fields,
        test_nodes_manager_interface_methods,
        test_agent_get_interface_config_endpoint,
        test_agent_set_interface_config_endpoint,
        test_agent_enable_disable_interface,
        test_node_interface_sync_workflow,
        test_database_schema_updates,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All Phase 6 tests passed!")
        return 0
    else:
        print("\n✗ Some Phase 6 tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
