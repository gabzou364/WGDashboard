"""
Integration Example for Peer Expiry Date API

This script demonstrates how to use the peer expiry date API in real-world scenarios.
It includes examples for common use cases and shows the expected workflow.

Note: This is a demonstration script. Actual integration would require:
1. A running WGDashboard instance
2. Valid authentication credentials
3. Existing WireGuard configuration and peers
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any


class MockWGDashboardAPI:
    """
    Mock API client for demonstration purposes
    In production, replace with actual HTTP requests
    """
    
    def __init__(self, base_url: str = "http://localhost:10086"):
        self.base_url = base_url
        
    def set_peer_expiry_date(self, configuration: str, peer: str, expiry_date: str) -> Dict[str, Any]:
        """
        Set an expiry date for a peer
        
        Args:
            configuration: Name of the WireGuard configuration (e.g., "wg0")
            peer: Public key of the peer
            expiry_date: Expiry date in format "YYYY-MM-DD HH:MM:SS"
        
        Returns:
            Response dictionary with status, message, and data
        """
        payload = {
            "Configuration": configuration,
            "Peer": peer,
            "ExpiryDate": expiry_date
        }
        
        # In production, this would be:
        # response = requests.post(f"{self.base_url}/api/setPeerExpiryDate", json=payload)
        # return response.json()
        
        # Mock response for demonstration
        return {
            "status": True,
            "message": f"Expiry date set successfully. Peer will be restricted on {expiry_date}",
            "data": [{
                "JobID": "550e8400-e29b-41d4-a716-446655440000",
                "Configuration": configuration,
                "Peer": peer,
                "Field": "date",
                "Operator": "lgt",
                "Value": expiry_date,
                "CreationDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ExpireDate": None,
                "Action": "restrict"
            }]
        }
    
    def save_peer_schedule_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a custom peer schedule job (advanced usage)
        
        Args:
            job: Job dictionary with all required fields
        
        Returns:
            Response dictionary
        """
        # In production: requests.post(f"{self.base_url}/api/savePeerScheduleJob", json={"Job": job})
        return {
            "status": True,
            "data": [job]
        }


def use_case_1_trial_period():
    """
    Use Case 1: Set up a 7-day trial period for a new user
    """
    print("=" * 70)
    print("Use Case 1: Trial Period (7 days)")
    print("=" * 70)
    
    api = MockWGDashboardAPI()
    
    # Configuration
    config_name = "wg0"
    peer_public_key = "TrialUser123PublicKeyABCDEFGHIJKLMNOP="
    trial_days = 7
    
    # Calculate expiry date
    expiry_date = (datetime.now() + timedelta(days=trial_days))
    expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Setting up trial period for peer: {peer_public_key[:20]}...")
    print(f"Configuration: {config_name}")
    print(f"Trial Duration: {trial_days} days")
    print(f"Expiry Date: {expiry_str}")
    print()
    
    # Call API
    response = api.set_peer_expiry_date(config_name, peer_public_key, expiry_str)
    
    if response["status"]:
        print("✓ Success!")
        print(f"  Message: {response['message']}")
        print(f"  Job ID: {response['data'][0]['JobID']}")
        print()
        print("What happens next:")
        print(f"  - User has full access until {expiry_str}")
        print(f"  - On {expiry_date.strftime('%Y-%m-%d')}, peer will be automatically restricted")
        print(f"  - Restriction is checked every 3 minutes")
    else:
        print(f"✗ Error: {response['message']}")
    
    print()


def use_case_2_monthly_subscription():
    """
    Use Case 2: Set up monthly subscription with automatic renewal date
    """
    print("=" * 70)
    print("Use Case 2: Monthly Subscription")
    print("=" * 70)
    
    api = MockWGDashboardAPI()
    
    # Configuration
    config_name = "wg0"
    peer_public_key = "MonthlySubscriber456PublicKey123ABCD="
    
    # Calculate end of current billing period (30 days)
    billing_end = datetime.now() + timedelta(days=30)
    expiry_str = billing_end.strftime("%Y-%m-%d 23:59:59")
    
    print(f"Setting up monthly subscription for peer: {peer_public_key[:20]}...")
    print(f"Configuration: {config_name}")
    print(f"Billing Period Ends: {expiry_str}")
    print()
    
    # Call API
    response = api.set_peer_expiry_date(config_name, peer_public_key, expiry_str)
    
    if response["status"]:
        print("✓ Success!")
        print(f"  Job ID: {response['data'][0]['JobID']}")
        print()
        print("Subscription Management:")
        print(f"  - Access valid until: {expiry_str}")
        print(f"  - Before expiry, call the API again with new date to extend")
        print(f"  - Example renewal: Add 30 more days from current expiry")
        
        # Show renewal example
        renewal_date = billing_end + timedelta(days=30)
        renewal_str = renewal_date.strftime("%Y-%m-%d 23:59:59")
        print()
        print("Renewal Example (call before expiry):")
        print(f"  New expiry date: {renewal_str}")
        renewal_payload = {
            "Configuration": config_name,
            "Peer": peer_public_key,
            "ExpiryDate": renewal_str
        }
        print(f"  Payload: {json.dumps(renewal_payload, indent=4)}")
    else:
        print(f"✗ Error: {response['message']}")
    
    print()


def use_case_3_temporary_access():
    """
    Use Case 3: Grant temporary access for a contractor (specific end date)
    """
    print("=" * 70)
    print("Use Case 3: Temporary Contractor Access")
    print("=" * 70)
    
    api = MockWGDashboardAPI()
    
    # Configuration
    config_name = "wg0"
    peer_public_key = "ContractorXYZPublicKey789ABCDEFGHIJK="
    
    # Specific end date for the contract
    contract_end = datetime(2025, 12, 31, 23, 59, 59)
    expiry_str = contract_end.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Setting up temporary access for contractor: {peer_public_key[:20]}...")
    print(f"Configuration: {config_name}")
    print(f"Contract End Date: {expiry_str}")
    print()
    
    # Call API
    response = api.set_peer_expiry_date(config_name, peer_public_key, expiry_str)
    
    if response["status"]:
        print("✓ Success!")
        print(f"  Job ID: {response['data'][0]['JobID']}")
        print()
        print("Access Details:")
        print(f"  - Contractor has access until: {expiry_str}")
        print(f"  - Access will be automatically revoked on expiry")
        print(f"  - No manual intervention needed")
    else:
        print(f"✗ Error: {response['message']}")
    
    print()


def use_case_4_combined_limits():
    """
    Use Case 4: Combine expiry date with data usage limit (advanced)
    """
    print("=" * 70)
    print("Use Case 4: Combined Time and Data Limits (Advanced)")
    print("=" * 70)
    
    api = MockWGDashboardAPI()
    
    # Configuration
    config_name = "wg0"
    peer_public_key = "CombinedLimitsUserPublicKey123ABCD="
    
    # Set both time and data limits
    expiry_date = datetime.now() + timedelta(days=30)
    expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    data_limit_gb = 100
    
    print(f"Setting combined limits for peer: {peer_public_key[:20]}...")
    print(f"Configuration: {config_name}")
    print(f"Time Limit: {expiry_str}")
    print(f"Data Limit: {data_limit_gb} GB")
    print()
    
    # Job 1: Time-based expiry
    time_job = {
        "JobID": "time-limit-" + peer_public_key[:10],
        "Configuration": config_name,
        "Peer": peer_public_key,
        "Field": "date",
        "Operator": "lgt",
        "Value": expiry_str,
        "CreationDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ExpireDate": None,
        "Action": "restrict"
    }
    
    # Job 2: Data usage limit
    data_job = {
        "JobID": "data-limit-" + peer_public_key[:10],
        "Configuration": config_name,
        "Peer": peer_public_key,
        "Field": "total_data",
        "Operator": "lgt",
        "Value": str(data_limit_gb),
        "CreationDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ExpireDate": None,
        "Action": "restrict"
    }
    
    print("Creating two jobs:")
    print()
    print("1. Time-based job:")
    print(json.dumps(time_job, indent=2))
    print()
    print("2. Data-based job:")
    print(json.dumps(data_job, indent=2))
    print()
    
    # Save both jobs
    response1 = api.save_peer_schedule_job(time_job)
    response2 = api.save_peer_schedule_job(data_job)
    
    if response1["status"] and response2["status"]:
        print("✓ Success! Both limits are now active.")
        print()
        print("What this means:")
        print(f"  - Peer will be restricted if date reaches {expiry_str}")
        print(f"  - OR if total data usage exceeds {data_limit_gb} GB")
        print(f"  - Whichever happens first will trigger the restriction")
    else:
        print("✗ Error setting up combined limits")
    
    print()


def demonstrate_error_handling():
    """
    Demonstrate proper error handling
    """
    print("=" * 70)
    print("Error Handling Examples")
    print("=" * 70)
    
    print("Common errors and how to handle them:")
    print()
    
    # Error 1: Past date
    print("1. Attempting to set a past date:")
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"   ExpiryDate: {past_date}")
    print(f"   Expected Error: 'ExpiryDate must be in the future'")
    print(f"   Solution: Use a future date")
    print()
    
    # Error 2: Invalid format
    print("2. Invalid date format:")
    print(f"   ExpiryDate: '2025-12-31' (missing time)")
    print(f"   Expected Error: 'Invalid date format'")
    print(f"   Solution: Use format 'YYYY-MM-DD HH:MM:SS'")
    print()
    
    # Error 3: Missing fields
    print("3. Missing required fields:")
    print(f"   Payload: {{'Configuration': 'wg0'}}")
    print(f"   Expected Error: 'Please specify Configuration, Peer, and ExpiryDate'")
    print(f"   Solution: Include all required fields")
    print()
    
    # Error 4: Non-existent peer
    print("4. Non-existent peer or configuration:")
    print(f"   Expected Error: 'Peer does not exist' or 'Configuration does not exist'")
    print(f"   Solution: Verify peer public key and configuration name")
    print()


def main():
    """
    Run all use case demonstrations
    """
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "Peer Expiry Date API Integration Examples" + " " * 11 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    # Run all use cases
    use_case_1_trial_period()
    use_case_2_monthly_subscription()
    use_case_3_temporary_access()
    use_case_4_combined_limits()
    demonstrate_error_handling()
    
    # Final notes
    print("=" * 70)
    print("Important Notes")
    print("=" * 70)
    print()
    print("1. Job Execution Frequency:")
    print("   - Jobs are checked every 3 minutes (180 seconds)")
    print("   - There may be up to 3 minutes delay before restriction")
    print()
    print("2. Date Format:")
    print("   - Always use: YYYY-MM-DD HH:MM:SS")
    print("   - Example: 2025-12-31 23:59:59")
    print()
    print("3. Timezone:")
    print("   - All dates are in the server's local timezone")
    print()
    print("4. Authentication:")
    print("   - API calls require valid authentication")
    print("   - Refer to main documentation for auth setup")
    print()
    print("5. Job Management:")
    print("   - Calling setPeerExpiryDate again updates the existing job")
    print("   - To remove expiry, delete the job via /api/deletePeerScheduleJob")
    print()
    print("For complete API documentation, see: API_PEER_EXPIRY.md")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
