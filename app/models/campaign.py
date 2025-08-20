"""Pydantic models for campaign management and bulk operations."""
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from app.models.creative import CreativeConfig, ProcessedCreative, ViewabilityConfig


class CampaignStatus(str, Enum):
    """Campaign status options."""
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class CampaignPhase(str, Enum):
    """Campaign phase for viewability strategy."""
    PHASE_1 = "phase_1"  # DV-only implementation
    PHASE_2 = "phase_2"  # IAS S2S + DV implementation


class LineItemType(str, Enum):
    """Amazon DSP line item types."""
    STANDARD_DISPLAY = "standard_display"
    VIDEO = "video"
    AUDIO = "audio"
    NATIVE = "native"


class GoalKPI(str, Enum):
    """Campaign goal and KPI options."""
    VIEWABILITY = "viewability"
    CTR = "ctr"
    CONVERSIONS = "conversions"
    REACH = "reach"
    VIDEO_COMPLETION = "video_completion"


class SupplySource(str, Enum):
    """Amazon DSP supply source options."""
    AMAZON_PUBLISHERS = "amazon_publishers"
    THIRD_PARTY_EXCHANGE = "third_party_exchange"
    AMAZON_DSP_DEALS = "amazon_dsp_deals"


class CampaignConfig(BaseModel):
    """Configuration for creating a new campaign."""
    name: str = Field(..., description="Campaign name")
    advertiser_id: str = Field(..., description="Amazon DSP advertiser ID")
    
    # Campaign settings
    goal_kpi: GoalKPI = Field(default=GoalKPI.VIEWABILITY)
    total_budget: float = Field(..., gt=0, description="Total campaign budget")
    start_date: date = Field(..., description="Campaign start date")
    end_date: date = Field(..., description="Campaign end date")
    
    # Viewability strategy
    phase: CampaignPhase = Field(..., description="Viewability implementation phase")
    viewability_config: ViewabilityConfig = Field(..., description="Viewability configuration")
    
    # Creative configurations
    runway_creatives: List[CreativeConfig] = Field(default_factory=list)
    video_creatives: List[CreativeConfig] = Field(default_factory=list)
    
    # Supply and targeting
    supply_source: SupplySource = Field(default=SupplySource.AMAZON_PUBLISHERS)
    device_types: List[str] = Field(default_factory=lambda: ["mobile", "desktop"])
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        """Validate end date is after start date."""
        start_date = values.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('runway_creatives', 'video_creatives')
    def validate_creative_configs(cls, v):
        """Validate that creative configs are properly formatted."""
        for creative in v:
            if not creative.name or not creative.snippet_url:
                raise ValueError('All creatives must have name and snippet_url')
        return v


class TargetingConfig(BaseModel):
    """Targeting configuration for campaigns."""
    geo_targeting: List[str] = Field(default_factory=lambda: ["US"], description="Geographic targeting")
    device_types: List[str] = Field(default_factory=lambda: ["mobile", "desktop", "tablet"], description="Device targeting")
    audiences: List[str] = Field(default_factory=list, description="Audience targeting")
    keywords: List[str] = Field(default_factory=list, description="Keyword targeting")
    categories: List[str] = Field(default_factory=list, description="Category targeting")
    supply_sources: List[str] = Field(default_factory=lambda: ["amazon_publishers"], description="Supply source targeting")
    viewability_threshold: float = Field(default=70.0, description="Viewability threshold percentage")
    brand_safety_level: str = Field(default="high", description="Brand safety level")


class BiddingStrategy(BaseModel):
    """Bidding strategy configuration."""
    strategy_type: str = Field(default="cpm", description="Bidding strategy type")
    max_bid: float = Field(..., gt=0, description="Maximum bid amount")
    target_cpa: Optional[float] = Field(default=None, description="Target cost per acquisition")
    target_roas: Optional[float] = Field(default=None, description="Target return on ad spend")
    bid_adjustments: Dict[str, float] = Field(default_factory=dict, description="Bid adjustments by dimension")


class LineItemConfig(BaseModel):
    """Configuration for a line item."""
    name: str = Field(..., description="Line item name")
    line_type: LineItemType = Field(..., description="Line item type")
    creative_format: str = Field(..., description="Creative format")
    dimensions: str = Field(..., description="Creative dimensions")
    device_type: str = Field(..., description="Target device type")
    bid: float = Field(..., gt=0, description="Bid amount")
    budget: float = Field(..., gt=0, description="Line item budget")
    
    # Video specific
    duration: Optional[int] = Field(default=None, description="Video duration in seconds")
    branded_canvas: bool = Field(default=False, description="Includes branded canvas")
    
    # Associated creative
    creative_id: str = Field(..., description="Associated creative ID")


class CreativeAssociation(BaseModel):
    """Creative association for bulk sheet."""
    advertiser_id: str = Field(..., description="Advertiser ID")
    operation_type: str = Field(default="Add", description="Operation type")
    ad_creative_id: str = Field(..., description="Creative ID")
    creative_name: str = Field(..., description="Creative name")
    format: str = Field(..., description="Creative format")
    status: str = Field(default="Active", description="Creative status")
    weight: int = Field(default=1, description="Creative weight")


class Campaign(BaseModel):
    """Campaign model with all associated data."""
    campaign_id: str = Field(..., description="Unique campaign identifier")
    name: str = Field(..., description="Campaign name")
    advertiser_id: str = Field(..., description="Amazon DSP advertiser ID")
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT)
    phase: CampaignPhase = Field(..., description="Viewability phase")
    
    # Configuration
    config: CampaignConfig = Field(..., description="Original campaign configuration")
    viewability_config: ViewabilityConfig = Field(..., description="Viewability settings")
    
    # Processed creatives
    creatives: Optional[List[ProcessedCreative]] = Field(default_factory=list)
    
    # Amazon DSP data
    order_id: Optional[str] = Field(default=None, description="Amazon DSP order ID")
    bulk_sheet_path: Optional[str] = Field(default=None, description="Generated bulk sheet path")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CampaignCreateRequest(BaseModel):
    """Request to create a new campaign."""
    campaign_config: CampaignConfig = Field(..., description="Campaign configuration")


class CampaignResponse(BaseModel):
    """Response with campaign information."""
    campaign_id: str = Field(..., description="Campaign ID")
    name: str = Field(..., description="Campaign name")
    advertiser_id: str = Field(..., description="Advertiser ID")
    status: CampaignStatus = Field(..., description="Campaign status")
    phase: CampaignPhase = Field(..., description="Viewability phase")
    creative_count: int = Field(..., description="Number of processed creatives")
    viewability_config: ViewabilityConfig = Field(..., description="Viewability configuration")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class BulkSheetGenerateRequest(BaseModel):
    """Request to generate Amazon DSP bulk sheet."""
    include_orders: bool = Field(default=True, description="Include ORDERS sheet")
    include_display_lines: bool = Field(default=True, description="Include DISPLAY LINE ITEMS sheet")
    include_video_lines: bool = Field(default=True, description="Include VIDEO LINE ITEMS sheet")
    include_creative_associations: bool = Field(default=True, description="Include CREATIVE ASSOCIATIONS sheet")
    
    # Optional overrides
    custom_order_id: Optional[str] = Field(default=None, description="Custom order ID")
    custom_goal_kpi: Optional[str] = Field(default=None, description="Custom goal KPI")


class BulkSheetResponse(BaseModel):
    """Response from bulk sheet generation."""
    campaign_id: str = Field(..., description="Campaign ID")
    file_path: str = Field(..., description="Generated file path")
    generated_at: datetime = Field(..., description="Generation timestamp")
    download_url: str = Field(..., description="Download URL")


class BulkSheetData(BaseModel):
    """Complete bulk sheet data structure."""
    orders: List[Dict[str, Any]] = Field(default_factory=list)
    display_line_items: List[LineItemConfig] = Field(default_factory=list)
    video_line_items: List[LineItemConfig] = Field(default_factory=list)
    creative_associations: List[CreativeAssociation] = Field(default_factory=list)
    
    # Metadata
    campaign_id: str = Field(..., description="Associated campaign ID")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_budget: float = Field(..., description="Total campaign budget")
    total_creatives: int = Field(..., description="Total number of creatives")


# Example campaign configuration
EXAMPLE_CAMPAIGN_CONFIG = CampaignConfig(
    name="RMI_Q3_2025_HighImpact_Phase1",
    advertiser_id="123456",
    goal_kpi=GoalKPI.VIEWABILITY,
    total_budget=50000.0,
    start_date=date(2025, 1, 1),
    end_date=date(2025, 3, 31),
    phase=CampaignPhase.PHASE_1,
    viewability_config=ViewabilityConfig(
        phase="phase_1",
        vendors=["double_verify"],
        method="platform_native"
    ),
    runway_creatives=[
        CreativeConfig(
            name="PMP_Amazon_RMI_Runway_Mobile",
            format="runway",
            dimensions="320x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/81298",
            device_type="mobile",
            viewability_config=ViewabilityConfig(
                phase="phase_1",
                vendors=["double_verify"],
                method="platform_native"
            )
        )
    ],
    video_creatives=[
        CreativeConfig(
            name="PMP_Amazon_RMI_PreRoll_15s",
            format="enhanced_preroll",
            dimensions="300x50",
            snippet_url="https://snippet.kargo.com/snippet/dm/81172",
            device_type="mobile",
            duration=15,
            branded_canvas=True,
            viewability_config=ViewabilityConfig(
                phase="phase_1",
                vendors=["double_verify"],
                method="vast_wrapped"
            )
        )
    ]
)