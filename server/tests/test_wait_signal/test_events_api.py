# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for the events CRUD API endpoints.

These tests exercise the legacy event-script API (script-bearing payloads,
manual /trigger). The OSS substrate ships with EVENT_SCRIPTS_ENABLED=False
by default — the autouse fixture below flips it on for this module so the
existing assertions still apply. Gate-specific behavior is tested in
tests/test_api/test_events_gate.py.
"""
import pytest
import uuid
from unittest.mock import patch, AsyncMock


@pytest.fixture(autouse=True)
def _enable_event_scripts(monkeypatch):
    """Flip EVENT_SCRIPTS_ENABLED on for this module; reset settings cache."""
    monkeypatch.setenv("EVENT_SCRIPTS_ENABLED", "true")
    import config.settings as settings_mod
    settings_mod._settings = None
    yield
    settings_mod._settings = None


class TestCreateEvent:
    def test_create_event(self, client):
        """POST /api/events with valid body creates event and returns 201."""
        response = client.post(
            "/api/events",
            json={
                "name": "My Interval Event",
                "type": "interval",
                "schedule": "5m",
                "script": "# test",
                "enabled": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Interval Event"
        assert data["type"] == "interval"
        assert data["schedule"] == "5m"
        assert "id" in data


class TestListEvents:
    def test_list_events(self, client, test_db):
        """GET /api/events returns a list (may be empty initially)."""
        response = client.get("/api/events")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestGetEvent:
    def test_get_event(self, client, test_db):
        """GET /api/events/{id} returns the created event."""
        from database.models.event import Event

        event = Event(name="Fetch Me", type="webhook", script="pass")
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.get(f"/api/events/{event.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Fetch Me"


class TestUpdateEvent:
    def test_update_event(self, client, test_db):
        """PATCH /api/events/{id} updates name."""
        from database.models.event import Event

        event = Event(name="Old Name", type="interval", script="")
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.patch(
            f"/api/events/{event.id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"


class TestDeleteEvent:
    def test_delete_event(self, client, test_db):
        """DELETE /api/events/{id} returns 204."""
        from database.models.event import Event

        event = Event(name="Delete Me", type="interval", script="")
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.delete(f"/api/events/{event.id}")
        assert response.status_code == 204

        # Verify it no longer exists
        response2 = client.get(f"/api/events/{event.id}")
        assert response2.status_code == 404


class TestEnableDisableEvent:
    def test_enable_disable_event(self, client, test_db):
        """POST /api/events/{id}/enable and /disable toggle enabled field."""
        from database.models.event import Event

        event = Event(name="Toggle Event", type="interval", script="", enabled=True)
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        # Disable
        response = client.post(f"/api/events/{event.id}/disable")
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        # Enable
        response = client.post(f"/api/events/{event.id}/enable")
        assert response.status_code == 200
        assert response.json()["enabled"] is True
