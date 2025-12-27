"""
FastAPI Server for Auto Claude
================================

HTTP/WebSocket API server that enables browser-based UI access
to Auto Claude's Python backend.

Supports three runtime modes:
1. Electron with IPC (existing)
2. Browser with HTTP/WebSocket (this server)
3. Browser with mocks (offline mode)

Usage:
    python -m auto_claude.api.server --port 8766 --host localhost
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

import uvicorn
from api.routes import env, project, provider, settings, task, workspace
from api.websocket.manager import WebSocketManager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Version
__version__ = "1.0.0"

# Create FastAPI app
app = FastAPI(
    title="Auto Claude API",
    description="HTTP/WebSocket API for Auto Claude autonomous coding framework",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Create WebSocket manager (singleton)
ws_manager = WebSocketManager()

# CORS middleware - allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Alternative Vite port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "websocket_connections": ws_manager.connection_count,
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "message": "Auto Claude API Server",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws/{client_id}",
    }


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time events.

    Events:
    - log: Task execution logs
    - progress: Task progress updates
    - error: Error messages
    - status-change: Task status changes
    - execution-progress: Phase transitions (planning, coding, QA)
    """
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            # Keep connection alive and receive client messages if needed
            data = await websocket.receive_text()
            # Echo back or handle client-initiated messages if needed
            # For now, this is primarily server-to-client
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)


# Mount route modules
app.include_router(task.router, prefix="/api", tags=["tasks"])
app.include_router(project.router, prefix="/api", tags=["projects"])
app.include_router(workspace.router, prefix="/api", tags=["workspace"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(env.router, prefix="/api", tags=["env"])
app.include_router(provider.router, prefix="/api", tags=["provider"])


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Auto Claude API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8766,
        help="Port to run server on (default: 8766)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development)",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    print(f"Starting Auto Claude API Server v{__version__}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"API Docs: http://{args.host}:{args.port}/docs")
    print(f"WebSocket: ws://{args.host}:{args.port}/ws/{{client_id}}")
    print("\nPress Ctrl+C to stop")

    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
