# Peer Expiry Date API Documentation

This document explains how to set expiry dates for peers that will automatically restrict them when the date is reached.

## Overview

WGDashboard includes a job scheduler system that can monitor peer attributes and trigger actions. One common use case is setting an expiry date for a peer that will automatically restrict the peer when that date is reached.

## Quick Start - Convenient API Endpoint

### Set Peer Expiry Date

The easiest way to set a peer expiry date is using the dedicated endpoint:

**Endpoint:** `POST /api/setPeerExpiryDate`

**Request Body:**
```json
{
  "Configuration": "wg0",
  "Peer": "peer_public_key_here",
  "ExpiryDate": "2025-12-31 23:59:59"
}
```

**Parameters:**
- `Configuration` (string, required): Name of the WireGuard configuration (e.g., "wg0")
- `Peer` (string, required): Public key of the peer
- `ExpiryDate` (string, required): Date and time when the peer should be restricted. Format: `YYYY-MM-DD HH:MM:SS`

**Success Response:**
```json
{
  "status": true,
  "message": "Expiry date set successfully. Peer will be restricted on 2025-12-31 23:59:59",
  "data": [
    {
      "JobID": "550e8400-e29b-41d4-a716-446655440000",
      "Configuration": "wg0",
      "Peer": "peer_public_key_here",
      "Field": "date",
      "Operator": "lgt",
      "Value": "2025-12-31 23:59:59",
      "CreationDate": "2024-12-21 12:00:00",
      "ExpireDate": null,
      "Action": "restrict"
    }
  ]
}
```

**Error Response:**
```json
{
  "status": false,
  "message": "Configuration 'wg0' does not exist"
}
```

### Example: Using cURL

```bash
curl -X POST http://localhost:10086/api/setPeerExpiryDate \
  -H "Content-Type: application/json" \
  -d '{
    "Configuration": "wg0",
    "Peer": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890ABCD=",
    "ExpiryDate": "2025-12-31 23:59:59"
  }'
```

### Example: Using Python

```python
import requests
from datetime import datetime, timedelta

# Set expiry date to 30 days from now
expiry_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

response = requests.post(
    "http://localhost:10086/api/setPeerExpiryDate",
    json={
        "Configuration": "wg0",
        "Peer": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890ABCD=",
        "ExpiryDate": expiry_date
    }
)

if response.json()["status"]:
    print(f"Expiry date set successfully!")
    print(f"Job ID: {response.json()['data'][0]['JobID']}")
else:
    print(f"Error: {response.json()['message']}")
```

### Example: Using JavaScript

```javascript
const setExpiryDate = async () => {
  // Set expiry date to 30 days from now
  const expiryDate = new Date();
  expiryDate.setDate(expiryDate.getDate() + 30);
  const formattedDate = expiryDate.toISOString()
    .slice(0, 19)
    .replace('T', ' ');

  try {
    const response = await fetch('http://localhost:10086/api/setPeerExpiryDate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        Configuration: 'wg0',
        Peer: 'AbCdEfGhIjKlMnOpQrStUvWxYz1234567890ABCD=',
        ExpiryDate: formattedDate
      })
    });

    const data = await response.json();
    if (data.status) {
      console.log('Expiry date set successfully!');
      console.log('Job ID:', data.data[0].JobID);
    } else {
      console.error('Error:', data.message);
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
};

setExpiryDate();
```

## Advanced Usage - Full Job Scheduler API

For more advanced use cases, you can use the full job scheduler API which allows you to:
- Monitor data usage (total_receive, total_sent, total_data)
- Use different operators (larger than, less than, equal, not equal)
- Trigger different actions (restrict, delete, reset_total_data_usage)

### Create a Custom Job

**Endpoint:** `POST /api/savePeerScheduleJob`

**Request Body:**
```json
{
  "Job": {
    "JobID": "550e8400-e29b-41d4-a716-446655440000",
    "Configuration": "wg0",
    "Peer": "peer_public_key_here",
    "Field": "date",
    "Operator": "lgt",
    "Value": "2025-12-31 23:59:59",
    "CreationDate": "",
    "ExpireDate": null,
    "Action": "restrict"
  }
}
```

**Available Fields:**
- `date` - Monitor based on date/time
- `total_receive` - Monitor received data (in GB)
- `total_sent` - Monitor sent data (in GB)
- `total_data` - Monitor total data usage (in GB)

**Available Operators:**
- `lgt` - Larger than (greater than)
- `lst` - Less than
- `eq` - Equal to
- `neq` - Not equal to

**Available Actions:**
- `restrict` - Restrict the peer (peer cannot connect)
- `delete` - Delete the peer permanently
- `reset_total_data_usage` - Reset data usage counters and toggle peer state

### Example: Set Data Usage Limit

Restrict peer when total usage exceeds 100 GB:

```json
{
  "Job": {
    "JobID": "550e8400-e29b-41d4-a716-446655440000",
    "Configuration": "wg0",
    "Peer": "peer_public_key_here",
    "Field": "total_data",
    "Operator": "lgt",
    "Value": "100",
    "CreationDate": "",
    "ExpireDate": null,
    "Action": "restrict"
  }
}
```

### Example: Delete Peer on Expiry

Delete peer when expiry date is reached:

```json
{
  "Job": {
    "JobID": "550e8400-e29b-41d4-a716-446655440000",
    "Configuration": "wg0",
    "Peer": "peer_public_key_here",
    "Field": "date",
    "Operator": "lgt",
    "Value": "2025-12-31 23:59:59",
    "CreationDate": "",
    "ExpireDate": null,
    "Action": "delete"
  }
}
```

### Delete a Job

**Endpoint:** `POST /api/deletePeerScheduleJob`

**Request Body:**
```json
{
  "Job": {
    "JobID": "550e8400-e29b-41d4-a716-446655440000",
    "Configuration": "wg0",
    "Peer": "peer_public_key_here",
    "Field": "date",
    "Operator": "lgt",
    "Value": "2025-12-31 23:59:59",
    "CreationDate": "2024-12-21 12:00:00",
    "ExpireDate": null,
    "Action": "restrict"
  }
}
```

### Get Job Logs

**Endpoint:** `GET /api/getPeerScheduleJobLogs/<configName>?requestAll=true`

**Example:**
```bash
curl http://localhost:10086/api/getPeerScheduleJobLogs/wg0?requestAll=true
```

## How It Works

1. **Job Creation**: When you create an expiry date job, it's stored in the database
2. **Background Scheduler**: A background thread runs every 3 minutes (180 seconds)
3. **Job Execution**: The scheduler checks all active jobs:
   - For date-based jobs: Compares current time with the target date
   - For data-based jobs: Compares actual usage with the limit
4. **Action Trigger**: When condition is met, the specified action is executed
5. **Job Completion**: Successfully executed jobs are automatically removed

## Important Notes

- **Date Format**: Always use `YYYY-MM-DD HH:MM:SS` format (e.g., `2025-12-31 23:59:59`)
- **Future Dates**: The `/api/setPeerExpiryDate` endpoint only accepts future dates
- **Job Frequency**: Jobs are checked every 3 minutes, so actions may have a delay of up to 3 minutes
- **Restricted Peers**: Once restricted, peers cannot connect until manually allowed
- **Updating Jobs**: Use the same JobID to update an existing job
- **Timezone**: All times are in the server's local timezone

## Common Use Cases

### Temporary Access (Trial Period)
Set an expiry date for trial users that automatically restricts them after the trial ends:
```bash
curl -X POST http://localhost:10086/api/setPeerExpiryDate \
  -H "Content-Type: application/json" \
  -d '{
    "Configuration": "wg0",
    "Peer": "trial_user_public_key=",
    "ExpiryDate": "2025-01-31 23:59:59"
  }'
```

### Monthly Subscriptions
For monthly subscriptions, set expiry to end of billing period:
```python
from datetime import datetime, timedelta

# Set expiry to 30 days from now
expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d 23:59:59")
```

### Data Caps with Expiry
Combine data limits with time limits for comprehensive control:
```json
{
  "Job1": {
    "Field": "total_data",
    "Operator": "lgt",
    "Value": "100",
    "Action": "restrict"
  },
  "Job2": {
    "Field": "date",
    "Operator": "lgt",
    "Value": "2025-12-31 23:59:59",
    "Action": "restrict"
  }
}
```

## Troubleshooting

### Job Not Executing
- Check that the background scheduler is running (logs show "Background Thread #2 Started")
- Verify the date format is correct
- Ensure the date is in the future
- Check job logs: `GET /api/getPeerScheduleJobLogs/<configName>`

### Peer Not Restricted
- Verify the job exists for the peer
- Check if the expiry date has actually passed
- Review job logs for errors
- Confirm the peer public key is correct

### Updating Expiry Date
To update an existing expiry date, simply call `/api/setPeerExpiryDate` again with the same Configuration and Peer but a new ExpiryDate. The system will automatically update the existing job.

## API Authentication

Note: All API endpoints require proper authentication. Ensure you're authenticated with valid credentials before making API calls. Refer to the main WGDashboard documentation for authentication details.
