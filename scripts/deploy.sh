#!/bin/bash

# Production deployment script
set -e

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROJECT_NAME="${PROJECT_NAME:-kargo-dsp}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        log_warn ".env file not found, creating from .env.example"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn "Please edit .env file with your configuration before continuing"
            exit 1
        else
            log_error ".env.example not found"
            exit 1
        fi
    fi
    
    log_info "Prerequisites check completed"
}

# Pre-deployment checks
pre_deployment_checks() {
    log_step "Running pre-deployment checks..."
    
    # Validate environment file
    source .env
    
    if [ -z "$SECRET_KEY" ] || [ ${#SECRET_KEY} -lt 32 ]; then
        log_error "SECRET_KEY must be at least 32 characters long"
        exit 1
    fi
    
    if [ -z "$POSTGRES_PASSWORD" ]; then
        log_error "POSTGRES_PASSWORD must be set"
        exit 1
    fi
    
    log_info "Pre-deployment checks completed"
}

# Deploy services
deploy() {
    log_step "Deploying services..."
    
    # Pull latest images
    log_info "Pulling latest images..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" pull
    
    # Build application if needed
    if [ "${BUILD_IMAGE:-false}" = "true" ]; then
        log_info "Building application image..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build app
    fi
    
    # Start services
    log_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
    
    log_info "Services deployed successfully"
}

# Health check
health_check() {
    log_step "Running health checks..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Health check attempt $attempt/$max_attempts"
        
        if curl -f http://localhost:8000/health/live >/dev/null 2>&1; then
            log_info "Application is healthy"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Health check failed after $max_attempts attempts"
            exit 1
        fi
        
        sleep 10
        attempt=$((attempt + 1))
    done
}

# Main deployment process
main() {
    log_info "🚀 Starting deployment for environment: $ENVIRONMENT"
    
    case "${1:-deploy}" in
        "deploy")
            check_prerequisites
            pre_deployment_checks
            deploy
            health_check
            log_info "🎉 Deployment completed successfully!"
            ;;
        "health")
            health_check
            ;;
        *)
            echo "Usage: $0 [deploy|health]"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"