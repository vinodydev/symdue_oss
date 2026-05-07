# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Application configuration using Pydantic Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "GraphMind Orchestrator"
    api_version: str = "0.1.0"
    
    # Database
    database_url: str = "postgresql://graphmind:your_password@localhost:5433/graphmind_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Temporal
    temporal_host: str = "localhost"
    temporal_port: int = 7233
    temporal_namespace: str = "graphmind"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    
    # Docker-out-of-Docker (DooD)
    host_workspace_root: str = "/workspaces"
    internal_workspace_root: str = "/app/workspaces"
    host_cache_root: str = "/cache"
    internal_cache_root: str = "/app/cache"
    host_storage_root: str = "/storage"
    internal_storage_root: str = "/app/storage"
    docker_host: str = "unix:///var/run/docker.sock"
    
    # LLM Configuration
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4"
    
    # Logging
    log_level: str = "INFO"
    sql_echo: bool = False
    
    # CORS
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True

    # Graph execution (loop support)
    max_graph_steps: int = 1000

    # Event scripts (default OFF — see SECURITY.md before enabling)
    # When False: API rejects creating/updating events with non-empty script
    # bodies, the scheduler does not run, queue listeners do not start, and the
    # runner refuses to exec(). Closes the unauthenticated RCE path (finding C1).
    event_scripts_enabled: bool = False

    # Wait/Signal/Event settings
    event_script_timeout_seconds: int = 60       # Max time a single event script may run
    max_wait_timeout_hours: int = 168            # 7 days — hard cap on wait node timeouts
    signal_channel_max_fanout: int = 100         # Max runs notified in one channel emit


# Placeholder values shipped in .env.example. The substrate refuses to start
# if any production secret matches one of these — a defense against operators
# who copy .env.example to .env without editing.
PLACEHOLDER_SECRETS = frozenset({
    "your_password",
    "your-secret-key-change-in-production",
    "minioadmin",
    "",
})


def assert_real_secrets(s: "Settings") -> None:
    """Refuse to start if any production secret is at its placeholder value.

    Called from the lifespan startup hook in main.py. See
    flowgraph_oss/SECURITY.md (§ "Replace the placeholder secrets") for context.
    """
    bad = []
    if s.secret_key in PLACEHOLDER_SECRETS:
        bad.append("SECRET_KEY")
    # POSTGRES_PASSWORD travels through DATABASE_URL — extract and check.
    import urllib.parse
    parsed = urllib.parse.urlparse(s.database_url)
    if parsed.password is not None and parsed.password in PLACEHOLDER_SECRETS:
        bad.append("DATABASE_URL password (POSTGRES_PASSWORD)")
    if bad:
        raise RuntimeError(
            f"Refusing to start: the following secrets are at placeholder values: {bad}. "
            "Run setup/run.sh to bootstrap a real .env, or set the values explicitly. "
            "See SECURITY.md."
        )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create settings instance (singleton pattern)
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

