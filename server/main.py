# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
GraphMind Orchestrator - FastAPI Main Application
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis.asyncio as redis
from config.settings import get_settings, assert_real_secrets
from database.connection import init_db
from services.temporal.client import TemporalClient
from utils.seed import seed_base_node_types

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager for startup and shutdown events
    """
    # Startup
    print("🚀 Starting GraphMind Orchestrator...")

    # Refuse to start with placeholder secrets — closes finding H1.
    assert_real_secrets(settings)

    # Initialize database tables
    print("📦 Initializing database...")
    init_db()
    
    # Seed base node types
    print("🌱 Seeding base node types...")
    seed_base_node_types()

    # Initialize Temporal client
    print("⏰ Initializing Temporal client...")
    try:
        await TemporalClient.get_client()
        print("✅ Temporal client connected")
    except Exception as e:
        print(f"⚠️  Temporal client connection failed: {e}")
        print("   Continuing without Temporal (workflows will not execute)")
    
    # Event scheduler — only when the gated feature is enabled.
    # See SECURITY.md "Trust model" and finding C1 for why this is OFF by default.
    stop_scheduler = None
    if settings.event_scripts_enabled:
        print("⏰ Starting event scheduler...")
        from services.events.scheduler import start_scheduler, stop_scheduler
        try:
            await start_scheduler()
            print("✅ Event scheduler started")
        except Exception as e:
            print(f"⚠️  Event scheduler failed to start: {e}")
            stop_scheduler = None
    else:
        print("⏸  Event scripts disabled (set EVENT_SCRIPTS_ENABLED=true to enable; see SECURITY.md)")

    print("✅ GraphMind Orchestrator started successfully")

    yield

    # Shutdown
    print("🛑 Shutting down GraphMind Orchestrator...")
    if stop_scheduler is not None:
        await stop_scheduler()
    await TemporalClient.close()
    print("✅ Shutdown complete")


app = FastAPI(
    title=settings.api_title,
    description="Visual Neural OS for building, deploying, and managing long-running AI agents",
    version=settings.api_version,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket Connection Manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.redis_client: redis.Redis | None = None
    
    async def connect(self, websocket: WebSocket, workspace_id: str):
        """Accept and register a WebSocket connection"""
        await websocket.accept()
        if workspace_id not in self.active_connections:
            self.active_connections[workspace_id] = []
        self.active_connections[workspace_id].append(websocket)
        print(f"✅ WebSocket connected for workspace: {workspace_id}")
    
    def disconnect(self, websocket: WebSocket, workspace_id: str):
        """Remove a WebSocket connection"""
        if workspace_id in self.active_connections:
            if websocket in self.active_connections[workspace_id]:
                self.active_connections[workspace_id].remove(websocket)
                print(f"❌ WebSocket disconnected for workspace: {workspace_id}")
    
    async def broadcast(self, workspace_id: str, message: str):
        """Broadcast a message to all connections for a workspace"""
        if workspace_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[workspace_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"⚠️  Error sending message to WebSocket: {e}")
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for connection in disconnected:
                self.disconnect(connection, workspace_id)


# Global connection manager instance
manager = ConnectionManager()


@app.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """
    WebSocket endpoint for real-time workspace updates
    
    Subscribes to:
    - workspace_updates:{workspace_id} - Workspace-level updates
    - run_updates:* - Run execution updates (pattern match)
    """
    await manager.connect(websocket, workspace_id)
    
    try:
        # Subscribe to Redis pub/sub for workspace updates
        redis_client = await redis.from_url(settings.redis_url, decode_responses=False)
        pubsub = redis_client.pubsub()
        
        # Subscribe to workspace updates (backward compat)
        await pubsub.subscribe(f"workspace_updates:{workspace_id}")

        # Subscribe to ALL execution events (new unified channel)
        await pubsub.psubscribe(f"execution:*")

        # Subscribe to run updates (backward compat)
        await pubsub.psubscribe(f"run_updates:*")
        
        # Listen for messages from Redis and broadcast to WebSocket clients
        async for message in pubsub.listen():
            if message["type"] == "message":
                # Direct message (workspace updates)
                await manager.broadcast(workspace_id, message["data"].decode())
            elif message["type"] == "pmessage":
                # Pattern match message (run updates)
                # Broadcast to all connections for this workspace
                # (runs may belong to this workspace)
                await manager.broadcast(workspace_id, message["data"].decode())
    except WebSocketDisconnect:
        manager.disconnect(websocket, workspace_id)
    except Exception as e:
        print(f"⚠️  WebSocket error: {e}")
        manager.disconnect(websocket, workspace_id)
    finally:
        try:
            await pubsub.unsubscribe(f"workspace_updates:{workspace_id}")
            await pubsub.punsubscribe(f"run_updates:*")
            await redis_client.close()
        except:
            pass


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GraphMind Orchestrator API",
        "version": settings.api_version,
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# API routes
from api import workspaces, nodes, edges, runs, node_types, llm_configs, storage
from api import signals, events, embeddings

app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(nodes.router, prefix="/api/workspaces", tags=["nodes"])
app.include_router(edges.router, prefix="/api/workspaces", tags=["edges"])
app.include_router(node_types.router, prefix="/api/node-types", tags=["node-types"])
app.include_router(llm_configs.router, prefix="/api/llm-configs", tags=["llm-configs"])
app.include_router(storage.router, tags=["storage"])
app.include_router(signals.router, prefix="/api", tags=["signals"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(embeddings.router, tags=["embeddings"])
# runs router last — its /{workspace_id}/{run_id} catch-all must not shadow signals /runs/{run_id}/waits
app.include_router(runs.router, prefix="/api", tags=["runs"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
