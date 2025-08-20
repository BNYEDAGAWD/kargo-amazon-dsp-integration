"""Viewability reporting service placeholder."""
from sqlalchemy.ext.asyncio import AsyncSession


class ViewabilityService:
    """Placeholder viewability service."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def configure_reporting(self, campaign_id: str) -> str:
        """Configure viewability reporting (placeholder)."""
        # TODO: Implement in Sprint 3
        raise NotImplementedError("Viewability reporting will be implemented in Sprint 3")