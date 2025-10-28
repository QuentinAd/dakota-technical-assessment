"""Shared pytest fixtures for all tests."""

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Load environment variables from .env file
load_dotenv()

# Add orchestration directory to Python path for dagster_project imports
orchestration_dir = Path(__file__).parent.parent / "orchestration"
sys.path.insert(0, str(orchestration_dir))


@pytest.fixture(scope="session")
def db_connection_string() -> str:
    """Provide database connection string from environment variables."""
    db_name = os.getenv("POSTGRES_DB", "energy_analytics")
    db_user = os.getenv("POSTGRES_USER", "dakota_user")
    db_password = os.getenv("POSTGRES_PASSWORD", "change_me")
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


@pytest.fixture(scope="session")
def db_engine(db_connection_string: str) -> Generator[Engine, None, None]:
    """Create a database engine for the test session."""
    engine = create_engine(db_connection_string)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Create a database session for each test function."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
