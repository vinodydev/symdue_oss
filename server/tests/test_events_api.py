# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for the events API endpoints.
"""
import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock


class TestCreateEvent:
    def test_create_event_returns_201(self, client):
        """POST /api/events should return 201 with the created event."""
        response = client.post(
            "/api/events",
            json={
                "name": "Test Event",
                "type": "interval",
                "schedule": "5m",
                "script": "# test script",
                "enabled": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Event"
        assert data["type"] == "interval"
        assert data["schedule"] == "5m"
        assert data["enabled"] is True
        assert "id" in data
        assert "created_at" in data


class TestListEvents:
    def test_list_events_returns_all(self, client, test_db):
        """GET /api/events should return all events."""
        from database.models.event import Event

        event1 = Event(name="Event 1", type="interval", script="")
        event2 = Event(name="Event 2", type="cron", script="", schedule="0 9 * * *")
        test_db.add(event1)
        test_db.add(event2)
        test_db.commit()

        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        names = [e["name"] for e in data]
        assert "Event 1" in names
        assert "Event 2" in names


class TestGetEvent:
    def test_get_event_by_id(self, client, test_db):
        """GET /api/events/{id} should return the event."""
        from database.models.event import Event

        event = Event(name="My Event", type="webhook", script="pass")
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.get(f"/api/events/{event.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "My Event"

    def test_get_event_404(self, client):
        """GET /api/events/{id} should return 404 for unknown id."""
        response = client.get(f"/api/events/{uuid.uuid4()}")
        assert response.status_code == 404


class TestUpdateEvent:
    def test_patch_event(self, client, test_db):
        """PATCH /api/events/{id} should update the event."""
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
    def test_delete_event_returns_204(self, client, test_db):
        """DELETE /api/events/{id} should return 204."""
        from database.models.event import Event

        event = Event(name="To Delete", type="interval", script="")
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.delete(f"/api/events/{event.id}")
        assert response.status_code == 204


class TestEnableDisableEvent:
    def test_disable_event(self, client, test_db):
        """POST /api/events/{id}/disable should set enabled=False."""
        from database.models.event import Event

        event = Event(name="Active Event", type="interval", script="", enabled=True)
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.post(f"/api/events/{event.id}/disable")
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_enable_event(self, client, test_db):
        """POST /api/events/{id}/enable should set enabled=True."""
        from database.models.event import Event

        event = Event(name="Inactive Event", type="interval", script="", enabled=False)
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        response = client.post(f"/api/events/{event.id}/enable")
        assert response.status_code == 200
        assert response.json()["enabled"] is True


class TestTriggerEvent:
    def test_trigger_event_returns_invocation(self, client, test_db):
        """POST /api/events/{id}/trigger should run the script and return an invocation."""
        from database.models.event import Event

        event = Event(name="Trigger Test", type="webhook", script="x = 1 + 1", enabled=True)
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        with patch("services.temporal.client.TemporalClient.get_client", AsyncMock(return_value=None)):
            response = client.post(f"/api/events/{event.id}/trigger", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == str(event.id)
        assert data["triggered_by"] == "manual"
        assert "id" in data
