"""Test configuration and fixtures for Kargo x Amazon DSP Integration."""
import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.models.database import Base, get_db_session
from app.models.creative import (
    CreativeConfig, 
    ViewabilityConfig, 
    CreativeFormat, 
    ViewabilityPhase, 
    ViewabilityVendor,
    DeviceType
)
from app.models.campaign import CampaignConfig, CampaignPhase, GoalKPI


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
def test_client(test_session):
    """Create test client with dependency override."""
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db_session] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db_session] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


# Test data fixtures
@pytest.fixture
def sample_runway_config() -> CreativeConfig:
    """Sample Runway creative configuration."""
    return CreativeConfig(
        name="Test_Runway_Creative",
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


@pytest.fixture
def sample_video_config() -> CreativeConfig:
    """Sample video creative configuration."""
    return CreativeConfig(
        name="Test_Video_Creative",
        format=CreativeFormat.ENHANCED_PREROLL,
        dimensions="300x50",
        snippet_url="https://snippet.kargo.com/snippet/dm/67890",
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


@pytest.fixture
def sample_campaign_config(sample_runway_config, sample_video_config) -> CampaignConfig:
    """Sample campaign configuration."""
    from datetime import date, timedelta
    
    return CampaignConfig(
        name="Test_Campaign",
        advertiser_id="123456",
        goal_kpi=GoalKPI.VIEWABILITY,
        total_budget=10000.0,
        start_date=date.today() + timedelta(days=1),
        end_date=date.today() + timedelta(days=31),
        phase=CampaignPhase.PHASE_1,
        viewability_config=ViewabilityConfig(
            phase=ViewabilityPhase.PHASE_1,
            vendors=[ViewabilityVendor.DOUBLE_VERIFY],
            method="platform_native"
        ),
        runway_creatives=[sample_runway_config],
        video_creatives=[sample_video_config]
    )


@pytest.fixture
def sample_kargo_snippet() -> str:
    """Sample Kargo creative snippet."""
    return """
    <div class="kargo-creative">
        <script type="text/javascript">
            // Kargo creative code
            var kargoConfig = {
                format: 'runway',
                dimensions: '320x50',
                clickUrl: '${CLICK_URL}'
            };
        </script>
        
        <!-- IAS tracking (to be removed in Phase 1) -->
        <img src="https://pixel.adsafeprotected.com/rfw/st/123456/12345?url=${CLICK_URL}" style="display:none;">
        
        <!-- DV tracking (to be wrapped for Amazon DSP) -->
        <script src="https://tps.doubleverify.com/visit.jpg?ctx=818052"></script>
        
        <div class="creative-content">
            <h3>Sample Runway Creative</h3>
            <p>This is a test creative</p>
        </div>
    </div>
    """


@pytest.fixture
def sample_vast_snippet() -> str:
    """Sample VAST video snippet."""
    return """
    <?xml version="1.0" encoding="UTF-8"?>
    <VAST version="3.0">
        <Ad id="test_video_ad">
            <InLine>
                <AdSystem>Kargo</AdSystem>
                <AdTitle>Test Video Creative</AdTitle>
                <Impression><![CDATA[https://snippet.kargo.com/impression/12345]]></Impression>
                
                <!-- IAS tracking -->
                <Impression><![CDATA[https://pixel.adsafeprotected.com/impression/67890]]></Impression>
                
                <Creatives>
                    <Creative>
                        <Linear>
                            <Duration>00:00:15</Duration>
                            <MediaFiles>
                                <MediaFile delivery="progressive" type="video/mp4" width="1920" height="1080">
                                    <![CDATA[https://cdn.kargo.com/video/test.mp4]]>
                                </MediaFile>
                            </MediaFiles>
                            <VideoClicks>
                                <ClickThrough><![CDATA[${CLICK_URL}]]></ClickThrough>
                            </VideoClicks>
                            <TrackingEvents>
                                <Tracking event="start"><![CDATA[https://tracking.kargo.com/start]]></Tracking>
                                <Tracking event="complete"><![CDATA[https://tracking.kargo.com/complete]]></Tracking>
                            </TrackingEvents>
                        </Linear>
                        <CompanionAds>
                            <Companion width="300" height="50">
                                <StaticResource creativeType="image/png">
                                    <![CDATA[https://cdn.kargo.com/companion/test.png]]>
                                </StaticResource>
                            </Companion>
                        </CompanionAds>
                    </Creative>
                </Creatives>
            </InLine>
        </Ad>
    </VAST>
    """


# Mock data and utilities
@pytest.fixture
def mock_amazon_response():
    """Mock Amazon DSP API response."""
    return {
        "creativeId": "amazon_12345",
        "status": "APPROVED",
        "name": "Test Creative",
        "format": "CUSTOM_HTML",
        "dimensions": {"width": 320, "height": 50}
    }


@pytest.fixture
def mock_kargo_response(sample_kargo_snippet):
    """Mock Kargo snippet API response."""
    return {
        "snippet": sample_kargo_snippet,
        "status": "active",
        "last_modified": "2024-01-01T00:00:00Z"
    }


# Test utilities
class MockHTTPResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, json_data=None, status_code=200, text=None):
        self.json_data = json_data
        self.status_code = status_code
        self.text = text or ""
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def mock_requests_success():
    """Mock successful HTTP requests."""
    def _mock_get(*args, **kwargs):
        return MockHTTPResponse({"success": True}, 200)
    
    def _mock_post(*args, **kwargs):
        return MockHTTPResponse({"id": "12345", "status": "created"}, 201)
    
    return {"get": _mock_get, "post": _mock_post}


# Async test helpers
async def create_test_creative(session: AsyncSession, config: CreativeConfig):
    """Helper to create a test creative in the database."""
    from app.services.creative_processor import CreativeProcessor
    
    processor = CreativeProcessor(session)
    return await processor.process_creative(config)


async def create_test_campaign(session: AsyncSession, config: CampaignConfig):
    """Helper to create a test campaign in the database."""
    from app.services.campaign_manager import CampaignManager
    
    manager = CampaignManager(session)
    return await manager.create_campaign(config)