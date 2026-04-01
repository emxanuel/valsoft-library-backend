FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app


FROM base AS builder

# System packages required to build some Python dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

# Copy project metadata and source so uv can resolve the project
COPY pyproject.toml .
COPY . .

# Create a virtual environment and install project (and its deps) with uv
RUN uv venv /venv && uv sync


FROM base AS runtime

ENV PATH="/venv/bin:$PATH"

# Copy the virtualenv with all installed dependencies
COPY --from=builder /venv /venv

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
