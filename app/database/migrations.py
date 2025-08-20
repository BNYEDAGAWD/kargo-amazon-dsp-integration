"""Database migration utilities and management."""
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.core.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """Manages database migrations using Alembic."""
    
    def __init__(self):
        self.settings = get_settings()
        self.project_root = Path(__file__).parent.parent.parent
        self.alembic_cfg_path = self.project_root / "alembic.ini"
        
    def get_alembic_config(self) -> Config:
        """Get Alembic configuration with proper database URL."""
        if not self.alembic_cfg_path.exists():
            raise FileNotFoundError(f"Alembic config file not found: {self.alembic_cfg_path}")
        
        alembic_cfg = Config(str(self.alembic_cfg_path))
        
        # Set the database URL from settings
        database_url = str(self.settings.database_url)
        if database_url.startswith("postgresql+asyncpg://"):
            # Convert asyncpg URL to psycopg2 for Alembic
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        
        return alembic_cfg
    
    def get_migration_history(self) -> List[Dict[str, Any]]:
        """Get the migration history from the database."""
        try:
            alembic_cfg = self.get_alembic_config()
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            
            # Get all migrations from the script directory
            revisions = []
            for revision in script_dir.walk_revisions():
                revisions.append({
                    "revision": revision.revision,
                    "down_revision": revision.down_revision,
                    "description": revision.doc,
                    "module_path": revision.module,
                })
            
            return list(reversed(revisions))  # Return in chronological order
            
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []
    
    def get_current_revision(self) -> Optional[str]:
        """Get the current database revision."""
        try:
            alembic_cfg = self.get_alembic_config()
            database_url = alembic_cfg.get_main_option("sqlalchemy.url")
            
            # Create synchronous engine for Alembic
            engine = create_engine(database_url)
            
            with engine.connect() as connection:
                migration_context = MigrationContext.configure(connection)
                current_rev = migration_context.get_current_revision()
                
            engine.dispose()
            return current_rev
            
        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None
    
    def get_pending_migrations(self) -> List[str]:
        """Get list of pending migrations that need to be applied."""
        try:
            alembic_cfg = self.get_alembic_config()
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            current_rev = self.get_current_revision()
            
            # Get head revision
            head_rev = script_dir.get_current_head()
            
            if current_rev is None:
                # No migrations applied yet, return all
                revisions = []
                for revision in script_dir.walk_revisions("base", head_rev):
                    revisions.append(revision.revision)
                return list(reversed(revisions))
            elif current_rev == head_rev:
                # Already at head
                return []
            else:
                # Get revisions between current and head
                revisions = []
                for revision in script_dir.walk_revisions(current_rev, head_rev):
                    if revision.revision != current_rev:
                        revisions.append(revision.revision)
                return list(reversed(revisions))
                
        except Exception as e:
            logger.error(f"Failed to get pending migrations: {e}")
            return []
    
    def create_migration(self, message: str, autogenerate: bool = True) -> bool:
        """Create a new migration file."""
        try:
            alembic_cfg = self.get_alembic_config()
            
            if autogenerate:
                logger.info(f"Creating new migration with autogenerate: {message}")
                command.revision(alembic_cfg, message=message, autogenerate=True)
            else:
                logger.info(f"Creating empty migration: {message}")
                command.revision(alembic_cfg, message=message)
            
            logger.info("Migration file created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            return False
    
    def upgrade(self, revision: str = "head") -> bool:
        """Run database upgrades to the specified revision."""
        try:
            logger.info(f"Running database upgrade to revision: {revision}")
            alembic_cfg = self.get_alembic_config()
            
            command.upgrade(alembic_cfg, revision)
            
            logger.info(f"Database upgraded to revision: {revision}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upgrade database: {e}")
            return False
    
    def downgrade(self, revision: str) -> bool:
        """Run database downgrade to the specified revision."""
        try:
            logger.info(f"Running database downgrade to revision: {revision}")
            alembic_cfg = self.get_alembic_config()
            
            command.downgrade(alembic_cfg, revision)
            
            logger.info(f"Database downgraded to revision: {revision}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to downgrade database: {e}")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        current_rev = self.get_current_revision()
        pending = self.get_pending_migrations()
        history = self.get_migration_history()
        
        return {
            "current_revision": current_rev,
            "pending_migrations": pending,
            "pending_count": len(pending),
            "total_migrations": len(history),
            "up_to_date": len(pending) == 0,
            "migration_history": history[-5:] if history else [],  # Last 5 migrations
        }
    
    def validate_database_connection(self) -> bool:
        """Validate that we can connect to the database."""
        try:
            database_url = str(self.settings.database_url)
            if database_url.startswith("postgresql+asyncpg://"):
                database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
            
            engine = create_engine(database_url, pool_timeout=5)
            
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            
            engine.dispose()
            logger.info("Database connection validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database connection validation failed: {e}")
            return False
    
    def initialize_database(self) -> bool:
        """Initialize database with migration tracking."""
        try:
            if not self.validate_database_connection():
                return False
            
            logger.info("Initializing database migration tracking")
            alembic_cfg = self.get_alembic_config()
            
            # Create migration tracking table
            command.stamp(alembic_cfg, "head")
            
            logger.info("Database migration tracking initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False


# Global migration manager instance
migration_manager = MigrationManager()


def get_migration_manager() -> MigrationManager:
    """Get the global migration manager instance."""
    return migration_manager


async def run_migrations() -> bool:
    """Run pending database migrations."""
    manager = get_migration_manager()
    
    logger.info("Starting database migrations")
    
    # Validate connection first
    if not manager.validate_database_connection():
        logger.error("Cannot connect to database, aborting migrations")
        return False
    
    # Get current status
    status = manager.get_migration_status()
    logger.info(f"Migration status: {status['pending_count']} pending migrations")
    
    if status["up_to_date"]:
        logger.info("Database is already up to date")
        return True
    
    # Run migrations
    success = manager.upgrade()
    
    if success:
        logger.info("Database migrations completed successfully")
    else:
        logger.error("Database migrations failed")
    
    return success


def create_initial_migration() -> bool:
    """Create the initial migration for the database schema."""
    manager = get_migration_manager()
    
    logger.info("Creating initial database migration")
    
    return manager.create_migration(
        message="Initial database schema",
        autogenerate=True
    )


def get_migration_status() -> Dict[str, Any]:
    """Get current migration status for health checks and monitoring."""
    manager = get_migration_manager()
    return manager.get_migration_status()