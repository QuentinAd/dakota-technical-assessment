# Setting up uv with Existing Project

This guide shows how to initialize `uv` in the existing Dakota Analytics project skeleton.

## Prerequisites

Install `uv` if you haven't already:

```bash
# macOS/Linux/Windows Git Bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows Powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

## Initializing the Project

The pyproject.toml was manually created to prevent creation of the default uv project structure.

### Initialize uv without creating a new project structure

```bash
# This will use the existing pyproject.toml and create a virtual environment
uv sync
```

This creates:
- `.venv/` - Virtual environment
- `uv.lock` - Lockfile with exact dependency versions

### Install with dev dependencies

```bash
# Sync with dev dependencies
uv sync --extra dev
```

## Recommended Usage

### Activating the virtual environment

```bash
# macOS/Linux
source .venv/bin/activate

# Windows on Git Bash
source .venv\\Scripts\\activate

# Windows Powershell
.venv\Scripts\activate
```

Or use `uv run` to run commands without activating:

```bash
# Run Python scripts
uv run python ingestion/eia_client.py

# Run pytest
uv run pytest

# Run ruff
uv run ruff check .
uv run ruff format .

# Run FastAPI
uv run uvicorn api.main:app --reload
```

### Adding new dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Example: Add a new library
uv add polars
uv add --dev black
```

### Removing dependencies

```bash
uv remove package-name
```

### Updating dependencies

```bash
# Update all dependencies
uv sync --upgrade

# Update a specific package
uv add package-name@latest
```

## Project Structure with uv

Your project should look like this after setup:

```
dakota-analytics/
├── .venv/                  # Virtual environment (gitignored)
├── pyproject.toml         # Project configuration
├── uv.lock               # Locked dependencies (commit this)
├──...
```

## Tips

### 1. Speed

`uv` is extremely fast. Dependency installation that takes minutes with pip takes seconds with uv.

### 2. Lockfile

The `uv.lock` file ensures reproducible builds. **Commit this to git**.

### 3. Python Version

`uv` can install Python versions for you:

```bash
# Install Python 3.13
uv python install 3.13

# Use a specific Python version
uv sync --python 3.13
```

### Scripts

Add custom scripts to pyproject.toml:

```toml
[project.scripts]
ingest = "ingestion.cli:main"
orchestrate = "orchestration.cli:main"
```

Then run with:

```bash
uv run ingest --source eia
```

### Pre-commit hooks

Set up pre-commit with ruff:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

## Common Commands Quick Reference

```bash
# Setup
uv sync                      # Install dependencies
uv sync --extra dev         # Include dev dependencies

# Run commands
uv run python script.py     # Run Python
uv run pytest              # Run tests
uv run ruff check .        # Lint code
uv run ruff format .       # Format code

# Manage dependencies
uv add package             # Add dependency
uv add --dev package       # Add dev dependency
uv remove package          # Remove dependency
uv sync --upgrade          # Update all dependencies

# Other
uv pip list               # List installed packages
uv pip freeze             # Show installed versions
uv tree                   # Show dependency tree
```

## Integration with Docker

You can use uv in Docker for faster builds:

```dockerfile
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Copy rest of the code
COPY . .

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0"]
```

## Troubleshooting

### Virtual environment not created

```bash
# Ensure you're in the project directory with pyproject.toml
ls pyproject.toml

# Try explicit sync
uv sync --no-cache
```

### Import errors

Make sure you're using `uv run` or have activated the virtual environment (see above).

Or:

```bash
uv run python script.py  # No activation needed
```

## Additional Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [uv GitHub Repository](https://github.com/astral-sh/uv)
- [Python Packaging Guide](https://packaging.python.org/)