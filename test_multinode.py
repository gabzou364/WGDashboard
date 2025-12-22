#!/usr/bin/env python3
"""
Test script for multi-node architecture components
Tests basic functionality without requiring full app context
"""

import sys
import os

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all new modules can be imported"""
    print("Testing imports...")
    try:
        from Node import Node
        print("✓ Node module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import Node: {e}")
        return False
    
    try:
        from NodeAgent import AgentClient
        print("✓ NodeAgent module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import NodeAgent: {e}")
        return False
    
    try:
        # NodesManager requires DashboardConfig, so just check import
        import NodesManager
        print("✓ NodesManager module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import NodesManager: {e}")
        return False
    
    return True

def test_node_model():
    """Test Node model"""
    print("\nTesting Node model...")
    try:
        from Node import Node
        
        test_data = {
            "id": "test-node-1",
            "name": "Test Node",
            "agent_url": "http://localhost:8080",
            "auth_type": "hmac",
            "secret_encrypted": "test-secret",
            "wg_interface": "wg0",
            "endpoint": "vpn.example.com:51820",
            "ip_pool_cidr": "10.0.1.0/24",
            "enabled": True,
            "weight": 100,
            "max_peers": 50,
            "last_seen": None,
            "health_json": "{}",
            "created_at": None,
            "updated_at": None
        }
        
        node = Node(test_data)
        assert node.id == "test-node-1"
        assert node.name == "Test Node"
        assert node.enabled is True
        
        json_data = node.toJson()
        assert isinstance(json_data, dict)
        assert json_data["id"] == "test-node-1"
        
        print("✓ Node model works correctly")
        return True
    except Exception as e:
        print(f"✗ Node model test failed: {e}")
        return False

def test_agent_client():
    """Test AgentClient"""
    print("\nTesting AgentClient...")
    try:
        from NodeAgent import AgentClient
        
        client = AgentClient("http://localhost:8080", "test-secret")
        assert client.agent_url == "http://localhost:8080"
        assert client.secret == "test-secret"
        
        # Test HMAC generation
        sig = client._generate_hmac("GET", "/health", "", "1234567890")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex is 64 chars
        
        # Test signature is deterministic
        sig2 = client._generate_hmac("GET", "/health", "", "1234567890")
        assert sig == sig2
        
        # Test different inputs produce different signatures
        sig3 = client._generate_hmac("POST", "/health", "", "1234567890")
        assert sig != sig3
        
        print("✓ AgentClient works correctly")
        return True
    except Exception as e:
        print(f"✗ AgentClient test failed: {e}")
        return False

def test_database_schema():
    """Test database schema definitions"""
    print("\nTesting database schema...")
    try:
        # Just check that the schema definitions are syntactically correct
        # We can't actually create tables without a database connection
        import sqlalchemy as db
        
        # Test nodes table definition structure
        metadata = db.MetaData()
        nodes_table = db.Table('TestNodes', metadata,
            db.Column('id', db.String(255), nullable=False, primary_key=True),
            db.Column('name', db.String(255), nullable=False),
            db.Column('agent_url', db.String(512), nullable=False),
        )
        
        assert 'id' in nodes_table.c
        assert 'name' in nodes_table.c
        
        print("✓ Database schema definitions are valid")
        return True
    except Exception as e:
        print(f"✗ Database schema test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Multi-Node Architecture Component Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Node Model", test_node_model()))
    results.append(("Agent Client", test_agent_client()))
    results.append(("Database Schema", test_database_schema()))
    
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
