# Infrastructure Layout

This directory contains container and deployment assets for cross-service infrastructure.

Current structure:

- `infra/database/` — PostgreSQL container build and initialization assets.

Recommended future additions:

- `infra/cache/` (e.g., Redis)
- `infra/message-broker/` (e.g., RabbitMQ, Kafka)
- `infra/observability/` (Prometheus, Grafana, Loki, etc.)
