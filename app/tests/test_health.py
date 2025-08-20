"""Tests for health check endpoints."""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, test_client: TestClient):
        """Test basic health check endpoint."""
        response = test_client.get("/health/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "kargo-amazon-dsp-integration"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
    
    def test_liveness_check(self, test_client: TestClient):
        """Test liveness check endpoint."""
        response = test_client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    def test_readiness_check(self, test_client: TestClient):
        """Test readiness check endpoint."""
        response = test_client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert "checks" in data
        assert data["checks"]["database"] == "healthy"
        assert data["checks"]["api"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_async(self, async_client: AsyncClient):
        """Test health check with async client."""
        response = await async_client.get("/health/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "kargo-amazon-dsp-integration"
    
    @pytest.mark.asyncio
    async def test_readiness_check_async(self, async_client: AsyncClient):
        """Test readiness check with async client."""
        response = await async_client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert "checks" in data


class TestRootEndpoint:
    """Test root API endpoint."""
    
    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint returns API information."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Kargo x Amazon DSP Integration"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"
        assert "description" in data