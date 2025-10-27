# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
This project uses `uv` for dependency management:
```bash
# Install dependencies
uv pip install -r requirements.txt

# Add new dependency
uv pip install <package>

# Generate requirements
uv pip freeze > requirements.txt
```

### dbt Operations
```bash
# From dbt/ directory:
dbt debug          # Test connection
dbt deps           # Install dependencies
dbt run            # Run all models
dbt test           # Run data quality tests
dbt docs generate  # Generate documentation
dbt docs serve     # Serve docs locally

# Run specific models
dbt run --select staging.*
dbt run --select +model_name  # Include upstream dependencies
dbt run --select model_name+  # Include downstream dependencies

# Incremental models
dbt run --full-refresh  # Force full rebuild
```

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it dakota_postgres psql -U dakota_user -d energy_analytics

# Run initialization scripts
docker exec -i dakota_postgres psql -U dakota_user -d energy_analytics < database/init/schema.sql
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

Each component should include tests:
- **API**: FastAPI TestClient for endpoint testing
- **Ingestion**: Mock API responses, test retry logic and error handling
- **dbt**: Data quality tests in schema.yml, custom tests for business logic
- **Orchestration**: Test DAG/workflow structure, sensor behavior
- **Database**: Schema validation, constraint testing

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
- Makefile with: `setup`, `run`, `test`, `report`, `clean` targets
- All six components fully implemented
- Documentation complete in `/docs/`
- Tests written and passing
- Clean environment test: `make clean && make setup && make run` succeeds
- No sensitive data committed
- Repository is public

## Common Pitfalls

- **EIA API rate limits**: Implement proper backoff and caching
- **dbt profile configuration**: Ensure correct connection strings for containerized postgres
- **Container startup ordering**: Use healthchecks and `depends_on` with conditions
- **Volume permissions**: May need to adjust for database init scripts
- **Network isolation**: Services must communicate via docker network names, not localhost
- **Incremental models**: Handle late-arriving data and full-refresh scenarios

## Assessment Evaluation Criteria

- Technical Excellence (40%): Code quality, error handling, testing, performance
- Architecture & Design (30%): Tool choices, database design, scalability, separation of concerns
- Documentation (20%): Clarity, completeness, decision rationale
- Innovation (10%): Creative solutions, best practices, additional value

Focus on demonstrating production-ready practices and clear architectural thinking over feature quantity.
