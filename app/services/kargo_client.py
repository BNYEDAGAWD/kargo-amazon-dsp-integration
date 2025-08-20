"""Kargo snippet API client with mock and real implementations."""
import asyncio
import logging
import time
from typing import Any, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel

from app.utils.logging import get_logger
from app.utils.retry import kargo_api_retry_async, RetryableHTTPError
from app.utils.metrics import MetricsCollector


logger = get_logger("kargo.client")


class KargoSnippetResponse(BaseModel):
    """Response model for Kargo snippet retrieval."""
    snippet_id: str
    snippet_url: str
    snippet_code: str
    format: str  # runway, instream_video, enhanced_preroll
    status: str  # active, inactive, archived
    dimensions: Optional[str] = None
    duration: Optional[int] = None  # For video creatives
    last_modified: datetime
    cache_buster_enabled: bool = True
    metadata: Dict[str, Any] = {}


class MockKargoClient:
    """Mock Kargo API client for development and testing."""
    
    def __init__(self, base_url: str = "https://snippet.kargo.com", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Mock snippet database
        self._mock_snippets = self._generate_mock_snippets()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
    
    def _generate_mock_snippets(self) -> Dict[str, Dict[str, Any]]:
        """Generate realistic mock snippet data."""
        snippets = {}
        
        # Runway Display Creatives
        runway_snippet = """
        <div class="kargo-runway-creative" data-format="runway" data-dimensions="320x50">
            <script type="text/javascript">
                var kargoConfig = {
                    format: 'runway',
                    dimensions: '320x50',
                    clickUrl: '${CLICK_URL}',
                    impressionUrl: '${IMPRESSION_URL}',
                    expandable: true,
                    autoPlay: false
                };
                
                // Kargo creative initialization
                (function() {
                    var kargoScript = document.createElement('script');
                    kargoScript.src = 'https://cdn.kargo.com/creative/runway-v2.js';
                    document.head.appendChild(kargoScript);
                })();
            </script>
            
            <!-- IAS Tracking (will be removed in Phase 1) -->
            <img src="https://pixel.adsafeprotected.com/rfw/st/818052/81298/skeleton.gif?gdpr=${GDPR}&gdpr_consent=${GDPR_CONSENT}" 
                 style="display:none;" width="1" height="1">
            <script type="text/javascript" src="https://fw.adsafeprotected.com/rfw/st/818052/81298/skeleton.js"></script>
            
            <!-- DoubleVerify Tracking (will be wrapped for Amazon DSP) -->
            <script src="https://cdn.doubleverify.com/dvtp_src.js?ctx=818052&cmp=${CAMPAIGN_ID}&sid=${SITE_ID}&plc=${PLACEMENT_ID}"></script>
            <noscript>
                <img src="https://tps.doubleverify.com/visit.jpg?ctx=818052&cmp=${CAMPAIGN_ID}&sid=${SITE_ID}&plc=${PLACEMENT_ID}" style="display:none;">
            </noscript>
            
            <!-- Creative Content -->
            <div class="runway-container" style="width: 320px; height: 50px; position: relative; overflow: hidden; background: linear-gradient(45deg, #1e3c72, #2a5298);">
                <div class="runway-content" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-family: Arial, sans-serif;">
                    <div class="runway-text" style="text-align: center;">
                        <h3 style="margin: 0; font-size: 14px; font-weight: bold;">Premium Brand Message</h3>
                        <p style="margin: 0; font-size: 10px;">Click to expand and explore</p>
                    </div>
                </div>
                
                <!-- Expansion Panel (hidden initially) -->
                <div class="runway-expansion" style="display: none; position: absolute; top: 50px; left: 0; width: 320px; height: 200px; background: white; border: 1px solid #ccc; z-index: 1000;">
                    <div style="padding: 20px; text-align: center;">
                        <h2 style="color: #1e3c72; margin-bottom: 10px;">Expanded Experience</h2>
                        <p style="color: #666; margin-bottom: 15px;">Engage with our premium content and discover more about our brand.</p>
                        <button onclick="window.open(kargoConfig.clickUrl, '_blank')" style="background: #2a5298; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">Learn More</button>
                    </div>
                </div>
            </div>
            
            <!-- Kargo Analytics -->
            <script>
                // Track creative interactions
                function trackRunwayEvent(event) {
                    fetch('https://analytics.kargo.com/track', {
                        method: 'POST',
                        body: JSON.stringify({
                            creative_id: '81298',
                            event: event,
                            timestamp: Date.now()
                        })
                    });
                }
                
                // Add click and expansion tracking
                document.querySelector('.runway-container').addEventListener('click', function() {
                    trackRunwayEvent('expansion');
                    document.querySelector('.runway-expansion').style.display = 'block';
                });
            </script>
        </div>
        """
        
        snippets["81298"] = {
            "snippet_id": "81298",
            "snippet_url": "https://snippet.kargo.com/snippet/dm/81298",
            "snippet_code": runway_snippet,
            "format": "runway",
            "status": "active",
            "dimensions": "320x50",
            "last_modified": datetime(2024, 1, 15, 10, 30, 0),
            "metadata": {
                "advertiser": "Premium Brand",
                "campaign": "Q1 2024 Awareness",
                "creative_type": "HTML5 Expandable",
                "auto_expand": False,
                "max_expansion_size": "320x250"
            }
        }
        
        # Enhanced Pre-Roll Video Creative
        vast_snippet = """
        <?xml version="1.0" encoding="UTF-8"?>
        <VAST version="3.0">
            <Ad id="kargo_preroll_81172">
                <InLine>
                    <AdSystem version="2.0">Kargo</AdSystem>
                    <AdTitle><![CDATA[Premium Brand Pre-Roll with Branded Canvas]]></AdTitle>
                    <Description><![CDATA[15-second pre-roll video with interactive branded canvas overlay]]></Description>
                    
                    <!-- Impression Tracking -->
                    <Impression><![CDATA[https://analytics.kargo.com/impression/81172?cb=${CACHEBUSTER}]]></Impression>
                    
                    <!-- IAS Tracking (will be removed in Phase 1) -->
                    <Impression><![CDATA[https://pixel.adsafeprotected.com/rfw/st/818052/81172/skeleton.gif?cb=${CACHEBUSTER}]]></Impression>
                    
                    <!-- DoubleVerify Tracking (will be wrapped) -->
                    <Impression><![CDATA[https://tps.doubleverify.com/visit.jpg?ctx=818052&cmp=${CAMPAIGN_ID}&sid=${SITE_ID}&plc=${PLACEMENT_ID}&cb=${CACHEBUSTER}]]></Impression>
                    
                    <Creatives>
                        <Creative id="video_creative" sequence="1">
                            <Linear>
                                <Duration>00:00:15</Duration>
                                <TrackingEvents>
                                    <Tracking event="start"><![CDATA[https://analytics.kargo.com/video/start/81172]]></Tracking>
                                    <Tracking event="firstQuartile"><![CDATA[https://analytics.kargo.com/video/25/81172]]></Tracking>
                                    <Tracking event="midpoint"><![CDATA[https://analytics.kargo.com/video/50/81172]]></Tracking>
                                    <Tracking event="thirdQuartile"><![CDATA[https://analytics.kargo.com/video/75/81172]]></Tracking>
                                    <Tracking event="complete"><![CDATA[https://analytics.kargo.com/video/complete/81172]]></Tracking>
                                    
                                    <!-- DoubleVerify Video Tracking -->
                                    <Tracking event="start"><![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${CAMPAIGN_ID}&evt=start]]></Tracking>
                                    <Tracking event="complete"><![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${CAMPAIGN_ID}&evt=complete]]></Tracking>
                                </TrackingEvents>
                                
                                <MediaFiles>
                                    <MediaFile delivery="progressive" type="video/mp4" width="1920" height="1080" scalable="true" maintainAspectRatio="true">
                                        <![CDATA[https://cdn.kargo.com/video/premium-brand-15s.mp4]]>
                                    </MediaFile>
                                    <MediaFile delivery="progressive" type="video/webm" width="1920" height="1080" scalable="true" maintainAspectRatio="true">
                                        <![CDATA[https://cdn.kargo.com/video/premium-brand-15s.webm]]>
                                    </MediaFile>
                                </MediaFiles>
                                
                                <VideoClicks>
                                    <ClickThrough><![CDATA[${CLICK_URL}]]></ClickThrough>
                                    <ClickTracking><![CDATA[https://analytics.kargo.com/click/81172]]></ClickTracking>
                                </VideoClicks>
                            </Linear>
                        </Creative>
                        
                        <!-- Branded Canvas Companion Ad -->
                        <Creative id="branded_canvas" sequence="1">
                            <CompanionAds>
                                <Companion width="300" height="50" id="branded_canvas_300x50">
                                    <StaticResource creativeType="text/html">
                                        <![CDATA[
                                        <div style="width: 300px; height: 50px; background: linear-gradient(45deg, #1e3c72, #2a5298); display: flex; align-items: center; justify-content: center; color: white; font-family: Arial, sans-serif; cursor: pointer;" onclick="window.open('${CLICK_URL}', '_blank');">
                                            <div style="text-align: center;">
                                                <div style="font-size: 12px; font-weight: bold;">Premium Brand</div>
                                                <div style="font-size: 9px;">Discover More</div>
                                            </div>
                                        </div>
                                        ]]>
                                    </StaticResource>
                                    <CompanionClickThrough><![CDATA[${CLICK_URL}]]></CompanionClickThrough>
                                    <CompanionClickTracking><![CDATA[https://analytics.kargo.com/companion-click/81172]]></CompanionClickTracking>
                                </Companion>
                            </CompanionAds>
                        </Creative>
                    </Creatives>
                    
                    <Extensions>
                        <Extension type="Kargo">
                            <KargoData>
                                <Format>enhanced_preroll</Format>
                                <BrandedCanvas>true</BrandedCanvas>
                                <InteractiveElements>true</InteractiveElements>
                                <CreativeId>81172</CreativeId>
                            </KargoData>
                        </Extension>
                    </Extensions>
                </InLine>
            </Ad>
        </VAST>
        """
        
        snippets["81172"] = {
            "snippet_id": "81172",
            "snippet_url": "https://snippet.kargo.com/snippet/dm/81172",
            "snippet_code": vast_snippet,
            "format": "enhanced_preroll",
            "status": "active",
            "dimensions": "300x50",  # Branded canvas dimensions
            "duration": 15,
            "last_modified": datetime(2024, 1, 20, 14, 45, 0),
            "metadata": {
                "advertiser": "Premium Brand",
                "campaign": "Q1 2024 Video Campaign",
                "creative_type": "VAST 3.0 with Branded Canvas",
                "video_duration": 15,
                "companion_ads": True,
                "interactive_elements": True
            }
        }
        
        # Additional test snippets
        snippets["12345"] = {
            "snippet_id": "12345",
            "snippet_url": "https://snippet.kargo.com/snippet/dm/12345",
            "snippet_code": "<div class='test-creative'>Test Creative for Development</div>",
            "format": "runway",
            "status": "active",
            "dimensions": "320x50",
            "last_modified": datetime(2024, 1, 1, 12, 0, 0),
            "metadata": {"type": "test"}
        }
        
        return snippets
    
    @kargo_api_retry_async
    async def get_snippet(self, snippet_url: str) -> KargoSnippetResponse:
        """Retrieve snippet by URL."""
        logger.info(f"Fetching snippet: {snippet_url}")
        
        # Simulate API latency
        await asyncio.sleep(0.1)
        
        # Extract snippet ID from URL
        snippet_id = self._extract_snippet_id(snippet_url)
        
        if snippet_id not in self._mock_snippets:
            raise RetryableHTTPError(404, f"Snippet not found: {snippet_id}")
        
        snippet_data = self._mock_snippets[snippet_id].copy()
        snippet_data["snippet_url"] = snippet_url
        
        # Record metrics
        MetricsCollector.record_kargo_request(
            endpoint="get_snippet",
            status_code=200,
            duration=0.1
        )
        
        logger.info(f"Snippet retrieved successfully: {snippet_id}")
        
        return KargoSnippetResponse(**snippet_data)
    
    def _extract_snippet_id(self, snippet_url: str) -> str:
        """Extract snippet ID from Kargo URL."""
        # Parse URL like https://snippet.kargo.com/snippet/dm/81298
        parsed = urlparse(snippet_url)
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) >= 3 and path_parts[0] == 'snippet' and path_parts[1] == 'dm':
            return path_parts[2]
        
        # Fallback for other URL patterns
        return path_parts[-1] if path_parts else "unknown"
    
    @kargo_api_retry_async
    async def get_snippet_metadata(self, snippet_id: str) -> Dict[str, Any]:
        """Get metadata for a snippet."""
        logger.info(f"Fetching snippet metadata: {snippet_id}")
        
        await asyncio.sleep(0.05)  # Simulate API latency
        
        if snippet_id not in self._mock_snippets:
            raise RetryableHTTPError(404, f"Snippet not found: {snippet_id}")
        
        snippet_data = self._mock_snippets[snippet_id]
        
        metadata = {
            "snippet_id": snippet_id,
            "format": snippet_data["format"],
            "dimensions": snippet_data.get("dimensions"),
            "duration": snippet_data.get("duration"),
            "status": snippet_data["status"],
            "last_modified": snippet_data["last_modified"],
            "size_bytes": len(snippet_data["snippet_code"]),
            **snippet_data.get("metadata", {})
        }
        
        # Record metrics
        MetricsCollector.record_kargo_request(
            endpoint="get_snippet_metadata",
            status_code=200,
            duration=0.05
        )
        
        return metadata
    
    async def validate_snippet_url(self, snippet_url: str) -> bool:
        """Validate that a snippet URL is accessible."""
        try:
            snippet_id = self._extract_snippet_id(snippet_url)
            return snippet_id in self._mock_snippets
        except Exception:
            return False
    
    def get_mock_snippet_ids(self) -> list[str]:
        """Get list of available mock snippet IDs for testing."""
        return list(self._mock_snippets.keys())


class RealKargoClient:
    """Real Kargo API client for production use."""
    
    def __init__(self, base_url: str = "https://snippet.kargo.com", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {}
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
    
    @kargo_api_retry_async
    async def get_snippet(self, snippet_url: str) -> KargoSnippetResponse:
        """Retrieve snippet from real Kargo API."""
        logger.info(f"Fetching snippet from Kargo API: {snippet_url}")
        
        start_time = time.time()
        
        try:
            response = await self.session.get(snippet_url)
            response.raise_for_status()
            
            snippet_code = response.text
            
            # Parse response and create structured data
            # This would need to be implemented based on actual Kargo API responses
            snippet_id = self._extract_snippet_id(snippet_url)
            
            duration = time.time() - start_time
            
            # Record metrics
            MetricsCollector.record_kargo_request(
                endpoint="get_snippet",
                status_code=response.status_code,
                duration=duration
            )
            
            # TODO: Implement proper parsing of Kargo response
            return KargoSnippetResponse(
                snippet_id=snippet_id,
                snippet_url=snippet_url,
                snippet_code=snippet_code,
                format="unknown",  # Would be parsed from response
                status="active",
                last_modified=datetime.utcnow(),
            )
            
        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time
            MetricsCollector.record_kargo_request(
                endpoint="get_snippet",
                status_code=e.response.status_code,
                duration=duration
            )
            
            if e.response.status_code in [404, 403]:
                raise RetryableHTTPError(e.response.status_code, f"Snippet not accessible: {snippet_url}")
            
            raise RetryableHTTPError(e.response.status_code, f"Kargo API error: {e}")
    
    def _extract_snippet_id(self, snippet_url: str) -> str:
        """Extract snippet ID from Kargo URL."""
        parsed = urlparse(snippet_url)
        path_parts = parsed.path.strip('/').split('/')
        return path_parts[-1] if path_parts else "unknown"


# Factory function for client creation
async def create_kargo_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    use_mock: bool = True
) -> MockKargoClient:
    """
    Create Kargo client instance.
    
    Args:
        base_url: Kargo API base URL
        api_key: API key for authentication
        use_mock: Whether to use mock client (True for development)
    """
    if use_mock:
        return MockKargoClient(base_url=base_url, api_key=api_key)
    else:
        return RealKargoClient(base_url=base_url, api_key=api_key)


# Global client instance for dependency injection
_kargo_client: Optional[MockKargoClient] = None


async def get_kargo_client() -> MockKargoClient:
    """Dependency injection for Kargo client."""
    global _kargo_client
    if _kargo_client is None:
        _kargo_client = await create_kargo_client()
    return _kargo_client