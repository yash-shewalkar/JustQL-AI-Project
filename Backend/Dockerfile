# 1. Use official Python slim image. 
# Slim is smaller than the full image but contains necessary C libraries for ML packages.
FROM python:3.11-slim-bookworm AS builder

# 2. Set environment variables for Python
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures stdout and stderr are printed directly to the terminal (useful for logging)
ENV PYTHONUNBUFFERED=1
# Set default port
ENV PORT=5000

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Install system dependencies
# build-essential is often required for compiling certain Python ML/Data packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .

# 6. Install dependencies
# We also install gunicorn here for the production server
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# 7. Copy the rest of your application code
COPY . .

# 8. Create a non-root user for security best practices
# Running containers as root is a major security risk
RUN useradd -m myappuser && chown -R myappuser:myappuser /app
USER myappuser

# 9. Expose the port the app runs on
EXPOSE $PORT

# 10. Command to run the application using Gunicorn
# --workers 3: Usually set to (2 * CPU cores) + 1
# --timeout 120: Gives LLM/RAG calls up to 2 minutes to respond before dropping the connection
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "app:app"]
