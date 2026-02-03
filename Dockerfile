# Use an official Python image (no sudo needed on host)
FROM python:3.12.3-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Signal we are in Docker
ENV IN_DOCKER=1

# Set working directory inside container
WORKDIR /app

# Install ffmpeg (and clean up to keep image small)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
    
# Copy repository into container
COPY . /app

# Make sure your startup script is executable
RUN chmod +x ./startProduction.sh

# Expose the port your app listens on
EXPOSE 8000

# Start your application
CMD ["bash", "./startProduction.sh"]
