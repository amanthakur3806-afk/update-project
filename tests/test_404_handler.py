"""
Unit and Integration Tests for 404 Not Found Page & Handler
============================================================
Validates:
1. Browser/page requests to non-existent routes return 404 with HTML page.
2. Direct access to /404 returns the 404 HTML page.
3. API requests to non-existent API routes return 404 with JSON {"detail": "..."}.
4. Requests with Accept: application/json receive JSON 404.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_404_html_page_for_browser_navigation(client):
    """Browser navigating to an unrecognized route receives the custom 404 HTML page."""
    response = client.get("/non-existent-page", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Page Not Found" in response.text
    assert "Luna" in response.text
    assert "404" in response.text


def test_404_html_page_direct_route(client):
    """Direct GET /404 serves the 404 HTML page."""
    response = client.get("/404")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Page Not Found" in response.text


def test_404_html_page_for_arbitrary_unrecognized_route(client):
    """GET to an arbitrary non-API route without accept headers receives 404 HTML."""
    response = client.get("/random/unknown/path")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "404" in response.text


def test_404_json_for_api_route(client):
    """GET to an unrecognized API endpoint returns JSON 404."""
    response = client.get("/agents/non-existent-agent/missing-endpoint")
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "detail" in data


def test_404_json_when_client_explicitly_requests_json(client):
    """GET to any route with Accept: application/json returns JSON 404."""
    response = client.get("/some-missing-page", headers={"Accept": "application/json"})
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "detail" in data
