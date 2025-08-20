"""Tests for creative processing service."""
import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.creative_processor import CreativeProcessor, SnippetTransformer
from app.models.creative import (
    CreativeConfig,
    CreativeFormat,
    ViewabilityConfig,
    ViewabilityPhase,
    ViewabilityVendor,
    DeviceType,
)


class TestSnippetTransformer:
    """Test snippet transformation logic."""
    
    def test_remove_ias_tags(self):
        """Test IAS tag removal."""
        snippet_with_ias = """
        <div class="creative">
            <img src="https://pixel.adsafeprotected.com/rfw/st/818052/81298/skeleton.gif" style="display:none;">
            <script src="https://fw.adsafeprotected.com/rfw/st/818052/81298/skeleton.js"></script>
            <p>Creative content</p>
        </div>
        """
        
        cleaned_code, removed_tags = SnippetTransformer.remove_ias_tags(snippet_with_ias)
        
        assert len(removed_tags) == 2
        assert "adsafeprotected" not in cleaned_code
        assert "Creative content" in cleaned_code
    
    def test_inject_amazon_macros(self):
        """Test Amazon macro injection."""
        snippet = """
        <div onclick="window.open('${CLICK_URL}')">
            <img src="${IMPRESSION_URL}">
        </div>
        """
        
        processed = SnippetTransformer.inject_amazon_macros(snippet)
        
        assert "${AMAZON_CLICK_URL}" in processed
        assert "${AMAZON_IMPRESSION_URL}" in processed
        assert "${CLICK_URL}" not in processed
        assert "${IMPRESSION_URL}" not in processed
    
    def test_inject_cache_buster(self):
        """Test cache buster injection."""
        snippet = "https://example.com/track?cb=${CACHEBUSTER}"
        
        processed = SnippetTransformer.inject_cache_buster(snippet, "123456789")
        
        assert "123456789" in processed
        assert "${CACHEBUSTER}" not in processed
    
    def test_wrap_display_html5_phase1(self):
        """Test Phase 1 display wrapper."""
        config = CreativeConfig(
            name="Test Runway",
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
        
        snippet_code = "<div>Original creative</div>"
        wrapped = SnippetTransformer.wrap_display_html5_phase1(snippet_code, config)
        
        assert 'data-phase="phase_1"' in wrapped
        assert '"viewability_vendor": "double_verify"' in wrapped
        assert '"viewability_method": "platform_native"' in wrapped
        assert "Original creative" in wrapped
        assert "amazonDSPConfig" in wrapped
    
    def test_wrap_display_html5_phase2(self):
        """Test Phase 2 display wrapper."""
        config = CreativeConfig(
            name="Test Runway Phase 2",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/12345",
            device_type=DeviceType.MOBILE,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_2,
                vendors=[ViewabilityVendor.IAS, ViewabilityVendor.DOUBLE_VERIFY],
                method="s2s_plus_native",
                ias_s2s_enabled=True,
                dsp_seat_id="KARGO_DSP_SEAT_001",
                pub_id="kargo_test_pub"
            )
        )
        
        snippet_code = "<div>Original creative</div>"
        wrapped = SnippetTransformer.wrap_display_html5_phase2(snippet_code, config)
        
        assert 'data-phase="phase_2"' in wrapped
        assert '"viewability_vendors": ["ias", "double_verify"]' in wrapped
        assert '"ias_s2s_enabled": true' in wrapped
        assert '"dsp_seat_id": "KARGO_DSP_SEAT_001"' in wrapped
        assert "ias-s2s-config" in wrapped
        assert "Original creative" in wrapped
    
    def test_wrap_vast_phase1(self):
        """Test Phase 1 VAST wrapper."""
        config = CreativeConfig(
            name="Test Video",
            format=CreativeFormat.ENHANCED_PREROLL,
            dimensions="300x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/67890",
            device_type=DeviceType.MOBILE,
            duration=15,
            branded_canvas=True,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="vast_wrapped"
            )
        )
        
        wrapped = SnippetTransformer.wrap_vast_phase1("", config)
        
        assert '<?xml version="1.0" encoding="UTF-8"?>' in wrapped
        assert '<VAST version="3.0">' in wrapped
        assert "Test Video_phase1" in wrapped
        assert "Kargo Amazon DSP Phase 1" in wrapped
        assert "<Duration>00:00:15</Duration>" in wrapped
        assert "doubleverify.com" in wrapped
        assert "CompanionAds" in wrapped  # Branded canvas enabled
        assert "${AMAZON_CLICK_URL}" in wrapped
    
    def test_wrap_vast_phase2(self):
        """Test Phase 2 VAST wrapper."""
        config = CreativeConfig(
            name="Test Video Phase 2",
            format=CreativeFormat.ENHANCED_PREROLL,
            dimensions="300x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/67890",
            device_type=DeviceType.MOBILE,
            duration=15,
            branded_canvas=False,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_2,
                vendors=[ViewabilityVendor.IAS, ViewabilityVendor.DOUBLE_VERIFY],
                method="s2s_plus_wrapped",
                ias_s2s_enabled=True,
                dsp_seat_id="KARGO_DSP_SEAT_001",
                pub_id="kargo_test_pub"
            )
        )
        
        wrapped = SnippetTransformer.wrap_vast_phase2("", config)
        
        assert '<VAST version="3.0">' in wrapped
        assert "Test Video Phase 2_phase2" in wrapped
        assert "Kargo Amazon DSP Phase 2" in wrapped
        assert "IAS_S2S" in wrapped
        assert "KARGO_DSP_SEAT_001" in wrapped
        assert "kargo_test_pub" in wrapped
        assert "CompanionAds" not in wrapped  # Branded canvas disabled
        assert "DualVendorEnabled" in wrapped


@pytest.mark.asyncio
class TestCreativeProcessor:
    """Test creative processing service."""
    
    async def test_process_runway_phase1(self, test_session: AsyncSession, sample_runway_config: CreativeConfig):
        """Test processing Runway creative in Phase 1."""
        processor = CreativeProcessor(test_session)
        
        # Override viewability config for Phase 1
        sample_runway_config.viewability_config = ViewabilityConfig(
            phase=ViewabilityPhase.PHASE_1,
            vendors=[ViewabilityVendor.DOUBLE_VERIFY],
            method="platform_native"
        )
        
        result = await processor.process_creative(sample_runway_config)
        
        assert result.creative_id is not None
        assert result.name == sample_runway_config.name
        assert result.format == CreativeFormat.RUNWAY
        assert result.amazon_dsp_ready is True
        assert result.creative_type == "CUSTOM_HTML"
        assert result.viewability_config.phase == ViewabilityPhase.PHASE_1
        
        # Check processed code contains expected elements
        assert 'data-phase="phase_1"' in result.processed_code
        assert "amazon-dsp-display-wrapper" in result.processed_code
        assert "${AMAZON_CLICK_URL}" in result.processed_code
        
        # Check metadata
        assert result.processing_metadata.phase_applied == ViewabilityPhase.PHASE_1
        assert len(result.processing_metadata.tags_removed) > 0  # IAS tags removed
        assert "amazon_macros" in result.processing_metadata.tags_added
        assert result.processing_metadata.processing_time_ms > 0
    
    async def test_process_runway_phase2(self, test_session: AsyncSession, sample_runway_config: CreativeConfig):
        """Test processing Runway creative in Phase 2."""
        processor = CreativeProcessor(test_session)
        
        # Override viewability config for Phase 2
        sample_runway_config.viewability_config = ViewabilityConfig(
            phase=ViewabilityPhase.PHASE_2,
            vendors=[ViewabilityVendor.IAS, ViewabilityVendor.DOUBLE_VERIFY],
            method="s2s_plus_native",
            ias_s2s_enabled=True,
            dsp_seat_id="KARGO_DSP_SEAT_001",
            pub_id="kargo_test_pub"
        )
        
        result = await processor.process_creative(sample_runway_config)
        
        assert result.viewability_config.phase == ViewabilityPhase.PHASE_2
        assert result.viewability_config.ias_s2s_enabled is True
        
        # Check processed code contains Phase 2 elements
        assert 'data-phase="phase_2"' in result.processed_code
        assert "ias-s2s-config" in result.processed_code
        assert "KARGO_DSP_SEAT_001" in result.processed_code
        assert "kargo_test_pub" in result.processed_code
    
    async def test_process_video_phase1(self, test_session: AsyncSession, sample_video_config: CreativeConfig):
        """Test processing video creative in Phase 1."""
        processor = CreativeProcessor(test_session)
        
        # Override for Phase 1
        sample_video_config.viewability_config = ViewabilityConfig(
            phase=ViewabilityPhase.PHASE_1,
            vendors=[ViewabilityVendor.DOUBLE_VERIFY],
            method="vast_wrapped"
        )
        
        result = await processor.process_creative(sample_video_config)
        
        assert result.format == CreativeFormat.ENHANCED_PREROLL
        assert result.creative_type == "VAST_3_0"
        
        # Check VAST structure
        assert '<?xml version="1.0" encoding="UTF-8"?>' in result.processed_code
        assert '<VAST version="3.0">' in result.processed_code
        assert "<Duration>00:00:15</Duration>" in result.processed_code
        assert "doubleverify.com" in result.processed_code
        assert "phase_1" in result.processed_code
    
    async def test_process_video_phase2(self, test_session: AsyncSession, sample_video_config: CreativeConfig):
        """Test processing video creative in Phase 2."""
        processor = CreativeProcessor(test_session)
        
        # Use the Phase 2 config from sample_video_config (already configured)
        result = await processor.process_creative(sample_video_config)
        
        assert result.viewability_config.phase == ViewabilityPhase.PHASE_2
        
        # Check Phase 2 VAST elements
        assert "IAS_S2S" in result.processed_code
        assert "DualVendorEnabled" in result.processed_code
        assert sample_video_config.viewability_config.dsp_seat_id in result.processed_code
    
    async def test_get_processed_creative(self, test_session: AsyncSession, sample_runway_config: CreativeConfig):
        """Test retrieving processed creative by ID."""
        processor = CreativeProcessor(test_session)
        
        # Process creative
        original = await processor.process_creative(sample_runway_config)
        
        # Retrieve by ID
        retrieved = await processor.get_processed_creative(original.creative_id)
        
        assert retrieved is not None
        assert retrieved.creative_id == original.creative_id
        assert retrieved.name == original.name
        assert retrieved.processed_code == original.processed_code
    
    async def test_get_nonexistent_creative(self, test_session: AsyncSession):
        """Test retrieving non-existent creative returns None."""
        processor = CreativeProcessor(test_session)
        
        result = await processor.get_processed_creative("nonexistent-id")
        assert result is None
    
    async def test_list_processed_creatives(self, test_session: AsyncSession, sample_runway_config: CreativeConfig):
        """Test listing processed creatives."""
        processor = CreativeProcessor(test_session)
        
        # Process multiple creatives
        config1 = sample_runway_config.copy()
        config1.name = "Test Creative 1"
        
        config2 = sample_runway_config.copy()
        config2.name = "Test Creative 2"
        
        await processor.process_creative(config1)
        await processor.process_creative(config2)
        
        # List creatives
        creatives = await processor.list_processed_creatives(skip=0, limit=10)
        
        assert len(creatives) == 2
        # Check they're ordered by creation date (most recent first)
        assert creatives[0].name == "Test Creative 2"
        assert creatives[1].name == "Test Creative 1"
    
    async def test_delete_processed_creative(self, test_session: AsyncSession, sample_runway_config: CreativeConfig):
        """Test deleting processed creative."""
        processor = CreativeProcessor(test_session)
        
        # Process creative
        original = await processor.process_creative(sample_runway_config)
        
        # Delete creative
        deleted = await processor.delete_processed_creative(original.creative_id)
        assert deleted is True
        
        # Verify it's gone
        retrieved = await processor.get_processed_creative(original.creative_id)
        assert retrieved is None
        
        # Try to delete non-existent creative
        deleted_again = await processor.delete_processed_creative(original.creative_id)
        assert deleted_again is False
    
    async def test_invalid_snippet_url(self, test_session: AsyncSession):
        """Test processing with invalid snippet URL."""
        processor = CreativeProcessor(test_session)
        
        config = CreativeConfig(
            name="Invalid URL Test",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://invalid-domain.com/snippet",
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        with pytest.raises(ValueError, match="Invalid snippet URL"):
            await processor.process_creative(config)
    
    async def test_processing_metadata_accuracy(self, test_session: AsyncSession, sample_kargo_snippet: str):
        """Test that processing metadata is accurate."""
        processor = CreativeProcessor(test_session)
        
        config = CreativeConfig(
            name="Metadata Test",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/81298",  # Has IAS tags in mock
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        result = await processor.process_creative(config)
        
        metadata = result.processing_metadata
        
        # Check processing time is recorded
        assert metadata.processing_time_ms > 0
        
        # Check size changes
        assert metadata.original_snippet_size > 0
        assert metadata.processed_snippet_size > metadata.original_snippet_size  # Wrapper adds content
        
        # Check tags were processed
        assert len(metadata.tags_removed) > 0  # IAS tags should be removed
        assert "amazon_macros" in metadata.tags_added
        assert "amazon_dsp_wrapper" in metadata.tags_added
        
        # Check phase is recorded
        assert metadata.phase_applied == ViewabilityPhase.PHASE_1
    
    async def test_phase_validation_warnings(self, test_session: AsyncSession):
        """Test that phase validation generates appropriate warnings."""
        processor = CreativeProcessor(test_session)
        
        # This config has a mismatch that should generate warnings
        config = CreativeConfig(
            name="Warning Test",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/81298",  # Mock has IAS tags
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,  # Phase 1 but snippet has IAS
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        result = await processor.process_creative(config)
        
        # Should have warnings about IAS tags being found in Phase 1
        assert len(result.processing_metadata.warnings) > 0
    
    @pytest.mark.integration
    async def test_end_to_end_processing_flow(self, test_session: AsyncSession):
        """Test complete end-to-end creative processing flow."""
        processor = CreativeProcessor(test_session)
        
        # Phase 1 Runway creative
        runway_config = CreativeConfig(
            name="E2E_Runway_Phase1",
            format=CreativeFormat.RUNWAY,
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/81298",
            device_type=DeviceType.MOBILE,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_1,
                vendors=[ViewabilityVendor.DOUBLE_VERIFY],
                method="platform_native"
            )
        )
        
        # Phase 2 Video creative
        video_config = CreativeConfig(
            name="E2E_Video_Phase2",
            format=CreativeFormat.ENHANCED_PREROLL,
            dimensions="300x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/81172",
            device_type=DeviceType.MOBILE,
            duration=15,
            branded_canvas=True,
            viewability_config=ViewabilityConfig(
                phase=ViewabilityPhase.PHASE_2,
                vendors=[ViewabilityVendor.IAS, ViewabilityVendor.DOUBLE_VERIFY],
                method="s2s_plus_wrapped",
                ias_s2s_enabled=True,
                dsp_seat_id="KARGO_DSP_SEAT_001",
                pub_id="kargo_test_pub"
            )
        )
        
        # Process both creatives
        runway_result = await processor.process_creative(runway_config)
        video_result = await processor.process_creative(video_config)
        
        # Verify results
        assert runway_result.amazon_dsp_ready is True
        assert video_result.amazon_dsp_ready is True
        
        # Verify they're stored in database
        all_creatives = await processor.list_processed_creatives()
        assert len(all_creatives) == 2
        
        # Verify different processing approaches
        assert runway_result.viewability_config.phase == ViewabilityPhase.PHASE_1
        assert video_result.viewability_config.phase == ViewabilityPhase.PHASE_2
        
        # Verify format-specific processing
        assert runway_result.creative_type == "CUSTOM_HTML"
        assert video_result.creative_type == "VAST_3_0"
        assert "VAST" in video_result.processed_code
        assert "amazon-dsp-display-wrapper" in runway_result.processed_code