"""Amazon DSP API client with mock implementation for development."""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from app.utils.logging import get_logger
from app.utils.retry import amazon_dsp_retry_async, RetryableHTTPError
from app.utils.metrics import MetricsCollector, time_database_operation


logger = get_logger("amazon_dsp.client")


class AmazonCreativeUploadRequest(BaseModel):
    """Request model for Amazon DSP creative upload."""
    name: str
    format: str  # CUSTOM_HTML, VAST_3_0, etc.
    creative_code: str
    width: int
    height: int
    advertiser_id: str
    click_url: Optional[str] = None
    viewability_config: Optional[Dict[str, Any]] = None


class AmazonCreativeUploadResponse(BaseModel):
    """Response model for Amazon DSP creative upload."""
    creative_id: str
    name: str
    status: str  # PENDING, APPROVED, REJECTED
    format: str
    approval_status: Optional[str] = None
    review_feedback: Optional[str] = None
    created_at: datetime
    last_modified: datetime


class AmazonCampaignRequest(BaseModel):
    """Request model for Amazon DSP campaign creation."""
    advertiser_id: str
    name: str
    budget: float
    start_date: str
    end_date: str
    goal: str
    status: str = "PAUSED"


class AmazonCampaignResponse(BaseModel):
    """Response model for Amazon DSP campaign."""
    campaign_id: str
    name: str
    status: str
    budget: float
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    created_at: datetime


class ViewabilityReportRequest(BaseModel):
    """Request model for viewability reporting configuration."""
    campaign_id: str
    metrics: List[str]
    reporting_frequency: str = "hourly"
    dashboard_enabled: bool = True
    api_access: bool = True


class ViewabilityReportResponse(BaseModel):
    """Response model for viewability reporting."""
    reporting_id: str
    campaign_id: str
    status: str
    metrics_configured: List[str]
    dashboard_url: Optional[str] = None


class MockAmazonDSPClient:
    """Mock Amazon DSP API client for development and testing."""
    
    def __init__(self, base_url: str = "https://api.amazon-adsystem.com", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Mock data storage
        self._creatives: Dict[str, Dict[str, Any]] = {}
        self._campaigns: Dict[str, Dict[str, Any]] = {}
        self._viewability_reports: Dict[str, Dict[str, Any]] = {}
        
        # Mock authentication token
        self._access_token = "mock_access_token_12345"
        self._token_expires_at = datetime.utcnow() + timedelta(hours=1)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
    
    def _generate_mock_id(self, prefix: str = "mock") -> str:
        """Generate a mock ID for testing."""
        timestamp = int(time.time() * 1000)
        return f"{prefix}_{timestamp}_{len(self._creatives) + len(self._campaigns)}"
    
    def _simulate_api_latency(self, min_ms: int = 100, max_ms: int = 500) -> None:
        """Simulate realistic API latency."""
        import random
        latency = random.randint(min_ms, max_ms) / 1000.0
        time.sleep(latency)
    
    async def _get_access_token(self) -> str:
        """Mock OAuth token retrieval."""
        if datetime.utcnow() < self._token_expires_at:
            return self._access_token
        
        # Simulate token refresh
        await asyncio.sleep(0.1)  # Simulate API call
        self._access_token = f"refreshed_token_{int(time.time())}"
        self._token_expires_at = datetime.utcnow() + timedelta(hours=1)
        
        logger.info("Mock access token refreshed")
        return self._access_token
    
    @amazon_dsp_retry_async
    async def upload_creative(self, request: AmazonCreativeUploadRequest) -> AmazonCreativeUploadResponse:
        """Mock creative upload to Amazon DSP."""
        logger.info(f"Uploading creative: {request.name}")
        
        # Simulate API latency
        await asyncio.sleep(0.2)
        
        # Mock validation
        if len(request.creative_code) < 50:
            raise RetryableHTTPError(400, "Creative code too short")
        
        if request.width <= 0 or request.height <= 0:
            raise RetryableHTTPError(400, "Invalid dimensions")
        
        # Generate mock response
        creative_id = self._generate_mock_id("creative")
        now = datetime.utcnow()
        
        # Simulate approval process
        status = "PENDING"
        approval_status = "UNDER_REVIEW"
        
        # Some creatives get auto-approved for testing
        if "test" in request.name.lower() or request.format == "CUSTOM_HTML":
            status = "APPROVED"
            approval_status = "APPROVED"
        
        creative_data = {
            "creative_id": creative_id,
            "name": request.name,
            "status": status,
            "format": request.format,
            "approval_status": approval_status,
            "review_feedback": None if status == "APPROVED" else "Pending creative review",
            "created_at": now,
            "last_modified": now,
            "width": request.width,
            "height": request.height,
            "advertiser_id": request.advertiser_id,
            "creative_code": request.creative_code,
        }
        
        self._creatives[creative_id] = creative_data
        
        # Record metrics
        MetricsCollector.record_amazon_dsp_request(
            endpoint="upload_creative",
            method="POST",
            status_code=201,
            duration=0.2
        )
        
        logger.info(f"Creative uploaded successfully: {creative_id}")
        
        return AmazonCreativeUploadResponse(**creative_data)
    
    @amazon_dsp_retry_async
    async def get_creative(self, creative_id: str) -> Optional[AmazonCreativeUploadResponse]:
        """Get creative by ID."""
        logger.info(f"Retrieving creative: {creative_id}")
        
        await asyncio.sleep(0.1)  # Simulate API latency
        
        creative_data = self._creatives.get(creative_id)
        if not creative_data:
            return None
        
        # Record metrics
        MetricsCollector.record_amazon_dsp_request(
            endpoint="get_creative",
            method="GET",
            status_code=200,
            duration=0.1
        )
        
        return AmazonCreativeUploadResponse(**creative_data)
    
    @amazon_dsp_retry_async
    async def create_campaign(self, request: AmazonCampaignRequest) -> AmazonCampaignResponse:
        """Mock campaign creation."""
        logger.info(f"Creating campaign: {request.name}")
        
        await asyncio.sleep(0.3)  # Simulate API latency
        
        campaign_id = self._generate_mock_id("campaign")
        now = datetime.utcnow()
        
        campaign_data = {
            "campaign_id": campaign_id,
            "name": request.name,
            "status": request.status,
            "budget": request.budget,
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "created_at": now,
            "advertiser_id": request.advertiser_id,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "goal": request.goal,
        }
        
        self._campaigns[campaign_id] = campaign_data
        
        # Record metrics
        MetricsCollector.record_amazon_dsp_request(
            endpoint="create_campaign",
            method="POST",
            status_code=201,
            duration=0.3
        )
        
        logger.info(f"Campaign created successfully: {campaign_id}")
        
        return AmazonCampaignResponse(**campaign_data)
    
    @amazon_dsp_retry_async
    async def setup_viewability_reporting(self, request: ViewabilityReportRequest) -> ViewabilityReportResponse:
        """Mock viewability reporting setup."""
        logger.info(f"Setting up viewability reporting for campaign: {request.campaign_id}")
        
        await asyncio.sleep(0.15)  # Simulate API latency
        
        reporting_id = self._generate_mock_id("report")
        
        report_data = {
            "reporting_id": reporting_id,
            "campaign_id": request.campaign_id,
            "status": "ACTIVE",
            "metrics_configured": request.metrics,
            "dashboard_url": f"https://dsp.amazon.com/reports/{reporting_id}" if request.dashboard_enabled else None,
            "frequency": request.reporting_frequency,
            "api_access": request.api_access,
        }
        
        self._viewability_reports[reporting_id] = report_data
        
        # Record metrics
        MetricsCollector.record_amazon_dsp_request(
            endpoint="setup_viewability_reporting",
            method="POST",
            status_code=201,
            duration=0.15
        )
        
        logger.info(f"Viewability reporting configured: {reporting_id}")
        
        return ViewabilityReportResponse(**report_data)
    
    @amazon_dsp_retry_async
    async def get_viewability_data(self, campaign_id: str, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Mock viewability data retrieval."""
        logger.info(f"Retrieving viewability data for campaign: {campaign_id}")
        
        await asyncio.sleep(0.2)  # Simulate API latency
        
        # Generate mock viewability data
        import random
        
        mock_data = {
            "campaign_id": campaign_id,
            "date_range": date_range or {"start": "2024-01-01", "end": "2024-01-31"},
            "summary": {
                "total_impressions": random.randint(10000, 100000),
                "viewable_impressions": random.randint(7000, 80000),
                "measurable_impressions": random.randint(9000, 95000),
                "viewability_rate": round(random.uniform(0.65, 0.85), 3),
                "average_view_time": round(random.uniform(2.5, 8.0), 1),
            },
            "daily_breakdown": [
                {
                    "date": f"2024-01-{i:02d}",
                    "impressions": random.randint(300, 3000),
                    "viewable_impressions": random.randint(200, 2500),
                    "viewability_rate": round(random.uniform(0.60, 0.90), 3),
                }
                for i in range(1, 31)
            ],
            "vendor_breakdown": {
                "double_verify": {
                    "impressions": random.randint(5000, 50000),
                    "viewability_rate": round(random.uniform(0.70, 0.85), 3),
                },
                "ias": {
                    "impressions": random.randint(5000, 50000),
                    "viewability_rate": round(random.uniform(0.65, 0.80), 3),
                } if random.choice([True, False]) else None,  # Phase 2 only
            }
        }
        
        # Record metrics
        MetricsCollector.record_amazon_dsp_request(
            endpoint="get_viewability_data",
            method="GET",
            status_code=200,
            duration=0.2
        )
        
        return mock_data
    
    async def batch_upload_creatives(self, requests: List[AmazonCreativeUploadRequest]) -> List[AmazonCreativeUploadResponse]:
        """Upload multiple creatives in batch."""
        logger.info(f"Batch uploading {len(requests)} creatives")
        
        results = []
        for request in requests:
            try:
                response = await self.upload_creative(request)
                results.append(response)
            except Exception as e:
                logger.error(f"Failed to upload creative {request.name}: {e}")
                # Continue with other creatives
                continue
        
        logger.info(f"Batch upload completed: {len(results)}/{len(requests)} successful")
        return results
    
    def get_mock_data_summary(self) -> Dict[str, Any]:
        """Get summary of mock data for testing purposes."""
        return {
            "creatives": len(self._creatives),
            "campaigns": len(self._campaigns),
            "viewability_reports": len(self._viewability_reports),
            "creative_ids": list(self._creatives.keys()),
            "campaign_ids": list(self._campaigns.keys()),
        }


# Factory function for client creation
async def create_amazon_dsp_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    use_mock: bool = True
) -> MockAmazonDSPClient:
    """
    Create Amazon DSP client instance.
    
    For now, always returns mock client. In production, this would
    return a real client when use_mock=False.
    """
    if use_mock:
        return MockAmazonDSPClient(base_url=base_url, api_key=api_key)
    else:
        # TODO: Implement real Amazon DSP client
        raise NotImplementedError("Real Amazon DSP client not yet implemented")


# Global client instance for dependency injection
_amazon_client: Optional[MockAmazonDSPClient] = None


async def get_amazon_dsp_client() -> MockAmazonDSPClient:
    """Dependency injection for Amazon DSP client."""
    global _amazon_client
    if _amazon_client is None:
        _amazon_client = await create_amazon_dsp_client()
    return _amazon_client