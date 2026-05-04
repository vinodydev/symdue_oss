"""
Tests proving that the EVENT_SCRIPTS_ENABLED gate works as documented.

Companion to flowgraph/security/C1-unauth-rce-event-script.md "Mitigation
Landed" section. The C1 partial mitigation gates the Event-script feature
off by default in OSS; these tests verify:

  1. POST /api/events with non-empty `script` returns 403 when gate is OFF
  2. POST /api/events with empty `script` succeeds (inert metadata, harmless)
  3. POST /api/events/{id}/trigger returns 503 when gate is OFF
  4. POST /api/events with non-empty `script` succeeds when gate is ON
     (validates the closed Cloud build's flag-flip path)
"""
import pytest


def _reset_settings_cache():
    """Drop the module-level settings singleton so env-var changes take effect."""
    import config.settings as settings_mod
    settings_mod._settings = None


class TestGateOff:
    """Default OSS configuration: EVENT_SCRIPTS_ENABLED=false."""

    @pytest.fixture(autouse=True)
    def _gate_off(self, monkeypatch):
        monkeypatch.setenv("EVENT_SCRIPTS_ENABLED", "false")
        _reset_settings_cache()
        yield
        _reset_settings_cache()

    def test_post_event_with_script_returns_403(self, client):
        """Creating an event with non-empty script must return 403 when gate off."""
        response = client.post(
            "/api/events",
            json={
                "name": "blocked",
                "type": "interval",
                "schedule": "5m",
                "script": "print('should not run')",
                "enabled": True,
            },
        )
        assert response.status_code == 403, response.text
        assert "Event scripts are disabled" in response.json()["detail"]

    def test_post_event_with_empty_script_succeeds(self, client):
        """Empty-script events are inert metadata records; allowed when gate off."""
        response = client.post(
            "/api/events",
            json={
                "name": "empty_script_ok",
                "type": "interval",
                "schedule": "5m",
                "script": "",
                "enabled": True,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["name"] == "empty_script_ok"

    def test_trigger_event_returns_503(self, client):
        """Manual trigger must return 503 when gate off."""
        # Need an event to trigger; create an empty-script one (allowed under gate-off)
        create = client.post(
            "/api/events",
            json={
                "name": "to_trigger",
                "type": "interval",
                "schedule": "5m",
                "script": "",
                "enabled": True,
            },
        )
        assert create.status_code == 201, create.text
        event_id = create.json()["id"]
        response = client.post(f"/api/events/{event_id}/trigger")
        assert response.status_code == 503, response.text
        assert "Event scripts are disabled" in response.json()["detail"]

    def test_patch_event_adding_script_returns_403(self, client):
        """Updating an existing event to add a script body must return 403."""
        # Create an inert event (empty script — allowed)
        create = client.post(
            "/api/events",
            json={"name": "to_patch", "type": "interval", "schedule": "5m", "script": ""},
        )
        assert create.status_code == 201, create.text
        event_id = create.json()["id"]
        # Try to patch in a script
        response = client.patch(
            f"/api/events/{event_id}",
            json={"script": "import os; os.system('uh oh')"},
        )
        assert response.status_code == 403, response.text


class TestGateOn:
    """Closed Cloud build configuration: EVENT_SCRIPTS_ENABLED=true."""

    @pytest.fixture(autouse=True)
    def _gate_on(self, monkeypatch):
        monkeypatch.setenv("EVENT_SCRIPTS_ENABLED", "true")
        _reset_settings_cache()
        yield
        _reset_settings_cache()

    def test_post_event_with_script_succeeds_when_gate_on(self, client):
        """Validates the closed Cloud build path: with the flag flipped, scripts work."""
        response = client.post(
            "/api/events",
            json={
                "name": "gate_on_works",
                "type": "interval",
                "schedule": "5m",
                "script": "# this would run if triggered",
                "enabled": True,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["name"] == "gate_on_works"
