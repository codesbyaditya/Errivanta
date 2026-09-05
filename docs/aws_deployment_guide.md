# ServiceWatch — AWS Production Deployment Blueprint

This document details the recommended cloud architecture and step-by-step roadmap for deploying **ServiceWatch** as a high-availability, multi-tenant SaaS platform on Amazon Web Services (AWS).

---

## 1. Cloud Architecture Overview

```mermaid
flowchart TD
    subgraph Edge["Edge & Delivery"]
        Route53["Route 53 DNS"] --> CF["CloudFront CDN"]
        CF --> S3["S3 (React SPA Build)"]
        Route53 --> ALB["Application Load Balancer (ALB)"]
    end

    subgraph VPC["Virtual Private Cloud (VPC) - Multi-AZ"]
        subgraph PublicSubnets["Public Subnets"]
            ALB
            NAT["NAT Gateway"]
        end

        subgraph PrivateAppSubnets["Private App Subnets (ECS Fargate)"]
            API["Monitoring API Service (Fargate Task)"]
            Worker["Monitoring Stream Worker (Fargate Task)"]
            PaySvc["Payment Service (Fargate Task)"]
            OrdSvc["Order Service (Fargate Task)"]
            UsrSvc["User Service (Fargate Task)"]
        end

        subgraph PrivateDataSubnets["Private Data Subnets"]
            RDS[("Amazon RDS PostgreSQL 16 (Multi-AZ)")]
            ElastiCache[("Amazon ElastiCache Redis 7 (Cluster)")]
        end
    end

    subgraph SecuritySecrets["Security & Operations"]
        SecretsMgr["AWS Secrets Manager<br/>(JWT Secret, DB Passwords)"]
        SES["Amazon SES<br/>(Transactional Incident Alerts)"]
        CloudWatch["CloudWatch Logs & Alarms"]
    end

    ALB --> API
    API --> RDS
    API --> ElastiCache
    Worker --> RDS
    Worker --> ElastiCache
    Worker --> SES
    PaySvc & OrdSvc & UsrSvc -- "Telemetry POST" --> ALB
```

---

## 2. Infrastructure Components

| Component | AWS Resource | Purpose |
| :--- | :--- | :--- |
| **Frontend** | **S3 + CloudFront** | Static React single-page application hosting with global edge caching and HTTPS. |
| **Ingress & TLS** | **Application Load Balancer (ALB)** | Terminates SSL (ACM certificate), distributes requests to API containers. |
| **Compute / Containers** | **Amazon ECS (AWS Fargate)** | Serverless Docker container hosting for `monitoring-api`, `worker`, and microservices. |
| **Database** | **Amazon RDS (PostgreSQL 16)** | Managed multi-AZ relational database for tenant organizations, events, and incidents. |
| **Metrics & Queue** | **Amazon ElastiCache (Redis 7)** | High-throughput in-memory datastore for telemetry counters, rolling metrics, and event queues. |
| **Secrets Management** | **AWS Secrets Manager** | Secure storage and rotation of `JWT_SECRET`, database passwords, and Slack webhooks. |
| **Email Alerting** | **Amazon Simple Email Service (SES)** | High-deliverability transactional email for critical incident notifications. |

---

## 3. Step-by-Step Deployment Roadmap

### Phase 1: Container Registry (ECR)
Create container repositories for each image:
```bash
aws ecr create-repository --repository-name servicewatch-monitoring-api
aws ecr create-repository --repository-name servicewatch-payment-service
aws ecr create-repository --repository-name servicewatch-order-service
aws ecr create-repository --repository-name servicewatch-user-service
```

Push Docker images:
```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag servicewatch-monitoring-api:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/servicewatch-monitoring-api:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/servicewatch-monitoring-api:latest
```

### Phase 2: Database & Redis Provisioning
1. Provision **RDS PostgreSQL** inside Private Data Subnets with Automated Backups and Multi-AZ enabled.
2. Provision **ElastiCache Redis** Cluster (1 primary + 1 replica in separate AZs).
3. Store connection strings in AWS Secrets Manager:
   ```json
   {
     "DATABASE_URL": "postgresql://sw_admin:PASSWORD@servicewatch-db.xxxx.us-east-1.rds.amazonaws.com:5432/servicewatch_prod",
     "REDIS_URL": "redis://servicewatch-cache.xxxx.us-east-1.cache.amazonaws.com:6379/0",
     "JWT_SECRET": "RANDOM_STRONG_GENERATED_SECRET"
   }
   ```

### Phase 3: ECS Fargate Task Definitions & Services
1. Create ECS Cluster: `servicewatch-production-cluster`.
2. Define Task Definitions referencing the ECR images and environment variables mapped from AWS Secrets Manager.
3. Attach ALB Target Groups:
   - Path `/api/*` and `/health` $\rightarrow$ `monitoring-api` Target Group (Port 8001).

### Phase 4: Frontend Deployment (S3 + CloudFront)
1. Build React dashboard:
   ```bash
   cd dashboard
   npm run build
   ```
2. Sync `dist/` directory to Amazon S3:
   ```bash
   aws s3 sync dist/ s3://servicewatch-dashboard-production --delete
   ```
3. Invalidate CloudFront distribution:
   ```bash
   aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*"
   ```

---

## 4. Cost Estimation (Production Baseline)

- **Fargate (2 vCPU, 4GB RAM total across tasks)**: ~$35/month
- **RDS PostgreSQL db.t4g.micro Multi-AZ**: ~$30/month
- **ElastiCache Redis cache.t4g.micro**: ~$15/month
- **ALB + CloudFront + Route 53**: ~$22/month
- **Total Estimated Cost**: **~$102/month**
