"""
API endpoint smoke tests using FastAPI TestClient.
No real EEG hardware, no external API calls.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Setup: patch EEG ingestion so TestClient doesn't try to connect hardware
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """
    Create TestClient with EEG hardware patched out.
    Tests only verify REST contract — no LSL, no Bluetooth.
    """
    with (
        patch("eeg.ingestion.EEGIngestion.start"),
        patch("eeg.watchdog.EEGWatchdog.run"),
    ):
        # Import app after patching to avoid hardware init
        from api.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "sessions" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# /start-session endpoint
# ---------------------------------------------------------------------------

class TestStartSession:
    def test_start_session_returns_session_id(self, client):
        response = client.post("/start-session", json={"topic": "derivatives"})
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_start_session_returns_lesson_plan(self, client):
        response = client.post("/start-session", json={"topic": "derivatives"})
        data = response.json()
        plan = data["lesson_plan"]
        assert "topic" in plan
        assert "blocks" in plan
        assert isinstance(plan["blocks"], list)
        assert len(plan["blocks"]) > 0
        assert "current_block" in plan

    def test_start_session_lesson_block_has_required_fields(self, client):
        response = client.post("/start-session", json={"topic": "derivatives"})
        data = response.json()
        block = data["lesson_plan"]["blocks"][0]
        assert "id" in block
        assert "title" in block
        assert "difficulty" in block

    def test_start_session_rejects_empty_topic(self, client):
        response = client.post("/start-session", json={"topic": ""})
        assert response.status_code == 422  # Pydantic validation error

    def test_start_session_unknown_topic_returns_fallback(self, client):
        """Unknown topic should return a fallback lesson plan, not 404."""
        response = client.post("/start-session", json={"topic": "underwater_basket_weaving"})
        assert response.status_code == 200
        data = response.json()
        assert "lesson_plan" in data


# ---------------------------------------------------------------------------
# /stop-session endpoint
# ---------------------------------------------------------------------------

class TestStopSession:
    def test_stop_session_returns_summary(self, client):
        # Start a session first
        start = client.post("/start-session", json={"topic": "algebra"})
        session_id = start.json()["session_id"]

        # Stop it
        stop = client.post("/stop-session", json={"session_id": session_id})
        assert stop.status_code == 200
        data = stop.json()
        assert "summary" in data
        summary = data["summary"]
        assert "duration_seconds" in summary
        assert "state_breakdown" in summary
        assert "topics" in summary
        assert "adaptation_events" in summary

    def test_stop_session_returns_404_for_missing(self, client):
        response = client.post("/stop-session", json={"session_id": "nonexistent"})
        assert response.status_code == 404

    def test_stop_session_cleans_up_session(self, client):
        start = client.post("/start-session", json={"topic": "calculus"})
        session_id = start.json()["session_id"]
        client.post("/stop-session", json={"session_id": session_id})
        # Stopping again should 404
        response = client.post("/stop-session", json={"session_id": session_id})
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /override-state endpoint
# ---------------------------------------------------------------------------

class TestOverrideState:
    def test_override_valid_state_returns_200(self, client):
        start = client.post("/start-session", json={"topic": "algebra"})
        session_id = start.json()["session_id"]
        response = client.post("/override-state", json={"session_id": session_id, "state": "FOCUSED"})
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "FOCUSED"
        assert data["overridden"] is True
        assert data["session_id"] == session_id

    def test_override_invalid_state_returns_422(self, client):
        start = client.post("/start-session", json={"topic": "algebra"})
        session_id = start.json()["session_id"]
        response = client.post("/override-state", json={"session_id": session_id, "state": "CAFFEINATED"})
        assert response.status_code == 422

    def test_override_missing_session_returns_404(self, client):
        response = client.post("/override-state", json={"session_id": "nonexistent", "state": "FOCUSED"})
        assert response.status_code == 404

    def test_override_all_valid_states_accepted(self, client):
        start = client.post("/start-session", json={"topic": "algebra"})
        session_id = start.json()["session_id"]
        for state in ("FOCUSED", "OVERLOADED", "DISENGAGED"):
            response = client.post("/override-state", json={"session_id": session_id, "state": state})
            assert response.status_code == 200


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

class TestCORS:
    def test_cors_allows_localhost_3000(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        # CORS middleware should add Allow-Origin header
        assert response.status_code in (200, 204)
