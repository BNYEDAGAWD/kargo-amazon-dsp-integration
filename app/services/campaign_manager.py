"""Campaign management service for orchestrating campaign lifecycle."""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.database import (
    CampaignDB,
    ProcessedCreativeDB,
    CampaignCreativeAssociationDB,
    AuditLogDB
)
from app.models.campaign import (
    CampaignConfig,
    LineItemConfig,
    TargetingConfig,
    BiddingStrategy
)
from app.models.creative import ViewabilityPhase
from app.services.amazon_client import (
    MockAmazonDSPClient,
    AmazonCampaignRequest,
    AmazonCampaignResponse,
    ViewabilityReportRequest
)
from app.services.creative_processor import CreativeProcessor
from app.utils.logging import get_logger
from app.utils.metrics import MetricsCollector

logger = get_logger("campaign_manager")


class CampaignCreationRequest(BaseModel):
    """Request model for campaign creation."""
    name: str
    advertiser_id: str
    campaign_type: str = "display_and_video"
    viewability_phase: ViewabilityPhase
    budget: float
    start_date: datetime
    end_date: datetime
    creatives: List[str]  # List of creative IDs
    targeting: Optional[TargetingConfig] = None
    bidding: Optional[BiddingStrategy] = None
    frequency_cap: Optional[Dict[str, Any]] = None
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class CampaignUpdateRequest(BaseModel):
    """Request model for campaign updates."""
    status: Optional[str] = None
    budget: Optional[float] = None
    end_date: Optional[datetime] = None
    targeting: Optional[TargetingConfig] = None
    bidding: Optional[BiddingStrategy] = None


class CampaignResponse(BaseModel):
    """Response model for campaign operations."""
    campaign_id: str
    name: str
    status: str
    viewability_phase: str
    budget: float
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    viewability_rate: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    amazon_order_id: Optional[str] = None
    bulk_sheet_url: Optional[str] = None
    creative_count: int
    processed_creatives_count: int


class LineItemCreationRequest(BaseModel):
    """Request model for line item creation."""
    campaign_id: str
    name: str
    creative_ids: List[str]
    budget: float
    bid: float
    targeting: Optional[TargetingConfig] = None
    schedule: Optional[Dict[str, Any]] = None


class CampaignManager:
    """Manages campaign lifecycle and orchestration."""
    
    def __init__(
        self,
        db_session: AsyncSession,
        amazon_client: MockAmazonDSPClient,
        creative_processor: CreativeProcessor
    ):
        self.db = db_session
        self.amazon_client = amazon_client
        self.creative_processor = creative_processor
        self.logger = logger
    
    async def create_campaign(
        self,
        request: CampaignCreationRequest
    ) -> CampaignResponse:
        """Create a new campaign with associated creatives."""
        self.logger.info(f"Creating campaign: {request.name}")
        
        # Generate campaign ID
        campaign_id = f"camp_{uuid4().hex[:12]}"
        
        # Validate creatives exist and are processed
        creative_records = await self._validate_creatives(request.creatives)
        
        # Create campaign in database
        campaign_db = CampaignDB(
            campaign_id=campaign_id,
            name=request.name,
            advertiser_id=request.advertiser_id,
            status="draft",
            phase=request.viewability_phase.value,
            config={
                "campaign_type": request.campaign_type,
                "targeting": request.targeting.dict() if request.targeting else {},
                "bidding": request.bidding.dict() if request.bidding else {},
                "frequency_cap": request.frequency_cap or {}
            },
            viewability_config={
                "phase": request.viewability_phase.value,
                "vendors": self._get_vendors_for_phase(request.viewability_phase),
                "reporting_enabled": True
            },
            total_budget=request.budget,
            start_date=request.start_date,
            end_date=request.end_date,
            creative_count=len(request.creatives),
            processed_creatives_count=len(creative_records)
        )
        
        self.db.add(campaign_db)
        
        # Create creative associations
        for creative in creative_records:
            association = CampaignCreativeAssociationDB(
                campaign_id=campaign_id,
                creative_id=creative.creative_id,
                line_item_name=f"{request.name}_line_item_{creative.format}",
                line_item_type=self._get_line_item_type(creative.format),
                bid=request.bidding.max_bid if request.bidding else 1.0,
                budget=request.budget / len(creative_records),  # Distribute budget
                status="active"
            )
            self.db.add(association)
        
        # Create campaign in Amazon DSP
        amazon_request = AmazonCampaignRequest(
            advertiser_id=request.advertiser_id,
            name=request.name,
            budget=request.budget,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            goal="AWARENESS" if request.campaign_type == "display_and_video" else "CONVERSIONS",
            status="PAUSED"  # Always start paused
        )
        
        amazon_response = await self.amazon_client.create_campaign(amazon_request)
        
        # Update campaign with Amazon order ID
        campaign_db.order_id = amazon_response.campaign_id
        
        # Setup viewability reporting
        if request.viewability_phase != ViewabilityPhase.PHASE_1:
            await self._setup_viewability_reporting(
                amazon_response.campaign_id,
                request.viewability_phase
            )
        
        # Create audit log
        audit_log = AuditLogDB(
            entity_type="campaign",
            entity_id=campaign_id,
            action="created",
            audit_metadata={
                "phase": request.viewability_phase.value,
                "creative_count": len(request.creatives),
                "budget": request.budget
            }
        )
        self.db.add(audit_log)
        
        await self.db.commit()
        await self.db.refresh(campaign_db)
        
        # Record metrics
        MetricsCollector.record_campaign_created(
            phase=request.viewability_phase.value,
            creative_count=len(request.creatives)
        )
        
        self.logger.info(f"Campaign created successfully: {campaign_id}")
        
        return CampaignResponse(
            campaign_id=campaign_id,
            name=campaign_db.name,
            status=campaign_db.status,
            viewability_phase=campaign_db.phase,
            budget=campaign_db.total_budget,
            spend=0.0,
            impressions=0,
            clicks=0,
            created_at=campaign_db.created_at,
            updated_at=campaign_db.updated_at,
            amazon_order_id=campaign_db.order_id,
            creative_count=campaign_db.creative_count,
            processed_creatives_count=campaign_db.processed_creatives_count
        )
    
    async def update_campaign(
        self,
        campaign_id: str,
        request: CampaignUpdateRequest
    ) -> CampaignResponse:
        """Update an existing campaign."""
        self.logger.info(f"Updating campaign: {campaign_id}")
        
        # Fetch campaign from database
        result = await self.db.execute(
            select(CampaignDB).where(CampaignDB.campaign_id == campaign_id)
        )
        campaign_db = result.scalar_one_or_none()
        
        if not campaign_db:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        # Update fields
        if request.status:
            campaign_db.status = request.status
        if request.budget:
            campaign_db.total_budget = request.budget
        if request.end_date:
            campaign_db.end_date = request.end_date
        if request.targeting:
            campaign_db.config["targeting"] = request.targeting.dict()
        if request.bidding:
            campaign_db.config["bidding"] = request.bidding.dict()
        
        campaign_db.updated_at = datetime.utcnow()
        
        # Create audit log
        audit_log = AuditLogDB(
            entity_type="campaign",
            entity_id=campaign_id,
            action="updated",
            changes={
                k: v for k, v in request.dict(exclude_unset=True).items()
            }
        )
        self.db.add(audit_log)
        
        await self.db.commit()
        await self.db.refresh(campaign_db)
        
        self.logger.info(f"Campaign updated successfully: {campaign_id}")
        
        return CampaignResponse(
            campaign_id=campaign_db.campaign_id,
            name=campaign_db.name,
            status=campaign_db.status,
            viewability_phase=campaign_db.phase,
            budget=campaign_db.total_budget,
            spend=0.0,
            impressions=0,
            clicks=0,
            created_at=campaign_db.created_at,
            updated_at=campaign_db.updated_at,
            amazon_order_id=campaign_db.order_id,
            creative_count=campaign_db.creative_count,
            processed_creatives_count=campaign_db.processed_creatives_count
        )
    
    async def get_campaign(self, campaign_id: str) -> CampaignResponse:
        """Get campaign details."""
        result = await self.db.execute(
            select(CampaignDB).where(CampaignDB.campaign_id == campaign_id)
        )
        campaign_db = result.scalar_one_or_none()
        
        if not campaign_db:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        # Get viewability data if available
        viewability_rate = None
        if campaign_db.order_id:
            try:
                viewability_data = await self.amazon_client.get_viewability_data(
                    campaign_db.order_id
                )
                viewability_rate = viewability_data.get("summary", {}).get("viewability_rate")
            except Exception as e:
                self.logger.warning(f"Failed to fetch viewability data: {e}")
        
        return CampaignResponse(
            campaign_id=campaign_db.campaign_id,
            name=campaign_db.name,
            status=campaign_db.status,
            viewability_phase=campaign_db.phase,
            budget=campaign_db.total_budget,
            spend=0.0,
            impressions=0,
            clicks=0,
            viewability_rate=viewability_rate,
            created_at=campaign_db.created_at,
            updated_at=campaign_db.updated_at,
            amazon_order_id=campaign_db.order_id,
            bulk_sheet_url=campaign_db.bulk_sheet_path,
            creative_count=campaign_db.creative_count,
            processed_creatives_count=campaign_db.processed_creatives_count
        )
    
    async def list_campaigns(
        self,
        advertiser_id: Optional[str] = None,
        status: Optional[str] = None,
        phase: Optional[ViewabilityPhase] = None
    ) -> List[CampaignResponse]:
        """List campaigns with optional filters."""
        query = select(CampaignDB)
        
        if advertiser_id:
            query = query.where(CampaignDB.advertiser_id == advertiser_id)
        if status:
            query = query.where(CampaignDB.status == status)
        if phase:
            query = query.where(CampaignDB.phase == phase.value)
        
        result = await self.db.execute(query)
        campaigns = result.scalars().all()
        
        return [
            CampaignResponse(
                campaign_id=campaign.campaign_id,
                name=campaign.name,
                status=campaign.status,
                viewability_phase=campaign.phase,
                budget=campaign.total_budget,
                spend=0.0,
                impressions=0,
                clicks=0,
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
                amazon_order_id=campaign.order_id,
                bulk_sheet_url=campaign.bulk_sheet_path,
                creative_count=campaign.creative_count,
                processed_creatives_count=campaign.processed_creatives_count
            )
            for campaign in campaigns
        ]
    
    async def activate_campaign(self, campaign_id: str) -> CampaignResponse:
        """Activate a campaign (set status to active)."""
        self.logger.info(f"Activating campaign: {campaign_id}")
        
        result = await self.db.execute(
            select(CampaignDB).where(CampaignDB.campaign_id == campaign_id)
        )
        campaign_db = result.scalar_one_or_none()
        
        if not campaign_db:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        if campaign_db.status == "active":
            self.logger.info(f"Campaign already active: {campaign_id}")
            return await self.get_campaign(campaign_id)
        
        # Validate campaign is ready for activation
        if not campaign_db.order_id:
            raise ValueError("Campaign not synced with Amazon DSP")
        
        if campaign_db.processed_creatives_count == 0:
            raise ValueError("No processed creatives available")
        
        # Update status
        campaign_db.status = "active"
        campaign_db.updated_at = datetime.utcnow()
        
        # Create audit log
        audit_log = AuditLogDB(
            entity_type="campaign",
            entity_id=campaign_id,
            action="activated",
            audit_metadata={
                "previous_status": "draft",
                "new_status": "active"
            }
        )
        self.db.add(audit_log)
        
        await self.db.commit()
        
        # Record metrics
        MetricsCollector.record_campaign_activated(campaign_id)
        
        self.logger.info(f"Campaign activated successfully: {campaign_id}")
        
        return await self.get_campaign(campaign_id)
    
    async def pause_campaign(self, campaign_id: str) -> CampaignResponse:
        """Pause a campaign."""
        self.logger.info(f"Pausing campaign: {campaign_id}")
        
        result = await self.db.execute(
            select(CampaignDB).where(CampaignDB.campaign_id == campaign_id)
        )
        campaign_db = result.scalar_one_or_none()
        
        if not campaign_db:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        previous_status = campaign_db.status
        campaign_db.status = "paused"
        campaign_db.updated_at = datetime.utcnow()
        
        # Create audit log
        audit_log = AuditLogDB(
            entity_type="campaign",
            entity_id=campaign_id,
            action="paused",
            audit_metadata={
                "previous_status": previous_status,
                "new_status": "paused"
            }
        )
        self.db.add(audit_log)
        
        await self.db.commit()
        
        self.logger.info(f"Campaign paused successfully: {campaign_id}")
        
        return await self.get_campaign(campaign_id)
    
    async def delete_campaign(self, campaign_id: str) -> Dict[str, str]:
        """Delete a campaign (soft delete by setting status)."""
        self.logger.info(f"Deleting campaign: {campaign_id}")
        
        result = await self.db.execute(
            select(CampaignDB).where(CampaignDB.campaign_id == campaign_id)
        )
        campaign_db = result.scalar_one_or_none()
        
        if not campaign_db:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        if campaign_db.status == "active":
            raise ValueError("Cannot delete active campaign. Please pause first.")
        
        campaign_db.status = "deleted"
        campaign_db.updated_at = datetime.utcnow()
        
        # Create audit log
        audit_log = AuditLogDB(
            entity_type="campaign",
            entity_id=campaign_id,
            action="deleted",
            audit_metadata={
                "deleted_at": datetime.utcnow().isoformat()
            }
        )
        self.db.add(audit_log)
        
        await self.db.commit()
        
        self.logger.info(f"Campaign deleted successfully: {campaign_id}")
        
        return {"message": f"Campaign {campaign_id} deleted successfully"}
    
    async def add_creatives_to_campaign(
        self,
        campaign_id: str,
        creative_ids: List[str]
    ) -> CampaignResponse:
        """Add additional creatives to an existing campaign."""
        self.logger.info(f"Adding {len(creative_ids)} creatives to campaign: {campaign_id}")
        
        # Fetch campaign
        result = await self.db.execute(
            select(CampaignDB).where(CampaignDB.campaign_id == campaign_id)
        )
        campaign_db = result.scalar_one_or_none()
        
        if not campaign_db:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        # Validate creatives
        creative_records = await self._validate_creatives(creative_ids)
        
        # Check for existing associations
        existing_result = await self.db.execute(
            select(CampaignCreativeAssociationDB.creative_id).where(
                CampaignCreativeAssociationDB.campaign_id == campaign_id
            )
        )
        existing_creative_ids = set(existing_result.scalars().all())
        
        # Add new associations
        new_creatives = []
        for creative in creative_records:
            if creative.creative_id not in existing_creative_ids:
                association = CampaignCreativeAssociationDB(
                    campaign_id=campaign_id,
                    creative_id=creative.creative_id,
                    line_item_name=f"{campaign_db.name}_line_item_{creative.format}",
                    line_item_type=self._get_line_item_type(creative.format),
                    bid=1.0,  # Default bid
                    budget=campaign_db.total_budget / (campaign_db.creative_count + len(new_creatives) + 1),
                    status="active"
                )
                self.db.add(association)
                new_creatives.append(creative.creative_id)
        
        # Update campaign counts
        campaign_db.creative_count += len(new_creatives)
        campaign_db.processed_creatives_count += len(new_creatives)
        campaign_db.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        self.logger.info(f"Added {len(new_creatives)} new creatives to campaign: {campaign_id}")
        
        return await self.get_campaign(campaign_id)
    
    async def _validate_creatives(self, creative_ids: List[str]) -> List[ProcessedCreativeDB]:
        """Validate that creatives exist and are processed."""
        result = await self.db.execute(
            select(ProcessedCreativeDB).where(
                ProcessedCreativeDB.creative_id.in_(creative_ids)
            )
        )
        creatives = result.scalars().all()
        
        if len(creatives) != len(creative_ids):
            found_ids = {c.creative_id for c in creatives}
            missing_ids = set(creative_ids) - found_ids
            raise ValueError(f"Creatives not found: {missing_ids}")
        
        # Check all creatives are processed
        unprocessed = [c.creative_id for c in creatives if c.status != "processed"]
        if unprocessed:
            raise ValueError(f"Creatives not processed: {unprocessed}")
        
        return creatives
    
    def _get_vendors_for_phase(self, phase: ViewabilityPhase) -> List[str]:
        """Get viewability vendors for a given phase."""
        if phase == ViewabilityPhase.PHASE_1:
            return ["double_verify"]
        elif phase == ViewabilityPhase.PHASE_2:
            return ["double_verify", "ias"]
        else:
            return []
    
    def _get_line_item_type(self, creative_format: str) -> str:
        """Determine line item type based on creative format."""
        if "video" in creative_format.lower():
            return "video"
        elif "display" in creative_format.lower() or "runway" in creative_format.lower():
            return "display"
        else:
            return "standard"
    
    async def _setup_viewability_reporting(
        self,
        amazon_campaign_id: str,
        phase: ViewabilityPhase
    ) -> None:
        """Setup viewability reporting for the campaign."""
        metrics = [
            "impressions",
            "viewable_impressions",
            "measurable_impressions",
            "viewability_rate",
            "time_in_view"
        ]
        
        if phase == ViewabilityPhase.PHASE_2:
            metrics.extend([
                "ias_viewability_rate",
                "ias_invalid_traffic",
                "brand_safety_incidents"
            ])
        
        report_request = ViewabilityReportRequest(
            campaign_id=amazon_campaign_id,
            metrics=metrics,
            reporting_frequency="hourly",
            dashboard_enabled=True,
            api_access=True
        )
        
        await self.amazon_client.setup_viewability_reporting(report_request)