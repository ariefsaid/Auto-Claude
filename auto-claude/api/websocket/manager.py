"""
WebSocket Connection Manager
=============================

Manages WebSocket connections for real-time event streaming to browser clients.

Features:
- Connection pool management
- Broadcast to all/specific clients
- Event type routing
- Auto-cleanup on disconnect
"""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time events."""

    def __init__(self):
        """Initialize the WebSocket manager."""
        # Client ID -> WebSocket mapping
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        """
        Accept and register a new WebSocket connection.

        Args:
            client_id: Unique client identifier
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client connected: {client_id}")
        logger.info(f"Active connections: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        """
        Disconnect and unregister a WebSocket connection.

        Args:
            client_id: Unique client identifier
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket client disconnected: {client_id}")
            logger.info(f"Active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, client_id: str):
        """
        Send message to a specific client.

        Args:
            message: Message payload (will be JSON serialized)
            client_id: Target client ID
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients.

        Args:
            message: Message payload (will be JSON serialized)
        """
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

    async def send_log(self, task_id: str, log: str, client_id: str | None = None):
        """
        Send task log event.

        Args:
            task_id: Task identifier
            log: Log message
            client_id: Optional specific client (broadcasts if None)
        """
        message = {
            "type": "log",
            "taskId": task_id,
            "log": log,
        }
        if client_id:
            await self.send_personal_message(message, client_id)
        else:
            await self.broadcast(message)

    async def send_progress(
        self, task_id: str, progress: dict, client_id: str | None = None
    ):
        """
        Send task progress event.

        Args:
            task_id: Task identifier
            progress: Progress data (implementation plan)
            client_id: Optional specific client (broadcasts if None)
        """
        message = {
            "type": "progress",
            "taskId": task_id,
            "progress": progress,
        }
        if client_id:
            await self.send_personal_message(message, client_id)
        else:
            await self.broadcast(message)

    async def send_error(self, task_id: str, error: str, client_id: str | None = None):
        """
        Send task error event.

        Args:
            task_id: Task identifier
            error: Error message
            client_id: Optional specific client (broadcasts if None)
        """
        message = {
            "type": "error",
            "taskId": task_id,
            "error": error,
        }
        if client_id:
            await self.send_personal_message(message, client_id)
        else:
            await self.broadcast(message)

    async def send_status_change(
        self, task_id: str, status: str, client_id: str | None = None
    ):
        """
        Send task status change event.

        Args:
            task_id: Task identifier
            status: New status
            client_id: Optional specific client (broadcasts if None)
        """
        message = {
            "type": "status-change",
            "taskId": task_id,
            "status": status,
        }
        if client_id:
            await self.send_personal_message(message, client_id)
        else:
            await self.broadcast(message)

    async def send_execution_progress(
        self, task_id: str, progress: dict, client_id: str | None = None
    ):
        """
        Send execution progress event (phase transitions).

        Args:
            task_id: Task identifier
            progress: Execution progress data
            client_id: Optional specific client (broadcasts if None)
        """
        message = {
            "type": "execution-progress",
            "taskId": task_id,
            "progress": progress,
        }
        if client_id:
            await self.send_personal_message(message, client_id)
        else:
            await self.broadcast(message)

    @property
    def connection_count(self) -> int:
        """Get current number of active connections."""
        return len(self.active_connections)
