"""Campaign management endpoints for Amazon DSP integration."""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db_session
from app.models.creative import ViewabilityPhase
from app.services.campaign_manager import (
    CampaignManager,
    CampaignCreationRequest,
    CampaignUpdateRequest,
    CampaignResponse
)
from app.services.bulk_generator import (
    BulkSheetGenerator,
    BulkSheetRequest,
    BulkSheetResponse
)
from app.services.amazon_client import get_amazon_dsp_client
from app.services.creative_processor import CreativeProcessor

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    request: CampaignCreationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Create a new campaign configuration."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaign = await manager.create_campaign(request)
            return campaign
            
    except Exception as e:
        logger.error(f"Campaign creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Campaign creation failed: {str(e)}"
        )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Retrieve a campaign by ID."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaign = await manager.get_campaign(campaign_id)
            return campaign
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to retrieve campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve campaign: {str(e)}"
        )


@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(
    advertiser_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phase: Optional[ViewabilityPhase] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> List[CampaignResponse]:
    """List campaigns with optional filters."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaigns = await manager.list_campaigns(
                advertiser_id=advertiser_id,
                status=status,
                phase=phase
            )
            return campaigns
            
    except Exception as e:
        logger.error(f"Failed to list campaigns: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list campaigns: {str(e)}"
        )


@router.post("/{campaign_id}/bulk-sheet", response_model=BulkSheetResponse)
async def generate_bulk_sheet(
    campaign_id: str,
    request: BulkSheetRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BulkSheetResponse:
    """Generate Amazon DSP bulk sheet for campaign."""
    try:
        async for session in get_db_session():
            generator = BulkSheetGenerator(session)
            response = await generator.generate_bulk_sheet(request)
            return response
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk sheet generation failed for campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Bulk sheet generation failed: {str(e)}"
        )


@router.get("/{campaign_id}/bulk-sheet/download")
async def download_bulk_sheet(
    campaign_id: str,
    file_path: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Download the generated bulk sheet for a campaign."""
    try:
        async for session in get_db_session():
            generator = BulkSheetGenerator(session)
            
            if file_path:
                # Download specific file
                file_bytes = await generator.download_bulk_sheet(file_path)
                
                return Response(
                    content=file_bytes,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=bulk_sheet_{campaign_id}.xlsx"}
                )
            else:
                # List available bulk sheets for campaign
                sheets = await generator.list_bulk_sheets(campaign_id)
                return {"bulk_sheets": sheets}
                
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk sheet download failed for campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Bulk sheet download failed: {str(e)}"
        )


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Update campaign configuration."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaign = await manager.update_campaign(campaign_id, request)
            return campaign
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update campaign: {str(e)}"
        )


@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Activate a campaign."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaign = await manager.activate_campaign(campaign_id)
            return campaign
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to activate campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate campaign: {str(e)}"
        )


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Pause a campaign."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaign = await manager.pause_campaign(campaign_id)
            return campaign
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pause campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause campaign: {str(e)}"
        )


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete a campaign."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            result = await manager.delete_campaign(campaign_id)
            return result
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete campaign: {str(e)}"
        )


@router.post("/{campaign_id}/creatives", response_model=CampaignResponse)
async def add_creatives_to_campaign(
    campaign_id: str,
    creative_ids: List[str],
    db: AsyncSession = Depends(get_db_session),
) -> CampaignResponse:
    """Add creatives to an existing campaign."""
    try:
        amazon_client = await get_amazon_dsp_client()
        creative_processor = CreativeProcessor()
        
        async for session in get_db_session():
            manager = CampaignManager(session, amazon_client, creative_processor)
            campaign = await manager.add_creatives_to_campaign(campaign_id, creative_ids)
            return campaign
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add creatives to campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add creatives to campaign: {str(e)}"
        )