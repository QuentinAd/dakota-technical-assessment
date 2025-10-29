.PHONY: setup run test report clean help

# Default target
.DEFAULT_GOAL := help

# Load environment variables from .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

help: ## Show this help message
	@echo "Dakota Analytics Energy Pipeline - Available Commands"
	@echo "======================================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Setup environment and install dependencies
	@echo "Setting up environment..."
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env file from template"; fi
	@echo "Installing Python dependencies with uv..."
	uv sync --all-extras
	@echo "Building Docker containers..."
	docker-compose build
	@echo "Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env and add your EIA_API_KEY"
	@echo "  2. Run 'make run' to start all services"

run: ## Start all services (PostgreSQL, FastAPI, Dagster)
	@echo "Starting all services..."
	docker-compose up -d
	@echo ""
	@echo "Services starting... please wait for health checks"
	@sleep 10
	@echo ""
	@echo "Services running:"
	@echo "PostgreSQL:     localhost:5432"
	@echo "Enrichment API: http://localhost:8000"
	@echo "Dagster UI:     http://localhost:3000"
	@echo ""
	@echo "Check status with: docker-compose ps"

test: ## Run all tests (unit + integration + dbt)
	@echo "Running Python unit tests..."
	uv run pytest tests/unit/ -v --cov=. --cov-report=term-missing
	@echo ""
	@echo "Running integration tests (requires database)..."
	uv run pytest tests/integration/ -v
	@echo ""
	@echo "Running dbt models..."
	cd dbt && POSTGRES_DB=$(POSTGRES_DB) POSTGRES_USER=$(POSTGRES_USER) POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) uv run dbt run
	@echo ""
	@echo "Running dbt tests..."
	cd dbt && POSTGRES_DB=$(POSTGRES_DB) POSTGRES_USER=$(POSTGRES_USER) POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) uv run dbt test
	@echo ""
	@echo "All tests passed!"

test-unit: ## Run only unit tests
	@echo "Running unit tests..."
	@set -a; . ./.env; set +a; uv run pytest tests/unit/ -v

test-integration: ## Run only integration tests
	@echo "Running integration tests..."
	@set -a; . ./.env; set +a; uv run pytest tests/integration/ -v

test-e2e: ## Run end-to-end pipeline tests
	@echo "Running end-to-end tests..."
	@set -a; . ./.env; set +a; uv run pytest tests/e2e/ -v

test-coverage: ## Run tests with detailed coverage report
	@echo "Running tests with coverage..."
	@set -a; . ./.env; set +a; uv run pytest --cov=. --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated: htmlcov/index.html"

lint: ## Run code quality checks
	@echo "Running ruff checks..."
	uv run ruff check .
	@echo ""
	@echo "Running ruff format check..."
	uv run ruff format --check .
	@echo ""
	@echo "Code quality checks passed!"

format: ## Format code with ruff
	@echo "Formatting code..."
	uv run ruff format .
	@echo "Code formatted!"

dbt-run: ## Run dbt models
	@echo "Running dbt models..."
	cd dbt && POSTGRES_DB=$(POSTGRES_DB) POSTGRES_USER=$(POSTGRES_USER) POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) uv run dbt run
	@echo "dbt models complete!"

dbt-test: dbt-run ## Run dbt tests (runs models first)
	@echo "Running dbt tests..."
	cd dbt && POSTGRES_DB=$(POSTGRES_DB) POSTGRES_USER=$(POSTGRES_USER) POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) uv run dbt test
	@echo "dbt tests passed!"

dbt-docs: ## Generate and serve dbt documentation
	@echo "Generating dbt documentation..."
	cd dbt && POSTGRES_DB=$(POSTGRES_DB) POSTGRES_USER=$(POSTGRES_USER) POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) uv run dbt docs generate
	@echo "Serving documentation on http://localhost:8080"
	cd dbt && POSTGRES_DB=$(POSTGRES_DB) POSTGRES_USER=$(POSTGRES_USER) POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) uv run dbt docs serve

report: ## Generate energy analytics reports (runs full pipeline)
	@echo "Running full pipeline: EIA ingestion -> Enrichment -> dbt -> Quality checks -> Reports"
	@echo ""
	docker exec dakota_dagster bash -c "cd /opt/dagster/app && uv run dagster asset materialize --select '*' -m dagster_project"
	@echo ""
	@echo "Pipeline complete! Check reports/output/ for generated notebooks and PDFs"
	@echo "View run details at: http://localhost:3000"

logs: ## View Docker service logs
	docker-compose logs -f

logs-dagster: ## View Dagster logs
	docker-compose logs -f dagster

logs-postgres: ## View PostgreSQL logs
	docker-compose logs -f postgres

logs-api: ## View Enrichment API logs
	docker-compose logs -f enrichment-api

ps: ## Show status of all services
	docker-compose ps

restart: ## Restart all services
	@echo "Restarting services..."
	docker-compose restart
	@echo "Services restarted!"

stop: ## Stop all services
	@echo "Stopping services..."
	docker-compose stop
	@echo "Services stopped!"

clean: ## Clean up all resources (containers, volumes, cache)
	@echo "Cleaning up..."
	docker-compose down -v
	@if [ -d .venv ]; then rm -rf .venv; fi
	@if [ -d .pytest_cache ]; then rm -rf .pytest_cache; fi
	@if [ -d htmlcov ]; then rm -rf htmlcov; fi
	@if [ -f .coverage ]; then rm -f .coverage; fi
	@if [ -d .ruff_cache ]; then rm -rf .ruff_cache; fi
	@echo "Cleanup complete!"

clean-reports: ## Clean generated reports
	@echo "Cleaning reports..."
	@if [ -d reports/output ]; then rm -f reports/output/*.ipynb; fi
	@if [ -d reports/output ]; then rm -f reports/output/*.pdf; fi
	@echo "Reports cleaned!"

db-shell: ## Connect to PostgreSQL shell
	docker exec -it dakota_postgres psql -U dakota_user -d energy_analytics

db-reset: ## Reset database (WARNING: Deletes all data)
	@echo "WARNING: This will delete all data!"
	@read -p "Press enter to continue..."
	docker-compose down -v
	docker-compose up -d postgres
	@echo "Database reset complete!"

verify: ## Run full verification (clean build + tests)
	@echo "Running full verification..."
	@echo ""
	@echo "Step 1: Clean environment"
	make clean
	@echo ""
	@echo "Step 2: Setup"
	make setup
	@echo ""
	@echo "Step 3: Start services"
	make run
	@sleep 30
	@echo ""
	@echo "Step 4: Run tests"
	make test
	@echo ""
	@echo "Full verification complete!"

status: ## Show comprehensive system status
	@echo "Dakota Analytics Energy Pipeline - System Status"
	@echo "================================================"
	@echo ""
	@echo "Docker Services:"
	@docker-compose ps
	@echo ""
	@echo "Python Environment:"
	@uv run python --version
	@echo ""
	@echo "Database Status:"
	@set -a; . ./.env; set +a; docker exec dakota_postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "SELECT current_database(), current_user, version();" 2>/dev/null || echo "Database not accessible"
	@echo ""
	@echo "Recent Reports:"
	@if [ -d reports/output ] && [ -n "$$(ls -A reports/output/*.pdf 2>/dev/null)" ]; then ls -1t reports/output/*.pdf | wc -l | xargs echo "reports found:"; else echo "No reports generated yet"; fi
