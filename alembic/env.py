"""Alembic migration environment configuration."""
import asyncio
import logging
import os
import sys
from logging.config import fileConfig
from typing import Any, Dict

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your models here for autogenerate support
from app.models.database import Base
from app.models.campaigns import Campaign, CampaignPhase, Creative
from app.models.reports import ViewabilityReport, PerformanceMetric

# This is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger(__name__)

# Set the target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url() -> str:
    """Get database URL from environment variables or config."""
    # Try to get from environment first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Convert asyncpg URL to psycopg2 for Alembic
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        return database_url
    
    # Fallback to config file
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        # Custom options
        render_as_batch=True,  # For SQLite compatibility during testing
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Get the database URL
    database_url = get_database_url()
    
    if not database_url or database_url == "driver://user:pass@localhost/dbname":
        logger.error("No valid database URL found. Please set DATABASE_URL environment variable.")
        sys.exit(1)
    
    logger.info(f"Running migrations against: {database_url.split('@')[1] if '@' in database_url else database_url}")
    
    # Create engine configuration
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url
    
    # Engine configuration for migrations
    engine_config = {
        "poolclass": pool.NullPool,  # Don't use connection pooling for migrations
        "isolation_level": "AUTOCOMMIT",  # Some migrations might need this
    }
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        **engine_config
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online_sync() -> None:
    """Synchronous wrapper for async migrations."""
    asyncio.run(run_migrations_online())


# Determine if we're running in offline mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online_sync()