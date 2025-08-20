#!/usr/bin/env python3
"""Database management CLI utility."""
import asyncio
import argparse
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.migrations import get_migration_manager, run_migrations
from app.core.config import validate_environment
from app.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


def print_status():
    """Print current migration status."""
    manager = get_migration_manager()
    
    print("🗄️  Database Migration Status")
    print("=" * 40)
    
    # Validate connection
    if not manager.validate_database_connection():
        print("❌ Cannot connect to database")
        return False
    
    status = manager.get_migration_status()
    
    print(f"Current Revision: {status['current_revision'] or 'None'}")
    print(f"Pending Migrations: {status['pending_count']}")
    print(f"Total Migrations: {status['total_migrations']}")
    print(f"Up to Date: {'✅' if status['up_to_date'] else '❌'}")
    
    if status['pending_migrations']:
        print("\nPending Migrations:")
        for rev in status['pending_migrations']:
            print(f"  - {rev}")
    
    if status['migration_history']:
        print("\nRecent Migration History:")
        for migration in status['migration_history']:
            print(f"  - {migration['revision']}: {migration['description']}")
    
    return True


def upgrade_database(revision="head"):
    """Upgrade database to specified revision."""
    manager = get_migration_manager()
    
    print(f"🚀 Upgrading database to: {revision}")
    
    if not manager.validate_database_connection():
        print("❌ Cannot connect to database")
        return False
    
    success = manager.upgrade(revision)
    
    if success:
        print("✅ Database upgrade completed successfully")
    else:
        print("❌ Database upgrade failed")
    
    return success


def downgrade_database(revision):
    """Downgrade database to specified revision."""
    manager = get_migration_manager()
    
    print(f"⬇️  Downgrading database to: {revision}")
    
    # Confirm destructive operation
    confirm = input("This operation may cause data loss. Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Operation cancelled")
        return False
    
    if not manager.validate_database_connection():
        print("❌ Cannot connect to database")
        return False
    
    success = manager.downgrade(revision)
    
    if success:
        print("✅ Database downgrade completed successfully")
    else:
        print("❌ Database downgrade failed")
    
    return success


def create_migration(message, autogenerate=True):
    """Create a new migration."""
    manager = get_migration_manager()
    
    print(f"📝 Creating new migration: {message}")
    
    success = manager.create_migration(message, autogenerate)
    
    if success:
        print("✅ Migration created successfully")
    else:
        print("❌ Failed to create migration")
    
    return success


def initialize_database():
    """Initialize database for migrations."""
    manager = get_migration_manager()
    
    print("🏗️  Initializing database")
    
    if not manager.validate_database_connection():
        print("❌ Cannot connect to database")
        return False
    
    success = manager.initialize_database()
    
    if success:
        print("✅ Database initialized successfully")
    else:
        print("❌ Failed to initialize database")
    
    return success


def run_async_migrations():
    """Run migrations asynchronously."""
    print("🚀 Running database migrations")
    
    success = asyncio.run(run_migrations())
    
    if success:
        print("✅ Migrations completed successfully")
    else:
        print("❌ Migrations failed")
    
    return success


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Database migration management")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    subparsers.add_parser("status", help="Show migration status")
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade database")
    upgrade_parser.add_argument("revision", nargs="?", default="head", help="Target revision (default: head)")
    
    # Downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade database")
    downgrade_parser.add_argument("revision", help="Target revision")
    
    # Create migration command
    create_parser = subparsers.add_parser("create", help="Create new migration")
    create_parser.add_argument("message", help="Migration message")
    create_parser.add_argument("--no-autogenerate", action="store_true", help="Create empty migration")
    
    # Initialize command
    subparsers.add_parser("init", help="Initialize database for migrations")
    
    # Migrate command (upgrade to head)
    subparsers.add_parser("migrate", help="Run all pending migrations")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Validate environment
        validate_environment()
        
        # Execute command
        if args.command == "status":
            success = print_status()
        elif args.command == "upgrade":
            success = upgrade_database(args.revision)
        elif args.command == "downgrade":
            success = downgrade_database(args.revision)
        elif args.command == "create":
            success = create_migration(args.message, not args.no_autogenerate)
        elif args.command == "init":
            success = initialize_database()
        elif args.command == "migrate":
            success = run_async_migrations()
        else:
            print(f"Unknown command: {args.command}")
            return 1
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())