# IntelliTutor Flask Application Dockerfile
# Multi-stage build for optimized production image

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files AND README (required by pyproject.toml)
COPY pyproject.toml README.md ./

# Install dependencies only (not the package itself)
RUN uv pip install --system --no-cache -r pyproject.toml

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Copy and set entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Environment configuration
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Database configuration (overridden by docker-compose)
ENV PG_HOST=db
ENV PG_PORT=5432
ENV PG_DB=tutor_db
ENV PG_USER=tutor_user
ENV PG_PASSWORD=tutor_pass

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Use entrypoint for initialization
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "auth_app.py"]
