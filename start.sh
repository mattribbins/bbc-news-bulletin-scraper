#!/bin/bash

# BBC News Bulletin Scraper - Quick Start Script

set -e

echo "🎵 BBC News Bulletin Scraper - Quick Start"
echo "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs output

# Make sure config file exists
if [ ! -f "config/config.yaml" ]; then
    echo "❌ Configuration file not found at config/config.yaml"
    echo "Please ensure the configuration file exists before running."
    exit 1
fi

echo "✅ Configuration file found"

# Check if containers are already running
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Containers are already running. Stopping them first..."
    docker-compose down
fi

# Build and start the application
echo "🚀 Building and starting BBC News Bulletin Scraper..."
docker-compose up --build -d

# Wait a moment for the application to start
echo "⏳ Waiting for application to start..."
sleep 10

# Check if the application is healthy
echo "🏥 Checking application health..."
if curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Application is healthy and running!"
    echo ""
    echo "📊 Health check: http://localhost:8080/health"
    echo "📈 Status: http://localhost:8080/status"
    echo "📉 Metrics: http://localhost:8080/metrics"
    echo ""
    echo "📋 To view logs: docker-compose logs -f"
    echo "🛑 To stop: docker-compose down"
    echo ""
    echo "✨ Setup complete! The scraper will automatically download bulletins according to your schedule."
else
    echo "⚠️  Application may not be fully ready yet. Check logs with:"
    echo "   docker-compose logs -f"
    echo ""
    echo "The application should be available at http://localhost:8080/health in a few moments."
fi

echo ""
echo "🎉 BBC News Bulletin Scraper is now running!"