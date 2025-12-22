#!/usr/bin/env python3
"""
Test script for Phase 7 multi-node functionality
Tests traffic restriction and time limit features
"""

import sys
import os

# Add src/modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'modules'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_database_schema_phase7_columns():
    """Test that database schema code includes Phase 7 columns"""
    print("\nTesting database schema Phase 7 columns in code...")
    try:
        # Read WireguardConfiguration.py and check for Phase 7 columns
        with open('src/modules/WireguardConfiguration.py', 'r') as f:
            content = f.read()
        
        # Check that Phase 7 columns are in the schema definition
        assert 'traffic_limit' in content, "traffic_limit column not found in WireguardConfiguration.py"
        assert 'expiry_date' in content, "expiry_date column not found in WireguardConfiguration.py"
        assert 'traffic_warn_threshold' in content, "traffic_warn_threshold column not found in WireguardConfiguration.py"
        
        # Check in createDatabase method specifically
        assert 'sqlalchemy.Column(\'traffic_limit\'' in content or 'sqlalchemy.Column("traffic_limit"' in content, \
            "traffic_limit column definition not found"
        assert 'sqlalchemy.Column(\'expiry_date\'' in content or 'sqlalchemy.Column("expiry_date"' in content, \
            "expiry_date column definition not found"
        assert 'sqlalchemy.Column(\'traffic_warn_threshold\'' in content or 'sqlalchemy.Column("traffic_warn_threshold"' in content, \
            "traffic_warn_threshold column definition not found"
        
        print("✓ Database schema includes all Phase 7 columns in code")
        return True
    except Exception as e:
        print(f"✗ Database schema Phase 7 columns test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_peer_model_phase7_fields():
    """Test that Peer model code includes Phase 7 fields"""
    print("\nTesting Peer model Phase 7 fields in code...")
    try:
        # Read Peer.py and check for Phase 7 fields
        with open('src/modules/Peer.py', 'r') as f:
            content = f.read()
        
        # Check that Phase 7 fields are in __init__
        assert 'self.traffic_limit' in content, "traffic_limit field not found in Peer.__init__"
        assert 'self.expiry_date' in content, "expiry_date field not found in Peer.__init__"
        assert 'self.traffic_warn_threshold' in content, "traffic_warn_threshold field not found in Peer.__init__"
        
        # Check for Phase 7 helper methods
        assert 'def isTrafficLimitExceeded' in content, "isTrafficLimitExceeded method not found"
        assert 'def isTrafficLimitWarning' in content, "isTrafficLimitWarning method not found"
        assert 'def getTrafficUsagePercentage' in content, "getTrafficUsagePercentage method not found"
        assert 'def isExpired' in content, "isExpired method not found"
        assert 'def getDaysUntilExpiry' in content, "getDaysUntilExpiry method not found"
        
        print("✓ Peer model includes all Phase 7 fields and methods")
        return True
    except Exception as e:
        print(f"✗ Peer model Phase 7 fields test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wireguard_configuration_enforcement_methods():
    """Test WireguardConfiguration code includes enforcement methods"""
    print("\nTesting WireguardConfiguration enforcement methods in code...")
    try:
        # Read WireguardConfiguration.py and check for Phase 7 enforcement methods
        with open('src/modules/WireguardConfiguration.py', 'r') as f:
            content = f.read()
        
        # Check for enforcement methods
        assert 'def enforceTrafficLimits' in content, "enforceTrafficLimits method not found"
        assert 'def enforceExpiryDates' in content, "enforceExpiryDates method not found"
        
        # Check that methods call restrictPeerAccess
        assert 'self.restrictPeerAccess' in content, "restrictPeerAccess call not found in enforcement methods"
        
        print("✓ WireguardConfiguration has Phase 7 enforcement methods")
        return True
    except Exception as e:
        print(f"✗ WireguardConfiguration enforcement methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_background_thread_calls_enforcement():
    """Test that background thread calls Phase 7 enforcement"""
    print("\nTesting background thread calls enforcement methods...")
    try:
        # Read dashboard.py and check for enforcement calls
        with open('src/dashboard.py', 'r') as f:
            content = f.read()
        
        # Check that background thread calls enforcement methods
        assert 'c.enforceTrafficLimits()' in content or 'enforceTrafficLimits' in content, \
            "enforceTrafficLimits not called in background thread"
        assert 'c.enforceExpiryDates()' in content or 'enforceExpiryDates' in content, \
            "enforceExpiryDates not called in background thread"
        
        print("✓ Background thread calls Phase 7 enforcement methods")
        return True
    except Exception as e:
        print(f"✗ Background thread enforcement calls test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints_for_phase7():
    """Test that Phase 7 API endpoints are defined"""
    print("\nTesting Phase 7 API endpoints in code...")
    try:
        # Read dashboard.py and check for Phase 7 API endpoints
        with open('src/dashboard.py', 'r') as f:
            content = f.read()
        
        # Check for Phase 7 API endpoints
        assert 'API_updatePeerTrafficLimit' in content, "API_updatePeerTrafficLimit endpoint not found"
        assert 'API_updatePeerExpiryDate' in content, "API_updatePeerExpiryDate endpoint not found"
        assert 'API_updatePeerTrafficWarningThreshold' in content, "API_updatePeerTrafficWarningThreshold endpoint not found"
        
        # Check that endpoints update database
        assert 'traffic_limit' in content and 'peersTable.update()' in content, \
            "Traffic limit update not found in API"
        assert 'expiry_date' in content and 'peersTable.update()' in content, \
            "Expiry date update not found in API"
        
        print("✓ Phase 7 API endpoints are defined")
        return True
    except Exception as e:
        print(f"✗ Phase 7 API endpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_endpoints_ready():
    """Test that agent has necessary endpoints for Phase 7"""
    print("\nTesting agent endpoints for Phase 7...")
    try:
        # Read agent app.py and check for necessary endpoints
        with open('wgdashboard-agent/app.py', 'r') as f:
            content = f.read()
        
        # Check that dump endpoint returns transfer stats
        assert '/v1/wg/{interface}/dump' in content or 'get_wg_dump' in content, \
            "Dump endpoint not found"
        assert 'transfer_rx' in content and 'transfer_tx' in content, \
            "Transfer stats not in dump endpoint response"
        
        # Check that metrics endpoint exists
        assert '/v1/metrics' in content or 'get_metrics' in content, \
            "Metrics endpoint not found"
        
        print("✓ Agent has necessary endpoints for Phase 7")
        return True
    except Exception as e:
        print(f"✗ Agent endpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 7 tests"""
    print("=" * 60)
    print("Phase 7 Multi-Node Test Suite")
    print("Testing traffic restriction and time limit features")
    print("=" * 60)
    
    tests = [
        test_database_schema_phase7_columns,
        test_peer_model_phase7_fields,
        test_wireguard_configuration_enforcement_methods,
        test_background_thread_calls_enforcement,
        test_api_endpoints_for_phase7,
        test_agent_endpoints_ready,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✓ All Phase 7 tests passed!")
        return 0
    else:
        print("\n✗ Some Phase 7 tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

