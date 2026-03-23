# Multi-Tool AI Agent - Makefile
# Convenience commands for development and testing

.PHONY: help install-backend install-frontend install test-backend test-frontend test lint-backend lint-frontend clean

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "Installation:"
	@echo "  install-backend       - Install backend Python dependencies"
	@echo "  install-frontend      - Install frontend Node dependencies"
	@echo "  install               - Install both backend and frontend"
	@echo ""
	@echo "Testing (from project root):"
	@echo "  test-backend          - Run backend tests with coverage"
	@echo "  test-frontend         - Run frontend component tests"
	@echo "  test-frontend-e2e     - Run frontend E2E tests (Playwright)"
	@echo "  test-frontend-e2e-ui  - Run E2E tests with UI"
	@echo "  test                  - Run all tests"
	@echo ""
	@echo "Linting:"
	@echo "  lint-backend          - Lint backend code with ruff"
	@echo "  lint-frontend         - Lint frontend code with eslint"
	@echo "  lint                  - Lint all code"
	@echo ""
	@echo "Formatting:"
	@echo "  format-backend        - Format backend code with black"
	@echo "  format-frontend       - Format frontend code with prettier"
	@echo "  format                - Format all code"
	@echo ""
	@echo "Development:"
	@echo "  dev-backend           - Start backend development server"
	@echo "  dev-frontend          - Start frontend development server"
	@echo "  dev                   - Start backend (run frontend in separate terminal)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up             - Start Docker services"
	@echo "  docker-down           - Stop Docker services"
	@echo "  docker-logs           - Follow Docker logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean                 - Remove cache and build artifacts"

# Installation
install-backend:
	@echo "Installing backend dependencies..."
	cd backend && if [ -f "requirements.txt" ]; then \
		pip install -r requirements.txt; \
	fi

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && if [ -f "package.json" ]; then \
		npm install; \
	fi

install: install-backend install-frontend
	@echo "Installation complete!"

# Testing
test-backend:
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

# 前端组件测试（Vitest）
test-frontend-components:
	@echo "Running frontend component tests..."
	cd frontend && npm test -- --coverage

# 前端 E2E 测试（Playwright）
test-frontend-e2e:
	@echo "Running frontend E2E tests..."
	cd frontend && npm run test:e2e

# 前端 E2E UI 模式
test-frontend-e2e-ui:
	@echo "Running frontend E2E tests (UI mode)..."
	cd frontend && npm run test:e2e:ui

# 所有前端测试
test-frontend: test-frontend-components
	@echo "Frontend tests complete!"

# 所有测试
test: test-backend test-frontend
	@echo "All tests complete!"

# Linting
lint-backend:
	@echo "Linting backend code..."
	cd backend && ruff check app/ tests/

lint-frontend:
	@echo "Linting frontend code..."
	cd frontend && npm run lint

lint: lint-backend lint-frontend
	@echo "Linting complete!"

# Formatting
format-backend:
	@echo "Formatting backend code..."
	cd backend && black app/ tests/

format-frontend:
	@echo "Formatting frontend code..."
	cd frontend && npm run format 2>/dev/null || echo "No format script found"

format: format-backend format-frontend
	@echo "Formatting complete!"

# Cleanup
clean:
	@echo "Cleaning cache and build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "Clean complete!"

# Docker
docker-up:
	@echo "Starting Docker services..."
	docker compose up -d

docker-down:
	@echo "Stopping Docker services..."
	docker compose down

docker-logs:
	@echo "Following Docker logs..."
	docker compose logs -f

# Development
dev-backend:
	@echo "Starting backend development server..."
	cd backend && uvicorn app.main:app --reload --log-level debug

dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

dev: dev-backend
	# Run in separate terminals for frontend
