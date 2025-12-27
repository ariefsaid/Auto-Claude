/**
 * HTTP/WebSocket API Client
 * ==========================
 *
 * Implements ElectronAPI interface using HTTP REST + WebSocket
 * for browser mode with live backend (FastAPI server).
 *
 * This enables running the UI in a browser while communicating
 * with the Python backend via HTTP instead of Electron IPC.
 */

import type { ElectronAPI } from '../../shared/types/ipc';
import type { IPCResult } from '../../shared/types/common';
import type {
  Task,
  TaskStatus,
  TaskStartOptions,
  ImplementationPlan,
  ExecutionProgress
} from '../../shared/types/task';
import type { Project } from '../../shared/types/project';

// Get API URLs from environment variables
const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8766';
const WS_BASE_URL = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8766';

/**
 * HTTP/WebSocket client implementing ElectronAPI interface.
 *
 * Connects to FastAPI backend for browser live mode.
 */
export class HttpApiClient implements Partial<ElectronAPI> {
  private ws: WebSocket | null = null;
  private wsClientId: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  // Event callback storage
  private taskProgressCallbacks: ((taskId: string, plan: ImplementationPlan) => void)[] = [];
  private taskErrorCallbacks: ((taskId: string, error: string) => void)[] = [];
  private taskLogCallbacks: ((taskId: string, log: string) => void)[] = [];
  private taskStatusChangeCallbacks: ((taskId: string, status: TaskStatus) => void)[] = [];
  private taskExecutionProgressCallbacks: ((taskId: string, progress: ExecutionProgress) => void)[] = [];

  constructor() {
    // Generate unique client ID
    this.wsClientId = `client-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    // Initialize WebSocket connection
    this.connectWebSocket();

    console.log('[HttpApiClient] Initialized', {
      apiUrl: API_BASE_URL,
      wsUrl: WS_BASE_URL,
      clientId: this.wsClientId,
    });
  }

  /**
   * Initialize WebSocket connection for real-time events.
   */
  private connectWebSocket(): void {
    try {
      const wsUrl = `${WS_BASE_URL}/ws/${this.wsClientId}`;
      console.log('[HttpApiClient] Connecting to WebSocket:', wsUrl);

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[HttpApiClient] WebSocket connected');
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleWebSocketMessage(message);
        } catch (error) {
          console.error('[HttpApiClient] Error parsing WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[HttpApiClient] WebSocket error:', error);
      };

      this.ws.onclose = () => {
        console.log('[HttpApiClient] WebSocket disconnected');
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('[HttpApiClient] Error creating WebSocket:', error);
      this.attemptReconnect();
    }
  }

  /**
   * Attempt to reconnect WebSocket with exponential backoff.
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

      console.log(`[HttpApiClient] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

      setTimeout(() => {
        this.connectWebSocket();
      }, delay);
    } else {
      console.error('[HttpApiClient] Max reconnection attempts reached');
    }
  }

  /**
   * Handle incoming WebSocket messages.
   */
  private handleWebSocketMessage(message: any): void {
    const { type, taskId } = message;

    switch (type) {
      case 'log':
        this.taskLogCallbacks.forEach(cb => cb(taskId, message.log));
        break;

      case 'progress':
        this.taskProgressCallbacks.forEach(cb => cb(taskId, message.progress));
        break;

      case 'error':
        this.taskErrorCallbacks.forEach(cb => cb(taskId, message.error));
        break;

      case 'status-change':
        this.taskStatusChangeCallbacks.forEach(cb => cb(taskId, message.status));
        break;

      case 'execution-progress':
        this.taskExecutionProgressCallbacks.forEach(cb => cb(taskId, message.progress));
        break;

      default:
        console.warn('[HttpApiClient] Unknown WebSocket message type:', type);
    }
  }

  /**
   * Make HTTP request to API server.
   */
  private async apiRequest<T>(
    method: string,
    endpoint: string,
    body?: any
  ): Promise<IPCResult<T>> {
    try {
      const url = `${API_BASE_URL}${endpoint}`;
      const options: RequestInit = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      if (body) {
        options.body = JSON.stringify(body);
      }

      const response = await fetch(url, options);
      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      return data;
    } catch (error) {
      console.error('[HttpApiClient] API request error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // =========================================================================
  // Task Operations
  // =========================================================================

  async getTasks(projectId: string): Promise<IPCResult<Task[]>> {
    return this.apiRequest<Task[]>('GET', `/api/tasks?project_id=${projectId}`);
  }

  startTask(taskId: string, options?: TaskStartOptions): void {
    // Fire and forget - progress comes via WebSocket
    // TODO: Extract projectId and specId from taskId or current context
    // For now, send minimal data - backend will need to infer from taskId
    this.apiRequest('POST', '/api/tasks/start', {
      taskId,
      projectId: '', // TODO: Get from context
      specId: null, // TODO: Get from taskId
      options,
    }).catch(error => {
      console.error('[HttpApiClient] Error starting task:', error);
    });
  }

  stopTask(taskId: string): void {
    // Fire and forget
    this.apiRequest('POST', '/api/tasks/stop', { taskId }).catch(error => {
      console.error('[HttpApiClient] Error stopping task:', error);
    });
  }

  // =========================================================================
  // Event Listeners
  // =========================================================================

  onTaskProgress(callback: (taskId: string, plan: ImplementationPlan) => void): () => void {
    this.taskProgressCallbacks.push(callback);
    return () => {
      const index = this.taskProgressCallbacks.indexOf(callback);
      if (index > -1) {
        this.taskProgressCallbacks.splice(index, 1);
      }
    };
  }

  onTaskError(callback: (taskId: string, error: string) => void): () => void {
    this.taskErrorCallbacks.push(callback);
    return () => {
      const index = this.taskErrorCallbacks.indexOf(callback);
      if (index > -1) {
        this.taskErrorCallbacks.splice(index, 1);
      }
    };
  }

  onTaskLog(callback: (taskId: string, log: string) => void): () => void {
    this.taskLogCallbacks.push(callback);
    return () => {
      const index = this.taskLogCallbacks.indexOf(callback);
      if (index > -1) {
        this.taskLogCallbacks.splice(index, 1);
      }
    };
  }

  onTaskStatusChange(callback: (taskId: string, status: TaskStatus) => void): () => void {
    this.taskStatusChangeCallbacks.push(callback);
    return () => {
      const index = this.taskStatusChangeCallbacks.indexOf(callback);
      if (index > -1) {
        this.taskStatusChangeCallbacks.splice(index, 1);
      }
    };
  }

  onTaskExecutionProgress(callback: (taskId: string, progress: ExecutionProgress) => void): () => void {
    this.taskExecutionProgressCallbacks.push(callback);
    return () => {
      const index = this.taskExecutionProgressCallbacks.indexOf(callback);
      if (index > -1) {
        this.taskExecutionProgressCallbacks.splice(index, 1);
      }
    };
  }

  // =========================================================================
  // Project Operations (Basic)
  // =========================================================================

  async getProjects(): Promise<IPCResult<Project[]>> {
    return this.apiRequest<Project[]>('GET', '/api/projects');
  }

  async addProject(projectPath: string): Promise<IPCResult<Project>> {
    return this.apiRequest<Project>('POST', '/api/projects', { projectPath });
  }

  // =========================================================================
  // Settings Operations
  // =========================================================================

  async getSettings(): Promise<IPCResult<any>> {
    return this.apiRequest('GET', '/api/settings');
  }

  async saveSettings(settings: Partial<any>): Promise<IPCResult<any>> {
    return this.apiRequest('POST', '/api/settings', { settings });
  }

  // =========================================================================
  // App Info
  // =========================================================================

  async getAppVersion(): Promise<string> {
    return '1.0.0-browser-live';
  }

  // Cleanup
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Export singleton instance
let httpApiClientInstance: HttpApiClient | null = null;

export function createHttpApiClient(): HttpApiClient {
  if (!httpApiClientInstance) {
    httpApiClientInstance = new HttpApiClient();
  }
  return httpApiClientInstance;
}
