# Kargo Amazon DSP Integration - API Documentation

This document provides comprehensive API documentation for the Kargo Amazon DSP Integration service.

## Table of Contents

- [Authentication](#authentication)
- [Base URLs](#base-urls)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [API Endpoints](#api-endpoints)
- [Webhooks](#webhooks)
- [SDKs](#sdks)

## Authentication

### Bearer Token Authentication

All API requests require authentication using a Bearer token in the Authorization header.

```http
Authorization: Bearer <your-access-token>
```

### Obtaining Access Tokens

```http
POST /api/auth/token
Content-Type: application/json

{
    "username": "your-username",
    "password": "your-password"
}
```

**Response:**
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 3600
}
```

## Base URLs

- **Production**: `https://api.kargo-dsp.com`
- **Staging**: `https://staging-api.kargo-dsp.com`
- **Development**: `http://localhost:8000`

## Response Format

All API responses follow a consistent JSON format:

```json
{
    "success": true,
    "data": {},
    "message": "Operation completed successfully",
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "req_123456789"
}
```

### Success Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Indicates if the request was successful |
| `data` | object/array | The response payload |
| `message` | string | Human-readable status message |
| `timestamp` | string | ISO 8601 timestamp of the response |
| `request_id` | string | Unique identifier for the request |

## Error Handling

### Error Response Format

```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid request parameters",
        "details": [
            {
                "field": "campaign_name",
                "message": "Campaign name is required"
            }
        ]
    },
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "req_123456789"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request parameters |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists |
| 422 | Unprocessable Entity - Validation errors |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |
| 503 | Service Unavailable - Service temporarily unavailable |

### Common Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `AUTHENTICATION_ERROR` | Authentication credentials invalid |
| `AUTHORIZATION_ERROR` | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `RESOURCE_CONFLICT` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | API rate limit exceeded |
| `EXTERNAL_API_ERROR` | External service error |
| `INTERNAL_ERROR` | Internal server error |

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Default**: 60 requests per minute per client
- **Burst**: Up to 10 additional requests in short bursts

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

## API Endpoints

### Health Check Endpoints

#### Get Service Health
```http
GET /health/live
```

Returns basic service health status.

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T00:00:00Z",
    "service": "kargo-amazon-dsp-integration",
    "version": "1.0.0",
    "uptime_seconds": 3600
}
```

#### Get Detailed Health
```http
GET /health/detailed
```

Returns comprehensive health status including dependencies and system metrics.

### Campaign Management

#### List Campaigns
```http
GET /api/campaigns?limit=20&offset=0&status=active
```

**Query Parameters:**
- `limit` (optional): Number of results to return (default: 20, max: 100)
- `offset` (optional): Number of results to skip (default: 0)
- `status` (optional): Filter by campaign status (`active`, `paused`, `completed`)
- `phase` (optional): Filter by campaign phase (`awareness`, `consideration`, `conversion`)

**Response:**
```json
{
    "success": true,
    "data": {
        "campaigns": [
            {
                "id": "camp_123456",
                "name": "Summer Sale Campaign",
                "status": "active",
                "phase": "awareness",
                "budget": 10000.00,
                "spent": 2500.00,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "creative_count": 5,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T12:00:00Z"
            }
        ],
        "total": 1,
        "limit": 20,
        "offset": 0
    }
}
```

#### Get Campaign Details
```http
GET /api/campaigns/{campaign_id}
```

**Path Parameters:**
- `campaign_id`: Unique campaign identifier

**Response:**
```json
{
    "success": true,
    "data": {
        "id": "camp_123456",
        "name": "Summer Sale Campaign",
        "status": "active",
        "phase": "awareness",
        "budget": 10000.00,
        "spent": 2500.00,
        "remaining_budget": 7500.00,
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "targeting": {
            "demographics": ["18-34", "35-54"],
            "interests": ["retail", "fashion"],
            "locations": ["US", "CA"]
        },
        "creatives": [
            {
                "id": "creative_789",
                "name": "Banner Ad 300x250",
                "format": "display",
                "status": "active",
                "performance": {
                    "impressions": 50000,
                    "clicks": 1500,
                    "ctr": 0.03
                }
            }
        ],
        "performance": {
            "impressions": 100000,
            "clicks": 3000,
            "conversions": 150,
            "ctr": 0.03,
            "conversion_rate": 0.05,
            "cost_per_click": 0.83,
            "cost_per_conversion": 16.67
        }
    }
}
```

#### Create Campaign
```http
POST /api/campaigns
Content-Type: application/json

{
    "name": "New Campaign",
    "phase": "awareness",
    "budget": 5000.00,
    "start_date": "2024-02-01",
    "end_date": "2024-02-28",
    "targeting": {
        "demographics": ["25-44"],
        "interests": ["technology"],
        "locations": ["US"]
    }
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": "camp_789012",
        "name": "New Campaign",
        "status": "draft",
        "phase": "awareness",
        "budget": 5000.00,
        "created_at": "2024-01-15T10:00:00Z"
    },
    "message": "Campaign created successfully"
}
```

#### Update Campaign
```http
PUT /api/campaigns/{campaign_id}
Content-Type: application/json

{
    "name": "Updated Campaign Name",
    "budget": 7500.00,
    "status": "paused"
}
```

#### Delete Campaign
```http
DELETE /api/campaigns/{campaign_id}
```

### Creative Management

#### List Creatives
```http
GET /api/creatives?campaign_id=camp_123456&format=display
```

**Query Parameters:**
- `campaign_id` (optional): Filter by campaign ID
- `format` (optional): Filter by creative format (`display`, `video`, `audio`)
- `status` (optional): Filter by status (`active`, `paused`, `review`)

#### Upload Creative
```http
POST /api/creatives
Content-Type: multipart/form-data

{
    "name": "Banner Ad",
    "format": "display",
    "campaign_id": "camp_123456",
    "file": <binary_data>
}
```

#### Process Creatives
```http
POST /api/creatives/process
Content-Type: application/json

{
    "creative_ids": ["creative_123", "creative_456"],
    "processing_options": {
        "resize": true,
        "optimize": true,
        "generate_variants": true
    }
}
```

### Bulk Operations

#### Generate Bulk Sheet
```http
POST /api/bulk/generate-sheet
Content-Type: application/json

{
    "campaign_ids": ["camp_123456", "camp_789012"],
    "include_creatives": true,
    "format": "excel"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "download_url": "/api/bulk/download/sheet_abc123",
        "expires_at": "2024-01-01T01:00:00Z",
        "file_size": 1048576,
        "record_count": 150
    }
}
```

#### Upload Bulk Sheet
```http
POST /api/bulk/upload-sheet
Content-Type: multipart/form-data

{
    "file": <excel_file>,
    "validate_only": false
}
```

### Reporting

#### Get Campaign Performance
```http
GET /api/reports/campaign-performance?campaign_id=camp_123456&start_date=2024-01-01&end_date=2024-01-31
```

**Query Parameters:**
- `campaign_id`: Campaign identifier
- `start_date`: Report start date (YYYY-MM-DD)
- `end_date`: Report end date (YYYY-MM-DD)
- `granularity` (optional): Data granularity (`daily`, `weekly`, `monthly`)

#### Get Viewability Report
```http
GET /api/reports/viewability?campaign_id=camp_123456&vendor=moat
```

#### Export Report
```http
POST /api/reports/export
Content-Type: application/json

{
    "report_type": "campaign_performance",
    "campaign_ids": ["camp_123456"],
    "date_range": {
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    },
    "format": "csv",
    "email_to": "user@example.com"
}
```

### Integration Management

#### Amazon DSP Integration
```http
GET /api/integrations/amazon-dsp/status
```

```http
POST /api/integrations/amazon-dsp/sync
Content-Type: application/json

{
    "campaign_ids": ["camp_123456"],
    "sync_options": {
        "creatives": true,
        "targeting": true,
        "budgets": false
    }
}
```

#### Kargo Integration
```http
GET /api/integrations/kargo/campaigns
```

```http
POST /api/integrations/kargo/push-campaign
Content-Type: application/json

{
    "campaign_id": "camp_123456",
    "kargo_settings": {
        "placement_types": ["display", "video"],
        "optimization_goal": "conversions"
    }
}
```

### Monitoring and Diagnostics

#### Get Error Statistics
```http
GET /api/errors/statistics
```

#### Get Performance Metrics
```http
GET /api/performance/summary
```

#### Get System Health
```http
GET /api/health/detailed
```

## Webhooks

The API supports webhooks for real-time notifications of events.

### Webhook Events

| Event | Description |
|-------|-------------|
| `campaign.created` | Campaign created |
| `campaign.updated` | Campaign updated |
| `campaign.deleted` | Campaign deleted |
| `creative.processed` | Creative processing completed |
| `bulk.sheet.generated` | Bulk sheet generation completed |
| `report.generated` | Report generation completed |
| `integration.sync.completed` | Integration sync completed |
| `error.critical` | Critical error occurred |

### Webhook Payload

```json
{
    "event": "campaign.created",
    "timestamp": "2024-01-01T00:00:00Z",
    "data": {
        "campaign_id": "camp_123456",
        "name": "New Campaign",
        "status": "draft"
    },
    "webhook_id": "wh_abc123",
    "retry_count": 0
}
```

### Webhook Configuration

```http
POST /api/webhooks
Content-Type: application/json

{
    "url": "https://your-app.com/webhooks/kargo-dsp",
    "events": ["campaign.created", "campaign.updated"],
    "secret": "your-webhook-secret",
    "active": true
}
```

## SDKs

### Python SDK

```python
from kargo_dsp_client import KargoDSPClient

client = KargoDSPClient(
    base_url="https://api.kargo-dsp.com",
    access_token="your-access-token"
)

# List campaigns
campaigns = client.campaigns.list(status="active")

# Create campaign
new_campaign = client.campaigns.create({
    "name": "Python SDK Campaign",
    "phase": "awareness",
    "budget": 1000.00
})

# Upload creative
creative = client.creatives.upload(
    campaign_id="camp_123456",
    file_path="/path/to/creative.jpg",
    name="My Creative"
)
```

### JavaScript SDK

```javascript
import { KargoDSPClient } from 'kargo-dsp-client';

const client = new KargoDSPClient({
    baseUrl: 'https://api.kargo-dsp.com',
    accessToken: 'your-access-token'
});

// List campaigns
const campaigns = await client.campaigns.list({ status: 'active' });

// Create campaign
const newCampaign = await client.campaigns.create({
    name: 'JavaScript SDK Campaign',
    phase: 'awareness',
    budget: 1000.00
});

// Process creatives
const result = await client.creatives.process({
    creativeIds: ['creative_123', 'creative_456'],
    processingOptions: {
        resize: true,
        optimize: true
    }
});
```

## Best Practices

### Request/Response Handling

1. **Always check the `success` field** in responses
2. **Handle rate limiting** by implementing exponential backoff
3. **Use pagination** for list endpoints with large datasets
4. **Include request IDs** in logs for debugging
5. **Validate data** before sending requests

### Error Handling

```python
try:
    response = client.campaigns.create(campaign_data)
    if response.success:
        campaign = response.data
        print(f"Campaign created: {campaign['id']}")
    else:
        print(f"Error: {response.error['message']}")
        for detail in response.error.get('details', []):
            print(f"  - {detail['field']}: {detail['message']}")
except RateLimitError:
    # Implement backoff and retry
    time.sleep(60)
    response = client.campaigns.create(campaign_data)
```

### Webhook Security

1. **Verify webhook signatures** using the provided secret
2. **Implement idempotency** to handle duplicate events
3. **Use HTTPS** for webhook endpoints
4. **Validate event structure** before processing

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
```

---

For additional API support or questions, please contact the development team or consult the interactive API documentation at `/docs` when running the service.