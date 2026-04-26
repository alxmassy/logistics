# =============================================================================
# Shared Python Services — Docker Image
#
# Used by: ingestion-api, context-assembly
# These services share the monorepo import structure
# (services.*, shared.*) so they use a single base image.
#
# Build context: repo root
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install the project and its dependencies
COPY pyproject.toml .
COPY README.md .
COPY services/ services/
COPY shared/ shared/

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

# Default CMD is the ingestion API — override in docker-compose per service
CMD ["python", "-m", "services.ingestion", "serve"]
