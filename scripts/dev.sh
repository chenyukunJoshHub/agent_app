#!/bin/bash

# Multi-Tool AI Agent Development Environment Setup

set -e

echo "🚀 Setting up Multi-Tool AI Agent development environment..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✅ .env created${NC}"
    echo -e "${YELLOW}⚠️  Please edit .env and add your API keys${NC}"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi

# Pull latest images
echo -e "${YELLOW}📦 Pulling latest Docker images...${NC}"
docker-compose pull

# Build and start services
echo -e "${YELLOW}🔨 Building and starting services...${NC}"
docker-compose up -d --build

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to be healthy...${NC}"

# Wait for PostgreSQL
timeout=60
while [ $timeout -gt 0 ]; do
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
        break
    fi
    sleep 2
    ((timeout-=2))
done

if [ $timeout -eq 0 ]; then
    echo -e "${RED}❌ PostgreSQL failed to start${NC}"
    docker-compose logs postgres
    exit 1
fi

# Wait for Backend
timeout=60
while [ $timeout -gt 0 ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is ready${NC}"
        break
    fi
    sleep 2
    ((timeout-=2))
done

if [ $timeout -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Backend health check timeout${NC}"
fi

# Wait for Frontend
timeout=60
while [ $timeout -gt 0 ]; do
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend is ready${NC}"
        break
    fi
    sleep 2
    ((timeout-=2))
done

if [ $timeout -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Frontend health check timeout${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Development environment is ready!${NC}"
echo ""
echo "📊 Service URLs:"
echo "  - Frontend:    http://localhost:3000"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs:    http://localhost:8000/api/docs"
echo "  - PostgreSQL:  localhost:5432"
echo "  - Ollama:      http://localhost:11434"
echo ""
echo "📝 Useful commands:"
echo "  - View logs:        docker-compose logs -f [service]"
echo "  - Stop services:    docker-compose down"
echo "  - Restart service:  docker-compose restart [service]"
echo "  - Run backend tests: docker-compose exec backend pytest"
echo ""
