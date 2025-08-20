"""Tests for Pydantic models."""
import pytest
from datetime import date, timedelta
from pydantic import ValidationError

from app.models.creative import (
    CreativeConfig, 
    ViewabilityConfig, 
    CreativeFormat, 
    ViewabilityPhase, 
    ViewabilityVendor,
    DeviceType,
    ProcessingMetadata,
    EXAMPLE_RUNWAY_CONFIG,
    EXAMPLE_VIDEO_CONFIG
)
from app.models.campaign import (
    CampaignConfig, 
    CampaignPhase, 
    GoalKPI,
    EXAMPLE_CAMPAIGN_CONFIG
)


class TestCreativeModels:
    """Test creative-related models."""
    
    def test_creative_config_valid(self):
        """Test valid creative configuration."""
        config = CreativeConfig(
            name="Test Creative",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/12345",
            device_type=DeviceType.MOBILE,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        assert config.name == "Test Creative"
        assert config.format == CreativeFormat.RUNWAY
        assert config.dimensions == "320x50"
        assert config.device_type == DeviceType.MOBILE
    
    def test_creative_config_invalid_dimensions(self):
        """Test creative configuration with invalid dimensions."""
        with pytest.raises(ValidationError) as exc_info:
            CreativeConfig(
                name="Test Creative",
                format=CreativeFormat.RUNWAY,
                dimensions="invalid",
                snippet_url="https://snippet.kargo.com/snippet/dm/12345",
                viewability_config=ViewabilityConfig(
                    phase=ViewabilityPhase.PHASE_1,
                    vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                    method="platform_native"
                )
            )
        
        assert "Dimensions must be in format" in str(exc_info.value)
    
    def test_viewability_config_phase_1(self):
        """Test Phase 1 viewability configuration."""
        config = ViewabilityConfig(
            phase=ViewabilityPhase.PHASE_1,
            vendors=[ViewabilityVendor.DOUBLE_VERIFY],
            method="platform_native"
        )
        
        assert config.phase == ViewabilityPhase.PHASE_1
        assert config.dv_native is True
        assert config.ias_removed is True
        assert config.ias_s2s_enabled is False
    
    def test_viewability_config_phase_1_with_ias_error(self):
        """Test Phase 1 configuration with IAS should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.IAS, ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        
        assert "Phase 1 should not include IAS" in str(exc_info.value)
    
    def test_viewability_config_phase_2(self):
        """Test Phase 2 viewability configuration."""
        config = ViewabilityConfig(
            phase=ViewabilityPhase.PHASE_2,
            vendors=[ViewabilityVendor.IAS, ViewabilityVendor.DOUBLE_VERIFY],
            method="s2s_plus_wrapped",
            ias_s2s_enabled=True,
            dsp_seat_id="KARGO_DSP_SEAT_001",
            pub_id="kargo_test_pub"
        )
        
        assert config.phase == ViewabilityPhase.PHASE_2
        assert config.ias_s2s_enabled is True
        assert config.dsp_seat_id == "KARGO_DSP_SEAT_001"
        assert ViewabilityVendor.IAS in config.vendors
        assert ViewabilityVendor.DOUBLE_VERIFY in config.vendors
    
    def test_viewability_config_phase_2_insufficient_vendors(self):
        """Test Phase 2 configuration with insufficient vendors."""
        with pytest.raises(ValidationError) as exc_info:
            ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_2,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="s2s_plus_wrapped"
            )
        
        assert "Phase 2 should include both IAS and DV vendors" in str(exc_info.value)
    
    def test_processing_metadata(self):
        """Test processing metadata model."""
        metadata = ProcessingMetadata(
            processing_time_ms=150.5,
            original_snippet_size=1024,
            processed_snippet_size=2048,
            tags_removed=["ias_tag_1", "ias_tag_2"],
            tags_added=["amazon_macro_1"],
            warnings=["Phase 1 warning"],
            phase_applied=ViewabilityPhase.PHASE_1
        )
        
        assert metadata.processing_time_ms == 150.5
        assert len(metadata.tags_removed) == 2
        assert len(metadata.tags_added) == 1
        assert metadata.phase_applied == ViewabilityPhase.PHASE_1
    
    def test_example_configs(self):
        """Test example configurations are valid."""
        # Should not raise validation errors
        assert EXAMPLE_RUNWAY_CONFIG.format == CreativeFormat.RUNWAY
        assert EXAMPLE_VIDEO_CONFIG.format == CreativeFormat.ENHANCED_PREROLL
        assert EXAMPLE_VIDEO_CONFIG.branded_canvas is True


class TestCampaignModels:
    """Test campaign-related models."""
    
    def test_campaign_config_valid(self):
        """Test valid campaign configuration."""
        start_date = date.today() + timedelta(days=1)
        end_date = date.today() + timedelta(days=31)
        
        config = CampaignConfig(
            name="Test Campaign",
            advertiser_id="123456",
            goal_kpi=GoalKPI.VIEWABILITY,
            total_budget=10000.0,
            start_date=start_date,
            end_date=end_date,
            phase=CampaignPhase.PHASE_1,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        assert config.name == "Test Campaign"
        assert config.total_budget == 10000.0
        assert config.phase == CampaignPhase.PHASE_1
    
    def test_campaign_config_invalid_dates(self):
        """Test campaign configuration with invalid dates."""
        start_date = date.today() + timedelta(days=10)
        end_date = date.today() + timedelta(days=5)  # Before start date
        
        with pytest.raises(ValidationError) as exc_info:
            CampaignConfig(
                name="Test Campaign",
                advertiser_id="123456",
                total_budget=10000.0,
                start_date=start_date,
                end_date=end_date,
                phase=CampaignPhase.PHASE_1,
                viewability_config=ViewabilityConfig(
                    phase=ViewabilityPhase.PHASE_1,
                    vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                    method="platform_native"
                )
            )
        
        assert "End date must be after start date" in str(exc_info.value)
    
    def test_campaign_config_negative_budget(self):
        """Test campaign configuration with negative budget."""
        start_date = date.today() + timedelta(days=1)
        end_date = date.today() + timedelta(days=31)
        
        with pytest.raises(ValidationError) as exc_info:
            CampaignConfig(
                name="Test Campaign",
                advertiser_id="123456",
                total_budget=-1000.0,  # Negative budget
                start_date=start_date,
                end_date=end_date,
                phase=CampaignPhase.PHASE_1,
                viewability_config=ViewabilityConfig(
                    phase=ViewabilityPhase.PHASE_1,
                    vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                    method="platform_native"
                )
            )
        
        assert "greater than 0" in str(exc_info.value)
    
    def test_campaign_config_with_creatives(self):
        """Test campaign configuration with creative lists."""
        start_date = date.today() + timedelta(days=1)
        end_date = date.today() + timedelta(days=31)
        
        runway_creative = CreativeConfig(
            name="Runway Creative",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/12345",
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        config = CampaignConfig(
            name="Test Campaign",
            advertiser_id="123456",
            total_budget=10000.0,
            start_date=start_date,
            end_date=end_date,
            phase=CampaignPhase.PHASE_1,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            ),
            runway_creatives=[runway_creative]
        )
        
        assert len(config.runway_creatives) == 1
        assert config.runway_creatives[0].name == "Runway Creative"
    
    def test_campaign_config_invalid_creative(self):
        """Test campaign configuration with invalid creative."""
        start_date = date.today() + timedelta(days=1)
        end_date = date.today() + timedelta(days=31)
        
        # Creative with missing name
        invalid_creative = CreativeConfig(
            name="",  # Empty name
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/12345",
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        with pytest.raises(ValidationError) as exc_info:
            CampaignConfig(
                name="Test Campaign",
                advertiser_id="123456",
                total_budget=10000.0,
                start_date=start_date,
                end_date=end_date,
                phase=CampaignPhase.PHASE_1,
                viewability_config=ViewabilityConfig(
                    phase=ViewabilityPhase.PHASE_1,
                    vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                    method="platform_native"
                ),
                runway_creatives=[invalid_creative]
            )
        
        assert "All creatives must have name and snippet_url" in str(exc_info.value)
    
    def test_example_campaign_config(self):
        """Test example campaign configuration is valid."""
        # Should not raise validation errors
        assert EXAMPLE_CAMPAIGN_CONFIG.name == "RMI_Q3_2025_HighImpact_Phase1"
        assert EXAMPLE_CAMPAIGN_CONFIG.phase == CampaignPhase.PHASE_1
        assert len(EXAMPLE_CAMPAIGN_CONFIG.runway_creatives) > 0