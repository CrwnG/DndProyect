"""Batch 58 (C3): the backend serves the frontend, making the app (and Playwright) reachable.

Playwright's webServer starts only uvicorn, and every spec does page.goto('/') then waits
for '.game-container' — but the app never served frontend/index.html, so all e2e specs
timed out (and there was no single-process way to run the game). Now the frontend is
mounted as static files at '/', after the API routers so /api/* keeps priority.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_the_game_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "game-container" in r.text


def test_frontend_js_is_served():
    r = client.get("/js/main.js")
    assert r.status_code == 200


def test_api_routes_keep_priority_over_static():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json().get("status") in ("ok", "healthy")
