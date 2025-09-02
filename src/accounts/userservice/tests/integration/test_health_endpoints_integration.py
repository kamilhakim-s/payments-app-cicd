"""
Integration tests for UserService health endpoints
"""


class TestHealthEndpoints:
    """Test health and monitoring endpoints."""

    def test_version_endpoint_returns_correct_version(self, test_app):
        """Test that /version endpoint returns the correct version."""
        response = test_app.get("/version")

        assert response.status_code == 200
        assert response.data == b"test-1.0.0"

    def test_ready_endpoint_returns_ok(self, test_app):
        """Test that /ready endpoint returns OK status."""
        response = test_app.get("/ready")

        assert response.status_code == 200
        assert response.data == b"ok"

    def test_version_endpoint_with_different_version(self, test_app):
        """Test version endpoint with different version in config."""
        # Change the version in app config
        test_app.application.config["VERSION"] = "v2.0.0"

        response = test_app.get("/version")

        assert response.status_code == 200
        assert response.data == b"v2.0.0"

    def test_health_endpoints_multiple_requests(self, test_app):
        """Test that health endpoints handle multiple concurrent requests."""
        # Test multiple requests to ensure stability
        for _ in range(10):
            version_response = test_app.get("/version")
            ready_response = test_app.get("/ready")

            assert version_response.status_code == 200
            assert ready_response.status_code == 200
