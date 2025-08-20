"""SQLAlchemy database models and session management."""
import os
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import Column, String, Text, DateTime, Float, Boolean, Integer, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import uuid

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/kargo_dsp"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
    pool_size=20,
    max_overflow=10,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base model
Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields."""
    __abstract__ = True
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ProcessedCreativeDB(BaseModel):
    """Database model for processed creatives."""
    __tablename__ = "processed_creatives"
    
    creative_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    format = Column(String, nullable=False)
    original_snippet_url = Column(Text, nullable=False)
    processed_code = Column(Text, nullable=False)
    
    # Amazon DSP integration
    amazon_dsp_ready = Column(Boolean, default=False)
    creative_type = Column(String, nullable=False)
    amazon_creative_id = Column(String, nullable=True)
    
    # Configuration (stored as JSON)
    viewability_config = Column(JSON, nullable=False)
    processing_metadata = Column(JSON, nullable=False)
    original_config = Column(JSON, nullable=False)
    
    # Status tracking
    status = Column(String, default="processed")
    upload_status = Column(String, nullable=True)
    
    def __repr__(self) -> str:
        return f"<ProcessedCreative(creative_id='{self.creative_id}', name='{self.name}')>"


class CampaignDB(BaseModel):
    """Database model for campaigns."""
    __tablename__ = "campaigns"
    
    campaign_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    advertiser_id = Column(String, nullable=False)
    status = Column(String, default="draft")
    phase = Column(String, nullable=False)  # phase_1 or phase_2
    
    # Campaign configuration (stored as JSON)
    config = Column(JSON, nullable=False)
    viewability_config = Column(JSON, nullable=False)
    
    # Amazon DSP data
    order_id = Column(String, nullable=True)
    bulk_sheet_path = Column(String, nullable=True)
    
    # Budget and dates
    total_budget = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Metrics
    creative_count = Column(Integer, default=0)
    processed_creatives_count = Column(Integer, default=0)
    
    def __repr__(self) -> str:
        return f"<Campaign(campaign_id='{self.campaign_id}', name='{self.name}')>"


class CampaignCreativeAssociationDB(BaseModel):
    """Database model for campaign-creative associations."""
    __tablename__ = "campaign_creative_associations"
    
    campaign_id = Column(String, nullable=False, index=True)
    creative_id = Column(String, nullable=False, index=True)
    
    # Line item configuration
    line_item_name = Column(String, nullable=False)
    line_item_type = Column(String, nullable=False)
    bid = Column(Float, nullable=False)
    budget = Column(Float, nullable=False)
    
    # Status
    status = Column(String, default="active")
    
    def __repr__(self) -> str:
        return f"<CampaignCreativeAssociation(campaign_id='{self.campaign_id}', creative_id='{self.creative_id}')>"


class AuditLogDB(BaseModel):
    """Database model for audit logging."""
    __tablename__ = "audit_logs"
    
    entity_type = Column(String, nullable=False)  # campaign, creative, etc.
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # created, updated, deleted, processed
    
    # User/system info
    user_id = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # Change details
    changes = Column(JSON, nullable=True)
    audit_metadata = Column(JSON, nullable=True)
    
    def __repr__(self) -> str:
        return f"<AuditLog(entity_type='{self.entity_type}', entity_id='{self.entity_id}', action='{self.action}')>"


class ViewabilityReportDB(BaseModel):
    """Database model for viewability reporting data."""
    __tablename__ = "viewability_reports"
    
    campaign_id = Column(String, nullable=False, index=True)
    creative_id = Column(String, nullable=False, index=True)
    
    # Reporting period
    report_date = Column(DateTime, nullable=False)
    report_hour = Column(Integer, nullable=True)  # For hourly reports
    
    # Metrics
    impressions = Column(Integer, default=0)
    viewable_impressions = Column(Integer, default=0)
    measurable_impressions = Column(Integer, default=0)
    viewability_rate = Column(Float, default=0.0)
    time_in_view = Column(Float, default=0.0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    
    # Vendor specific data
    vendor = Column(String, nullable=False)  # dv, ias
    vendor_data = Column(JSON, nullable=True)
    
    def __repr__(self) -> str:
        return f"<ViewabilityReport(campaign_id='{self.campaign_id}', vendor='{self.vendor}', date='{self.report_date}')>"


# Database session dependency
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Database initialization
async def init_database() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_database() -> None:
    """Drop all database tables (for testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Database health check
async def check_database_health() -> bool:
    """Check database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False