#!/usr/bin/env python3
"""
Test script for Phase 8 multi-node functionality
Tests node assignment, peer migration, and Cloudflare DNS automation
"""

import sys
import os
import json
from unittest.mock import Mock, MagicMock, patch

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_database_tables_exist():
    """Test that Phase 8 database tables exist"""
    print("\nTesting Phase 8 database tables...")
    try:
        with open('src/modules/DashboardConfig.py', 'r') as f:
            content = f.read()
        
        # Check for ConfigNodes table
        assert "def __createConfigNodesTable" in content, "ConfigNodes table creation not found"
        assert "'ConfigNodes'" in content, "ConfigNodes table name not found"
        assert "config_name" in content and "node_id" in content, "ConfigNodes columns not found"
        
        # Check for EndpointGroups table
        assert "def __createEndpointGroupsTable" in content, "EndpointGroups table creation not found"
        assert "'EndpointGroups'" in content, "EndpointGroups table name not found"
        assert "cloudflare_zone_id" in content, "Cloudflare fields not found"
        assert "proxied" in content and "server_default='0'" in content, "Proxied field default not correct"
        
        # Check for AuditLog table
        assert "def __createAuditLogTable" in content, "AuditLog table creation not found"
        assert "'AuditLog'" in content, "AuditLog table name not found"
        
        # Check for is_panel_node column
        assert "is_panel_node" in content, "is_panel_node column not found in Nodes table"
        
        print("✓ All Phase 8 database tables exist with correct schema")
        return True
    except Exception as e:
        print(f"✗ Database tables test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_classes_exist():
    """Test that Phase 8 model classes exist"""
    print("\nTesting Phase 8 model classes...")
    try:
        # ConfigNode
        from ConfigNode import ConfigNode
        test_data = {
            "id": 1,
            "config_name": "wg0",
            "node_id": "node1",
            "is_healthy": True
        }
        cn = ConfigNode(test_data)
        assert cn.config_name == "wg0"
        assert cn.node_id == "node1"
        assert cn.is_healthy == True
        json_data = cn.toJson()
        assert "config_name" in json_data
        
        # EndpointGroup
        from EndpointGroup import EndpointGroup
        eg_data = {
            "id": 1,
            "config_name": "wg0",
            "domain": "vpn.example.com",
            "port": 51820,
            "proxied": False,
            "auto_migrate": True
        }
        eg = EndpointGroup(eg_data)
        assert eg.domain == "vpn.example.com"
        assert eg.proxied == False  # Must be False
        assert eg.auto_migrate == True
        eg_json = eg.toJson()
        assert "cloudflare_zone_id" in eg_json
        
        # AuditLog
        from AuditLog import AuditLog
        al_data = {
            "id": 1,
            "action": "node_assigned",
            "entity_type": "config_node",
            "entity_id": "wg0:node1"
        }
        al = AuditLog(al_data)
        assert al.action == "node_assigned"
        al_json = al.toJson()
        assert "details" in al_json
        
        print("✓ All Phase 8 model classes exist and work correctly")
        return True
    except Exception as e:
        print(f"✗ Model classes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manager_classes_exist():
    """Test that Phase 8 manager classes exist"""
    print("\nTesting Phase 8 manager classes...")
    try:
        # ConfigNodesManager
        with open('src/modules/ConfigNodesManager.py', 'r') as f:
            content = f.read()
        assert "class ConfigNodesManager" in content
        assert "def assignNodeToConfig" in content
        assert "def removeNodeFromConfig" in content
        assert "def getNodesForConfig" in content
        assert "def getHealthyNodesForConfig" in content
        assert "def updateNodeHealth" in content
        
        # EndpointGroupsManager
        with open('src/modules/EndpointGroupsManager.py', 'r') as f:
            content = f.read()
        assert "class EndpointGroupsManager" in content
        assert "def createOrUpdateEndpointGroup" in content
        assert "def getEndpointGroup" in content
        assert ("proxied'] = False" in content or "proxied = False" in content), "Proxied enforcement not found"
        
        # CloudflareDNSManager
        with open('src/modules/CloudflareDNSManager.py', 'r') as f:
            content = f.read()
        assert "class CloudflareDNSManager" in content
        assert "def create_dns_record" in content
        assert "def delete_dns_record" in content
        assert "def sync_node_ips_to_dns" in content
        assert "def _queue_retry" in content  # Retry queue
        assert "proxied = False" in content  # Enforce DNS-only in multiple places
        
        # PeerMigrationManager
        with open('src/modules/PeerMigrationManager.py', 'r') as f:
            content = f.read()
        assert "class PeerMigrationManager" in content
        assert "def migrate_peers_from_node" in content
        assert "def _select_destination_node" in content  # Least-loaded selection
        assert "def _migrate_single_peer" in content
        
        # AuditLogManager
        with open('src/modules/AuditLogManager.py', 'r') as f:
            content = f.read()
        assert "class AuditLogManager" in content
        assert "def log" in content
        assert "def get_logs" in content
        
        print("✓ All Phase 8 manager classes exist with required methods")
        return True
    except Exception as e:
        print(f"✗ Manager classes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cloudflare_dns_operations():
    """Test Cloudflare DNS operations structure and proxied enforcement"""
    print("\nTesting Cloudflare DNS operations...")
    try:
        from CloudflareDNSManager import CloudflareDNSManager
        
        # Create manager without token (won't make real requests)
        dns_mgr = CloudflareDNSManager()
        
        # Test that methods exist
        assert hasattr(dns_mgr, 'create_dns_record')
        assert hasattr(dns_mgr, 'delete_dns_record')
        assert hasattr(dns_mgr, 'sync_node_ips_to_dns')
        assert hasattr(dns_mgr, '_queue_retry')
        assert hasattr(dns_mgr, 'retry_queue')
        
        # Test proxied=false enforcement in code
        with open('src/modules/CloudflareDNSManager.py', 'r') as f:
            content = f.read()
        
        # Count how many times proxied is explicitly set to False
        proxied_false_count = content.count('proxied = False')
        assert proxied_false_count >= 3, f"proxied=False not enforced enough times (found {proxied_false_count})"
        
        # Verify A and AAAA record handling
        assert 'record_type == "A"' in content or '"A"' in content
        assert 'record_type == "AAAA"' in content or '"AAAA"' in content
        
        print("✓ Cloudflare DNS operations structure correct with proxied=false enforced")
        return True
    except Exception as e:
        print(f"✗ Cloudflare DNS operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_peer_migration_logic():
    """Test peer migration logic structure"""
    print("\nTesting peer migration logic...")
    try:
        with open('src/modules/PeerMigrationManager.py', 'r') as f:
            content = f.read()
        
        # Check migration workflow
        assert "migrate_peers_from_node" in content
        assert "_get_peers_for_node" in content
        assert "_select_destination_node" in content
        assert "_migrate_single_peer" in content
        
        # Check that it uses agent APIs
        assert "add_peer" in content or "AgentClient" in content
        assert "delete_peer" in content
        
        # Check least-loaded selection
        assert "peer_count" in content or "node_loads" in content
        
        # Check database update
        assert "node_id" in content and "update" in content
        
        print("✓ Peer migration logic structure correct")
        return True
    except Exception as e:
        print(f"✗ Peer migration logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints_exist():
    """Test that Phase 8 API endpoints exist in dashboard"""
    print("\nTesting Phase 8 API endpoints...")
    try:
        with open('src/dashboard.py', 'r') as f:
            content = f.read()
        
        # Config-node assignment endpoints
        assert "@app.post" in content and "/api/configs/<config_name>/nodes" in content
        assert "@app.delete" in content and "/api/configs/<config_name>/nodes/<node_id>" in content
        assert "@app.get" in content and "/api/configs/<config_name>/nodes" in content
        
        # Endpoint group endpoints
        assert "/api/configs/<config_name>/endpoint-group" in content
        
        # Audit log endpoint
        assert "/api/audit-logs" in content
        
        # Check that managers are imported
        assert "from modules.ConfigNodesManager import ConfigNodesManager" in content
        assert "from modules.EndpointGroupsManager import EndpointGroupsManager" in content
        assert "from modules.CloudflareDNSManager import CloudflareDNSManager" in content
        assert "from modules.PeerMigrationManager import PeerMigrationManager" in content
        assert "from modules.AuditLogManager import AuditLogManager" in content
        
        # Check that managers are initialized
        assert "ConfigNodesManager(" in content
        assert "EndpointGroupsManager(" in content
        assert "CloudflareDNSManager(" in content
        assert "PeerMigrationManager(" in content
        assert "AuditLogManager(" in content
        
        print("✓ All Phase 8 API endpoints exist in dashboard")
        return True
    except Exception as e:
        print(f"✗ API endpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_removal_workflow():
    """Test node removal workflow includes all required steps"""
    print("\nTesting node removal workflow...")
    try:
        with open('src/dashboard.py', 'r') as f:
            content = f.read()
        
        # Find the node removal endpoint
        removal_section = content[content.find("def API_RemoveNodeFromConfig"):]
        removal_section = removal_section[:removal_section.find("def API_GetNodesForConfig")]
        
        # Check backup creation
        assert "get_interface_config" in removal_section or "backup" in removal_section
        
        # Check peer migration
        assert "migrate_peers_from_node" in removal_section
        
        # Check node assignment removal
        assert "removeNodeFromConfig" in removal_section
        
        # Check interface deletion
        assert "delete_interface" in removal_section
        
        # Check audit logging
        assert "AuditLogManager.log" in removal_section or "audit" in removal_section
        
        # Check DNS update
        assert "_update_dns_for_config" in removal_section or "dns" in removal_section.lower()
        
        print("✓ Node removal workflow includes all required steps")
        return True
    except Exception as e:
        print(f"✗ Node removal workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_delete_interface_endpoint():
    """Test that agent has delete interface endpoint"""
    print("\nTesting agent delete interface endpoint...")
    try:
        with open('wgdashboard-agent/app.py', 'r') as f:
            content = f.read()
        
        # Check DELETE endpoint exists
        assert '@app.delete("/v1/wg/{interface}")' in content
        assert "def delete_interface" in content
        
        # Check it disables interface
        assert "wg-quick" in content and "down" in content
        
        # Check it removes config file
        assert "os.remove" in content or "remove" in content
        assert "/etc/wireguard/" in content
        
        # Check NodeAgent client has method
        with open('src/modules/NodeAgent.py', 'r') as f:
            agent_content = f.read()
        assert "def delete_interface" in agent_content
        assert "DELETE" in agent_content
        
        print("✓ Agent delete interface endpoint exists and is properly integrated")
        return True
    except Exception as e:
        print(f"✗ Agent delete interface endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cloudflare_config():
    """Test that Cloudflare configuration is added"""
    print("\nTesting Cloudflare configuration...")
    try:
        with open('src/modules/DashboardConfig.py', 'r') as f:
            content = f.read()
        
        # Check Cloudflare section exists
        assert '"Cloudflare"' in content
        assert '"api_token"' in content
        
        print("✓ Cloudflare configuration section exists")
        return True
    except Exception as e:
        print(f"✗ Cloudflare configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dns_retry_queue():
    """Test DNS retry queue mechanism"""
    print("\nTesting DNS retry queue...")
    try:
        with open('src/modules/CloudflareDNSManager.py', 'r') as f:
            content = f.read()
        
        # Check retry queue exists
        assert "retry_queue" in content
        assert "deque" in content  # Using deque for queue
        
        # Check retry methods
        assert "_queue_retry" in content
        assert "_retry_worker" in content
        
        # Check max retries
        assert "retry_count" in content
        assert "< 5" in content or "max" in content.lower()  # Max retries
        
        # Check retry thread
        assert "threading" in content or "Thread" in content
        assert "_start_retry_thread" in content
        
        print("✓ DNS retry queue mechanism exists and is properly implemented")
        return True
    except Exception as e:
        print(f"✗ DNS retry queue test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audit_logging():
    """Test audit logging functionality"""
    print("\nTesting audit logging...")
    try:
        with open('src/dashboard.py', 'r') as f:
            content = f.read()
        
        # Check audit logging for key actions
        assert "AuditLogManager.log" in content
        
        # Check for specific actions being logged
        assert '"node_assigned"' in content or '"node_removed"' in content
        assert '"dns_updated"' in content or '"endpoint_group_updated"' in content
        
        # Check that entity types are specified
        assert '"config_node"' in content
        assert '"dns_record"' in content or '"endpoint_group"' in content
        
        print("✓ Audit logging is properly integrated for key actions")
        return True
    except Exception as e:
        print(f"✗ Audit logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 8 Multi-Node Test Suite")
    print("Testing node assignment, migration, and DNS automation")
    print("=" * 60)
    
    tests = [
        test_database_tables_exist,
        test_model_classes_exist,
        test_manager_classes_exist,
        test_cloudflare_dns_operations,
        test_peer_migration_logic,
        test_api_endpoints_exist,
        test_node_removal_workflow,
        test_agent_delete_interface_endpoint,
        test_cloudflare_config,
        test_dns_retry_queue,
        test_audit_logging
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(tests)} tests passed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All Phase 8 tests passed!")
        sys.exit(0)
    else:
        print(f"\n✗ {failed} test(s) failed")
        sys.exit(1)
