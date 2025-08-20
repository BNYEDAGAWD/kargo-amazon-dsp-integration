"""Tests for Kargo snippet API client."""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.kargo_client import MockKargoClient, create_kargo_client


@pytest.mark.asyncio
class TestMockKargoClient:
    """Test mock Kargo client functionality."""
    
    async def test_get_snippet_success(self):
        """Test successful snippet retrieval."""
        async with MockKargoClient() as client:
            response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81298")
            
            assert response.snippet_id == "81298"
            assert response.snippet_url == "https://snippet.kargo.com/snippet/dm/81298"
            assert response.format == "runway"
            assert response.status == "active"
            assert response.dimensions == "320x50"
            assert len(response.snippet_code) > 0
            assert "kargo-runway-creative" in response.snippet_code
            assert isinstance(response.last_modified, datetime)
    
    async def test_get_snippet_video(self):
        """Test retrieving video snippet."""
        async with MockKargoClient() as client:
            response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81172")
            
            assert response.snippet_id == "81172"
            assert response.format == "enhanced_preroll"
            assert response.duration == 15
            assert response.dimensions == "300x50"  # Branded canvas dimensions
            assert "<?xml version" in response.snippet_code
            assert "<VAST version=\"3.0\">" in response.snippet_code
            assert "Premium Brand" in response.snippet_code
    
    async def test_get_snippet_not_found(self):
        """Test snippet retrieval with non-existent ID."""
        async with MockKargoClient() as client:
            with pytest.raises(Exception) as exc_info:
                await client.get_snippet("https://snippet.kargo.com/snippet/dm/99999")
            
            assert "Snippet not found" in str(exc_info.value)
    
    async def test_extract_snippet_id_standard_url(self):
        """Test snippet ID extraction from standard URL format."""
        client = MockKargoClient()
        
        snippet_id = client._extract_snippet_id("https://snippet.kargo.com/snippet/dm/81298")
        assert snippet_id == "81298"
        
        snippet_id = client._extract_snippet_id("https://snippet.kargo.com/snippet/dm/12345?param=value")
        assert snippet_id == "12345"
    
    async def test_extract_snippet_id_alternative_format(self):
        """Test snippet ID extraction from alternative URL formats."""
        client = MockKargoClient()
        
        # Test fallback to last path component
        snippet_id = client._extract_snippet_id("https://example.com/path/to/67890")
        assert snippet_id == "67890"
        
        snippet_id = client._extract_snippet_id("https://snippet.kargo.com/different/format/54321")
        assert snippet_id == "54321"
    
    async def test_get_snippet_metadata(self):
        """Test snippet metadata retrieval."""
        async with MockKargoClient() as client:
            metadata = await client.get_snippet_metadata("81298")
            
            assert metadata["snippet_id"] == "81298"
            assert metadata["format"] == "runway"
            assert metadata["dimensions"] == "320x50"
            assert metadata["status"] == "active"
            assert "size_bytes" in metadata
            assert metadata["size_bytes"] > 0
            assert "advertiser" in metadata
            assert metadata["advertiser"] == "Premium Brand"
    
    async def test_get_snippet_metadata_video(self):
        """Test video snippet metadata."""
        async with MockKargoClient() as client:
            metadata = await client.get_snippet_metadata("81172")
            
            assert metadata["format"] == "enhanced_preroll"
            assert metadata["duration"] == 15
            assert metadata["video_duration"] == 15
            assert metadata["companion_ads"] is True
            assert metadata["interactive_elements"] is True
    
    async def test_get_snippet_metadata_not_found(self):
        """Test metadata retrieval for non-existent snippet."""
        async with MockKargoClient() as client:
            with pytest.raises(Exception) as exc_info:
                await client.get_snippet_metadata("99999")
            
            assert "Snippet not found" in str(exc_info.value)
    
    async def test_validate_snippet_url_valid(self):
        """Test URL validation for valid snippets."""
        async with MockKargoClient() as client:
            # Valid snippet URLs
            assert await client.validate_snippet_url("https://snippet.kargo.com/snippet/dm/81298") is True
            assert await client.validate_snippet_url("https://snippet.kargo.com/snippet/dm/81172") is True
            assert await client.validate_snippet_url("https://snippet.kargo.com/snippet/dm/12345") is True
    
    async def test_validate_snippet_url_invalid(self):
        """Test URL validation for invalid snippets."""
        async with MockKargoClient() as client:
            # Invalid snippet URLs
            assert await client.validate_snippet_url("https://snippet.kargo.com/snippet/dm/99999") is False
            assert await client.validate_snippet_url("https://invalid.com/snippet") is False
            assert await client.validate_snippet_url("invalid-url") is False
    
    async def test_get_mock_snippet_ids(self):
        """Test getting list of available mock snippet IDs."""
        async with MockKargoClient() as client:
            snippet_ids = client.get_mock_snippet_ids()
            
            assert isinstance(snippet_ids, list)
            assert len(snippet_ids) > 0
            assert "81298" in snippet_ids  # Runway creative
            assert "81172" in snippet_ids  # Video creative
            assert "12345" in snippet_ids  # Test creative
    
    async def test_snippet_content_has_tracking_tags(self):
        """Test that mock snippets contain expected tracking tags."""
        async with MockKargoClient() as client:
            # Runway snippet should have both IAS and DV tags
            runway_response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81298")
            runway_code = runway_response.snippet_code
            
            assert "adsafeprotected.com" in runway_code  # IAS tracking
            assert "doubleverify.com" in runway_code     # DV tracking
            assert "${CLICK_URL}" in runway_code         # Generic macros
            assert "${IMPRESSION_URL}" in runway_code
            
            # Video snippet should have VAST structure with tracking
            video_response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81172")
            video_code = video_response.snippet_code
            
            assert "<VAST version=\"3.0\">" in video_code
            assert "<TrackingEvents>" in video_code
            assert "adsafeprotected.com" in video_code
            assert "doubleverify.com" in video_code
            assert "CompanionAds" in video_code  # Branded canvas
    
    async def test_snippet_content_runway_features(self):
        """Test Runway snippet contains expected features."""
        async with MockKargoClient() as client:
            response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81298")
            code = response.snippet_code
            
            # Runway specific features
            assert 'data-format="runway"' in code
            assert 'data-dimensions="320x50"' in code
            assert "expandable" in code.lower()
            assert "runway-expansion" in code
            assert "trackRunwayEvent" in code
    
    async def test_snippet_content_video_features(self):
        """Test video snippet contains expected VAST features."""
        async with MockKargoClient() as client:
            response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81172")
            code = response.snippet_code
            
            # VAST specific features
            assert "<Duration>00:00:15</Duration>" in code
            assert "<MediaFiles>" in code
            assert "<VideoClicks>" in code
            assert "<Companion" in code  # Branded canvas
            assert "KargoData" in code   # Kargo extensions
    
    @patch('time.time')
    async def test_client_caching_behavior(self, mock_time):
        """Test that client properly handles caching (if implemented)."""
        mock_time.return_value = 1640995200  # Fixed timestamp
        
        async with MockKargoClient() as client:
            # Get same snippet twice
            response1 = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81298")
            response2 = await client.get_snippet("https://snippet.kargo.com/snippet/dm/81298")
            
            # Should return same content
            assert response1.snippet_code == response2.snippet_code
            assert response1.snippet_id == response2.snippet_id


@pytest.mark.asyncio 
class TestKargoClientFactory:
    """Test Kargo client factory function."""
    
    async def test_create_mock_client(self):
        """Test creating mock client through factory."""
        client = await create_kargo_client(use_mock=True)
        
        assert isinstance(client, MockKargoClient)
        assert client.base_url == "https://snippet.kargo.com"
        
        # Should be able to fetch snippets
        response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/12345")
        assert response.snippet_id == "12345"
    
    async def test_create_client_with_custom_config(self):
        """Test creating client with custom configuration."""
        custom_base_url = "https://custom.kargo.com"
        custom_api_key = "test_api_key_123"
        
        client = await create_kargo_client(
            base_url=custom_base_url,
            api_key=custom_api_key,
            use_mock=True
        )
        
        assert client.base_url == custom_base_url
        assert client.api_key == custom_api_key
    
    async def test_create_real_client_not_implemented(self):
        """Test that real client creation is not yet implemented."""
        with pytest.raises(NotImplementedError):
            await create_kargo_client(use_mock=False)


@pytest.mark.asyncio
class TestKargoClientIntegration:
    """Integration tests for Kargo client."""
    
    async def test_multiple_snippet_formats(self):
        """Test fetching different snippet formats."""
        async with MockKargoClient() as client:
            # Fetch all available snippet types
            snippet_ids = client.get_mock_snippet_ids()
            
            formats_found = set()
            for snippet_id in snippet_ids:
                metadata = await client.get_snippet_metadata(snippet_id)
                formats_found.add(metadata["format"])
            
            # Should have multiple formats available
            assert len(formats_found) > 1
            assert "runway" in formats_found
            assert "enhanced_preroll" in formats_found
    
    async def test_snippet_consistency(self):
        """Test consistency between snippet content and metadata."""
        async with MockKargoClient() as client:
            snippet_url = "https://snippet.kargo.com/snippet/dm/81298"
            
            # Get both snippet content and metadata
            snippet_response = await client.get_snippet(snippet_url)
            metadata = await client.get_snippet_metadata("81298")
            
            # Verify consistency
            assert snippet_response.snippet_id == metadata["snippet_id"]
            assert snippet_response.format == metadata["format"]
            assert snippet_response.dimensions == metadata["dimensions"]
            assert snippet_response.status == metadata["status"]
            assert len(snippet_response.snippet_code) == metadata["size_bytes"]
    
    async def test_error_handling_and_recovery(self):
        """Test error handling with retry logic."""
        async with MockKargoClient() as client:
            # Test with multiple invalid URLs to ensure consistent error handling
            invalid_urls = [
                "https://snippet.kargo.com/snippet/dm/invalid1",
                "https://snippet.kargo.com/snippet/dm/invalid2", 
                "https://snippet.kargo.com/snippet/dm/99999"
            ]
            
            for url in invalid_urls:
                with pytest.raises(Exception) as exc_info:
                    await client.get_snippet(url)
                assert "not found" in str(exc_info.value).lower()
            
            # But valid URLs should still work
            valid_response = await client.get_snippet("https://snippet.kargo.com/snippet/dm/12345")
            assert valid_response.snippet_id == "12345"