"""
Integration tests for UserService user registration
"""


class TestUserRegistration:
    """Test user registration functionality with real database."""

    def test_create_user_success_with_valid_data(self, test_app, sample_user_data):
        """Test successful user creation with valid data."""
        response = test_app.post("/users", data=sample_user_data)

        assert response.status_code == 201

        # Response should be empty JSON for successful creation
        response_data = response.get_json()
        assert response_data == {}

    def test_create_user_duplicate_username_fails(self, test_app, sample_user_data):
        """Test that creating a user with duplicate username fails."""
        # Create first user
        first_response = test_app.post("/users", data=sample_user_data)
        assert first_response.status_code == 201

        # Try to create user with same username
        second_response = test_app.post("/users", data=sample_user_data)
        assert second_response.status_code == 409  # Conflict

        # Check error message (plain text response)
        error_text = second_response.get_data(as_text=True)
        assert "already exists" in error_text.lower()

    def test_create_user_missing_required_fields(self, test_app, invalid_user_data):
        """Test user creation fails with missing required fields."""
        response = test_app.post("/users", data=invalid_user_data["missing_fields"])

        assert response.status_code == 400

        error_text = response.get_data(as_text=True)
        assert "missing" in error_text.lower()

    def test_create_user_invalid_username_format(self, test_app, invalid_user_data):
        """Test user creation fails with invalid username format."""
        response = test_app.post("/users", data=invalid_user_data["invalid_username"])

        assert response.status_code == 400

        error_text = response.get_data(as_text=True)
        assert "username" in error_text.lower()

    def test_create_user_password_mismatch(self, test_app, invalid_user_data):
        """Test user creation fails when passwords don't match."""
        response = test_app.post("/users", data=invalid_user_data["password_mismatch"])

        assert response.status_code == 400

        error_text = response.get_data(as_text=True)
        assert "password" in error_text.lower()

    def test_create_user_with_special_characters_in_username(self, test_app, sample_user_data):
        """Test user creation fails with special characters in username."""
        invalid_data = sample_user_data.copy()
        invalid_data["username"] = "user@name!"

        response = test_app.post("/users", data=invalid_data)

        assert response.status_code == 400

        error_text = response.get_data(as_text=True)
        assert "username" in error_text.lower()

    def test_create_user_username_too_long(self, test_app, sample_user_data):
        """Test user creation fails with username too long."""
        invalid_data = sample_user_data.copy()
        invalid_data["username"] = "a" * 20  # Too long (max is 15)

        response = test_app.post("/users", data=invalid_data)

        assert response.status_code == 400

        error_text = response.get_data(as_text=True)
        assert "username" in error_text.lower()

    def test_create_user_empty_fields(self, test_app, sample_user_data):
        """Test user creation fails with empty required fields."""
        invalid_data = sample_user_data.copy()
        invalid_data["firstname"] = ""

        response = test_app.post("/users", data=invalid_data)

        assert response.status_code == 400

        error_text = response.get_data(as_text=True)
        assert "missing" in error_text.lower() or "field" in error_text.lower()

    def test_create_multiple_users_with_different_usernames(self, test_app, sample_user_data):
        """Test creating multiple users with different usernames succeeds."""
        # Create first user
        first_response = test_app.post("/users", data=sample_user_data)
        assert first_response.status_code == 201

        # Create second user with different username
        second_user_data = sample_user_data.copy()
        second_user_data["username"] = "testuser456"
        second_user_data["ssn"] = "987-65-4321"  # Different SSN

        second_response = test_app.post("/users", data=second_user_data)
        assert second_response.status_code == 201

        # Both responses should be empty JSON
        assert first_response.get_json() == {}
        assert second_response.get_json() == {}
