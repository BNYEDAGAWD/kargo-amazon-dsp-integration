"""Core creative processing service for Kargo x Amazon DSP integration."""
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.creative import (
    CreativeConfig,
    ProcessedCreative,
    ProcessingMetadata,
    CreativeFormat,
    ViewabilityPhase,
    ViewabilityVendor,
)
from app.models.database import ProcessedCreativeDB
from app.services.kargo_client import get_kargo_client, KargoSnippetResponse
from app.services.amazon_client import get_amazon_dsp_client, AmazonCreativeUploadRequest
from app.utils.logging import get_logger
from app.utils.validation import CreativeValidator
from app.utils.metrics import MetricsCollector, time_creative_processing


logger = get_logger("creative.processor")


class SnippetTransformer:
    """Transforms Kargo snippets based on viewability phase and format."""
    
    # Regular expressions for tag detection and removal
    IAS_PATTERNS = [
        r'<img[^>]*adsafeprotected[^>]*>',
        r'<script[^>]*adsafeprotected[^>]*>.*?</script>',
        r'<script[^>]*fw\.adsafeprotected[^>]*>.*?</script>',
        r'pixel\.adsafeprotected\.com[^"\s>]*',
        r'fw\.adsafeprotected\.com[^"\s>]*',
    ]
    
    DV_PATTERNS = [
        r'<img[^>]*doubleverify[^>]*>',
        r'<script[^>]*doubleverify[^>]*>.*?</script>',
        r'<script[^>]*dvtp_src[^>]*>.*?</script>',
        r'tps\.doubleverify\.com[^"\s>]*',
        r'cdn\.doubleverify\.com[^"\s>]*',
    ]
    
    AMAZON_MACROS = {
        '${CLICK_URL}': '${AMAZON_CLICK_URL}',
        '${IMPRESSION_URL}': '${AMAZON_IMPRESSION_URL}',
        '${CAMPAIGN_ID}': '${AMAZON_CAMPAIGN_ID}',
        '${CREATIVE_ID}': '${AMAZON_CREATIVE_ID}',
        '${PLACEMENT_ID}': '${AMAZON_PLACEMENT_ID}',
        '${SITE_ID}': '${AMAZON_SITE_ID}',
        '${CACHEBUSTER}': '${AMAZON_CACHEBUSTER}',
        '${GDPR}': '${AMAZON_GDPR}',
        '${GDPR_CONSENT}': '${AMAZON_GDPR_CONSENT}',
    }
    
    @classmethod
    def remove_ias_tags(cls, snippet_code: str) -> Tuple[str, List[str]]:
        """Remove IAS tracking tags from snippet code."""
        removed_tags = []
        cleaned_code = snippet_code
        
        for pattern in cls.IAS_PATTERNS:
            matches = re.findall(pattern, cleaned_code, re.IGNORECASE | re.DOTALL)
            if matches:
                removed_tags.extend(matches)
                cleaned_code = re.sub(pattern, '', cleaned_code, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean up extra whitespace
        cleaned_code = re.sub(r'\n\s*\n', '\n', cleaned_code)
        
        return cleaned_code.strip(), removed_tags
    
    @classmethod
    def inject_amazon_macros(cls, snippet_code: str) -> str:
        """Replace generic macros with Amazon DSP specific macros."""
        processed_code = snippet_code
        
        for generic_macro, amazon_macro in cls.AMAZON_MACROS.items():
            processed_code = processed_code.replace(generic_macro, amazon_macro)
        
        return processed_code
    
    @classmethod
    def generate_cache_buster(cls) -> str:
        """Generate unique cache buster."""
        return str(int(time.time() * 1000))
    
    @classmethod
    def inject_cache_buster(cls, snippet_code: str, cache_buster: Optional[str] = None) -> str:
        """Inject cache buster into snippet code."""
        if cache_buster is None:
            cache_buster = cls.generate_cache_buster()
        
        # Replace cache buster placeholders
        processed_code = snippet_code.replace('${CACHEBUSTER}', cache_buster)
        processed_code = processed_code.replace('${AMAZON_CACHEBUSTER}', cache_buster)
        
        return processed_code
    
    @classmethod
    def wrap_display_html5_phase1(cls, snippet_code: str, config: CreativeConfig) -> str:
        """Wrap HTML5 display creative for Phase 1 (DV-only)."""
        wrapped_code = f"""
        <div class="amazon-dsp-display-wrapper" data-phase="phase_1">
            <script type="application/json" class="amazon-config">
            {{
                "format": "display_html5",
                "creative_name": "{config.name}",
                "dimensions": "{config.dimensions}",
                "device_type": "{config.device_type}",
                "viewability_vendor": "double_verify",
                "viewability_method": "platform_native",
                "phase": "phase_1"
            }}
            </script>
            
            <!-- Original Kargo Creative (IAS removed, DV preserved) -->
            {snippet_code}
            
            <script>
                // Amazon DSP integration
                window.amazonDSPConfig = {{
                    clickUrl: '${{AMAZON_CLICK_URL}}',
                    impressionUrl: '${{AMAZON_IMPRESSION_URL}}',
                    campaignId: '${{AMAZON_CAMPAIGN_ID}}',
                    creativeId: '${{AMAZON_CREATIVE_ID}}',
                    viewabilityMethod: 'platform_native'
                }};
                
                // DV viewability handled by Amazon DSP platform
                // No additional viewability pixels needed
                console.log('Amazon DSP Phase 1 creative loaded:', window.amazonDSPConfig);
            </script>
        </div>
        """
        
        return wrapped_code.strip()
    
    @classmethod
    def wrap_display_html5_phase2(cls, snippet_code: str, config: CreativeConfig) -> str:
        """Wrap HTML5 display creative for Phase 2 (IAS S2S + DV)."""
        wrapped_code = f"""
        <div class="amazon-dsp-display-wrapper" data-phase="phase_2">
            <script type="application/json" class="amazon-config">
            {{
                "format": "display_html5",
                "creative_name": "{config.name}",
                "dimensions": "{config.dimensions}",
                "device_type": "{config.device_type}",
                "viewability_vendors": ["ias", "double_verify"],
                "viewability_method": "s2s_plus_native",
                "phase": "phase_2",
                "ias_s2s_enabled": true,
                "dsp_seat_id": "{config.viewability_config.dsp_seat_id}",
                "pub_id": "{config.viewability_config.pub_id}"
            }}
            </script>
            
            <!-- IAS S2S Configuration (no client-side tags needed) -->
            <script type="application/json" class="ias-s2s-config">
            {{
                "seat_id": "{config.viewability_config.dsp_seat_id}",
                "publisher_id": "{config.viewability_config.pub_id}",
                "campaign_id": "${{AMAZON_CAMPAIGN_ID}}",
                "creative_id": "${{AMAZON_CREATIVE_ID}}",
                "measurement_method": "server_to_server"
            }}
            </script>
            
            <!-- Original Kargo Creative (IAS removed, DV preserved) -->
            {snippet_code}
            
            <script>
                // Amazon DSP integration with dual vendor support
                window.amazonDSPConfig = {{
                    clickUrl: '${{AMAZON_CLICK_URL}}',
                    impressionUrl: '${{AMAZON_IMPRESSION_URL}}',
                    campaignId: '${{AMAZON_CAMPAIGN_ID}}',
                    creativeId: '${{AMAZON_CREATIVE_ID}}',
                    viewabilityMethod: 's2s_plus_native',
                    vendors: {{
                        ias: 'server_side',
                        dv: 'platform_native'
                    }}
                }};
                
                console.log('Amazon DSP Phase 2 creative loaded:', window.amazonDSPConfig);
            </script>
        </div>
        """
        
        return wrapped_code.strip()
    
    @classmethod
    def wrap_vast_phase1(cls, snippet_code: str, config: CreativeConfig) -> str:
        """Wrap VAST creative for Phase 1 (DV-only)."""
        # Generate unique IDs for VAST elements
        ad_id = f"{config.name}_phase1"
        
        vast_wrapper = f"""<?xml version="1.0" encoding="UTF-8"?>
        <VAST version="3.0">
            <Ad id="{ad_id}">
                <Wrapper>
                    <AdSystem>Kargo Amazon DSP Phase 1</AdSystem>
                    <VASTAdTagURI>
                        <![CDATA[{config.snippet_url}?cb=${{AMAZON_CACHEBUSTER}}]]>
                    </VASTAdTagURI>
                    
                    <!-- Amazon DSP Impression Tracking -->
                    <Impression>
                        <![CDATA[${{AMAZON_IMPRESSION_URL}}]]>
                    </Impression>
                    
                    <!-- DV Viewability Tracking (wrapped within VAST) -->
                    <Impression>
                        <![CDATA[https://tps.doubleverify.com/visit.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&sid=${{AMAZON_SITE_ID}}&plc=${{AMAZON_PLACEMENT_ID}}&crt=${{AMAZON_CREATIVE_ID}}&tagtype=video&dvtagver=6.1.src&cb=${{AMAZON_CACHEBUSTER}}]]>
                    </Impression>
                    
                    <Creatives>
                        <Creative>
                            <Linear>
                                <Duration>00:00:{config.duration:02d}</Duration>
                                
                                <!-- DV Video Tracking Events -->
                                <TrackingEvents>
                                    <Tracking event="start">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=start&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="firstQuartile">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=25&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="midpoint">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=50&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="thirdQuartile">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=75&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="complete">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=complete&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                </TrackingEvents>
                                
                                <VideoClicks>
                                    <ClickThrough>
                                        <![CDATA[${{AMAZON_CLICK_URL}}]]>
                                    </ClickThrough>
                                </VideoClicks>
                            </Linear>
                            
                            <!-- Branded Canvas Companion (if enabled) -->"""
        
        if config.branded_canvas:
            canvas_width, canvas_height = config.dimensions.split('x')
            vast_wrapper += f"""
                            <CompanionAds>
                                <Companion width="{canvas_width}" height="{canvas_height}">
                                    <StaticResource creativeType="text/html">
                                        <![CDATA[
                                        <div class="branded-canvas-phase1" style="width: {canvas_width}px; height: {canvas_height}px; background: linear-gradient(45deg, #1e3c72, #2a5298); display: flex; align-items: center; justify-content: center; color: white; font-family: Arial, sans-serif; cursor: pointer;" onclick="window.open('${{AMAZON_CLICK_URL}}', '_blank');">
                                            <div style="text-align: center;">
                                                <div style="font-size: 12px; font-weight: bold;">Premium Brand</div>
                                                <div style="font-size: 9px;">Discover More</div>
                                            </div>
                                        </div>
                                        ]]>
                                    </StaticResource>
                                    <CompanionClickThrough>
                                        <![CDATA[${{AMAZON_CLICK_URL}}]]>
                                    </CompanionClickThrough>
                                </Companion>
                            </CompanionAds>"""
        
        vast_wrapper += """
                        </Creative>
                    </Creatives>
                    
                    <Extensions>
                        <Extension type="Amazon_DSP">
                            <AmazonData>
                                <Phase>phase_1</Phase>
                                <ViewabilityMethod>dv_wrapped</ViewabilityMethod>
                                <CreativeName>{}</CreativeName>
                            </AmazonData>
                        </Extension>
                    </Extensions>
                </Wrapper>
            </Ad>
        </VAST>""".format(config.name)
        
        return vast_wrapper.strip()
    
    @classmethod
    def wrap_vast_phase2(cls, snippet_code: str, config: CreativeConfig) -> str:
        """Wrap VAST creative for Phase 2 (IAS S2S + DV)."""
        ad_id = f"{config.name}_phase2"
        
        vast_wrapper = f"""<?xml version="1.0" encoding="UTF-8"?>
        <VAST version="3.0">
            <Ad id="{ad_id}">
                <Wrapper>
                    <AdSystem>Kargo Amazon DSP Phase 2</AdSystem>
                    <VASTAdTagURI>
                        <![CDATA[{config.snippet_url}?cb=${{AMAZON_CACHEBUSTER}}]]>
                    </VASTAdTagURI>
                    
                    <!-- Amazon DSP Impression Tracking -->
                    <Impression>
                        <![CDATA[${{AMAZON_IMPRESSION_URL}}]]>
                    </Impression>
                    
                    <!-- DV Viewability Tracking (wrapped within VAST) -->
                    <Impression>
                        <![CDATA[https://tps.doubleverify.com/visit.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&sid=${{AMAZON_SITE_ID}}&plc=${{AMAZON_PLACEMENT_ID}}&crt=${{AMAZON_CREATIVE_ID}}&tagtype=video&dvtagver=6.1.src&cb=${{AMAZON_CACHEBUSTER}}]]>
                    </Impression>
                    
                    <Creatives>
                        <Creative>
                            <Linear>
                                <Duration>00:00:{config.duration:02d}</Duration>
                                
                                <!-- DV Video Tracking Events -->
                                <TrackingEvents>
                                    <Tracking event="start">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=start&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="firstQuartile">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=25&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="midpoint">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=50&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="thirdQuartile">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=75&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                    <Tracking event="complete">
                                        <![CDATA[https://tps.doubleverify.com/event.jpg?ctx=818052&cmp=${{AMAZON_CAMPAIGN_ID}}&evt=complete&cb=${{AMAZON_CACHEBUSTER}}]]>
                                    </Tracking>
                                </TrackingEvents>
                                
                                <VideoClicks>
                                    <ClickThrough>
                                        <![CDATA[${{AMAZON_CLICK_URL}}]]>
                                    </ClickThrough>
                                </VideoClicks>
                            </Linear>
                            
                            <!-- Branded Canvas Companion (if enabled) -->"""
        
        if config.branded_canvas:
            canvas_width, canvas_height = config.dimensions.split('x')
            vast_wrapper += f"""
                            <CompanionAds>
                                <Companion width="{canvas_width}" height="{canvas_height}">
                                    <StaticResource creativeType="text/html">
                                        <![CDATA[
                                        <div class="branded-canvas-phase2" style="width: {canvas_width}px; height: {canvas_height}px; background: linear-gradient(45deg, #1e3c72, #2a5298); display: flex; align-items: center; justify-content: center; color: white; font-family: Arial, sans-serif; cursor: pointer;" onclick="window.open('${{AMAZON_CLICK_URL}}', '_blank');">
                                            <div style="text-align: center;">
                                                <div style="font-size: 12px; font-weight: bold;">Premium Brand</div>
                                                <div style="font-size: 9px;">Discover More</div>
                                            </div>
                                        </div>
                                        ]]>
                                    </StaticResource>
                                    <CompanionClickThrough>
                                        <![CDATA[${{AMAZON_CLICK_URL}}]]>
                                    </CompanionClickThrough>
                                </Companion>
                            </CompanionAds>"""
        
        vast_wrapper += f"""
                        </Creative>
                    </Creatives>
                    
                    <Extensions>
                        <!-- IAS S2S Configuration -->
                        <Extension type="IAS_S2S">
                            <IASData>
                                <SeatId>{config.viewability_config.dsp_seat_id}</SeatId>
                                <PublisherId>{config.viewability_config.pub_id}</PublisherId>
                                <MeasurementType>server_to_server</MeasurementType>
                                <CampaignId>${{AMAZON_CAMPAIGN_ID}}</CampaignId>
                                <CreativeId>${{AMAZON_CREATIVE_ID}}</CreativeId>
                            </IASData>
                        </Extension>
                        
                        <Extension type="Amazon_DSP">
                            <AmazonData>
                                <Phase>phase_2</Phase>
                                <ViewabilityMethod>ias_s2s_plus_dv_wrapped</ViewabilityMethod>
                                <CreativeName>{config.name}</CreativeName>
                                <DualVendorEnabled>true</DualVendorEnabled>
                            </AmazonData>
                        </Extension>
                    </Extensions>
                </Wrapper>
            </Ad>
        </VAST>"""
        
        return vast_wrapper.strip()


class CreativeProcessor:
    """Main creative processing service."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.transformer = SnippetTransformer()
        self.validator = CreativeValidator()
    
    async def process_creative(self, config: CreativeConfig) -> ProcessedCreative:
        """Process a creative configuration into Amazon DSP ready format."""
        logger.info(f"Processing creative: {config.name}")
        
        start_time = time.time()
        
        # Validate configuration
        await self._validate_config(config)
        
        # Fetch snippet from Kargo
        kargo_client = await get_kargo_client()
        snippet_response = await kargo_client.get_snippet(config.snippet_url)
        
        original_size = len(snippet_response.snippet_code)
        
        # Process based on phase and format
        processed_code, processing_metadata = await self._transform_snippet(
            snippet_response, config
        )
        
        # Generate unique creative ID
        creative_id = str(uuid.uuid4())
        
        # Create processed creative
        processed_creative = ProcessedCreative(
            creative_id=creative_id,
            name=config.name,
            format=config.format,
            original_snippet_url=config.snippet_url,
            processed_code=processed_code,
            amazon_dsp_ready=True,
            creative_type=self._get_amazon_creative_type(config.format),
            viewability_config=config.viewability_config,
            processing_metadata=processing_metadata,
        )
        
        # Store in database
        await self._store_processed_creative(processed_creative, config)
        
        processing_time = (time.time() - start_time) * 1000
        
        # Record metrics
        MetricsCollector.record_creative_processing(
            format=config.format.value,
            phase=config.viewability_config.phase.value,
            duration=processing_time / 1000,
            status="success"
        )
        
        logger.info(f"Creative processed successfully: {creative_id} ({processing_time:.1f}ms)")
        
        return processed_creative
    
    async def _validate_config(self, config: CreativeConfig) -> None:
        """Validate creative configuration."""
        # Validate snippet URL
        if not self.validator.validate_snippet_url(config.snippet_url):
            raise ValueError(f"Invalid snippet URL: {config.snippet_url}")
        
        # Validate dimensions for format
        if not self.validator.validate_creative_format_dimensions(config.format, config.dimensions):
            logger.warning(f"Unusual dimensions {config.dimensions} for format {config.format}")
        
        # Validate viewability configuration
        warnings = self.validator.validate_phase_configuration(
            config.viewability_config.phase,
            config.viewability_config.vendors,
            ""  # We'll validate against actual snippet code later
        )
        
        for warning in warnings:
            logger.warning(f"Configuration warning: {warning}")
    
    async def _transform_snippet(
        self, snippet_response: KargoSnippetResponse, config: CreativeConfig
    ) -> Tuple[str, ProcessingMetadata]:
        """Transform snippet based on phase and format."""
        start_time = time.time()
        original_code = snippet_response.snippet_code
        tags_removed = []
        tags_added = []
        warnings = []
        
        # Phase 1: Remove IAS tags
        if config.viewability_config.phase == ViewabilityPhase.PHASE_1:
            processed_code, removed_ias_tags = self.transformer.remove_ias_tags(original_code)
            tags_removed.extend(removed_ias_tags)
            
            if removed_ias_tags:
                logger.info(f"Removed {len(removed_ias_tags)} IAS tags for Phase 1")
        else:
            processed_code = original_code
        
        # Inject Amazon macros
        processed_code = self.transformer.inject_amazon_macros(processed_code)
        tags_added.append("amazon_macros")
        
        # Inject cache buster
        if config.cache_buster:
            processed_code = self.transformer.inject_cache_buster(processed_code)
            tags_added.append("cache_buster")
        
        # Format-specific processing
        if config.format == CreativeFormat.RUNWAY:
            if config.viewability_config.phase == ViewabilityPhase.PHASE_1:
                processed_code = self.transformer.wrap_display_html5_phase1(processed_code, config)
            else:
                processed_code = self.transformer.wrap_display_html5_phase2(processed_code, config)
            tags_added.append("amazon_dsp_wrapper")
            
        elif config.format in [CreativeFormat.INSTREAM_VIDEO, CreativeFormat.ENHANCED_PREROLL]:
            if config.viewability_config.phase == ViewabilityPhase.PHASE_1:
                processed_code = self.transformer.wrap_vast_phase1(processed_code, config)
            else:
                processed_code = self.transformer.wrap_vast_phase2(processed_code, config)
            tags_added.append("vast_wrapper")
            
            # Validate VAST structure
            vast_errors = self.validator.validate_vast_structure(processed_code)
            if vast_errors:
                warnings.extend(vast_errors)
        
        # Final validation
        phase_warnings = self.validator.validate_phase_configuration(
            config.viewability_config.phase,
            config.viewability_config.vendors,
            processed_code
        )
        warnings.extend(phase_warnings)
        
        processing_time = (time.time() - start_time) * 1000
        
        metadata = ProcessingMetadata(
            processing_time_ms=processing_time,
            original_snippet_size=len(original_code),
            processed_snippet_size=len(processed_code),
            tags_removed=tags_removed,
            tags_added=tags_added,
            warnings=warnings,
            phase_applied=config.viewability_config.phase,
        )
        
        return processed_code, metadata
    
    def _get_amazon_creative_type(self, format: CreativeFormat) -> str:
        """Map creative format to Amazon DSP creative type."""
        mapping = {
            CreativeFormat.RUNWAY: "CUSTOM_HTML",
            CreativeFormat.INSTREAM_VIDEO: "VAST_3_0",
            CreativeFormat.ENHANCED_PREROLL: "VAST_3_0",
        }
        return mapping.get(format, "CUSTOM_HTML")
    
    async def _store_processed_creative(self, creative: ProcessedCreative, config: CreativeConfig) -> None:
        """Store processed creative in database."""
        db_creative = ProcessedCreativeDB(
            creative_id=creative.creative_id,
            name=creative.name,
            format=creative.format.value,
            original_snippet_url=creative.original_snippet_url,
            processed_code=creative.processed_code,
            amazon_dsp_ready=creative.amazon_dsp_ready,
            creative_type=creative.creative_type,
            viewability_config=creative.viewability_config.dict(),
            processing_metadata=creative.processing_metadata.dict(),
            original_config=config.dict(),
        )
        
        self.db_session.add(db_creative)
        await self.db_session.flush()
    
    async def get_processed_creative(self, creative_id: str) -> Optional[ProcessedCreative]:
        """Retrieve processed creative by ID."""
        result = await self.db_session.execute(
            select(ProcessedCreativeDB).where(ProcessedCreativeDB.creative_id == creative_id)
        )
        db_creative = result.scalar_one_or_none()
        
        if not db_creative:
            return None
        
        return ProcessedCreative(
            creative_id=db_creative.creative_id,
            name=db_creative.name,
            format=CreativeFormat(db_creative.format),
            original_snippet_url=db_creative.original_snippet_url,
            processed_code=db_creative.processed_code,
            amazon_dsp_ready=db_creative.amazon_dsp_ready,
            creative_type=db_creative.creative_type,
            viewability_config=db_creative.viewability_config,
            processing_metadata=db_creative.processing_metadata,
            created_at=db_creative.created_at,
            updated_at=db_creative.updated_at,
        )
    
    async def list_processed_creatives(self, skip: int = 0, limit: int = 100) -> List[ProcessedCreative]:
        """List processed creatives with pagination."""
        result = await self.db_session.execute(
            select(ProcessedCreativeDB)
            .offset(skip)
            .limit(limit)
            .order_by(ProcessedCreativeDB.created_at.desc())
        )
        db_creatives = result.scalars().all()
        
        return [
            ProcessedCreative(
                creative_id=db_creative.creative_id,
                name=db_creative.name,
                format=CreativeFormat(db_creative.format),
                original_snippet_url=db_creative.original_snippet_url,
                processed_code=db_creative.processed_code,
                amazon_dsp_ready=db_creative.amazon_dsp_ready,
                creative_type=db_creative.creative_type,
                viewability_config=db_creative.viewability_config,
                processing_metadata=db_creative.processing_metadata,
                created_at=db_creative.created_at,
                updated_at=db_creative.updated_at,
            )
            for db_creative in db_creatives
        ]
    
    async def delete_processed_creative(self, creative_id: str) -> bool:
        """Delete processed creative."""
        result = await self.db_session.execute(
            select(ProcessedCreativeDB).where(ProcessedCreativeDB.creative_id == creative_id)
        )
        db_creative = result.scalar_one_or_none()
        
        if not db_creative:
            return False
        
        await self.db_session.delete(db_creative)
        return True
    
    async def upload_to_amazon_dsp(self, creative_id: str, advertiser_id: str) -> str:
        """Upload processed creative to Amazon DSP."""
        # Get processed creative
        creative = await self.get_processed_creative(creative_id)
        if not creative:
            raise ValueError(f"Processed creative not found: {creative_id}")
        
        # Prepare upload request
        width, height = creative.viewability_config.phase.split('x') if 'x' in str(creative.viewability_config.phase) else (320, 50)
        
        # This is a placeholder - we need dimensions from the config
        # For now, parse from common dimensions
        dimensions = "320x50"  # Default, should be extracted from processed creative
        if 'x' in dimensions:
            width, height = map(int, dimensions.split('x'))
        else:
            width, height = 320, 50
        
        upload_request = AmazonCreativeUploadRequest(
            name=creative.name,
            format=creative.creative_type,
            creative_code=creative.processed_code,
            width=width,
            height=height,
            advertiser_id=advertiser_id,
            viewability_config=creative.viewability_config.dict(),
        )
        
        # Upload to Amazon DSP
        amazon_client = await get_amazon_dsp_client()
        upload_response = await amazon_client.upload_creative(upload_request)
        
        # Update database with Amazon creative ID
        result = await self.db_session.execute(
            select(ProcessedCreativeDB).where(ProcessedCreativeDB.creative_id == creative_id)
        )
        db_creative = result.scalar_one_or_none()
        
        if db_creative:
            db_creative.amazon_creative_id = upload_response.creative_id
            db_creative.upload_status = upload_response.status
            await self.db_session.flush()
        
        logger.info(f"Creative uploaded to Amazon DSP: {creative_id} -> {upload_response.creative_id}")
        
        return upload_response.creative_id