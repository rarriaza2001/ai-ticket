# ECS deployment assumptions (Phase 2+)

This folder intentionally avoids checked-in Terraform/CDK. The following assumptions guide production layout:

## Services

- **`api-service`**: one ECS service behind an **Application Load Balancer**. Health checks hit `GET /health` (liveness) and `GET /ready` (readiness). Scale on request rate / latency.
- **`ai-worker`**: one ECS **service without a load balancer**. Tasks scale on **queue depth** (SQS `ApproximateNumberOfMessagesVisible`) or custom metrics. No inbound HTTP required.

## Data dependencies

- **Amazon RDS for PostgreSQL** with the **pgvector** extension enabled to match local dev semantics.
- **Amazon ElastiCache (Redis)** for ephemeral cache only. Loss of Redis must not destroy authoritative ticket data.

## Secrets and configuration

- Database URLs, Redis URLs, and future vendor keys (for example OpenAI) should be injected via **AWS Secrets Manager** or **SSM Parameter Store**, referenced from the task definition as secrets (not baked into images).

## Networking

- API tasks in **private subnets** with egress via NAT for vendor APIs (Phase 2).
- Worker tasks share the same data-plane access to RDS/ElastiCache security groups as the API, with least-privilege security group rules.

## Local vs production

Docker Compose runs Postgres, Redis, API, and worker together for developer ergonomics. Production separates data planes (RDS/ElastiCache) from compute (ECS).
