"""Application configuration management with validation and environment support."""
import os
import secrets
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseSettings, validator, Field
from pydantic.networks import AnyHttpUrl, PostgresDsn


class Settings(BaseSettings):
    """Application settings with validation and environment variable support."""
    
    # Application settings
    app_name: str = "kargo-amazon-dsp-integration"
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Security
    secret_key: str = Field(env="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, env="JWT_EXPIRE_MINUTES")
    allowed_hosts: List[str] = Field(default=["localhost", "127.0.0.1"], env="ALLOWED_HOSTS")
    cors_origins: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    
    # Database
    database_url: Optional[PostgresDsn] = Field(env="DATABASE_URL")
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=3600, env="DATABASE_POOL_RECYCLE")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    redis_timeout: int = Field(default=5, env="REDIS_TIMEOUT")
    
    # External APIs
    amazon_dsp_base_url: AnyHttpUrl = Field(env="AMAZON_DSP_BASE_URL")
    amazon_dsp_timeout: int = Field(default=30, env="AMAZON_DSP_TIMEOUT")
    amazon_dsp_max_retries: int = Field(default=3, env="AMAZON_DSP_MAX_RETRIES")
    amazon_dsp_backoff_factor: float = Field(default=0.5, env="AMAZON_DSP_BACKOFF_FACTOR")
    
    kargo_api_base_url: AnyHttpUrl = Field(env="KARGO_API_BASE_URL")
    kargo_api_timeout: int = Field(default=30, env="KARGO_API_TIMEOUT")
    kargo_api_max_retries: int = Field(default=3, env="KARGO_API_MAX_RETRIES")
    kargo_api_backoff_factor: float = Field(default=0.5, env="KARGO_API_BACKOFF_FACTOR")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    reload: bool = Field(default=False, env="RELOAD")
    
    # Monitoring and observability
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    tracing_enabled: bool = Field(default=True, env="TRACING_ENABLED")
    health_check_timeout: int = Field(default=30, env="HEALTH_CHECK_TIMEOUT")
    
    # OpenTelemetry
    otel_service_name: str = Field(default="kargo-amazon-dsp-integration", env="OTEL_SERVICE_NAME")
    otel_service_version: str = Field(default="1.0.0", env="OTEL_SERVICE_VERSION")
    otel_exporter_otlp_endpoint: Optional[str] = Field(env="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_resource_attributes: str = Field(default="", env="OTEL_RESOURCE_ATTRIBUTES")
    
    # File storage
    upload_dir: str = Field(default="/app/data/uploads", env="UPLOAD_DIR")
    temp_dir: str = Field(default="/app/tmp", env="TEMP_DIR")
    max_upload_size: int = Field(default=50 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 50MB
    
    # Task processing
    task_queue_max_size: int = Field(default=1000, env="TASK_QUEUE_MAX_SIZE")
    task_worker_count: int = Field(default=4, env="TASK_WORKER_COUNT")
    task_timeout: int = Field(default=300, env="TASK_TIMEOUT")
    
    # Rate limiting
    rate_limit_requests_per_minute: int = Field(default=60, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    rate_limit_burst: int = Field(default=10, env="RATE_LIMIT_BURST")
    
    # Caching
    cache_ttl_default: int = Field(default=300, env="CACHE_TTL_DEFAULT")
    cache_ttl_user_sessions: int = Field(default=3600, env="CACHE_TTL_USER_SESSIONS")
    cache_ttl_api_responses: int = Field(default=60, env="CACHE_TTL_API_RESPONSES")
    
    # Deployment metadata
    deployment_id: Optional[str] = Field(env="DEPLOYMENT_ID")
    build_date: Optional[str] = Field(env="BUILD_DATE")
    git_commit: Optional[str] = Field(env="VCS_REF")
    pod_name: Optional[str] = Field(env="POD_NAME")
    node_name: Optional[str] = Field(env="NODE_NAME")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("secret_key", pre=True)
    def validate_secret_key(cls, v: Optional[str]) -> str:
        if v is None:
            return secrets.token_urlsafe(32)
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        valid_environments = ["development", "staging", "production", "testing"]
        if v.lower() not in valid_environments:
            raise ValueError(f"ENVIRONMENT must be one of: {', '.join(valid_environments)}")
        return v.lower()
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @validator("allowed_hosts", pre=True)
    def parse_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @validator("workers")
    def validate_workers(cls, v: int) -> int:
        if v < 1:
            raise ValueError("WORKERS must be at least 1")
        if v > 8:
            raise ValueError("WORKERS should not exceed 8 for this application")
        return v
    
    @validator("port")
    def validate_port(cls, v: int) -> int:
        if v < 1 or v > 65535:
            raise ValueError("PORT must be between 1 and 65535")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == "testing"
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration parameters."""
        return {
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "pool_timeout": self.database_pool_timeout,
            "pool_recycle": self.database_pool_recycle,
        }
    
    def get_api_config(self, service: str) -> Dict[str, Any]:
        """Get API configuration for a specific service."""
        if service == "amazon_dsp":
            return {
                "base_url": str(self.amazon_dsp_base_url),
                "timeout": self.amazon_dsp_timeout,
                "max_retries": self.amazon_dsp_max_retries,
                "backoff_factor": self.amazon_dsp_backoff_factor,
            }
        elif service == "kargo":
            return {
                "base_url": str(self.kargo_api_base_url),
                "timeout": self.kargo_api_timeout,
                "max_retries": self.kargo_api_max_retries,
                "backoff_factor": self.kargo_api_backoff_factor,
            }
        else:
            raise ValueError(f"Unknown service: {service}")
    
    def get_cache_config(self) -> Dict[str, int]:
        """Get cache TTL configuration."""
        return {
            "default": self.cache_ttl_default,
            "user_sessions": self.cache_ttl_user_sessions,
            "api_responses": self.cache_ttl_api_responses,
        }
    
    def get_otel_resource_attributes(self) -> Dict[str, str]:
        """Parse and return OpenTelemetry resource attributes."""
        attributes = {
            "service.name": self.otel_service_name,
            "service.version": self.otel_service_version,
            "deployment.environment": self.environment,
        }
        
        # Add deployment metadata if available
        if self.deployment_id:
            attributes["deployment.id"] = self.deployment_id
        if self.build_date:
            attributes["deployment.build_date"] = self.build_date
        if self.git_commit:
            attributes["deployment.git_commit"] = self.git_commit
        if self.pod_name:
            attributes["k8s.pod.name"] = self.pod_name
        if self.node_name:
            attributes["k8s.node.name"] = self.node_name
        
        # Parse additional attributes from environment
        if self.otel_resource_attributes:
            for pair in self.otel_resource_attributes.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    attributes[key.strip()] = value.strip()
        
        return attributes


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def validate_environment() -> None:
    """Validate environment configuration on startup."""
    try:
        settings = get_settings()
        
        # Create required directories
        os.makedirs(settings.upload_dir, exist_ok=True)
        os.makedirs(settings.temp_dir, exist_ok=True)
        os.makedirs("/app/logs", exist_ok=True)
        
        # Validate required environment variables for production
        if settings.is_production():
            required_vars = [
                "SECRET_KEY",
                "DATABASE_URL", 
                "AMAZON_DSP_BASE_URL",
                "KARGO_API_BASE_URL",
                "POSTGRES_PASSWORD"
            ]
            
            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                raise ValueError(f"Missing required environment variables for production: {', '.join(missing_vars)}")
        
        print(f"✅ Environment validation passed for {settings.environment} environment")
        
    except Exception as e:
        print(f"❌ Environment validation failed: {e}")
        raise


def get_config_summary() -> Dict[str, Any]:
    """Get a summary of current configuration for debugging."""
    settings = get_settings()
    
    return {
        "app": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
        },
        "server": {
            "host": settings.host,
            "port": settings.port,
            "workers": settings.workers,
        },
        "database": {
            "url_set": bool(settings.database_url),
            "pool_size": settings.database_pool_size,
        },
        "external_apis": {
            "amazon_dsp_url": str(settings.amazon_dsp_base_url),
            "kargo_api_url": str(settings.kargo_api_base_url),
        },
        "monitoring": {
            "metrics_enabled": settings.metrics_enabled,
            "tracing_enabled": settings.tracing_enabled,
        },
        "deployment": {
            "deployment_id": settings.deployment_id,
            "build_date": settings.build_date,
            "git_commit": settings.git_commit,
        }
    }