"""Tests for creative processing API endpoints."""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.models.creative import CreativeFormat, ViewabilityPhase


class TestCreativeAPI:
    """Test creative processing API endpoints."""
    
    def test_process_creative_runway_phase1(self, test_client: TestClient):
        """Test processing Runway creative via API - Phase 1."""
        request_data = {
            "creative_config": {
                "name": "API_Test_Runway_Phase1",
                "format": "runway",
                "dimensions": "320x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/81298",
                "device_type": "mobile",
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "platform_native"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "API_Test_Runway_Phase1"
        assert data["format"] == "runway"
        assert data["amazon_dsp_ready"] is True
        assert data["viewability_config"]["phase"] == "phase_1"
        assert "creative_id" in data
        assert len(data["processed_code"]) > 0
        
        # Check Phase 1 specific elements
        assert 'data-phase="phase_1"' in data["processed_code"]
        assert "amazon-dsp-display-wrapper" in data["processed_code"]
    
    def test_process_creative_video_phase2(self, test_client: TestClient):
        """Test processing video creative via API - Phase 2."""
        request_data = {
            "creative_config": {
                "name": "API_Test_Video_Phase2",
                "format": "enhanced_preroll",
                "dimensions": "300x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/81172",
                "device_type": "mobile",
                "duration": 15,
                "branded_canvas": True,
                "viewability_config": {
                    "phase": "phase_2",
                    "vendors": ["ias", "double_verify"],
                    "method": "s2s_plus_wrapped",
                    "ias_s2s_enabled": True,
                    "dsp_seat_id": "KARGO_DSP_SEAT_001",
                    "pub_id": "kargo_test_pub"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "API_Test_Video_Phase2"
        assert data["format"] == "enhanced_preroll"
        assert data["viewability_config"]["phase"] == "phase_2"
        assert data["viewability_config"]["ias_s2s_enabled"] is True
        
        # Check Phase 2 VAST elements
        assert "<?xml version" in data["processed_code"]
        assert "<VAST version=\"3.0\">" in data["processed_code"]
        assert "IAS_S2S" in data["processed_code"]
        assert "KARGO_DSP_SEAT_001" in data["processed_code"]
    
    def test_process_creative_invalid_config(self, test_client: TestClient):
        """Test processing creative with invalid configuration."""
        request_data = {
            "creative_config": {
                "name": "",  # Empty name should fail validation
                "format": "runway",
                "dimensions": "invalid",  # Invalid dimensions
                "snippet_url": "https://snippet.kargo.com/snippet/dm/81298",
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "platform_native"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_process_creative_invalid_snippet_url(self, test_client: TestClient):
        """Test processing creative with invalid snippet URL."""
        request_data = {
            "creative_config": {
                "name": "Invalid URL Test",
                "format": "runway",
                "dimensions": "320x50",
                "snippet_url": "https://invalid.com/snippet",  # Invalid URL
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "platform_native"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        assert response.status_code == 500  # Server error due to invalid URL
    
    def test_get_processed_creative(self, test_client: TestClient):
        """Test retrieving processed creative by ID."""
        # First, process a creative
        request_data = {
            "creative_config": {
                "name": "Get Test Creative",
                "format": "runway",
                "dimensions": "320x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "platform_native"
                }
            }
        }
        
        process_response = test_client.post("/api/v1/creative/process", json=request_data)
        assert process_response.status_code == 200
        
        creative_id = process_response.json()["creative_id"]
        
        # Now retrieve it
        get_response = test_client.get(f"/api/v1/creative/{creative_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data["creative_id"] == creative_id
        assert data["name"] == "Get Test Creative"
        assert data["amazon_dsp_ready"] is True
    
    def test_get_nonexistent_creative(self, test_client: TestClient):
        """Test retrieving non-existent creative."""
        response = test_client.get("/api/v1/creative/nonexistent-id")
        assert response.status_code == 404
    
    def test_list_processed_creatives(self, test_client: TestClient):
        """Test listing processed creatives."""
        # Process multiple creatives first
        for i in range(3):
            request_data = {
                "creative_config": {
                    "name": f"List Test Creative {i}",
                    "format": "runway",
                    "dimensions": "320x50",
                    "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                    "viewability_config": {
                        "phase": "phase_1",
                        "vendors": ["double_verify"],
                        "method": "platform_native"
                    }
                }
            }
            
            response = test_client.post("/api/v1/creative/process", json=request_data)
            assert response.status_code == 200
        
        # List creatives
        list_response = test_client.get("/api/v1/creative/")
        
        assert list_response.status_code == 200
        data = list_response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 3
        
        # Check they're properly formatted
        for creative in data:
            assert "creative_id" in creative
            assert "name" in creative
            assert "format" in creative
            assert "amazon_dsp_ready" in creative
    
    def test_list_creatives_with_pagination(self, test_client: TestClient):
        """Test listing creatives with pagination parameters."""
        response = test_client.get("/api/v1/creative/?skip=0&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 2  # Should respect limit
    
    def test_delete_processed_creative(self, test_client: TestClient):
        """Test deleting processed creative."""
        # First, process a creative
        request_data = {
            "creative_config": {
                "name": "Delete Test Creative",
                "format": "runway",
                "dimensions": "320x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "platform_native"
                }
            }
        }
        
        process_response = test_client.post("/api/v1/creative/process", json=request_data)
        assert process_response.status_code == 200
        
        creative_id = process_response.json()["creative_id"]
        
        # Delete it
        delete_response = test_client.delete(f"/api/v1/creative/{creative_id}")
        
        assert delete_response.status_code == 200
        assert "deleted successfully" in delete_response.json()["message"]
        
        # Verify it's gone
        get_response = test_client.get(f"/api/v1/creative/{creative_id}")
        assert get_response.status_code == 404
    
    def test_delete_nonexistent_creative(self, test_client: TestClient):
        """Test deleting non-existent creative."""
        response = test_client.delete("/api/v1/creative/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCreativeAPIAsync:
    """Async tests for creative processing API."""
    
    async def test_process_creative_bulk(self, async_client: AsyncClient):
        """Test bulk creative processing."""
        request_data = [
            {
                "creative_config": {
                    "name": "Bulk Test Creative 1",
                    "format": "runway",
                    "dimensions": "320x50",
                    "snippet_url": "https://snippet.kargo.com/snippet/dm/81298",
                    "viewability_config": {
                        "phase": "phase_1",
                        "vendors": ["double_verify"],
                        "method": "platform_native"
                    }
                }
            },
            {
                "creative_config": {
                    "name": "Bulk Test Creative 2",
                    "format": "enhanced_preroll",
                    "dimensions": "300x50",
                    "snippet_url": "https://snippet.kargo.com/snippet/dm/81172",
                    "duration": 15,
                    "viewability_config": {
                        "phase": "phase_1",
                        "vendors": ["double_verify"],
                        "method": "vast_wrapped"
                    }
                }
            }
        ]
        
        response = await async_client.post("/api/v1/creative/process/bulk", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Check both creatives were processed
        assert data[0]["name"] == "Bulk Test Creative 1"
        assert data[0]["format"] == "runway"
        assert data[1]["name"] == "Bulk Test Creative 2"
        assert data[1]["format"] == "enhanced_preroll"
    
    async def test_process_creative_bulk_partial_failure(self, async_client: AsyncClient):
        """Test bulk processing with some failures."""
        request_data = [
            {
                "creative_config": {
                    "name": "Valid Creative",
                    "format": "runway",
                    "dimensions": "320x50",
                    "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                    "viewability_config": {
                        "phase": "phase_1",
                        "vendors": ["double_verify"],
                        "method": "platform_native"
                    }
                }
            },
            {
                "creative_config": {
                    "name": "Invalid Creative",
                    "format": "runway",
                    "dimensions": "320x50",
                    "snippet_url": "https://invalid.com/snippet",  # Invalid URL
                    "viewability_config": {
                        "phase": "phase_1",
                        "vendors": ["double_verify"],
                        "method": "platform_native"
                    }
                }
            }
        ]
        
        response = await async_client.post("/api/v1/creative/process/bulk", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only return the successful one
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Valid Creative"


class TestCreativeAPIValidation:
    """Test API input validation."""
    
    def test_phase1_ias_validation_error(self, test_client: TestClient):
        """Test that Phase 1 with IAS vendors returns validation error."""
        request_data = {
            "creative_config": {
                "name": "Invalid Phase 1 Config",
                "format": "runway",
                "dimensions": "320x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["ias", "double_verify"],  # IAS not allowed in Phase 1
                    "method": "platform_native"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        assert response.status_code == 422
    
    def test_phase2_missing_s2s_config(self, test_client: TestClient):
        """Test that Phase 2 without S2S config returns validation error."""
        request_data = {
            "creative_config": {
                "name": "Incomplete Phase 2 Config",
                "format": "runway", 
                "dimensions": "320x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                "viewability_config": {
                    "phase": "phase_2",
                    "vendors": ["ias", "double_verify"],
                    "method": "s2s_plus_native"
                    # Missing dsp_seat_id and pub_id
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        # This should still work but may generate warnings in processing metadata
        assert response.status_code in [200, 422]
    
    def test_invalid_creative_format(self, test_client: TestClient):
        """Test invalid creative format returns validation error."""
        request_data = {
            "creative_config": {
                "name": "Invalid Format Test",
                "format": "invalid_format",  # Not a valid CreativeFormat
                "dimensions": "320x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "platform_native"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        assert response.status_code == 422
    
    def test_missing_video_duration(self, test_client: TestClient):
        """Test video creative without duration."""
        request_data = {
            "creative_config": {
                "name": "Video Without Duration",
                "format": "enhanced_preroll",
                "dimensions": "300x50",
                "snippet_url": "https://snippet.kargo.com/snippet/dm/81172",
                # Missing duration field for video
                "viewability_config": {
                    "phase": "phase_1",
                    "vendors": ["double_verify"],
                    "method": "vast_wrapped"
                }
            }
        }
        
        response = test_client.post("/api/v1/creative/process", json=request_data)
        # Should still work with default duration from snippet
        assert response.status_code == 200