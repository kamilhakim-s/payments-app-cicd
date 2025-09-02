"""
Test data fixtures and utilities for UserService integration tests
"""


class UserDataFactory:
    """Factory for creating test user data."""
    
    @staticmethod
    def create_valid_user(username="testuser", password="SecurePass123!"):
        """Create valid user data."""
        return {
            "username": username,
            "password": password,
            "password-repeat": password,
            "firstname": "John",
            "lastname": "Doe",
            "birthday": "1990-01-01",
            "timezone": "America/New_York",
            "address": "123 Test Street",
            "state": "NY",
            "zip": "10001",
            "ssn": "123-45-6789"
        }
    
    @staticmethod
    def create_user_with_missing_fields():
        """Create user data with missing required fields."""
        return {
            "username": "testuser",
            "password": "password123"
            # Missing other required fields
        }
    
    @staticmethod
    def create_user_with_invalid_username(invalid_username):
        """Create user data with invalid username."""
        return {
            "username": invalid_username,
            "password": "SecurePass123!",
            "password-repeat": "SecurePass123!",
            "firstname": "John",
            "lastname": "Doe",
            "birthday": "1990-01-01",
            "timezone": "America/New_York",
            "address": "123 Test Street",
            "state": "NY",
            "zip": "10001",
            "ssn": "123-45-6789"
        }


# Common test constants
VALID_USERNAMES = [
    "user123",
    "test_user",
    "a" * 15,  # Max length
    "user_123",
    "TestUser99"
]

INVALID_USERNAMES = [
    "a",  # Too short
    "a" * 16,  # Too long
    "user@name",  # Invalid characters
    "user.name",  # Invalid characters
    "user name",  # Space not allowed
    "user-name",  # Hyphen not allowed
    "",  # Empty
    "123",  # Only numbers (valid but edge case)
]

TEST_PASSWORDS = [
    "password123",
    "SecurePass123!",
    "P@ssw0rd",
    "a" * 100,  # Very long password
]
