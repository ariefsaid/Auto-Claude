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
  ExecutionProgress,
  WorktreeStatus,
  WorktreeDiff,
  WorktreeMergeResult,
  WorktreeDiscardResult,
  WorktreeListResult,
  TaskRecoveryResult,
  TaskRecoveryOptions,
  TaskMetadata
} from '../../shared/types/task';
import type {
  Project,
  ProjectContextData,
  ProjectIndex,
  ProjectEnvConfig,
  GitStatus
} from '../../shared/types/project';

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
   * Map backend status to valid UI TaskStatus.
   * Backend sends statuses like: spec_creating, spec_ready, spec_failed, started, completed, failed
   * UI Kanban columns expect: backlog, in_progress, ai_review, human_review, done
   */
  private mapBackendStatusToUI(backendStatus: string): TaskStatus {
    const statusMap: Record<string, TaskStatus> = {
      // Spec creation statuses
      'spec_creating': 'in_progress',
      'spec_ready': 'in_progress',  // Spec done, task will start execution
      'spec_failed': 'backlog',     // Failed, user can retry

      // Task execution statuses
      'started': 'in_progress',
      'running': 'in_progress',
      'completed': 'ai_review',     // Completed tasks go to AI review
      'failed': 'backlog',          // Failed tasks go back to backlog
      'stopped': 'backlog',         // Stopped tasks go back to backlog

      // Already valid UI statuses (pass through)
      'backlog': 'backlog',
      'in_progress': 'in_progress',
      'ai_review': 'ai_review',
      'human_review': 'human_review',
      'done': 'done',
    };

    const mappedStatus = statusMap[backendStatus];
    if (!mappedStatus) {
      console.warn(`[HttpApiClient] Unknown backend status: ${backendStatus}, defaulting to 'in_progress'`);
      return 'in_progress';
    }
    return mappedStatus;
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

      case 'status-change': {
        // Map backend status to valid UI status
        const uiStatus = this.mapBackendStatusToUI(message.status);
        console.log(`[HttpApiClient] Status change: ${message.status} -> ${uiStatus}`);
        this.taskStatusChangeCallbacks.forEach(cb => cb(taskId, uiStatus));
        break;
      }

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

  startTask(taskId: string, options?: TaskStartOptions & { projectId?: string; specId?: string }): void {
    // Fire and forget - progress comes via WebSocket
    // projectId and specId are passed via enriched options from task-store
    this.apiRequest('POST', '/api/tasks/start', {
      taskId,
      projectId: options?.projectId || '',
      specId: options?.specId || null,
      options: {
        parallel: options?.parallel,
        workers: options?.workers,
        model: options?.model,
        baseBranch: options?.baseBranch,
      },
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

  async createTask(
    projectId: string,
    title: string,
    description: string,
    metadata?: TaskMetadata
  ): Promise<IPCResult<Task>> {
    return this.apiRequest<Task>('POST', '/api/tasks', {
      projectId,
      title,
      description,
      requireReviewBeforeCoding: metadata?.requireReviewBeforeCoding || false
    });
  }

  async deleteTask(taskId: string): Promise<IPCResult> {
    // taskId format is "task-{specId}" or just specId
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    // Note: Need project_id from context - for now use query param
    return this.apiRequest('DELETE', `/api/tasks/${specId}?project_id=`);
  }

  async updateTask(
    taskId: string,
    updates: { title?: string; description?: string }
  ): Promise<IPCResult<Task>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<Task>('PUT', `/api/tasks/${specId}?project_id=`, updates);
  }

  async submitReview(
    taskId: string,
    approved: boolean,
    feedback?: string
  ): Promise<IPCResult> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest('POST', `/api/tasks/${specId}/review`, {
      action: approved ? 'approve' : 'reject',
      feedback,
      projectId: ''
    });
  }

  async updateTaskStatus(taskId: string, status: TaskStatus): Promise<IPCResult> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest('POST', `/api/tasks/${specId}/status?project_id=`, {
      status,
      autoStart: false
    });
  }

  async recoverStuckTask(
    taskId: string,
    _options?: TaskRecoveryOptions
  ): Promise<IPCResult<TaskRecoveryResult>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<TaskRecoveryResult>('POST', `/api/tasks/${specId}/recover?project_id=`);
  }

  async checkTaskRunning(taskId: string): Promise<IPCResult<boolean>> {
    const result = await this.apiRequest<{ count: number; tasks: any[] }>('GET', '/api/tasks/running');
    if (result.success && result.data) {
      const isRunning = result.data.tasks.some((t: any) => t.taskId === taskId);
      return { success: true, data: isRunning };
    }
    return { success: true, data: false };
  }

  async getRunningTaskCount(): Promise<IPCResult<number>> {
    const result = await this.apiRequest<{ count: number }>('GET', '/api/tasks/running');
    if (result.success && result.data) {
      return { success: true, data: result.data.count };
    }
    return { success: true, data: 0 };
  }

  // =========================================================================
  // Workspace/Worktree Operations
  // =========================================================================

  async getWorktreeStatus(taskId: string): Promise<IPCResult<WorktreeStatus>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<WorktreeStatus>('GET', `/api/workspace/status?spec_id=${specId}&project_id=`);
  }

  async getWorktreeDiff(taskId: string): Promise<IPCResult<WorktreeDiff>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<WorktreeDiff>('GET', `/api/workspace/diff?spec_id=${specId}&project_id=`);
  }

  async mergeWorktree(
    taskId: string,
    options?: { noCommit?: boolean }
  ): Promise<IPCResult<WorktreeMergeResult>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<WorktreeMergeResult>('POST', '/api/workspace/merge', {
      specId,
      projectId: '',
      noCommit: options?.noCommit
    });
  }

  async mergeWorktreePreview(taskId: string): Promise<IPCResult<WorktreeMergeResult>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<WorktreeMergeResult>('POST', '/api/workspace/merge-preview', {
      specId,
      projectId: ''
    });
  }

  async discardWorktree(taskId: string): Promise<IPCResult<WorktreeDiscardResult>> {
    const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
    return this.apiRequest<WorktreeDiscardResult>('POST', '/api/workspace/discard', {
      specId,
      projectId: ''
    });
  }

  async listWorktrees(projectId: string): Promise<IPCResult<WorktreeListResult>> {
    return this.apiRequest<WorktreeListResult>('GET', `/api/workspace/list?project_id=${projectId}`);
  }

  // =========================================================================
  // Task Archive Operations
  // =========================================================================

  async archiveTasks(
    projectId: string,
    taskIds: string[],
    _version?: string
  ): Promise<IPCResult<boolean>> {
    // Archive each task individually
    const results = await Promise.all(
      taskIds.map(taskId => {
        const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
        return this.apiRequest('POST', `/api/tasks/${specId}/archive?project_id=${projectId}`);
      })
    );
    const allSuccess = results.every(r => r.success);
    return { success: allSuccess, data: allSuccess };
  }

  async unarchiveTasks(projectId: string, taskIds: string[]): Promise<IPCResult<boolean>> {
    const results = await Promise.all(
      taskIds.map(taskId => {
        const specId = taskId.startsWith('task-') ? taskId.substring(5) : taskId;
        return this.apiRequest('POST', `/api/tasks/${specId}/unarchive?project_id=${projectId}`);
      })
    );
    const allSuccess = results.every(r => r.success);
    return { success: allSuccess, data: allSuccess };
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
  // Project Operations
  // =========================================================================

  async getProjects(): Promise<IPCResult<Project[]>> {
    return this.apiRequest<Project[]>('GET', '/api/projects');
  }

  async addProject(projectPath: string): Promise<IPCResult<Project>> {
    return this.apiRequest<Project>('POST', '/api/projects', { projectPath });
  }

  async removeProject(projectId: string): Promise<IPCResult> {
    return this.apiRequest('DELETE', `/api/projects/${projectId}`);
  }

  async updateProjectSettings(
    projectId: string,
    settings: Partial<any>
  ): Promise<IPCResult> {
    return this.apiRequest('PUT', `/api/projects/${projectId}`, { settings });
  }

  async initializeProject(projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('POST', `/api/projects/${projectId}/init`);
  }

  // =========================================================================
  // Context Operations
  // =========================================================================

  async getProjectContext(projectId: string): Promise<IPCResult<ProjectContextData>> {
    return this.apiRequest<ProjectContextData>('GET', `/api/context?project_id=${projectId}`);
  }

  async refreshProjectIndex(projectId: string): Promise<IPCResult<ProjectIndex>> {
    return this.apiRequest<ProjectIndex>('POST', `/api/context/refresh?project_id=${projectId}`);
  }

  async searchContext(
    projectId: string,
    query: string,
    limit?: number
  ): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/context/search?project_id=${projectId}&query=${encodeURIComponent(query)}&limit=${limit || 20}`);
  }

  // =========================================================================
  // Git Operations
  // =========================================================================

  async getGitStatus(projectId: string): Promise<IPCResult<GitStatus>> {
    return this.apiRequest<GitStatus>('GET', `/api/git/status?project_id=${projectId}`);
  }

  async getGitBranches(projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/git/branches?project_id=${projectId}`);
  }

  async getCurrentBranch(projectId: string): Promise<IPCResult<string>> {
    const result = await this.apiRequest<{ branch: string }>('GET', `/api/git/current-branch?project_id=${projectId}`);
    if (result.success && result.data) {
      return { success: true, data: result.data.branch };
    }
    return { success: false, error: result.error };
  }

  async getMainBranch(projectId: string): Promise<IPCResult<string>> {
    const result = await this.apiRequest<{ mainBranch: string }>('GET', `/api/git/main-branch?project_id=${projectId}`);
    if (result.success && result.data) {
      return { success: true, data: result.data.mainBranch };
    }
    return { success: false, error: result.error };
  }

  async initGit(projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('POST', `/api/git/init?project_id=${projectId}`);
  }

  // =========================================================================
  // Provider Operations
  // =========================================================================

  async getProviderStatus(): Promise<IPCResult<any>> {
    return this.apiRequest('GET', '/api/provider/status');
  }

  async validateProvider(
    provider: string,
    apiKey: string
  ): Promise<IPCResult<any>> {
    return this.apiRequest('POST', '/api/provider/validate', { provider, apiKey });
  }

  async testProvider(
    provider: string,
    apiKey: string,
    model?: string
  ): Promise<IPCResult<any>> {
    return this.apiRequest('POST', '/api/provider/test', { provider, apiKey, model });
  }

  async getConfiguredProviders(): Promise<IPCResult<any>> {
    return this.apiRequest('GET', '/api/provider/configured');
  }

  async addProviderToGlobal(
    provider: string,
    apiKey: string
  ): Promise<IPCResult<any>> {
    return this.apiRequest('POST', '/api/provider/add', { provider, apiKey });
  }

  async removeGlobalProvider(providerId: string): Promise<IPCResult<any>> {
    return this.apiRequest('DELETE', `/api/provider/${providerId}`);
  }

  async getProviderModels(provider?: string): Promise<IPCResult<any>> {
    const url = provider ? `/api/provider/models?provider=${provider}` : '/api/provider/models';
    return this.apiRequest('GET', url);
  }

  /**
   * Get available models from OpenCode CLI.
   *
   * Fetches the list of provider/model pairs from `opencode models` command.
   * No API keys needed - OpenCode already has credentials configured.
   *
   * @returns Promise with models array containing { provider, model, fullId }
   */
  async getOpenCodeModels(): Promise<IPCResult<{
    models: Array<{ provider: string; model: string; fullId: string }>;
    providers: string[];
    count: number;
  }>> {
    return this.apiRequest('GET', '/api/providers/opencode/models');
  }

  // =========================================================================
  // Environment Operations
  // =========================================================================

  async checkClaudeAuth(_projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', '/api/env/check-auth');
  }

  // =========================================================================
  // Spec Operations
  // =========================================================================

  async getSpecContent(specId: string, projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/spec/${specId}?project_id=${projectId}`);
  }

  async getSpecPlan(specId: string, projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/spec/${specId}/plan?project_id=${projectId}`);
  }

  async getSpecQA(specId: string, projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/spec/${specId}/qa?project_id=${projectId}`);
  }

  async getSpecLogs(specId: string, projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/spec/${specId}/logs?project_id=${projectId}`);
  }

  async clearSpecLogs(specId: string, projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('POST', `/api/spec/${specId}/logs/clear?project_id=${projectId}`);
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
  // Project Environment Operations
  // =========================================================================

  async getProjectEnv(projectId: string): Promise<IPCResult<any>> {
    return this.apiRequest('GET', `/api/projects/${projectId}/env`);
  }

  async updateProjectEnv(projectId: string, config: Partial<any>): Promise<IPCResult<any>> {
    return this.apiRequest('PUT', `/api/projects/${projectId}/env`, { config });
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
