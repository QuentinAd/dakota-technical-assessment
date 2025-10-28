# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY PRACTICES

**CRITICAL: This project enforces strict Test-Driven Development (TDD)**
- **NEVER write implementation code before writing tests**
- **ALWAYS write failing tests first, then implement**
- Minimum 80% code coverage required
- Always run `uv run ruff check --fix` and `ruff lint` and `uv run ruff format` in the refactor phase ensure highest code quality standards

**IMPORTANT: This project uses `uv` for dependency management**
- **ALWAYS use `uv add` to add dependencies** (auto-updates pyproject.toml)
- **ALWAYS use `uv run` to execute commands** (no manual venv activation needed)
- **NEVER manually edit pyproject.toml dependencies**
- **ALWAYS commit both pyproject.toml and uv.lock together**
- See [UV_SETUP_GUIDE.md](UV_SETUP_GUIDE.md) for complete guide

## Project Overview

This is a Dakota Analytics technical assessment for building an end-to-end data pipeline. The project demonstrates production-ready data engineering practices including data ingestion, transformation, orchestration, and reporting for energy analytics use cases.

## Core Architecture

The system consists of six interconnected components:

1. **FastAPI Service** ([api/](api/)) - Synthetic data generation service for enrichment
2. **Data Ingestion** ([ingestion/](ingestion/)) - Clients for EIA API and FastAPI service
3. **Orchestration** ([orchestration/](orchestration/)) - Workflow management (Dagster)
4. **Database** ([database/](database/)) - PostgreSQL with raw and transformed schemas
5. **dbt Transformations** ([dbt/](dbt/)) - Layered transformation models
6. **Reports** ([reports/](reports/)) - Automated report generation

### Data Flow

```
External API (EIA) ──┐
                     ├──> Ingestion ──> PostgreSQL (raw) ──> dbt ──> PostgreSQL (transformed) ──> Reports
FastAPI Service ─────┘                     ▲                   ▲
                                          │                   │
                                    Orchestrator manages entire pipeline
```

All services are containerized and orchestrated via Docker Compose. The orchestrator coordinates daily batch ingestion, frequent enrichment updates, dbt runs, quality checks, and report generation.

## Development Commands

### Environment Setup
```bash
# Create .env from template
cp .env.example .env

# Start all services
docker-compose up -d

# Build all containers
docker-compose build

# Stop services
docker-compose down

# Clean volumes (reset database)
docker-compose down -v
```

### Python Dependency Management
This project uses `uv` for dependency management. See [UV_SETUP_GUIDE.md](UV_SETUP_GUIDE.md) for detailed setup instructions.

**IMPORTANT**: All development must follow these uv best practices:

```bash
# Initial setup - sync all dependencies from pyproject.toml
uv sync --all-extras

# Add runtime dependencies (automatically updates pyproject.toml)
uv add <package>

# Add dev dependencies (automatically updates pyproject.toml)
uv add --dev <package>

# Remove dependencies (automatically updates pyproject.toml)
uv remove <package>

# Run commands without activating venv
uv run python script.py
uv run pytest
uv run ruff check .
```

**Dependency Management Rules**:
- NEVER manually edit the `[project.dependencies]` or `[project.optional-dependencies]` sections
- ALWAYS use `uv add` or `uv add --dev` to add new dependencies
- ALWAYS commit both `pyproject.toml` and `uv.lock` together
- Run `uv sync --all-extras` after pulling changes that modify dependencies
- Use `uv add <package>` during development, which automatically updates pyproject.toml

### dbt Operations
```bash
# From dbt/ directory (use uv run for consistency):
uv run dbt debug          # Test connection
uv run dbt deps           # Install dependencies
uv run dbt run            # Run all models
uv run dbt test           # Run data quality tests
uv run dbt docs generate  # Generate documentation
uv run dbt docs serve     # Serve docs locally

# Run specific models
uv run dbt run --select staging.*
uv run dbt run --select +model_name  # Include upstream dependencies
uv run dbt run --select model_name+  # Include downstream dependencies

# Incremental models
uv run dbt run --full-refresh  # Force full rebuild
```

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it dakota_postgres psql -U dakota_user -d energy_analytics

# Run initialization scripts
docker exec -i dakota_postgres psql -U dakota_user -d energy_analytics < database/init/schema.sql
```

## Development Workflow

### TDD Workflow with uv

When implementing any new feature, follow this exact workflow:

**Step 1: Write the test first**
```bash
# Create test file (if it doesn't exist)
touch tests/unit/test_new_feature.py

# Write failing test using pytest
# Example: tests/unit/test_api.py
```

**Step 2: Identify required dependencies**
```python
# If your test needs a new library, add it BEFORE running tests
# Example: testing requires httpx
```

```bash
# Add the dependency using uv (updates pyproject.toml automatically)
uv add --dev httpx  # for dev/test dependencies
uv add requests     # for runtime dependencies
```

**Step 3: Run the test and verify it fails**
```bash
uv run pytest tests/unit/test_new_feature.py -v
# Should fail with clear reason
```

**Step 4: Implement the minimal code**
```python
# Write just enough code to pass the test
# Example: api/endpoints.py
```

**Step 5: Run tests again**
```bash
# Run the specific test
uv run pytest tests/unit/test_new_feature.py -v

# Run all tests to ensure no regression
uv run pytest

# Check coverage
uv run pytest --cov=. --cov-report=term-missing
```

**Step 6: Refactor if needed**
```bash
# Clean up code, run tests after each change
uv run pytest

# Format and lint
uv run ruff check . --fix
uv run ruff format .
```

**Step 7: Commit with both pyproject.toml and uv.lock**
```bash
git add pyproject.toml uv.lock tests/ <implementation_files>
git commit -m "feat: add new feature with tests"
```

### Adding Dependencies During Development

**Runtime Dependencies** (needed by the application):
```bash
uv add fastapi uvicorn sqlalchemy psycopg2-binary httpx pydantic-settings
```

**Development Dependencies** (testing, linting, formatting):
```bash
uv add --dev pytest pytest-cov pytest-asyncio pytest-mock ruff black mypy
```

**Always verify changes**:
```bash
# Check that pyproject.toml was updated
git diff pyproject.toml

# Ensure uv.lock is updated
git diff uv.lock

# Verify installation
uv run python -c "import <new_package>"
```

## Key Technical Decisions

### Database Schema Strategy
- **Raw Schema**: Stores ingested data unchanged with metadata (ingestion_timestamp, source)
- **Staging/Intermediate/Marts**: Transformed data organized by architecture pattern chosen
- **Time-series considerations**: Partitioning, indexing on timestamp columns for query performance

### dbt Model Organization
Models should be organized in a layered architecture (medallion):
- Document the chosen pattern and rationale in `docs/decisions.md`
- Use incremental models for large time-series data
- Include data quality tests (not_null, unique, relationships, accepted_values)
- Document all models in schema.yml files

### Orchestration Patterns
The orchestrator must coordinate:
- **Daily batch**: EIA API ingestion (rate limits apply)
- **Frequent updates**: FastAPI enrichment service (configurable frequency)
- **dbt execution**: Triggered after successful ingestion
- **Data quality**: Validation between pipeline stages
- **Report generation**: Final step after transformations complete
- **Error handling**: Retries with exponential backoff, alerts on failure

### API Design Principles
FastAPI service should:
- Generate synthetic data that meaningfully enriches energy analytics
- Include Pydantic models for request/response validation
- Provide `/health` endpoint for orchestrator checks
- Auto-generate OpenAPI documentation at `/docs`
- Handle errors gracefully with appropriate HTTP status codes

## Testing Requirements

**MANDATORY: Test-Driven Development (TDD)**

This project follows strict TDD practices. All code development MUST follow this workflow:

1. **Write the test first**: Before implementing any feature or fixing any bug, write a failing test
2. **Run the test**: Verify it fails for the right reason (`uv run pytest`)
3. **Implement minimal code**: Write just enough code to make the test pass
4. **Run tests again**: Ensure the test passes (`uv run pytest`)
5. **Refactor**: Clean up code while keeping tests green
6. **Repeat**: Move to the next test

**Test Coverage Requirements**:
- Minimum 80% code coverage for all Python modules
- 100% coverage for critical paths (API endpoints, data transformations, error handling)
- Run coverage reports: `uv run pytest --cov=. --cov-report=html --cov-report=term`

**Component-Specific Testing**:
- **API**: FastAPI TestClient for endpoint testing, test all success and error paths
- **Ingestion**: Mock API responses, test retry logic and error handling, test rate limiting
- **dbt**: Data quality tests in schema.yml, custom tests for business logic
- **Orchestration**: Test DAG/workflow structure, sensor behavior, error recovery
- **Database**: Schema validation, constraint testing, migration testing

**Testing Commands**:
```bash
# Run all tests with coverage
uv run pytest --cov=. --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_api.py

# Run tests matching pattern
uv run pytest -k "test_ingestion"

# Run with verbose output
uv run pytest -v

# Watch mode for TDD (requires pytest-watch)
uv run ptw
```

**Test Organization**:
```
tests/
├── unit/           # Unit tests for individual functions/classes
├── integration/    # Tests that involve multiple components
├── e2e/           # End-to-end pipeline tests
├── conftest.py    # Shared fixtures
└── __init__.py
```

**No Code Without Tests**: Pull requests without corresponding tests will be rejected

## Environment Variables

Required in `.env`:
```
POSTGRES_DB=energy_analytics
POSTGRES_USER=dakota_user
POSTGRES_PASSWORD=<secure_password>
EIA_API_KEY=<your_eia_api_key>
```

Additional variables depend on implementation choices (orchestrator configs, API service ports, etc.)

## Docker Compose Structure

Services communicate via `dakota_network` bridge network. The postgres service includes:
- Health checks for dependency management
- Volume mounting for init scripts at `/docker-entrypoint-initdb.d`
- Persistent data storage via named volume

Add services for:
- FastAPI app (depends on postgres)
- Orchestrator (depends on postgres, api)
- dbt runner (depends on postgres)
- Optional: Jupyter for notebook reports

## Documentation Standards

Maintain documentation in `docs/`:
- **architecture.md**: System design, technology choices, data flow, scalability considerations
- **decisions.md**: Key technical decisions, trade-offs, alternatives, rationale
- **er_diagram.png**: Database schema visualization

Update README.md with:
- Setup instructions specific to your implementation
- How to run the complete pipeline
- How to access generated reports
- Troubleshooting common issues

## Submission Checklist

Before submitting, verify:
- **✅ TDD and Testing**:
  - All features have corresponding tests (written first)
  - Minimum 80% test coverage achieved: `uv run pytest --cov=. --cov-report=term`
  - All tests passing: `uv run pytest`
  - Test organization follows structure (unit/integration/e2e)

- **✅ Dependency Management**:
  - All dependencies added via `uv add` (not pip or manual edits)
  - Both `pyproject.toml` and `uv.lock` committed
  - `uv sync --all-extras` runs successfully
  - No requirements.txt files (uses pyproject.toml)

- **✅ Code Quality**:
  - Linting passes: `uv run ruff check .`
  - Formatting applied: `uv run ruff format .`
  - Type hints present on all functions
  - Docstrings for public APIs

- **✅ Core Requirements**:
  - Makefile with: `setup`, `run`, `test`, `report`, `clean` targets
  - All six components fully implemented
  - Documentation complete in `/docs/`
  - Clean environment test: `make clean && make setup && make run` succeeds

- **✅ Repository**:
  - No sensitive data committed (check .env.example vs .env)
  - `.gitignore` includes `.venv/`, `.env`, `*.pyc`, `__pycache__/`
  - Repository is public
  - README.md updated with setup and usage instructions

## Common Pitfalls

- **Not following TDD**: Writing implementation before tests - THIS WILL BE REJECTED
- **Using pip instead of uv**: Always use `uv add` not `pip install` or manually editing pyproject.toml
- **Forgetting uv run**: Use `uv run pytest` not just `pytest` for consistency
- **Not committing uv.lock**: Both pyproject.toml and uv.lock must be committed together
- **Missing test coverage**: Minimum 80% coverage required, 100% for critical paths
- **EIA API rate limits**: Implement proper backoff and caching
- **dbt profile configuration**: Ensure correct connection strings for containerized postgres
- **Container startup ordering**: Use healthchecks and `depends_on` with conditions
- **Volume permissions**: May need to adjust for database init scripts
- **Network isolation**: Services must communicate via docker network names, not localhost
- **Incremental models**: Handle late-arriving data and full-refresh scenarios

## Assessment Evaluation Criteria

- **Technical Excellence (40%)**:
  - **Test coverage and TDD adherence** (critical - can result in rejection if missing)
  - Code quality and maintainability
  - Error handling and resilience
  - Performance optimization

- **Architecture & Design (30%)**:
  - Tool choices and justification
  - Database design and schema organization
  - Scalability considerations
  - Separation of concerns

- **Documentation (20%)**:
  - Code documentation and type hints
  - Architecture documentation clarity
  - Decision rationale and trade-offs
  - Setup and usage instructions

- **Innovation (10%)**:
  - Creative solutions to challenges
  - Best practices implementation
  - Additional value and polish

**Focus**: Demonstrate production-ready practices with TDD, comprehensive testing, and clear architectural thinking. Feature quantity is less important than code quality and test coverage.
