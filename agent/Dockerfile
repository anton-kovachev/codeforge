FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

#Version 1
# Configure UV for container environment
ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1

COPY . .
# Install from pyproject.toml directory
RUN uname -m && python -c "import platform; print(platform.machine())"
RUN UV_HTTP_TIMEOUT=300 uv pip install .

RUN UV_HTTP_TIMEOUT=300 uv pip install aws-opentelemetry-distro>=0.10.1

# Set AWS region environment variable
ARG AWS_REGION=eu-north-1
ENV AWS_REGION=${AWS_REGION}
ENV AWS_DEFAULT_REGION=${AWS_REGION}

# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080
EXPOSE 8000

# Copy entire project (respecting .dockerignore)
COPY . .

# Use the full module path
CMD ["opentelemetry-instrument", "python", "-m", "agent"]
