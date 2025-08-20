"""Tests for campaign manager service."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.campaign_manager import (
    CampaignManager,
    CampaignCreationRequest,
    CampaignUpdateRequest,
    CampaignResponse
)
from app.services.amazon_client import MockAmazonDSPClient
from app.services.creative_processor import CreativeProcessor
from app.models.creative import ViewabilityPhase
from app.models.database import CampaignDB, ProcessedCreativeDB


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_amazon_client():
    """Mock Amazon DSP client."""
    return MockAmazonDSPClient()


@pytest.fixture
def mock_creative_processor(mock_db_session):
    """Mock creative processor.""" 
    return CreativeProcessor(mock_db_session)


@pytest.fixture
def campaign_manager(mock_db_session, mock_amazon_client, mock_creative_processor):
    """Campaign manager instance."""
    return CampaignManager(mock_db_session, mock_amazon_client, mock_creative_processor)


@pytest.fixture
def sample_campaign_request():
    """Sample campaign creation request."""
    return CampaignCreationRequest(
        name="Test Campaign",
        advertiser_id="adv_123",
        campaign_type="display_and_video",
        viewability_phase=ViewabilityPhase.PHASE_1,
        budget=10000.0,
        start_date=datetime.utcnow() + timedelta(days=1),
        end_date=datetime.utcnow() + timedelta(days=30),
        creatives=["creative_1", "creative_2"]
    )


@pytest.fixture
def mock_processed_creative():
    """Mock processed creative."""
    return ProcessedCreativeDB(
        creative_id="creative_1",
        name="Test Creative",
        format="runway_display",
        original_snippet_url="https://example.com/snippet",
        processed_code="<div>Processed HTML</div>",
        amazon_dsp_ready=True,
        creative_type="display",
        viewability_config={"phase": "phase_1", "vendors": ["double_verify"]},
        processing_metadata={"width": 300, "height": 250},
        original_config={},
        status="processed"
    )


class TestCampaignManager:
    """Test campaign manager functionality."""
    
    @pytest.mark.asyncio
    async def test_create_campaign_success(
        self,
        campaign_manager,
        sample_campaign_request,
        mock_processed_creative,
        mock_db_session
    ):
        """Test successful campaign creation."""
        # Mock creative validation
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
            mock_processed_creative
        ]
        
        # Mock Amazon campaign creation
        campaign_manager.amazon_client._campaigns = {}
        
        # Create campaign
        result = await campaign_manager.create_campaign(sample_campaign_request)
        
        # Assertions
        assert isinstance(result, CampaignResponse)
        assert result.name == "Test Campaign"
        assert result.viewability_phase == "phase_1"
        assert result.budget == 10000.0
        assert result.creative_count == 2
        assert result.processed_creatives_count == 1
        
        # Verify database operations
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_campaign_missing_creatives(
        self,
        campaign_manager,
        sample_campaign_request,
        mock_db_session
    ):
        """Test campaign creation with missing creatives."""
        # Mock empty creative result
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Creatives not found"):
            await campaign_manager.create_campaign(sample_campaign_request)
    
    @pytest.mark.asyncio
    async def test_get_campaign_success(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test successful campaign retrieval."""
        # Mock campaign data
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="draft",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=2,
            processed_creatives_count=2,
            order_id="order_123"
        )
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_campaign
        
        # Get campaign
        result = await campaign_manager.get_campaign("camp_123")
        
        # Assertions
        assert isinstance(result, CampaignResponse)
        assert result.campaign_id == "camp_123"
        assert result.name == "Test Campaign"
        assert result.amazon_order_id == "order_123"
    
    @pytest.mark.asyncio
    async def test_get_campaign_not_found(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test campaign retrieval with missing campaign."""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(ValueError, match="Campaign not found"):
            await campaign_manager.get_campaign("nonexistent")
    
    @pytest.mark.asyncio
    async def test_update_campaign_success(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test successful campaign update."""
        # Mock existing campaign
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="draft",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=2,
            processed_creatives_count=2
        )
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_campaign
        
        # Update request
        update_request = CampaignUpdateRequest(
            status="active",
            budget=15000.0
        )
        
        # Update campaign
        result = await campaign_manager.update_campaign("camp_123", update_request)
        
        # Assertions
        assert result.status == "active"
        assert result.budget == 15000.0
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_activate_campaign_success(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test successful campaign activation."""
        # Mock campaign with order ID
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="draft",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=2,
            processed_creatives_count=2,
            order_id="order_123"
        )
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_campaign
        
        # Activate campaign
        result = await campaign_manager.activate_campaign("camp_123")
        
        # Assertions
        assert result.status == "active"
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_activate_campaign_not_ready(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test campaign activation when not ready."""
        # Mock campaign without order ID
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="draft",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=2,
            processed_creatives_count=0,
            order_id=None
        )
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_campaign
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Campaign not synced with Amazon DSP"):
            await campaign_manager.activate_campaign("camp_123")
    
    @pytest.mark.asyncio
    async def test_list_campaigns_with_filters(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test campaign listing with filters."""
        # Mock campaign list
        mock_campaigns = [
            CampaignDB(
                campaign_id="camp_1",
                name="Campaign 1",
                advertiser_id="adv_123",
                status="active",
                phase="phase_1",
                config={},
                viewability_config={},
                total_budget=10000.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                creative_count=2,
                processed_creatives_count=2
            ),
            CampaignDB(
                campaign_id="camp_2",
                name="Campaign 2",
                advertiser_id="adv_123",
                status="draft",
                phase="phase_2",
                config={},
                viewability_config={},
                total_budget=20000.0,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                creative_count=3,
                processed_creatives_count=3
            )
        ]
        
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_campaigns
        
        # List campaigns
        result = await campaign_manager.list_campaigns(
            advertiser_id="adv_123",
            status="active"
        )
        
        # Assertions
        assert len(result) == 2  # Mock returns all, filter would be in query
        assert all(isinstance(campaign, CampaignResponse) for campaign in result)
    
    @pytest.mark.asyncio
    async def test_add_creatives_to_campaign(
        self,
        campaign_manager,
        mock_processed_creative,
        mock_db_session
    ):
        """Test adding creatives to existing campaign."""
        # Mock existing campaign
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="draft",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=1,
            processed_creatives_count=1
        )
        
        # Mock database responses
        mock_db_session.execute.side_effect = [
            # First call: get campaign
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_campaign)),
            # Second call: validate creatives
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_processed_creative])))),
            # Third call: get existing associations
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        ]
        
        # Add creatives
        result = await campaign_manager.add_creatives_to_campaign(
            "camp_123",
            ["creative_1"]
        )
        
        # Assertions
        assert isinstance(result, CampaignResponse)
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_delete_campaign_success(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test successful campaign deletion."""
        # Mock draft campaign
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="draft",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=2,
            processed_creatives_count=2
        )
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_campaign
        
        # Delete campaign
        result = await campaign_manager.delete_campaign("camp_123")
        
        # Assertions
        assert "deleted successfully" in result["message"]
        assert mock_campaign.status == "deleted"
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_delete_active_campaign_fails(
        self,
        campaign_manager,
        mock_db_session
    ):
        """Test deletion of active campaign fails."""
        # Mock active campaign
        mock_campaign = CampaignDB(
            campaign_id="camp_123",
            name="Test Campaign",
            advertiser_id="adv_123",
            status="active",
            phase="phase_1",
            config={},
            viewability_config={},
            total_budget=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            creative_count=2,
            processed_creatives_count=2
        )
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_campaign
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Cannot delete active campaign"):
            await campaign_manager.delete_campaign("camp_123")
    
    def test_get_vendors_for_phase(self, campaign_manager):
        """Test vendor selection by phase."""
        # Phase 1: DV only
        vendors = campaign_manager._get_vendors_for_phase(ViewabilityPhase.PHASE_1)
        assert vendors == ["double_verify"]
        
        # Phase 2: DV + IAS
        vendors = campaign_manager._get_vendors_for_phase(ViewabilityPhase.PHASE_2)
        assert vendors == ["double_verify", "ias"]
    
    def test_get_line_item_type(self, campaign_manager):
        """Test line item type determination."""
        # Video format
        line_item_type = campaign_manager._get_line_item_type("enhanced_pre_roll_video")
        assert line_item_type == "video"
        
        # Display format
        line_item_type = campaign_manager._get_line_item_type("runway_display")
        assert line_item_type == "display"
        
        # Unknown format
        line_item_type = campaign_manager._get_line_item_type("unknown_format")
        assert line_item_type == "standard"