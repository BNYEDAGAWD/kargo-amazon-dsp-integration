"""Tests for campaign API endpoints."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.services.campaign_manager import CampaignResponse
from app.services.bulk_generator import BulkSheetResponse
from app.models.creative import ViewabilityPhase


@pytest.fixture
def client():
    """Test client for API testing."""
    return TestClient(app)


@pytest.fixture
def sample_campaign_request():
    """Sample campaign creation request."""
    return {
        "name": "Test Campaign API",
        "advertiser_id": "adv_456",
        "campaign_type": "display_and_video",
        "viewability_phase": "phase_1",
        "budget": 25000.0,
        "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "creatives": ["creative_1", "creative_2"]
    }


@pytest.fixture
def mock_campaign_response():
    """Mock campaign response."""
    return CampaignResponse(
        campaign_id="camp_api_123",
        name="Test Campaign API",
        status="draft",
        viewability_phase="phase_1",
        budget=25000.0,
        spend=0.0,
        impressions=0,
        clicks=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        amazon_order_id="order_456",
        creative_count=2,
        processed_creatives_count=2
    )


class TestCampaignAPI:
    """Test campaign API endpoints."""
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_create_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        sample_campaign_request,
        mock_campaign_response
    ):
        """Test successful campaign creation via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.create_campaign.return_value = mock_campaign_response
            mock_manager_class.return_value = mock_manager
            
            # Make request
            response = client.post("/api/v1/campaign/", json=sample_campaign_request)
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["campaign_id"] == "camp_api_123"
            assert data["name"] == "Test Campaign API"
            assert data["budget"] == 25000.0
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_create_campaign_validation_error(
        self,
        mock_amazon_client,
        mock_db_session,
        client
    ):
        """Test campaign creation with validation error."""
        # Invalid request (missing required fields)
        invalid_request = {
            "name": "Test Campaign",
            # Missing required fields
        }
        
        # Make request
        response = client.post("/api/v1/campaign/", json=invalid_request)
        
        # Assertions
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_get_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        mock_campaign_response
    ):
        """Test successful campaign retrieval via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.get_campaign.return_value = mock_campaign_response
            mock_manager_class.return_value = mock_manager
            
            # Make request
            response = client.get("/api/v1/campaign/camp_api_123")
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["campaign_id"] == "camp_api_123"
            assert data["name"] == "Test Campaign API"
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_get_campaign_not_found(
        self,
        mock_amazon_client,
        mock_db_session,
        client
    ):
        """Test campaign retrieval with missing campaign."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Mock campaign manager to raise ValueError
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.get_campaign.side_effect = ValueError("Campaign not found")
            mock_manager_class.return_value = mock_manager
            
            # Make request
            response = client.get("/api/v1/campaign/nonexistent")
            
            # Assertions
            assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_list_campaigns_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        mock_campaign_response
    ):
        """Test successful campaign listing via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.list_campaigns.return_value = [mock_campaign_response]
            mock_manager_class.return_value = mock_manager
            
            # Make request with filters
            response = client.get(
                "/api/v1/campaign/",
                params={
                    "advertiser_id": "adv_456",
                    "status": "active",
                    "phase": "phase_1"
                }
            )
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["campaign_id"] == "camp_api_123"
    
    @patch('app.api.campaign.get_db_session')
    def test_generate_bulk_sheet_success(
        self,
        mock_db_session,
        client
    ):
        """Test successful bulk sheet generation via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock bulk sheet response
        mock_bulk_response = BulkSheetResponse(
            file_path="/tmp/bulk_sheet_camp_123.xlsx",
            file_name="bulk_sheet_camp_123.xlsx",
            total_rows=25,
            sheets=["Campaign_Info", "Creatives", "Line_Items"],
            created_at=datetime.utcnow()
        )
        
        # Mock bulk sheet generator
        with patch('app.api.campaign.BulkSheetGenerator') as mock_generator_class:
            mock_generator = AsyncMock()
            mock_generator.generate_bulk_sheet.return_value = mock_bulk_response
            mock_generator_class.return_value = mock_generator
            
            # Bulk sheet request
            request_data = {
                "campaign_id": "camp_123",
                "include_creatives": True,
                "include_line_items": True,
                "include_targeting": True,
                "format": "xlsx"
            }
            
            # Make request
            response = client.post("/api/v1/campaign/camp_123/bulk-sheet", json=request_data)
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["file_name"] == "bulk_sheet_camp_123.xlsx"
            assert data["total_rows"] == 25
            assert len(data["sheets"]) == 3
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_update_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        mock_campaign_response
    ):
        """Test successful campaign update via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Update response
        updated_response = mock_campaign_response.copy()
        updated_response.status = "active"
        updated_response.budget = 30000.0
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.update_campaign.return_value = updated_response
            mock_manager_class.return_value = mock_manager
            
            # Update request
            update_data = {
                "status": "active",
                "budget": 30000.0
            }
            
            # Make request
            response = client.put("/api/v1/campaign/camp_123", json=update_data)
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "active"
            assert data["budget"] == 30000.0
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_activate_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        mock_campaign_response
    ):
        """Test successful campaign activation via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Active response
        active_response = mock_campaign_response.copy()
        active_response.status = "active"
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.activate_campaign.return_value = active_response
            mock_manager_class.return_value = mock_manager
            
            # Make request
            response = client.post("/api/v1/campaign/camp_123/activate")
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "active"
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_pause_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        mock_campaign_response
    ):
        """Test successful campaign pause via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Paused response
        paused_response = mock_campaign_response.copy()
        paused_response.status = "paused"
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.pause_campaign.return_value = paused_response
            mock_manager_class.return_value = mock_manager
            
            # Make request
            response = client.post("/api/v1/campaign/camp_123/pause")
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "paused"
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_delete_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client
    ):
        """Test successful campaign deletion via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.delete_campaign.return_value = {
                "message": "Campaign camp_123 deleted successfully"
            }
            mock_manager_class.return_value = mock_manager
            
            # Make request
            response = client.delete("/api/v1/campaign/camp_123")
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "deleted successfully" in data["message"]
    
    @patch('app.api.campaign.get_db_session')
    @patch('app.api.campaign.get_amazon_dsp_client')
    def test_add_creatives_to_campaign_success(
        self,
        mock_amazon_client,
        mock_db_session,
        client,
        mock_campaign_response
    ):
        """Test successful addition of creatives to campaign via API."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock Amazon client
        mock_amazon_client.return_value = AsyncMock()
        
        # Updated response with more creatives
        updated_response = mock_campaign_response.copy()
        updated_response.creative_count = 4
        updated_response.processed_creatives_count = 4
        
        # Mock campaign manager
        with patch('app.api.campaign.CampaignManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.add_creatives_to_campaign.return_value = updated_response
            mock_manager_class.return_value = mock_manager
            
            # Creative IDs to add
            creative_ids = ["creative_3", "creative_4"]
            
            # Make request
            response = client.post(
                "/api/v1/campaign/camp_123/creatives",
                json=creative_ids
            )
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["creative_count"] == 4
            assert data["processed_creatives_count"] == 4
    
    @patch('app.api.campaign.get_db_session')
    def test_download_bulk_sheet_list(
        self,
        mock_db_session,
        client
    ):
        """Test bulk sheet listing via download endpoint."""
        # Mock database session
        mock_session = AsyncMock()
        mock_db_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock async generator
        async def mock_get_db():
            yield mock_session
        mock_db_session.return_value = mock_get_db()
        
        # Mock bulk sheets list
        mock_sheets = [
            {
                "file_name": "bulk_sheet_camp_123_20240101.xlsx",
                "file_path": "/tmp/bulk_sheet_camp_123_20240101.xlsx",
                "size": 1024,
                "created_at": datetime.utcnow(),
                "modified_at": datetime.utcnow()
            }
        ]
        
        # Mock bulk sheet generator
        with patch('app.api.campaign.BulkSheetGenerator') as mock_generator_class:
            mock_generator = AsyncMock()
            mock_generator.list_bulk_sheets.return_value = mock_sheets
            mock_generator_class.return_value = mock_generator
            
            # Make request (no file_path parameter = list mode)
            response = client.get("/api/v1/campaign/camp_123/bulk-sheet/download")
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "bulk_sheets" in data
            assert len(data["bulk_sheets"]) == 1