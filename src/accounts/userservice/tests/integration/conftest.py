"""
Test fixtures for UserService integration tests
"""

import os
import pytest
from testcontainers.postgres import PostgresContainer
from unittest.mock import patch, mock_open

from userservice.userservice import create_app

# Test constants
TEST_PASSWORD = "SecurePass123!"
TEST_TIMEZONE = "America/New_York"
TEST_ADDRESS = "123 Test Street"
TEST_STATE = "NY"
TEST_ZIP = "10001"
TEST_SSN = "123-45-6789"


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for testing."""
    with PostgresContainer("postgres:13", username="test", password="test", dbname="test") as postgres:
        # Wait for the container to be ready
        postgres.get_connection_url()
        yield postgres


@pytest.fixture
def test_keys():
    """Provide test JWT keys."""
    test_keys_dir = os.path.join(os.path.dirname(__file__), "fixtures", "test_keys")
    private_key_path = os.path.join(test_keys_dir, "test_private_key")
    public_key_path = os.path.join(test_keys_dir, "test_public_key")

    with open(private_key_path, "r") as f:
        private_key = f.read()
    with open(public_key_path, "r") as f:
        public_key = f.read()

    return {
        "private_key": private_key,
        "public_key": public_key,
        "private_key_path": private_key_path,
        "public_key_path": public_key_path,
    }


@pytest.fixture(autouse=True)
def clean_database(test_app):
    """Clean the database before each test."""
    # This fixture runs before each test automatically
    yield  # Run the test

    # Clean up after the test
    try:
        from userservice.db import UserDb
        import os

        db_url = os.environ.get("ACCOUNTS_DB_URI")
        if db_url:
            user_db = UserDb(db_url)
            with user_db.engine.connect() as conn:
                conn.execute(user_db.users_table.delete())
                conn.commit()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def test_app(postgres_container, test_keys):
    """Create a Flask test app with real database."""
    db_url = postgres_container.get_connection_url()

    # Mock the file reading for keys
    def mock_open_func(filename, mode="r"):
        if "private" in filename or filename == test_keys["private_key_path"]:
            return mock_open(read_data=test_keys["private_key"]).return_value
        elif "public" in filename or filename == test_keys["public_key_path"]:
            return mock_open(read_data=test_keys["public_key"]).return_value
        else:
            return open(filename, mode)

    # Mock environment variables
    env_vars = {
        "VERSION": "test-1.0.0",
        "TOKEN_EXPIRY_SECONDS": "3600",
        "PRIV_KEY_PATH": test_keys["private_key_path"],
        "PUB_KEY_PATH": test_keys["public_key_path"],
        "ENABLE_TRACING": "false",
        "ACCOUNTS_DB_URI": db_url,
    }

    with patch("os.environ", env_vars):
        with patch("builtins.open", side_effect=mock_open_func):
            app = create_app()
            app.config["TESTING"] = True

            # Create database tables
            with app.app_context():
                from userservice.db import UserDb

                user_db = UserDb(db_url)
                # Create all tables defined in the metadata
                user_db.users_table.metadata.create_all(user_db.engine)

            # Create the test client
            with app.test_client() as client:
                with app.app_context():
                    yield client


@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "username": "testuser123",
        "password": TEST_PASSWORD,
        "password-repeat": TEST_PASSWORD,
        "firstname": "John",
        "lastname": "Doe",
        "birthday": "1990-01-01",
        "timezone": TEST_TIMEZONE,
        "address": TEST_ADDRESS,
        "state": TEST_STATE,
        "zip": TEST_ZIP,
        "ssn": TEST_SSN,
    }


@pytest.fixture
def invalid_user_data():
    """Provide various invalid user data for negative testing."""
    return {
        "missing_fields": {
            "username": "testuser",
            "password": "password123",
            # Missing other required fields
        },
        "invalid_username": {
            "username": "a",  # Too short
            "password": TEST_PASSWORD,
            "password-repeat": TEST_PASSWORD,
            "firstname": "John",
            "lastname": "Doe",
            "birthday": "1990-01-01",
            "timezone": TEST_TIMEZONE,
            "address": TEST_ADDRESS,
            "state": TEST_STATE,
            "zip": TEST_ZIP,
            "ssn": TEST_SSN,
        },
        "password_mismatch": {
            "username": "testuser123",
            "password": TEST_PASSWORD,
            "password-repeat": "DifferentPass123!",
            "firstname": "John",
            "lastname": "Doe",
            "birthday": "1990-01-01",
            "timezone": TEST_TIMEZONE,
            "address": TEST_ADDRESS,
            "state": TEST_STATE,
            "zip": TEST_ZIP,
            "ssn": TEST_SSN,
        },
    }
