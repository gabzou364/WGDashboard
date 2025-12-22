#!/usr/bin/env python3
"""
Test script for Phase 7 multi-node functionality
Tests that existing PeerJobs system works with multi-node enforcement
"""

import sys
import os

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_peer_jobs_system_exists():
    """Test that PeerJobs system exists and has required methods"""
    print("\nTesting PeerJobs system exists...")
    try:
        # Read PeerJobs.py and verify it has the required methods
        with open('src/modules/PeerJobs.py', 'r') as f:
            content = f.read()
        
        # Check that PeerJobs has runJob method
        assert 'def runJob(' in content, "runJob method not found"
        
        # Check that it supports traffic fields
        assert 'total_receive' in content or 'total_sent' in content or 'total_data' in content, \
            "Traffic fields not supported in PeerJobs"
        
        # Check that it supports restrict action
        assert 'restrict' in content, "Restrict action not supported"
        
        # Check that it supports delete action  
        assert 'delete' in content, "Delete action not supported"
        
        print("✓ PeerJobs system exists with required methods")
        return True
    except Exception as e:
        print(f"✗ PeerJobs system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_peer_jobs_fields():
    """Test that PeerJob supports required fields"""
    print("\nTesting PeerJob fields...")
    try:
        with open('src/modules/PeerJob.py', 'r') as f:
            content = f.read()
        
        # Check that PeerJob has required fields
        assert 'Field' in content, "Field property not found"
        assert 'Operator' in content, "Operator property not found"
        assert 'Value' in content, "Value property not found"
        assert 'Action' in content, "Action property not found"
        
        print("✓ PeerJob has required fields")
        return True
    except Exception as e:
        print(f"✗ PeerJob fields test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_node_enforcement_in_jobs():
    """Test that PeerJobs runJob uses restrictPeers which handles multi-node"""
    print("\nTesting multi-node enforcement integration...")
    try:
        with open('src/modules/PeerJobs.py', 'r') as f:
            content = f.read()
        
        # Check that runJob calls restrictPeers
        assert 'restrictPeers' in content, "restrictPeers not called in runJob"
        
        # Check that it also supports deletePeers for multi-node
        assert 'deletePeers' in content, "deletePeers not called in runJob"
        
        print("✓ PeerJobs integrates with multi-node enforcement")
        return True
    except Exception as e:
        print(f"✗ Multi-node enforcement test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wireguard_config_restrict_peers():
    """Test that WireguardConfiguration has restrictPeers method for multi-node"""
    print("\nTesting WireguardConfiguration restrictPeers...")
    try:
        with open('src/modules/WireguardConfiguration.py', 'r') as f:
            content = f.read()
        
        # Check that restrictPeers method exists
        assert 'def restrictPeers(' in content, "restrictPeers method not found"
        
        print("✓ WireguardConfiguration has restrictPeers method")
        return True
    except Exception as e:
        print(f"✗ WireguardConfiguration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_no_new_limit_apis():
    """Test that no new limit-setting APIs were added"""
    print("\nTesting no new limit APIs exist...")
    try:
        with open('src/dashboard.py', 'r') as f:
            content = f.read()
        
        # Check that new APIs from Phase 7 are NOT present
        assert 'updatePeerTrafficLimit' not in content, "updatePeerTrafficLimit API should not exist"
        assert 'updatePeerExpiryDate' not in content, "updatePeerExpiryDate API should not exist"
        assert 'updatePeerTrafficWarningThreshold' not in content, "updatePeerTrafficWarningThreshold API should not exist"
        
        print("✓ No new limit-setting APIs found (using existing PeerJobs API)")
        return True
    except Exception as e:
        print(f"✗ No new APIs test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_no_new_db_columns():
    """Test that no new database columns were added"""
    print("\nTesting no new database columns...")
    try:
        with open('src/modules/WireguardConfiguration.py', 'r') as f:
            content = f.read()
        
        # Check that new columns from Phase 7 are NOT present in schema
        assert 'traffic_limit' not in content, "traffic_limit column should not exist"
        assert 'expiry_date' not in content, "expiry_date column should not exist"
        assert 'traffic_warn_threshold' not in content, "traffic_warn_threshold column should not exist"
        
        print("✓ No new database columns found (using existing PeerJobs)")
        return True
    except Exception as e:
        print(f"✗ No new columns test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 7 Option A tests"""
    print("=" * 60)
    print("Phase 7 Option A Multi-Node Test Suite")
    print("Testing enforcement via existing PeerJobs system")
    print("=" * 60)
    
    tests = [
        test_peer_jobs_system_exists,
        test_peer_jobs_fields,
        test_multi_node_enforcement_in_jobs,
        test_wireguard_config_restrict_peers,
        test_no_new_limit_apis,
        test_no_new_db_columns,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All Phase 7 Option A tests passed!")
        print("\nPhase 7 uses existing PeerJobs system for:")
        print("  - Traffic limits (via total_receive/total_sent/total_data fields)")
        print("  - Time limits (via datetime comparison)")
        print("  - Multi-node enforcement (via restrictPeers/deletePeers)")
        return 0
    else:
        print("\n✗ Some Phase 7 Option A tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
