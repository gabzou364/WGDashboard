#!/usr/bin/env python3
"""
Test script for Phase 4 multi-node functionality
Tests drift detection, reconciliation, and per-node overrides
"""

import sys
import os
from unittest.mock import MagicMock, patch

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_drift_detection_no_drift():
    """Test drift detection when there is no drift"""
    print("\nTesting Drift Detection (no drift)...")
    try:
        from DriftDetector import DriftDetector
        
        # Mock DashboardConfig
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.GetConfig = MagicMock(return_value=(True, '/etc/wireguard'))
        
        detector = DriftDetector(mock_config)
        
        # Mock database to return empty peers
        with patch.object(detector, '_getNodePeersFromDB', return_value={}):
            # Agent reports no peers
            wg_dump = {'peers': []}
            
            result = detector.detectDrift('node-1', wg_dump)
            
            assert result['has_drift'] is False
            assert len(result['unknown_peers']) == 0
            assert len(result['missing_peers']) == 0
            assert len(result['mismatched_peers']) == 0
            assert result['summary']['total_issues'] == 0
        
        print("✓ Drift detection correctly reports no drift")
        return True
    except Exception as e:
        print(f"✗ Drift detection (no drift) test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_drift_detection_unknown_peers():
    """Test drift detection for unknown peers on node"""
    print("\nTesting Drift Detection (unknown peers)...")
    try:
        from DriftDetector import DriftDetector
        
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.GetConfig = MagicMock(return_value=(True, '/etc/wireguard'))
        
        detector = DriftDetector(mock_config)
        
        # Mock database to return no peers
        with patch.object(detector, '_getNodePeersFromDB', return_value={}):
            # Agent reports a peer that's not in DB
            wg_dump = {
                'peers': [
                    {
                        'public_key': 'unknown_peer_key_12345',
                        'allowed_ips': ['10.0.1.100/32'],
                        'persistent_keepalive': 25
                    }
                ]
            }
            
            result = detector.detectDrift('node-1', wg_dump)
            
            assert result['has_drift'] is True
            assert len(result['unknown_peers']) == 1
            assert result['unknown_peers'][0]['public_key'] == 'unknown_peer_key_12345'
            assert len(result['missing_peers']) == 0
            assert len(result['mismatched_peers']) == 0
            assert result['summary']['total_issues'] == 1
        
        print("✓ Drift detection correctly identifies unknown peers")
        return True
    except Exception as e:
        print(f"✗ Drift detection (unknown peers) test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_drift_detection_missing_peers():
    """Test drift detection for missing peers on node"""
    print("\nTesting Drift Detection (missing peers)...")
    try:
        from DriftDetector import DriftDetector
        
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.GetConfig = MagicMock(return_value=(True, '/etc/wireguard'))
        
        detector = DriftDetector(mock_config)
        
        # Mock database to return a peer
        db_peers = {
            'peer_key_abc123': {
                'id': 'peer-1',
                'name': 'Test Peer',
                'public_key': 'peer_key_abc123',
                'allowed_ips': ['10.0.1.2/32'],
                'persistent_keepalive': 25
            }
        }
        
        with patch.object(detector, '_getNodePeersFromDB', return_value=db_peers):
            # Agent reports no peers
            wg_dump = {'peers': []}
            
            result = detector.detectDrift('node-1', wg_dump)
            
            assert result['has_drift'] is True
            assert len(result['unknown_peers']) == 0
            assert len(result['missing_peers']) == 1
            assert result['missing_peers'][0]['public_key'] == 'peer_key_abc123'
            assert result['missing_peers'][0]['name'] == 'Test Peer'
            assert len(result['mismatched_peers']) == 0
            assert result['summary']['total_issues'] == 1
        
        print("✓ Drift detection correctly identifies missing peers")
        return True
    except Exception as e:
        print(f"✗ Drift detection (missing peers) test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_drift_detection_mismatched_peers():
    """Test drift detection for mismatched peer configurations"""
    print("\nTesting Drift Detection (mismatched configurations)...")
    try:
        from DriftDetector import DriftDetector
        
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.GetConfig = MagicMock(return_value=(True, '/etc/wireguard'))
        
        detector = DriftDetector(mock_config)
        
        # Mock database peer with specific configuration
        db_peers = {
            'peer_key_xyz789': {
                'id': 'peer-2',
                'name': 'Mismatched Peer',
                'public_key': 'peer_key_xyz789',
                'allowed_ips': ['10.0.1.2/32', '10.0.1.3/32'],
                'persistent_keepalive': 25
            }
        }
        
        with patch.object(detector, '_getNodePeersFromDB', return_value=db_peers):
            # Agent reports same peer but with different config
            wg_dump = {
                'peers': [
                    {
                        'public_key': 'peer_key_xyz789',
                        'allowed_ips': ['10.0.1.2/32'],  # Missing 10.0.1.3/32
                        'persistent_keepalive': 30  # Different keepalive
                    }
                ]
            }
            
            result = detector.detectDrift('node-1', wg_dump)
            
            assert result['has_drift'] is True
            assert len(result['unknown_peers']) == 0
            assert len(result['missing_peers']) == 0
            assert len(result['mismatched_peers']) == 1
            assert result['mismatched_peers'][0]['public_key'] == 'peer_key_xyz789'
            assert len(result['mismatched_peers'][0]['mismatches']) == 2  # Both allowed_ips and keepalive
            assert result['summary']['total_issues'] == 1
            
            # Check specific mismatches
            mismatches = {m['field']: m for m in result['mismatched_peers'][0]['mismatches']}
            assert 'allowed_ips' in mismatches
            assert 'persistent_keepalive' in mismatches
            assert set(mismatches['allowed_ips']['expected']) == {'10.0.1.2/32', '10.0.1.3/32'}
            assert set(mismatches['allowed_ips']['actual']) == {'10.0.1.2/32'}
            assert mismatches['persistent_keepalive']['expected'] == 25
            assert mismatches['persistent_keepalive']['actual'] == 30
        
        print("✓ Drift detection correctly identifies mismatched configurations")
        return True
    except Exception as e:
        print(f"✗ Drift detection (mismatched peers) test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_drift_detection_combined():
    """Test drift detection with multiple types of drift"""
    print("\nTesting Drift Detection (combined drift types)...")
    try:
        from DriftDetector import DriftDetector
        
        mock_config = MagicMock()
        mock_config.engine = MagicMock()
        mock_config.GetConfig = MagicMock(return_value=(True, '/etc/wireguard'))
        
        detector = DriftDetector(mock_config)
        
        # Mock database with two peers
        db_peers = {
            'peer_in_db_1': {
                'id': 'peer-1',
                'name': 'DB Peer 1',
                'public_key': 'peer_in_db_1',
                'allowed_ips': ['10.0.1.2/32'],
                'persistent_keepalive': 25
            },
            'peer_in_db_2': {
                'id': 'peer-2',
                'name': 'DB Peer 2',
                'public_key': 'peer_in_db_2',
                'allowed_ips': ['10.0.1.3/32'],
                'persistent_keepalive': 25
            }
        }
        
        with patch.object(detector, '_getNodePeersFromDB', return_value=db_peers):
            # Agent reports one matching, one unknown, and missing one
            wg_dump = {
                'peers': [
                    # peer_in_db_1 matches (no drift)
                    {
                        'public_key': 'peer_in_db_1',
                        'allowed_ips': ['10.0.1.2/32'],
                        'persistent_keepalive': 25
                    },
                    # peer_unknown not in DB (unknown)
                    {
                        'public_key': 'peer_unknown',
                        'allowed_ips': ['10.0.1.100/32'],
                        'persistent_keepalive': 0
                    }
                    # peer_in_db_2 is missing from agent
                ]
            }
            
            result = detector.detectDrift('node-1', wg_dump)
            
            assert result['has_drift'] is True
            assert len(result['unknown_peers']) == 1
            assert result['unknown_peers'][0]['public_key'] == 'peer_unknown'
            assert len(result['missing_peers']) == 1
            assert result['missing_peers'][0]['public_key'] == 'peer_in_db_2'
            assert len(result['mismatched_peers']) == 0
            assert result['summary']['total_issues'] == 2
        
        print("✓ Drift detection correctly handles combined drift types")
        return True
    except Exception as e:
        print(f"✗ Drift detection (combined) test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_node_overrides():
    """Test per-node override fields"""
    print("\nTesting Per-Node Overrides...")
    try:
        from Node import Node
        
        # Create node with override fields
        node_data = {
            'id': 'node-1',
            'name': 'Test Node',
            'agent_url': 'http://agent:8080',
            'wg_interface': 'wg0',
            'enabled': True,
            'override_listen_port': 51821,
            'override_dns': '8.8.8.8',
            'override_mtu': 1380,
            'override_keepalive': 30,
            'override_endpoint_allowed_ip': '0.0.0.0/0,::/0'
        }
        
        node = Node(node_data)
        
        # Verify override fields are stored
        assert node.override_listen_port == 51821
        assert node.override_dns == '8.8.8.8'
        assert node.override_mtu == 1380
        assert node.override_keepalive == 30
        assert node.override_endpoint_allowed_ip == '0.0.0.0/0,::/0'
        
        # Verify JSON serialization includes overrides
        json_data = node.toJson()
        assert json_data['override_listen_port'] == 51821
        assert json_data['override_dns'] == '8.8.8.8'
        assert json_data['override_mtu'] == 1380
        
        print("✓ Per-node overrides work correctly")
        return True
    except Exception as e:
        print(f"✗ Per-node overrides test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_syncconf_method():
    """Test that AgentClient has syncconf method"""
    print("\nTesting AgentClient syncconf method...")
    try:
        from NodeAgent import AgentClient
        
        client = AgentClient('http://test:8080', 'test-secret')
        
        # Verify syncconf method exists
        assert hasattr(client, 'syncconf')
        assert callable(client.syncconf)
        
        print("✓ AgentClient syncconf method exists")
        return True
    except Exception as e:
        print(f"✗ AgentClient syncconf test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Phase 4 Multi-Node Feature Tests")
    print("=" * 60)
    
    tests = [
        test_drift_detection_no_drift,
        test_drift_detection_unknown_peers,
        test_drift_detection_missing_peers,
        test_drift_detection_mismatched_peers,
        test_drift_detection_combined,
        test_node_overrides,
        test_agent_syncconf_method,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("✓ All Phase 4 tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
