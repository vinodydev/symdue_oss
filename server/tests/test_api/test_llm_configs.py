# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Tests for LLM config API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_create_llm_config(test_db):
    """Test creating an LLM config"""
    response = client.post(
        "/api/llm-configs",
        json={
            "name": "Test LLM",
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key",
            "config": {}
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test LLM"
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4"
    assert "id" in data


def test_list_llm_configs(test_db):
    """Test listing LLM configs"""
    # Create a config first
    client.post(
        "/api/llm-configs",
        json={
            "name": "Test LLM",
            "provider": "openai",
            "model": "gpt-4"
        }
    )
    
    # List configs
    response = client.get("/api/llm-configs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_llm_config(test_db):
    """Test getting an LLM config by ID"""
    # Create config
    create_response = client.post(
        "/api/llm-configs",
        json={
            "name": "Test LLM",
            "provider": "openai",
            "model": "gpt-4"
        }
    )
    config_id = create_response.json()["id"]
    
    # Get config
    response = client.get(f"/api/llm-configs/{config_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == config_id
    assert data["name"] == "Test LLM"


def test_update_llm_config(test_db):
    """Test updating an LLM config"""
    # Create config
    create_response = client.post(
        "/api/llm-configs",
        json={
            "name": "Test LLM",
            "provider": "openai",
            "model": "gpt-4"
        }
    )
    config_id = create_response.json()["id"]
    
    # Update config
    response = client.put(
        f"/api/llm-configs/{config_id}",
        json={
            "name": "Updated LLM",
            "model": "gpt-3.5-turbo"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated LLM"
    assert data["model"] == "gpt-3.5-turbo"


def test_delete_llm_config(test_db):
    """Test deleting an LLM config (soft delete)"""
    # Create config
    create_response = client.post(
        "/api/llm-configs",
        json={
            "name": "Test LLM",
            "provider": "openai",
            "model": "gpt-4"
        }
    )
    config_id = create_response.json()["id"]
    
    # Delete config
    response = client.delete(f"/api/llm-configs/{config_id}")
    assert response.status_code == 204
    
    # Verify soft deleted
    get_response = client.get(f"/api/llm-configs/{config_id}")
    assert get_response.status_code == 404


def test_restore_llm_config(test_db):
    """Test restoring a deleted LLM config"""
    # Create and delete config
    create_response = client.post(
        "/api/llm-configs",
        json={
            "name": "To Restore",
            "provider": "openai",
            "model": "gpt-4"
        }
    )
    config_id = create_response.json()["id"]
    client.delete(f"/api/llm-configs/{config_id}")
    
    # Restore config
    restore_response = client.post(f"/api/llm-configs/{config_id}/restore")
    assert restore_response.status_code == 200
    assert restore_response.json()["name"] == "To Restore"

