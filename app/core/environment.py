"""Environment-specific configuration and utilities."""
import os
import sys
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EnvironmentManager:
    """Manages environment-specific configurations and behaviors."""
    
    def __init__(self):
        self.settings = get_settings()
        
    def get_environment_info(self) -> Dict[str, Any]:
        """Get comprehensive environment information."""
        return {
            "environment": self.settings.environment,
            "python_version": sys.version,
            "platform": sys.platform,
            "app_version": self.settings.app_version,
            "debug_mode": self.settings.debug,
            "deployment_info": {
                "deployment_id": self.settings.deployment_id,
                "build_date": self.settings.build_date,
                "git_commit": self.settings.git_commit,
                "pod_name": self.settings.pod_name,
                "node_name": self.settings.node_name,
            },
            "system_info": {
                "pid": os.getpid(),
                "working_directory": os.getcwd(),
                "user": os.getenv("USER", "unknown"),
                "hostname": os.getenv("HOSTNAME", "unknown"),
            }
        }
    
    def configure_for_environment(self) -> None:
        """Apply environment-specific configurations."""
        if self.settings.is_production():
            self._configure_production()
        elif self.settings.is_development():
            self._configure_development()
        elif self.settings.is_testing():
            self._configure_testing()
        else:
            logger.warning(f"Unknown environment: {self.settings.environment}")
    
    def _configure_production(self) -> None:
        """Configure for production environment."""
        logger.info("Configuring for production environment")
        
        # Set production-specific environment variables
        os.environ["PYTHONOPTIMIZE"] = "1"
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        
        # Validate critical settings
        self._validate_production_settings()
        
    def _configure_development(self) -> None:
        """Configure for development environment."""
        logger.info("Configuring for development environment")
        
        # Enable development features
        if self.settings.debug:
            os.environ["PYTHONDEVMODE"] = "1"
    
    def _configure_testing(self) -> None:
        """Configure for testing environment."""
        logger.info("Configuring for testing environment")
        
        # Set testing-specific configurations
        os.environ["PYTHONHASHSEED"] = "0"  # Reproducible hash behavior
        
    def _validate_production_settings(self) -> None:
        """Validate settings for production environment."""
        issues = []
        
        # Security validations
        if self.settings.debug:
            issues.append("DEBUG mode is enabled in production")
        
        if len(self.settings.secret_key) < 32:
            issues.append("SECRET_KEY is too short for production")
        
        if not self.settings.database_url:
            issues.append("DATABASE_URL is not configured")
            
        # Performance validations
        if self.settings.database_pool_size < 5:
            issues.append("Database pool size may be too small for production")
        
        if self.settings.workers < 2:
            issues.append("Consider using more workers in production")
        
        # SSL/Security validations
        if "localhost" in self.settings.allowed_hosts and len(self.settings.allowed_hosts) == 1:
            issues.append("ALLOWED_HOSTS should be configured for production")
        
        if issues:
            for issue in issues:
                logger.warning(f"Production configuration issue: {issue}")
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """Get environment-specific feature flags."""
        base_flags = {
            "debug_mode": self.settings.debug,
            "metrics_enabled": self.settings.metrics_enabled,
            "tracing_enabled": self.settings.tracing_enabled,
            "rate_limiting": True,
        }
        
        if self.settings.is_production():
            return {
                **base_flags,
                "detailed_errors": False,
                "profiling": False,
                "admin_ui": False,
            }
        elif self.settings.is_development():
            return {
                **base_flags,
                "detailed_errors": True,
                "profiling": True,
                "admin_ui": True,
                "auto_reload": self.settings.reload,
            }
        elif self.settings.is_testing():
            return {
                **base_flags,
                "detailed_errors": True,
                "profiling": False,
                "admin_ui": False,
                "rate_limiting": False,
            }
        
        return base_flags
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get environment-specific logging configuration."""
        base_config = {
            "level": self.settings.log_level,
            "format": "json" if self.settings.is_production() else "console",
        }
        
        if self.settings.is_production():
            return {
                **base_config,
                "enable_access_logs": True,
                "log_sql_queries": False,
                "log_request_bodies": False,
            }
        elif self.settings.is_development():
            return {
                **base_config,
                "enable_access_logs": True,
                "log_sql_queries": True,
                "log_request_bodies": True,
            }
        elif self.settings.is_testing():
            return {
                **base_config,
                "level": "WARNING",  # Less verbose during tests
                "enable_access_logs": False,
                "log_sql_queries": False,
                "log_request_bodies": False,
            }
        
        return base_config
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get environment-specific database configuration."""
        base_config = self.settings.get_database_config()
        
        if self.settings.is_production():
            return {
                **base_config,
                "echo": False,
                "pool_pre_ping": True,
                "connect_timeout": 30,
            }
        elif self.settings.is_development():
            return {
                **base_config,
                "echo": True,  # Log SQL queries
                "pool_pre_ping": False,
                "connect_timeout": 10,
            }
        elif self.settings.is_testing():
            return {
                **base_config,
                "echo": False,
                "pool_size": 1,  # Single connection for tests
                "max_overflow": 0,
                "pool_pre_ping": False,
                "connect_timeout": 5,
            }
        
        return base_config
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get environment-specific cache configuration."""
        base_ttls = self.settings.get_cache_config()
        
        if self.settings.is_production():
            return {
                "ttls": base_ttls,
                "max_connections": self.settings.redis_max_connections,
                "timeout": self.settings.redis_timeout,
                "retry_on_timeout": True,
            }
        elif self.settings.is_development():
            return {
                "ttls": {k: min(v, 60) for k, v in base_ttls.items()},  # Shorter TTLs
                "max_connections": 5,
                "timeout": 5,
                "retry_on_timeout": False,
            }
        elif self.settings.is_testing():
            return {
                "ttls": {k: 1 for k in base_ttls.keys()},  # Very short TTLs
                "max_connections": 1,
                "timeout": 1,
                "retry_on_timeout": False,
            }
        
        return {
            "ttls": base_ttls,
            "max_connections": self.settings.redis_max_connections,
            "timeout": self.settings.redis_timeout,
            "retry_on_timeout": True,
        }
    
    def should_enable_cors(self) -> bool:
        """Determine if CORS should be enabled."""
        return not self.settings.is_production() or bool(self.settings.cors_origins)
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration."""
        if self.settings.is_production():
            return {
                "allow_origins": self.settings.cors_origins,
                "allow_credentials": True,
                "allow_methods": ["GET", "POST", "PUT", "DELETE"],
                "allow_headers": ["*"],
            }
        else:
            return {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            }
    
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limiting configuration."""
        return {
            "requests_per_minute": self.settings.rate_limit_requests_per_minute,
            "burst": self.settings.rate_limit_burst,
            "enabled": self.get_feature_flags()["rate_limiting"],
        }


# Global environment manager instance
env_manager = EnvironmentManager()


def get_environment_manager() -> EnvironmentManager:
    """Get the global environment manager instance."""
    return env_manager


def configure_environment() -> None:
    """Configure the application for the current environment."""
    env_manager.configure_for_environment()
    
    logger.info(
        "Environment configured",
        environment=env_manager.settings.environment,
        features=env_manager.get_feature_flags(),
    )