"""Creative processing endpoints for Kargo x Amazon DSP integration."""
import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel
from sqlalchemy import select

from app.models.creative import (
    CreativeConfig,
    CreativeProcessRequest,
    CreativeProcessResponse,
    ProcessedCreative,
)
from app.models.database import get_db_session, ProcessedCreativeDB
from app.services.creative_processor import CreativeProcessor
from app.services.amazon_client import (
    get_amazon_dsp_client,
    AmazonCreativeUploadRequest,
    AmazonCreativeUploadResponse
)
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger("creative.api")


async def batch_upload_to_amazon(creative_ids: List[str], advertiser_id: str) -> Dict[str, Any]:
    """Background task to upload processed creatives to Amazon DSP."""
    logger.info(f"Starting batch upload to Amazon DSP for {len(creative_ids)} creatives")
    
    results = {
        "uploaded": [],
        "failed": [],
        "total": len(creative_ids)
    }
    
    try:
        amazon_client = await get_amazon_dsp_client()
        
        async for session in get_db_session():
            # Fetch creatives from database
            result = await session.execute(
                select(ProcessedCreativeDB).where(
                    ProcessedCreativeDB.creative_id.in_(creative_ids)
                )
            )
            creatives = result.scalars().all()
            
            upload_requests = []
            
            # Prepare upload requests
            for creative in creatives:
                if not creative.amazon_dsp_ready:
                    results["failed"].append({
                        "creative_id": creative.creative_id,
                        "error": "Creative not ready for Amazon DSP"
                    })
                    continue
                
                # Extract dimensions from metadata
                metadata = creative.processing_metadata or {}
                width = metadata.get("width", 300)
                height = metadata.get("height", 250)
                
                upload_request = AmazonCreativeUploadRequest(
                    name=creative.name,
                    format="CUSTOM_HTML" if "display" in creative.format.lower() else "VAST_3_0",
                    creative_code=creative.processed_code,
                    width=width,
                    height=height,
                    advertiser_id=advertiser_id,
                    viewability_config=creative.viewability_config
                )
                upload_requests.append((creative, upload_request))
            
            # Batch upload to Amazon DSP
            async with amazon_client:
                upload_results = await amazon_client.batch_upload_creatives(
                    [req for _, req in upload_requests]
                )
                
                # Update database with Amazon creative IDs
                for (creative, _), upload_response in zip(upload_requests, upload_results):
                    try:
                        creative.amazon_creative_id = upload_response.creative_id
                        creative.upload_status = upload_response.status
                        await session.commit()
                        
                        results["uploaded"].append({
                            "creative_id": creative.creative_id,
                            "amazon_creative_id": upload_response.creative_id,
                            "status": upload_response.status
                        })
                    except Exception as e:
                        logger.error(f"Failed to update creative {creative.creative_id}: {e}")
                        results["failed"].append({
                            "creative_id": creative.creative_id,
                            "error": str(e)
                        })
    
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
        for creative_id in creative_ids:
            if not any(r["creative_id"] == creative_id for r in results["uploaded"]):
                results["failed"].append({
                    "creative_id": creative_id,
                    "error": str(e)
                })
    
    logger.info(f"Batch upload completed: {len(results['uploaded'])} uploaded, {len(results['failed'])} failed")
    return results


@router.post("/process", response_model=CreativeProcessResponse)
async def process_creative(
    request: CreativeProcessRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CreativeProcessResponse:
    """
    Process Kargo creative for Amazon DSP integration.
    
    Supports both Phase 1 (DV-only) and Phase 2 (IAS S2S + DV) configurations.
    """
    try:
        async for session in get_db_session():
            processor = CreativeProcessor()
            processed_creative = await processor.process_creative(
                request.creative_config,
                session
            )
            
            return CreativeProcessResponse(
                creative_id=processed_creative.creative_id,
                name=processed_creative.name,
                format=processed_creative.format,
                processed_code=processed_creative.processed_code,
                viewability_config=processed_creative.viewability_config,
                amazon_dsp_ready=processed_creative.amazon_dsp_ready,
                processing_metadata=processed_creative.processing_metadata,
            )
    except Exception as e:
        logger.error(f"Creative processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Creative processing failed: {str(e)}"
        )


class BulkProcessRequest(BaseModel):
    """Request model for bulk creative processing."""
    creative_configs: List[CreativeConfig]
    advertiser_id: str
    upload_to_amazon: bool = False


class BulkProcessResponse(BaseModel):
    """Response model for bulk creative processing."""
    total_processed: int
    successful: int
    failed: int
    results: List[CreativeProcessResponse]
    failed_items: List[Dict[str, str]]


@router.post("/process/bulk", response_model=BulkProcessResponse)
async def process_creatives_bulk(
    request: BulkProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
) -> BulkProcessResponse:
    """Process multiple creatives in bulk with optional Amazon DSP upload."""
    try:
        async for session in get_db_session():
            processor = CreativeProcessor()
            results = []
            failed_items = []
            
            # Process creatives
            for creative_config in request.creative_configs:
                try:
                    processed_creative = await processor.process_creative(
                        creative_config,
                        session
                    )
                    results.append(CreativeProcessResponse(
                        creative_id=processed_creative.creative_id,
                        name=processed_creative.name,
                        format=processed_creative.format,
                        processed_code=processed_creative.processed_code,
                        viewability_config=processed_creative.viewability_config,
                        amazon_dsp_ready=processed_creative.amazon_dsp_ready,
                        processing_metadata=processed_creative.processing_metadata,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to process creative {creative_config.name}: {e}")
                    failed_items.append({
                        "creative_name": creative_config.name,
                        "error": str(e)
                    })
                    continue
            
            # Schedule Amazon DSP upload if requested
            if request.upload_to_amazon and results:
                background_tasks.add_task(
                    batch_upload_to_amazon,
                    [r.creative_id for r in results],
                    request.advertiser_id
                )
            
            return BulkProcessResponse(
                total_processed=len(request.creative_configs),
                successful=len(results),
                failed=len(failed_items),
                results=results,
                failed_items=failed_items
            )
            
    except Exception as e:
        logger.error(f"Bulk creative processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Bulk creative processing failed: {str(e)}"
        )


@router.post("/upload/amazon-dsp")
async def upload_creatives_to_amazon(
    creative_ids: List[str],
    advertiser_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Upload processed creatives to Amazon DSP."""
    try:
        # Validate that creatives exist and are ready
        async for session in get_db_session():
            result = await session.execute(
                select(ProcessedCreativeDB).where(
                    ProcessedCreativeDB.creative_id.in_(creative_ids)
                )
            )
            creatives = result.scalars().all()
            
            if len(creatives) != len(creative_ids):
                found_ids = {c.creative_id for c in creatives}
                missing_ids = set(creative_ids) - found_ids
                raise HTTPException(
                    status_code=404,
                    detail=f"Creatives not found: {list(missing_ids)}"
                )
            
            # Check readiness
            not_ready = [c.creative_id for c in creatives if not c.amazon_dsp_ready]
            if not_ready:
                raise HTTPException(
                    status_code=400,
                    detail=f"Creatives not ready for Amazon DSP: {not_ready}"
                )
            
            # Schedule background upload
            background_tasks.add_task(
                batch_upload_to_amazon,
                creative_ids,
                advertiser_id
            )
            
            return {
                "message": f"Batch upload of {len(creative_ids)} creatives scheduled",
                "creative_ids": creative_ids,
                "advertiser_id": advertiser_id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule Amazon DSP upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule Amazon DSP upload: {str(e)}"
        )


@router.get("/{creative_id}", response_model=ProcessedCreative)
async def get_creative(
    creative_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ProcessedCreative:
    """Retrieve a processed creative by ID."""
    try:
        processor = CreativeProcessor(db)
        creative = await processor.get_processed_creative(creative_id)
        
        if not creative:
            raise HTTPException(
                status_code=404,
                detail=f"Creative with ID {creative_id} not found"
            )
        
        return creative
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve creative {creative_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve creative: {str(e)}"
        )


@router.get("/", response_model=List[ProcessedCreative])
async def list_creatives(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
) -> List[ProcessedCreative]:
    """List all processed creatives with pagination."""
    try:
        processor = CreativeProcessor(db)
        creatives = await processor.list_processed_creatives(skip=skip, limit=limit)
        return creatives
    except Exception as e:
        logger.error(f"Failed to list creatives: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list creatives: {str(e)}"
        )


@router.delete("/{creative_id}")
async def delete_creative(
    creative_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Delete a processed creative."""
    try:
        processor = CreativeProcessor(db)
        deleted = await processor.delete_processed_creative(creative_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Creative with ID {creative_id} not found"
            )
        
        return {"message": f"Creative {creative_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete creative {creative_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete creative: {str(e)}"
        )