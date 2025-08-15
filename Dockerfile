FROM debian:bookworm-slim

# Set the working directory inside the container
WORKDIR /app

# Arguments needed at build-time, to be provided by Coolify
ARG DEBUG
ARG SECRET_KEY
ARG DATABASE_URL

# Install system dependencies needed by our app
RUN apt-get update && apt-get install -y \
    build-essential \
    curl wget \
    && rm -rf /var/lib/apt/lists/*

# Install uv, the fast Python package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy only the dependency definitions first to leverage Docker's layer caching
COPY pyproject.toml uv.lock .python-version ./

# Install Python dependencies for production
RUN uv sync --no-group dev --group prod

# Copy the rest of the application code into the container
COPY . .

# Collect the static files
RUN uv run --no-sync ./manage.py collectstatic --noinput

# Migrate the database
RUN uv run --no-sync ./manage.py migrate

# Expose the port Gunicorn will run on
EXPOSE 8000

# Run with gunicorn
CMD ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "config.wsgi:application"]