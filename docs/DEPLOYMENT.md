# Kargo Amazon DSP Integration - Deployment Guide

This comprehensive guide covers deploying the Kargo Amazon DSP Integration service in production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Docker Deployment](#docker-deployment)
- [Database Setup](#database-setup)
- [Monitoring & Observability](#monitoring--observability)
- [Health Checks](#health-checks)
- [Scaling](#scaling)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Prerequisites

### System Requirements

- **Docker**: Version 20.0 or higher
- **Docker Compose**: Version 2.0 or higher
- **Memory**: Minimum 2GB RAM, recommended 4GB+
- **CPU**: Minimum 2 cores, recommended 4+ cores
- **Disk**: 10GB+ free space
- **Network**: Stable internet connection for API calls

### External Dependencies

- **PostgreSQL**: Version 13+ (can be containerized)
- **Redis**: Version 6+ (can be containerized)
- **Amazon DSP API**: Valid credentials and access
- **Kargo API**: Valid credentials and access

## Environment Configuration

### 1. Create Environment File

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

### 2. Configure Required Variables

Edit `.env` with your production values:

```bash
# Application Configuration
APP_VERSION=1.0.0
ENVIRONMENT=production
LOG_LEVEL=INFO
WORKERS=4

# Security (CRITICAL - Change these!)
SECRET_KEY=your-very-secure-secret-key-at-least-32-characters-long
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Database
POSTGRES_DB=kargo_dsp
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-database-password
DATABASE_URL=postgresql+asyncpg://postgres:your-secure-database-password@db:5432/kargo_dsp

# External APIs
AMAZON_DSP_BASE_URL=https://advertising-api.amazon.com
KARGO_API_BASE_URL=https://api.kargo.com

# Monitoring
METRICS_ENABLED=true
OTEL_SERVICE_NAME=kargo-amazon-dsp-integration
```

### 3. Environment Validation

Validate your configuration:

```bash
python -c "from app.core.config import validate_environment; validate_environment()"
```

## Docker Deployment

### 1. Build the Application

```bash
# Build with version tagging
export APP_VERSION=1.0.0
export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
export VCS_REF=$(git rev-parse --short HEAD)

./scripts/docker-build.sh
```

### 2. Deploy with Docker Compose

```bash
# Start all services
./scripts/deploy.sh

# Or manually with docker-compose
docker-compose up -d
```

### 3. Verify Deployment

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f app

# Check health
curl http://localhost:8000/health/live
```

## Database Setup

### 1. Initialize Database

```bash
# Run database migrations
python scripts/manage-db.py migrate

# Check migration status
python scripts/manage-db.py status
```

### 2. Create Initial Data (if needed)

```bash
# Run any seed scripts
docker-compose exec app python -m scripts.seed_data
```

### 3. Backup Strategy

Set up regular database backups:

```bash
# Create backup
docker-compose exec db pg_dump -U postgres kargo_dsp > backup_$(date +%Y%m%d).sql

# Schedule backups (add to crontab)
0 2 * * * /path/to/backup_script.sh
```

## Monitoring & Observability

### 1. Built-in Monitoring

The application includes comprehensive monitoring:

- **Health Checks**: `/health/live`, `/health/ready`, `/health/detailed`
- **Metrics**: `/health/metrics` (Prometheus format)
- **Performance**: `/api/performance/summary`
- **Error Tracking**: `/api/errors/statistics`

### 2. External Monitoring (Optional)

Deploy monitoring stack:

```bash
# With monitoring services
docker-compose --profile monitoring up -d

# Access Grafana
open http://localhost:3000

# Access Prometheus
open http://localhost:9090
```

### 3. Log Management

Logs are structured and include correlation IDs for tracing:

```bash
# View application logs
docker-compose logs -f app

# Search logs by correlation ID
docker-compose logs app | grep "correlation_id=abc123"
```

## Health Checks

### Application Health Endpoints

1. **Liveness Check** (`/health/live`)
   - Quick check if application is running
   - Used by container orchestration

2. **Readiness Check** (`/health/ready`)
   - Comprehensive check including dependencies
   - Returns 503 if not ready

3. **Detailed Health** (`/health/detailed`)
   - Full system status with metrics
   - Memory, CPU, disk usage

### Kubernetes Health Checks

```yaml
# Example Kubernetes health check configuration
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 10
  failureThreshold: 3
```

### Load Balancer Health Checks

Configure your load balancer to use `/health/ready`:

- **Path**: `/health/ready`
- **Port**: `8000`
- **Interval**: `30s`
- **Timeout**: `10s`
- **Healthy Threshold**: `2`
- **Unhealthy Threshold**: `3`

## Scaling

### Horizontal Scaling

1. **Increase Workers**:
   ```bash
   # Update docker-compose.yml
   environment:
     - WORKERS=8  # Increase worker count
   
   docker-compose up -d app
   ```

2. **Multiple Instances**:
   ```bash
   # Scale to multiple containers
   docker-compose up -d --scale app=3
   ```

### Vertical Scaling

1. **Resource Limits**:
   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 2G
         cpus: '1.0'
       reservations:
         memory: 1G
         cpus: '0.5'
   ```

### Database Scaling

1. **Connection Pooling**:
   ```bash
   # Increase pool size
   DATABASE_POOL_SIZE=20
   DATABASE_MAX_OVERFLOW=40
   ```

2. **Read Replicas** (if using external PostgreSQL):
   - Configure read-only replica
   - Update connection strings for read queries

## Troubleshooting

### Common Issues

1. **Application Won't Start**
   ```bash
   # Check configuration
   python scripts/manage-db.py status
   
   # Verify environment
   docker-compose config
   
   # Check logs
   docker-compose logs app
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connectivity
   docker-compose exec app python -c "from app.models.database import check_database_health; print(check_database_health())"
   
   # Check database logs
   docker-compose logs db
   ```

3. **High Memory Usage**
   ```bash
   # Monitor memory usage
   curl http://localhost:8000/api/performance/system-metrics
   
   # Check for memory leaks
   curl http://localhost:8000/api/errors/recent?category=internal_error
   ```

4. **Slow Performance**
   ```bash
   # Check slow operations
   curl http://localhost:8000/api/performance/slow-operations
   
   # Review performance summary
   curl http://localhost:8000/api/performance/summary
   ```

### Log Analysis

Key log patterns to monitor:

```bash
# Error patterns
grep -i "error\|exception\|failed" logs/app.log

# Performance issues
grep -i "slow\|timeout\|duration" logs/app.log

# Security issues
grep -i "unauthorized\|forbidden\|invalid" logs/app.log
```

### Recovery Procedures

1. **Service Recovery**:
   ```bash
   # Restart application
   docker-compose restart app
   
   # Full redeploy
   ./scripts/deploy.sh
   ```

2. **Database Recovery**:
   ```bash
   # Restore from backup
   docker-compose exec db psql -U postgres -d kargo_dsp < backup_20240101.sql
   
   # Run migrations
   python scripts/manage-db.py migrate
   ```

## Security Considerations

### 1. Environment Security

- Store secrets in environment variables, never in code
- Use strong, unique passwords for all services
- Rotate secrets regularly
- Limit environment file permissions: `chmod 600 .env`

### 2. Network Security

```yaml
# Example secure network configuration
networks:
  kargo-network:
    driver: bridge
    internal: true  # Internal network only
```

### 3. Container Security

- Run containers as non-root user (already configured)
- Keep base images updated
- Scan images for vulnerabilities
- Use resource limits

### 4. API Security

- Enable rate limiting (configured)
- Use HTTPS in production
- Implement proper authentication
- Monitor for suspicious activity

### 5. Database Security

- Use connection encryption
- Implement proper access controls
- Regular security updates
- Backup encryption

## Production Checklist

Before going live, verify:

- [ ] All environment variables configured
- [ ] Database migrations completed
- [ ] Health checks responding correctly
- [ ] Monitoring and alerting configured
- [ ] Backup procedures tested
- [ ] Security hardening applied
- [ ] Performance testing completed
- [ ] Incident response procedures defined
- [ ] Documentation updated
- [ ] Team training completed

## Support and Maintenance

### Regular Tasks

1. **Daily**:
   - Monitor health checks
   - Review error logs
   - Check performance metrics

2. **Weekly**:
   - Review security logs
   - Update dependencies
   - Performance optimization

3. **Monthly**:
   - Security audit
   - Disaster recovery testing
   - Capacity planning review

### Emergency Contacts

- **Infrastructure**: DevOps team
- **Application**: Development team
- **Database**: Database administrators
- **Security**: Security team

### Resources

- **Repository**: https://github.com/your-org/kargo-amazon-dsp-integration
- **Documentation**: Internal wiki or documentation system
- **Monitoring**: Grafana dashboards
- **Alerting**: PagerDuty or alerting system

---

For additional help or questions, consult the development team or create an issue in the project repository.