# Kargo Amazon DSP Integration - Infrastructure Guide

This document provides detailed information about the infrastructure requirements, architecture, and operational considerations for the Kargo Amazon DSP Integration service.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Kargo API     │    │  Amazon DSP API │
│   (Nginx/ALB)   │    │                 │    │                 │
└─────────┬───────┘    └─────────────────┘    └─────────────────┘
          │                       ▲                       ▲
          ▼                       │                       │
┌─────────────────┐              │                       │
│   Application   │              │                       │
│   (FastAPI)     │──────────────┼───────────────────────┘
│                 │              │
└─────────┬───────┘              │
          │                      │
          ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │
│   Database      │    │     Cache       │
│                 │    │                 │
└─────────────────┘    └─────────────────┘
```

## Infrastructure Components

### 1. Application Layer

#### Containerized Application
- **Technology**: Docker containers with FastAPI
- **Resource Requirements**:
  - CPU: 0.5-2.0 cores per instance
  - Memory: 512MB-2GB per instance
  - Storage: 1GB for logs and temporary files

#### Load Balancer
- **Options**: Nginx, AWS ALB, Google Cloud Load Balancer
- **Features Required**:
  - Health checks
  - SSL termination
  - Rate limiting
  - Request routing

### 2. Data Layer

#### PostgreSQL Database
- **Version**: 13+ recommended
- **Resource Requirements**:
  - CPU: 2-4 cores
  - Memory: 4-8GB
  - Storage: 100GB+ SSD
  - IOPS: 3000+ for production workloads

#### Redis Cache
- **Version**: 6+ recommended
- **Resource Requirements**:
  - CPU: 1-2 cores
  - Memory: 1-4GB
  - Storage: Minimal (in-memory)

### 3. External Dependencies

#### Amazon DSP API
- **Endpoint**: https://advertising-api.amazon.com
- **Requirements**: Valid credentials and API access
- **Rate Limits**: Varies by endpoint (typically 100-1000 req/min)

#### Kargo API
- **Endpoint**: https://api.kargo.com
- **Requirements**: Valid API credentials
- **Rate Limits**: As per Kargo's documentation

## Deployment Topologies

### 1. Single Server Deployment

**Use Case**: Development, testing, small production workloads

```
┌─────────────────────────────────────────┐
│           Single Server                  │
│                                         │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐  │
│  │   App   │ │PostgreSQL│ │  Redis   │  │
│  │         │ │          │ │          │  │
│  └─────────┘ └──────────┘ └──────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

**Specifications**:
- CPU: 4 cores minimum
- Memory: 8GB minimum
- Storage: 50GB SSD
- Network: 1Gbps

### 2. Multi-Server Deployment

**Use Case**: Production workloads, high availability

```
┌─────────────────┐    ┌─────────────────┐
│ Load Balancer   │    │  Monitoring     │
│ (Nginx/HAProxy) │    │  (Prometheus)   │
└─────────────────┘    └─────────────────┘
          │
          ▼
┌─────────────────┐    ┌─────────────────┐
│   App Server 1  │    │   App Server 2  │
│                 │    │                 │
└─────────────────┘    └─────────────────┘
          │                      │
          └──────────┬───────────┘
                     ▼
┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │
│   Primary       │    │   Cluster       │
│                 │    │                 │
└─────────────────┘    └─────────────────┘
```

### 3. Cloud-Native Deployment

**Use Case**: Kubernetes, auto-scaling, cloud platforms

```yaml
# Example Kubernetes deployment structure
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kargo-dsp-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kargo-dsp-app
  template:
    spec:
      containers:
      - name: app
        image: kargo-amazon-dsp-integration:latest
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
```

## Cloud Provider Configurations

### AWS Deployment

#### ECS with Fargate
```json
{
  "family": "kargo-dsp-integration",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "your-account.dkr.ecr.region.amazonaws.com/kargo-dsp:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:kargo-dsp-secrets"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health/live || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

#### RDS Configuration
```terraform
resource "aws_db_instance" "kargo_dsp_db" {
  identifier             = "kargo-dsp-production"
  engine                 = "postgres"
  engine_version        = "13.13"
  instance_class        = "db.t3.medium"
  allocated_storage     = 100
  max_allocated_storage = 1000
  storage_type          = "gp2"
  storage_encrypted     = true
  
  db_name  = "kargo_dsp"
  username = "postgres"
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "kargo-dsp-final-snapshot"
  
  tags = {
    Environment = "production"
    Application = "kargo-dsp-integration"
  }
}
```

### Google Cloud Platform

#### Cloud Run Configuration
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: kargo-dsp-integration
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/minScale: "1"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 80
      containers:
      - image: gcr.io/project-id/kargo-dsp-integration:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            cpu: 1000m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
        env:
        - name: ENVIRONMENT
          value: production
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: kargo-dsp-secrets
              key: secret-key
```

### Azure Deployment

#### Container Instances
```json
{
  "apiVersion": "2018-10-01",
  "type": "Microsoft.ContainerInstance/containerGroups",
  "name": "kargo-dsp-integration",
  "location": "East US",
  "properties": {
    "containers": [
      {
        "name": "app",
        "properties": {
          "image": "youracr.azurecr.io/kargo-dsp-integration:latest",
          "resources": {
            "requests": {
              "cpu": 1,
              "memoryInGb": 2
            }
          },
          "ports": [
            {
              "port": 8000,
              "protocol": "TCP"
            }
          ],
          "environmentVariables": [
            {
              "name": "ENVIRONMENT",
              "value": "production"
            }
          ]
        }
      }
    ],
    "osType": "Linux",
    "restartPolicy": "Always"
  }
}
```

## Monitoring and Observability

### Application Performance Monitoring

#### Prometheus Metrics
- Custom business metrics
- HTTP request metrics
- Database operation metrics
- External API call metrics

#### Health Check Endpoints
- `/health/live` - Liveness probe
- `/health/ready` - Readiness probe
- `/health/detailed` - Comprehensive status
- `/health/metrics` - Prometheus metrics

#### Logging Strategy
- Structured JSON logging
- Correlation ID tracking
- Log aggregation (ELK, Fluentd, etc.)
- Log retention policies

### Infrastructure Monitoring

#### System Metrics
- CPU utilization
- Memory usage
- Disk I/O
- Network performance
- Container metrics

#### Database Monitoring
- Connection pool usage
- Query performance
- Replication lag (if applicable)
- Storage utilization

## Security Configuration

### Network Security

#### Firewall Rules
```bash
# Application servers (8000)
iptables -A INPUT -p tcp --dport 8000 -s load_balancer_ip -j ACCEPT

# Database (5432) - Internal only
iptables -A INPUT -p tcp --dport 5432 -s app_server_network -j ACCEPT

# Redis (6379) - Internal only
iptables -A INPUT -p tcp --dport 6379 -s app_server_network -j ACCEPT

# SSH (22) - Admin access only
iptables -A INPUT -p tcp --dport 22 -s admin_network -j ACCEPT
```

#### Security Groups (AWS Example)
```terraform
resource "aws_security_group" "app" {
  name = "kargo-dsp-app"
  
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]  # Load balancer subnet
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "db" {
  name = "kargo-dsp-db"
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}
```

### Secrets Management

#### Environment Variables
```bash
# Use secrets management systems
SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id kargo-dsp/secret-key --query SecretString --output text)
DATABASE_PASSWORD=$(aws secretsmanager get-secret-value --secret-id kargo-dsp/db-password --query SecretString --output text)
```

#### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: kargo-dsp-secrets
type: Opaque
data:
  secret-key: <base64-encoded-secret>
  db-password: <base64-encoded-password>
```

## Backup and Disaster Recovery

### Database Backups

#### Automated Backups
```bash
#!/bin/bash
# Daily backup script
BACKUP_DIR="/backups/kargo-dsp"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/kargo_dsp_$DATE.sql"

# Create backup
pg_dump -h $DB_HOST -U $DB_USER -d kargo_dsp > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Upload to S3 (or other storage)
aws s3 cp $BACKUP_FILE.gz s3://kargo-dsp-backups/daily/

# Clean old backups (keep last 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

#### Point-in-Time Recovery
- Enable WAL archiving
- Configure continuous backup
- Test recovery procedures regularly

### Application Backups
- Container images in registry
- Configuration files
- SSL certificates
- Application data

## Scaling Strategies

### Horizontal Scaling

#### Auto-scaling Configuration
```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: kargo-dsp-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: kargo-dsp-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Load Balancer Configuration
```nginx
upstream kargo_dsp_backend {
    least_conn;
    server app1:8000 max_fails=3 fail_timeout=30s;
    server app2:8000 max_fails=3 fail_timeout=30s;
    server app3:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://kargo_dsp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Health check
        proxy_next_upstream error timeout http_500 http_502 http_503;
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### Vertical Scaling
- Monitor resource utilization
- Adjust container limits
- Database instance sizing
- Cache memory allocation

## Performance Optimization

### Application Tuning
- Connection pool optimization
- Async operation tuning
- Cache strategy optimization
- Query optimization

### Infrastructure Tuning
- CPU and memory allocation
- Network bandwidth
- Storage IOPS
- Load balancer configuration

## Compliance and Governance

### Data Protection
- Encryption at rest and in transit
- Data retention policies
- Access controls
- Audit logging

### Regulatory Requirements
- GDPR compliance (if applicable)
- SOC 2 compliance
- Industry-specific requirements
- Data sovereignty

## Cost Optimization

### Resource Right-sizing
- Monitor actual usage
- Adjust instance types
- Optimize storage costs
- Review network charges

### Reserved Instances
- Use reserved instances for predictable workloads
- Spot instances for non-critical workloads
- Auto-scaling for variable workloads

## Maintenance Procedures

### Regular Tasks
- Security patching
- Dependency updates
- Performance monitoring
- Capacity planning

### Emergency Procedures
- Incident response
- Rollback procedures
- Data recovery
- Communication protocols

---

This infrastructure guide provides the foundation for deploying and managing the Kargo Amazon DSP Integration service. For specific implementation details, consult the deployment guide and your organization's infrastructure standards.