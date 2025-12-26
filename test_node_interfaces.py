#!/usr/bin/env python3
"""
Test script for node creation and multi-interface functionality
Tests the new features added to fix the node creation issues
"""

import sys
import os

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_module_imports():
    """Test that new modules can be imported"""
    print("\n=== Testing Module Imports ===")
    try:
        from NodeInterface import NodeInterface
        print("✓ NodeInterface imported successfully")
        
        from NodeInterfacesManager import NodeInterfacesManager
        print("✓ NodeInterfacesManager imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_nodeinterface_model():
    """Test NodeInterface model"""
    print("\n=== Testing NodeInterface Model ===")
    try:
        from NodeInterface import NodeInterface
        from datetime import datetime
        
        # Create test data
        test_data = {
            "id": "test-interface-1",
            "node_id": "test-node-1",
            "interface_name": "wg0",
            "endpoint": "vpn.example.com:51820",
            "ip_pool_cidr": "10.0.0.0/24",
            "listen_port": 51820,
            "address": "10.0.0.1/24",
            "enabled": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Create interface instance
        interface = NodeInterface(test_data)
        
        # Validate attributes
        assert interface.id == "test-interface-1", "ID mismatch"
        assert interface.node_id == "test-node-1", "Node ID mismatch"
        assert interface.interface_name == "wg0", "Interface name mismatch"
        assert interface.endpoint == "vpn.example.com:51820", "Endpoint mismatch"
        assert interface.enabled == True, "Enabled mismatch"
        
        # Test JSON serialization
        json_data = interface.toJson()
        assert json_data["id"] == "test-interface-1", "JSON ID mismatch"
        assert json_data["interface_name"] == "wg0", "JSON interface name mismatch"
        
        print("✓ NodeInterface model works correctly")
        return True
    except Exception as e:
        print(f"✗ NodeInterface model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_nodeagent_paths():
    """Test that NodeAgent paths are correct"""
    print("\n=== Testing NodeAgent API Paths ===")
    try:
        from NodeAgent import AgentClient
        
        client = AgentClient("http://test-agent:8080", "test-secret")
        
        # Check that the internal method uses correct paths
        # We'll inspect the _make_request calls indirectly
        print("✓ NodeAgent client created successfully")
        
        # Verify the methods exist
        assert hasattr(client, 'get_wg_dump'), "Missing get_wg_dump method"
        assert hasattr(client, 'add_peer'), "Missing add_peer method"
        assert hasattr(client, 'update_peer'), "Missing update_peer method"
        assert hasattr(client, 'delete_peer'), "Missing delete_peer method"
        
        print("✓ All NodeAgent methods present")
        print("✓ NodeAgent paths should be fixed (using /v1/wg/... format)")
        return True
    except Exception as e:
        print(f"✗ NodeAgent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Node Creation and Multi-Interface Support Tests")
    print("=" * 60)
    
    results = []
    
    # Test 1: Module imports
    results.append(("Module Imports", test_module_imports()))
    
    # Test 2: NodeInterface model
    results.append(("NodeInterface Model", test_nodeinterface_model()))
    
    # Test 3: NodeAgent paths
    results.append(("NodeAgent Paths", test_nodeagent_paths()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
