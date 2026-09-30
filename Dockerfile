FROM python:3.12-alpine

LABEL maintainer="wade <wade67168@gmail.com>"
LABEL description="Monitor Google/YouTube IP region and send alerts on changes"

WORKDIR /app

# Copy source code and installation configuration
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install directly using pip (zero external dependencies needed)
RUN pip install --no-cache-dir .

# Create persistent state directory
RUN mkdir -p /var/tmp

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    DAEMON_MODE=true \
    CHECK_INTERVAL=3600 \
    INTERVAL=3600

# Start in daemon mode by default
CMD ["check-google-region", "--daemon"]
