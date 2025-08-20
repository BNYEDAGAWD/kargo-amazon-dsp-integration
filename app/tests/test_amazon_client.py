"""Tests for Amazon DSP API client."""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.amazon_client import (
    MockAmazonDSPClient,
    AmazonCreativeUploadRequest,
    AmazonCampaignRequest,
    ViewabilityReportRequest,
)


@pytest.mark.asyncio
class TestMockAmazonDSPClient:
    """Test mock Amazon DSP client functionality."""
    
    async def test_upload_creative_success(self):
        """Test successful creative upload."""
        async with MockAmazonDSPClient() as client:
            request = AmazonCreativeUploadRequest(
                name="Test Creative",
                format="CUSTOM_HTML",
                creative_code="<div>Test creative content</div>",
                width=320,
                height=50,
                advertiser_id="123456"
            )
            
            response = await client.upload_creative(request)
            
            assert response.name == "Test Creative"
            assert response.format == "CUSTOM_HTML"
            assert response.status in ["PENDING", "APPROVED"]
            assert response.creative_id.startswith("creative_")
            assert isinstance(response.created_at, datetime)
    
    async def test_upload_creative_validation_error(self):
        """Test creative upload with validation error."""
        async with MockAmazonDSPClient() as client:
            request = AmazonCreativeUploadRequest(
                name="Invalid Creative",
                format="CUSTOM_HTML",
                creative_code="<div>Short</div>",  # Too short, triggers validation error
                width=320,
                height=50,
                advertiser_id="123456"
            )
            
            with pytest.raises(Exception) as exc_info:
                await client.upload_creative(request)
            
            assert "Creative code too short" in str(exc_info.value)
    
    async def test_upload_creative_invalid_dimensions(self):
        """Test creative upload with invalid dimensions."""
        async with MockAmazonDSPClient() as client:
            request = AmazonCreativeUploadRequest(
                name="Invalid Dimensions",
                format="CUSTOM_HTML",
                creative_code="<div>Valid creative content with sufficient length</div>",
                width=0,  # Invalid width
                height=50,
                advertiser_id="123456"
            )
            
            with pytest.raises(Exception) as exc_info:
                await client.upload_creative(request)
            
            assert "Invalid dimensions" in str(exc_info.value)
    
    async def test_get_creative_success(self):
        """Test successful creative retrieval."""
        async with MockAmazonDSPClient() as client:
            # First upload a creative
            upload_request = AmazonCreativeUploadRequest(
                name="Test Get Creative",
                format="CUSTOM_HTML",
                creative_code="<div>Test creative for retrieval</div>",
                width=320,
                height=50,
                advertiser_id="123456"
            )
            
            upload_response = await client.upload_creative(upload_request)
            creative_id = upload_response.creative_id
            
            # Then retrieve it
            retrieved = await client.get_creative(creative_id)
            
            assert retrieved is not None
            assert retrieved.creative_id == creative_id
            assert retrieved.name == "Test Get Creative"
            assert retrieved.format == "CUSTOM_HTML"
    
    async def test_get_creative_not_found(self):
        """Test creative retrieval with non-existent ID."""
        async with MockAmazonDSPClient() as client:
            retrieved = await client.get_creative("nonexistent_id")
            assert retrieved is None
    
    async def test_create_campaign_success(self):
        """Test successful campaign creation."""
        async with MockAmazonDSPClient() as client:
            request = AmazonCampaignRequest(
                advertiser_id="123456",
                name="Test Campaign",
                budget=10000.0,
                start_date="2024-01-01",
                end_date="2024-01-31",
                goal="VIEWABILITY"
            )
            
            response = await client.create_campaign(request)
            
            assert response.name == "Test Campaign"
            assert response.budget == 10000.0
            assert response.status == "PAUSED"  # Default status
            assert response.campaign_id.startswith("campaign_")
            assert response.spend == 0.0
            assert response.impressions == 0
    
    async def test_setup_viewability_reporting(self):
        """Test viewability reporting configuration."""
        async with MockAmazonDSPClient() as client:
            request = ViewabilityReportRequest(
                campaign_id="test_campaign_123",
                metrics=["viewable_impressions", "viewability_rate", "clicks"],
                reporting_frequency="hourly",
                dashboard_enabled=True
            )
            
            response = await client.setup_viewability_reporting(request)
            
            assert response.campaign_id == "test_campaign_123"
            assert response.status == "ACTIVE"
            assert len(response.metrics_configured) == 3
            assert "viewable_impressions" in response.metrics_configured
            assert response.dashboard_url is not None
            assert "reports" in response.dashboard_url
    
    async def test_get_viewability_data(self):
        """Test viewability data retrieval."""
        async with MockAmazonDSPClient() as client:
            data = await client.get_viewability_data("test_campaign_123")
            
            assert data["campaign_id"] == "test_campaign_123"
            assert "summary" in data
            assert "daily_breakdown" in data
            assert "vendor_breakdown" in data
            
            # Check summary metrics
            summary = data["summary"]
            assert "total_impressions" in summary
            assert "viewable_impressions" in summary
            assert "viewability_rate" in summary
            assert isinstance(summary["viewability_rate"], float)
            assert 0 <= summary["viewability_rate"] <= 1
            
            # Check daily breakdown
            daily = data["daily_breakdown"]
            assert len(daily) == 30  # 30 days of data
            assert all("date" in day for day in daily)
            assert all("viewability_rate" in day for day in daily)
    
    async def test_batch_upload_creatives(self):
        """Test batch creative upload."""
        async with MockAmazonDSPClient() as client:
            requests = [
                AmazonCreativeUploadRequest(
                    name=f"Batch Creative {i}",
                    format="CUSTOM_HTML",
                    creative_code=f"<div>Batch creative content {i}</div>",
                    width=320,
                    height=50,
                    advertiser_id="123456"
                )
                for i in range(3)
            ]
            
            responses = await client.batch_upload_creatives(requests)
            
            assert len(responses) == 3
            for i, response in enumerate(responses):
                assert response.name == f"Batch Creative {i}"
                assert response.creative_id.startswith("creative_")
    
    async def test_batch_upload_with_failures(self):
        """Test batch upload with some failures."""
        async with MockAmazonDSPClient() as client:
            requests = [
                # Valid creative
                AmazonCreativeUploadRequest(
                    name="Valid Creative",
                    format="CUSTOM_HTML",
                    creative_code="<div>Valid creative content</div>",
                    width=320,
                    height=50,
                    advertiser_id="123456"
                ),
                # Invalid creative (too short)
                AmazonCreativeUploadRequest(
                    name="Invalid Creative",
                    format="CUSTOM_HTML",
                    creative_code="<div>Bad</div>",  # Too short
                    width=320,
                    height=50,
                    advertiser_id="123456"
                ),
            ]
            
            responses = await client.batch_upload_creatives(requests)
            
            # Should only get response for valid creative
            assert len(responses) == 1
            assert responses[0].name == "Valid Creative"
    
    async def test_mock_data_summary(self):
        """Test mock data summary functionality."""
        async with MockAmazonDSPClient() as client:
            # Upload some test data
            creative_request = AmazonCreativeUploadRequest(
                name="Summary Test Creative",
                format="CUSTOM_HTML",
                creative_code="<div>Test creative for summary</div>",
                width=320,
                height=50,
                advertiser_id="123456"
            )
            
            campaign_request = AmazonCampaignRequest(
                advertiser_id="123456",
                name="Summary Test Campaign",
                budget=5000.0,
                start_date="2024-01-01",
                end_date="2024-01-31",
                goal="VIEWABILITY"
            )
            
            creative_response = await client.upload_creative(creative_request)
            campaign_response = await client.create_campaign(campaign_request)
            
            # Get summary
            summary = client.get_mock_data_summary()
            
            assert summary["creatives"] >= 1
            assert summary["campaigns"] >= 1
            assert creative_response.creative_id in summary["creative_ids"]
            assert campaign_response.campaign_id in summary["campaign_ids"]
    
    async def test_access_token_refresh(self):
        """Test access token refresh logic."""
        async with MockAmazonDSPClient() as client:
            # Get initial token
            token1 = await client._get_access_token()
            assert token1 == "mock_access_token_12345"
            
            # Force token expiration
            from datetime import datetime, timedelta
            client._token_expires_at = datetime.utcnow() - timedelta(minutes=1)
            
            # Get token again - should refresh
            token2 = await client._get_access_token()
            assert token2.startswith("refreshed_token_")
            assert token2 != token1
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    async def test_api_latency_simulation(self, mock_sleep):
        """Test that API latency simulation is working."""
        async with MockAmazonDSPClient() as client:
            request = AmazonCreativeUploadRequest(
                name="Latency Test",
                format="CUSTOM_HTML",
                creative_code="<div>Testing latency simulation</div>",
                width=320,
                height=50,
                advertiser_id="123456"
            )
            
            await client.upload_creative(request)
            
            # Should have called sleep for latency simulation
            assert mock_sleep.called


@pytest.mark.asyncio
class TestAmazonClientIntegration:
    """Integration tests for Amazon client."""
    
    async def test_creative_upload_and_retrieval_flow(self):
        """Test complete upload and retrieval flow."""
        async with MockAmazonDSPClient() as client:
            # Upload creative
            upload_request = AmazonCreativeUploadRequest(
                name="Integration Test Creative",
                format="VAST_3_0",
                creative_code="<?xml version='1.0'?><VAST version='3.0'>...</VAST>",
                width=300,
                height=50,
                advertiser_id="789012"
            )
            
            upload_response = await client.upload_creative(upload_request)
            
            # Retrieve creative
            retrieved = await client.get_creative(upload_response.creative_id)
            
            # Verify consistency
            assert retrieved.creative_id == upload_response.creative_id
            assert retrieved.name == upload_request.name
            assert retrieved.format == upload_request.format
    
    async def test_campaign_and_viewability_flow(self):
        """Test campaign creation and viewability setup flow."""
        async with MockAmazonDSPClient() as client:
            # Create campaign
            campaign_request = AmazonCampaignRequest(
                advertiser_id="456789",
                name="Integration Test Campaign",
                budget=25000.0,
                start_date="2024-02-01",
                end_date="2024-02-29",
                goal="VIEWABILITY"
            )
            
            campaign_response = await client.create_campaign(campaign_request)
            
            # Setup viewability reporting
            viewability_request = ViewabilityReportRequest(
                campaign_id=campaign_response.campaign_id,
                metrics=["viewable_impressions", "measurable_impressions", "viewability_rate"],
                reporting_frequency="daily"
            )
            
            viewability_response = await client.setup_viewability_reporting(viewability_request)
            
            # Get viewability data
            viewability_data = await client.get_viewability_data(campaign_response.campaign_id)
            
            # Verify flow consistency
            assert viewability_response.campaign_id == campaign_response.campaign_id
            assert viewability_data["campaign_id"] == campaign_response.campaign_id
            assert len(viewability_response.metrics_configured) == 3