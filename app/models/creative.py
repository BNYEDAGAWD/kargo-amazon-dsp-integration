"""Pydantic models for creative processing and configuration."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class CreativeFormat(str, Enum):
    """Supported creative formats."""
    RUNWAY = "runway"
    INSTREAM_VIDEO = "instream_video"
    ENHANCED_PREROLL = "enhanced_preroll"


class ViewabilityPhase(str, Enum):
    """Viewability implementation phases."""
    PHASE_1 = "phase_1"  # DV-only
    PHASE_2 = "phase_2"  # IAS S2S + DV


class ViewabilityVendor(str, Enum):
    """Supported viewability vendors."""
    DOUBLE_VERIFY = "double_verify"
    IAS = "ias"


class DeviceType(str, Enum):
    """Supported device types."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    CTV = "ctv"


class ViewabilityConfig(BaseModel):
    """Viewability measurement configuration."""
    phase: ViewabilityPhase
    vendors: List[ViewabilityVendor]
    method: str = Field(..., description="Measurement method (native, wrapped, s2s)")
    
    # Phase 1 specific
    dv_native: bool = Field(default=True, description="Use Amazon native DV integration")
    ias_removed: bool = Field(default=True, description="Remove IAS tags to prevent conflicts")
    
    # Phase 2 specific
    ias_s2s_enabled: bool = Field(default=False, description="Enable IAS server-to-server")
    dsp_seat_id: Optional[str] = Field(default=None, description="Kargo DSP seat ID for S2S")
    pub_id: Optional[str] = Field(default=None, description="Publisher ID for IAS S2S")
    
    @validator('vendors')
    def validate_vendors_for_phase(cls, v, values):
        """Validate vendor configuration based on phase."""
        phase = values.get('phase')
        if phase == ViewabilityPhase.PHASE_1:
            if ViewabilityVendor.IAS in v:
                raise ValueError("Phase 1 should not include IAS (removed to prevent conflicts)")
        elif phase == ViewabilityPhase.PHASE_2:
            if len(v) < 2:
                raise ValueError("Phase 2 should include both IAS and DV vendors")
        return v


class CreativeConfig(BaseModel):
    """Configuration for processing a creative."""
    name: str = Field(..., description="Creative name")
    format: CreativeFormat = Field(..., description="Creative format type")
    dimensions: str = Field(..., description="Creative dimensions (e.g., '320x50')")
    snippet_url: str = Field(..., description="Kargo snippet URL")
    device_type: DeviceType = Field(default=DeviceType.MOBILE)
    
    # Video specific
    duration: Optional[int] = Field(default=None, description="Video duration in seconds")
    vast_version: Optional[str] = Field(default="3.0", description="VAST version")
    branded_canvas: bool = Field(default=False, description="Include branded canvas overlay")
    
    # Processing options
    cache_buster: bool = Field(default=True, description="Include cache buster")
    viewability_config: ViewabilityConfig = Field(..., description="Viewability configuration")
    
    # Amazon DSP specific
    amazon_macros: bool = Field(default=True, description="Include Amazon DSP macros")
    click_tracking: bool = Field(default=True, description="Enable click tracking")
    
    @validator('dimensions')
    def validate_dimensions(cls, v):
        """Validate dimensions format."""
        try:
            width, height = v.split('x')
            int(width)
            int(height)
        except (ValueError, AttributeError):
            raise ValueError("Dimensions must be in format 'widthxheight' (e.g., '320x50')")
        return v


class ProcessingMetadata(BaseModel):
    """Metadata about the creative processing."""
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    original_snippet_size: int = Field(..., description="Original snippet size in bytes")
    processed_snippet_size: int = Field(..., description="Processed snippet size in bytes")
    tags_removed: List[str] = Field(default_factory=list, description="List of removed tags")
    tags_added: List[str] = Field(default_factory=list, description="List of added tags")
    warnings: List[str] = Field(default_factory=list, description="Processing warnings")
    phase_applied: ViewabilityPhase = Field(..., description="Applied viewability phase")


class ProcessedCreative(BaseModel):
    """A processed creative ready for Amazon DSP."""
    creative_id: str = Field(..., description="Unique creative identifier")
    name: str = Field(..., description="Creative name")
    format: CreativeFormat = Field(..., description="Creative format")
    original_snippet_url: str = Field(..., description="Original Kargo snippet URL")
    processed_code: str = Field(..., description="Processed creative code")
    
    # Amazon DSP integration
    amazon_dsp_ready: bool = Field(..., description="Ready for Amazon DSP upload")
    creative_type: str = Field(..., description="Amazon DSP creative type")
    
    # Configuration
    viewability_config: ViewabilityConfig = Field(..., description="Applied viewability config")
    processing_metadata: ProcessingMetadata = Field(..., description="Processing metadata")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreativeProcessRequest(BaseModel):
    """Request to process a creative."""
    creative_config: CreativeConfig = Field(..., description="Creative configuration")


class CreativeProcessResponse(BaseModel):
    """Response from creative processing."""
    creative_id: str = Field(..., description="Generated creative ID")
    name: str = Field(..., description="Creative name")
    format: CreativeFormat = Field(..., description="Creative format")
    processed_code: str = Field(..., description="Processed creative code")
    viewability_config: ViewabilityConfig = Field(..., description="Applied viewability config")
    amazon_dsp_ready: bool = Field(..., description="Ready for Amazon DSP")
    processing_metadata: ProcessingMetadata = Field(..., description="Processing metadata")


class CreativeUploadRequest(BaseModel):
    """Request to upload creative to Amazon DSP."""
    creative_id: str = Field(..., description="Processed creative ID")
    advertiser_id: str = Field(..., description="Amazon DSP advertiser ID")
    campaign_id: Optional[str] = Field(default=None, description="Campaign ID for association")


class CreativeUploadResponse(BaseModel):
    """Response from Amazon DSP creative upload."""
    amazon_creative_id: str = Field(..., description="Amazon DSP creative ID")
    creative_id: str = Field(..., description="Our creative ID")
    upload_status: str = Field(..., description="Upload status")
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    amazon_approval_status: Optional[str] = Field(default=None, description="Amazon approval status")


# Example configurations for testing
EXAMPLE_RUNWAY_CONFIG = CreativeConfig(
    name="PMP_Amazon_RMI_CORE_Runway_Anim_GE_v2_Mobile",
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

EXAMPLE_VIDEO_CONFIG = CreativeConfig(
    name="PMP_Amazon_RMI_Pre-Roll_Branded_Canvas_15s",
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
        pub_id="kargo_publisher_id"
    )
)