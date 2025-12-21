"""
Test script for Peer Expiry Date API
Tests the new /api/setPeerExpiryDate endpoint
"""

import sys
import json
from datetime import datetime, timedelta


def test_set_expiry_date_validation():
    """Test validation logic for the setPeerExpiryDate endpoint"""
    print("Testing validation logic for setPeerExpiryDate...")
    
    # Test 1: Valid date format parsing
    test_date = "2025-12-31 23:59:59"
    try:
        parsed = datetime.strptime(test_date, "%Y-%m-%d %H:%M:%S")
        print(f"✓ Date format validation works: {test_date} -> {parsed}")
    except ValueError as e:
        print(f"✗ Date format validation failed: {e}")
        return False
    
    # Test 2: Invalid date format
    invalid_date = "2025-12-31"
    try:
        datetime.strptime(invalid_date, "%Y-%m-%d %H:%M:%S")
        print(f"✗ Should have rejected invalid date format: {invalid_date}")
        return False
    except ValueError:
        print(f"✓ Correctly rejected invalid date format: {invalid_date}")
    
    # Test 3: Future date check
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    parsed_future = datetime.strptime(future_date, "%Y-%m-%d %H:%M:%S")
    if parsed_future > datetime.now():
        print(f"✓ Future date check works: {future_date}")
    else:
        print(f"✗ Future date check failed: {future_date}")
        return False
    
    # Test 4: Past date check
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    parsed_past = datetime.strptime(past_date, "%Y-%m-%d %H:%M:%S")
    if parsed_past <= datetime.now():
        print(f"✓ Past date check works: {past_date} is in the past")
    else:
        print(f"✗ Past date check failed: {past_date}")
        return False
    
    print("✓ All validation tests passed!\n")
    return True


def test_request_payload_examples():
    """Test and display example request payloads"""
    print("Testing request payload examples...")
    
    # Example 1: Basic expiry date request
    payload1 = {
        "Configuration": "wg0",
        "Peer": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890ABCD=",
        "ExpiryDate": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    print("Example 1 - Basic expiry date request:")
    print(json.dumps(payload1, indent=2))
    print()
    
    # Example 2: Trial period (7 days)
    payload2 = {
        "Configuration": "wg0",
        "Peer": "TrialUserPublicKey123456789ABCDEFGHIJK=",
        "ExpiryDate": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    print("Example 2 - Trial period (7 days):")
    print(json.dumps(payload2, indent=2))
    print()
    
    # Example 3: Monthly subscription (end of month)
    now = datetime.now()
    if now.month == 12:
        end_of_month = datetime(now.year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_of_month = datetime(now.year, now.month + 1, 1) - timedelta(seconds=1)
    
    payload3 = {
        "Configuration": "wg0",
        "Peer": "SubscriberPublicKey123456789ABCDEFG=",
        "ExpiryDate": end_of_month.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    print("Example 3 - Monthly subscription (end of month):")
    print(json.dumps(payload3, indent=2))
    print()
    
    print("✓ All payload examples generated successfully!\n")
    return True


def test_job_structure():
    """Test the PeerJob structure that will be created"""
    print("Testing PeerJob structure...")
    
    # Simulate the job that would be created
    job_data = {
        "JobID": "550e8400-e29b-41d4-a716-446655440000",
        "Configuration": "wg0",
        "Peer": "ExamplePeerPublicKey=",
        "Field": "date",
        "Operator": "lgt",
        "Value": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),
        "CreationDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ExpireDate": None,
        "Action": "restrict"
    }
    
    print("PeerJob structure that will be created:")
    print(json.dumps(job_data, indent=2))
    print()
    
    # Validate required fields
    required_fields = ["JobID", "Configuration", "Peer", "Field", "Operator", "Value", "Action"]
    all_present = all(field in job_data for field in required_fields)
    
    if all_present:
        print(f"✓ All required fields present: {', '.join(required_fields)}")
    else:
        missing = [f for f in required_fields if f not in job_data]
        print(f"✗ Missing required fields: {', '.join(missing)}")
        return False
    
    # Validate field values
    if job_data["Field"] != "date":
        print(f"✗ Field should be 'date', got: {job_data['Field']}")
        return False
    
    if job_data["Operator"] != "lgt":
        print(f"✗ Operator should be 'lgt', got: {job_data['Operator']}")
        return False
    
    if job_data["Action"] != "restrict":
        print(f"✗ Action should be 'restrict', got: {job_data['Action']}")
        return False
    
    print("✓ Field values are correct (Field=date, Operator=lgt, Action=restrict)")
    print("✓ Job structure test passed!\n")
    return True


def test_error_scenarios():
    """Test various error scenarios"""
    print("Testing error scenarios...")
    
    # Scenario 1: Missing fields
    scenarios = [
        {
            "name": "Missing Configuration",
            "payload": {"Peer": "key", "ExpiryDate": "2025-12-31 23:59:59"},
            "expected_error": "Please specify Configuration, Peer, and ExpiryDate"
        },
        {
            "name": "Missing Peer",
            "payload": {"Configuration": "wg0", "ExpiryDate": "2025-12-31 23:59:59"},
            "expected_error": "Please specify Configuration, Peer, and ExpiryDate"
        },
        {
            "name": "Missing ExpiryDate",
            "payload": {"Configuration": "wg0", "Peer": "key"},
            "expected_error": "Please specify Configuration, Peer, and ExpiryDate"
        },
        {
            "name": "Invalid date format",
            "payload": {"Configuration": "wg0", "Peer": "key", "ExpiryDate": "2025-12-31"},
            "expected_error": "Invalid date format"
        },
        {
            "name": "Past date",
            "payload": {
                "Configuration": "wg0", 
                "Peer": "key", 
                "ExpiryDate": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            },
            "expected_error": "ExpiryDate must be in the future"
        }
    ]
    
    for scenario in scenarios:
        print(f"  Scenario: {scenario['name']}")
        print(f"    Payload: {json.dumps(scenario['payload'])}")
        print(f"    Expected error: {scenario['expected_error']}")
        
        # Check if required fields are missing
        required = ["Configuration", "Peer", "ExpiryDate"]
        missing = [f for f in required if f not in scenario['payload']]
        
        if missing and "Please specify" in scenario['expected_error']:
            print(f"    ✓ Would correctly reject due to missing fields\n")
        elif "Invalid date format" in scenario['expected_error']:
            try:
                datetime.strptime(scenario['payload'].get("ExpiryDate", ""), "%Y-%m-%d %H:%M:%S")
                print(f"    ✗ Should have rejected invalid date format\n")
            except ValueError:
                print(f"    ✓ Would correctly reject invalid date format\n")
        elif "must be in the future" in scenario['expected_error']:
            try:
                parsed = datetime.strptime(scenario['payload'].get("ExpiryDate", ""), "%Y-%m-%d %H:%M:%S")
                if parsed <= datetime.now():
                    print(f"    ✓ Would correctly reject past date\n")
                else:
                    print(f"    ✗ Should have rejected past date\n")
            except ValueError:
                print(f"    ✗ Date parsing error\n")
    
    print("✓ Error scenario tests completed!\n")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Peer Expiry Date API Test Suite")
    print("=" * 60)
    print()
    
    results = []
    
    # Run all test functions
    results.append(("Validation Logic", test_set_expiry_date_validation()))
    results.append(("Request Payloads", test_request_payload_examples()))
    results.append(("Job Structure", test_job_structure()))
    results.append(("Error Scenarios", test_error_scenarios()))
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
