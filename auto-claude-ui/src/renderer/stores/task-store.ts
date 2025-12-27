import { create } from 'zustand';
import type { Task, TaskStatus, ImplementationPlan, Subtask, TaskMetadata, ExecutionProgress, ExecutionPhase, ReviewReason, TaskDraft } from '../../shared/types';

interface TaskState {
  tasks: Task[];
  selectedTaskId: string | null;
  isLoading: boolean;
  error: string | null;

  // Parallel execution control
  maxParallelTasks: number;
  taskQueue: string[];  // Task IDs waiting for execution slots

  // Actions
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (taskId: string, updates: Partial<Task>) => void;
  updateTaskStatus: (taskId: string, status: TaskStatus) => void;
  updateTaskFromPlan: (taskId: string, plan: ImplementationPlan) => void;
  updateExecutionProgress: (taskId: string, progress: Partial<ExecutionProgress>) => void;
  appendLog: (taskId: string, log: string) => void;
  selectTask: (taskId: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearTasks: () => void;

  // Queue management actions
  setMaxParallelTasks: (max: number) => void;
  queueTask: (taskId: string, reason?: 'slot_limit' | 'manual_hold') => void;
  dequeueTask: (taskId: string) => void;
  processQueue: () => Promise<void>;

  // Selectors
  getSelectedTask: () => Task | undefined;
  getTasksByStatus: (status: TaskStatus) => Task[];
}

// Load parallel execution settings from localStorage
const loadParallelSettings = (): { maxParallelTasks: number } => {
  try {
    const stored = localStorage.getItem('parallel-execution-settings');
    if (stored) {
      const parsed = JSON.parse(stored);
      return { maxParallelTasks: parsed.maxParallelTasks || 2 };
    }
  } catch (error) {
    console.error('Failed to load parallel execution settings:', error);
  }
  return { maxParallelTasks: 2 };  // Default to 2
};

// Save parallel execution settings to localStorage
const saveParallelSettings = (maxParallelTasks: number): void => {
  try {
    localStorage.setItem('parallel-execution-settings', JSON.stringify({
      maxParallelTasks,
      version: 1
    }));
  } catch (error) {
    console.error('Failed to save parallel execution settings:', error);
  }
};

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  selectedTaskId: null,
  isLoading: false,
  error: null,

  // Initialize parallel execution settings from localStorage
  ...loadParallelSettings(),
  taskQueue: [],

  setTasks: (tasks) => set({ tasks }),

  addTask: (task) =>
    set((state) => ({
      tasks: [...state.tasks, task]
    })),

  updateTask: (taskId, updates) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId || t.specId === taskId ? { ...t, ...updates } : t
      )
    })),

  updateTaskStatus: (taskId, status) => {
    // Update status - NO slot checking here
    // Slot checking happens in startTask() before calling backend
    set((state) => ({
      tasks: state.tasks.map((t) => {
        if (t.id !== taskId && t.specId !== taskId) return t;

        // When status goes to backlog, reset execution progress to idle
        // This ensures the planning/coding animation stops when task is stopped
        // Also clear queue metadata if task was queued
        const executionProgress = status === 'backlog'
          ? { phase: 'idle' as ExecutionPhase, phaseProgress: 0, overallProgress: 0 }
          : t.executionProgress;

        const updates: Partial<Task> = {
          status,
          executionProgress,
          updatedAt: new Date()
        };

        // Clear queue metadata when task moves out of queue
        if (status !== 'backlog' || !t.queuedAt) {
          updates.queuedAt = undefined;
          updates.queuePosition = undefined;
          updates.queueReason = undefined;
        }

        return { ...t, ...updates };
      })
    }));

    // Trigger queue processing when task moves to human_review
    // (ai_review still holds slot - QA agent is using API)
    if (status === 'human_review') {
      setTimeout(() => get().processQueue(), 100);
    }
  },

  updateTaskFromPlan: (taskId, plan) =>
    set((state) => ({
      tasks: state.tasks.map((t) => {
        if (t.id !== taskId && t.specId !== taskId) return t;

        // Extract subtasks from plan
        const subtasks: Subtask[] = plan.phases.flatMap((phase) =>
          phase.subtasks.map((subtask) => ({
            id: subtask.id,
            title: subtask.description,
            description: subtask.description,
            status: subtask.status,
            files: [],
            verification: subtask.verification as Subtask['verification']
          }))
        );

        // Determine status and reviewReason based on subtasks
        // This logic must match the backend (project-store.ts) exactly
        const allCompleted = subtasks.length > 0 && subtasks.every((s) => s.status === 'completed');
        const anyInProgress = subtasks.some((s) => s.status === 'in_progress');
        const anyFailed = subtasks.some((s) => s.status === 'failed');
        const anyCompleted = subtasks.some((s) => s.status === 'completed');

        let status: TaskStatus = t.status;
        let reviewReason: ReviewReason | undefined = t.reviewReason;

        if (allCompleted) {
          // Manual tasks skip AI review and go directly to human review
          status = t.metadata?.sourceType === 'manual' ? 'human_review' : 'ai_review';
          if (t.metadata?.sourceType === 'manual') {
            reviewReason = 'completed';
          } else {
            reviewReason = undefined;
          }
        } else if (anyFailed) {
          // Some subtasks failed - needs human attention
          status = 'human_review';
          reviewReason = 'errors';
        } else if (anyInProgress || anyCompleted) {
          // Work in progress
          status = 'in_progress';
          reviewReason = undefined;
        }

        return {
          ...t,
          title: plan.feature || t.title,
          subtasks,
          status,
          reviewReason,
          updatedAt: new Date()
        };
      })
    })),

  updateExecutionProgress: (taskId, progress) =>
    set((state) => ({
      tasks: state.tasks.map((t) => {
        if (t.id !== taskId && t.specId !== taskId) return t;

        // Merge with existing progress
        const existingProgress = t.executionProgress || {
          phase: 'idle' as ExecutionPhase,
          phaseProgress: 0,
          overallProgress: 0
        };

        return {
          ...t,
          executionProgress: {
            ...existingProgress,
            ...progress
          },
          updatedAt: new Date()
        };
      })
    })),

  appendLog: (() => {
    // Module-level cache for deduplication
    const dedupCache = new Map<string, number>();

    return (taskId: string, log: string) => {
      // Deduplication: prevent duplicate logs from race conditions
      const now = Date.now();
      const dedupKey = `${taskId}:${log.substring(0, 100)}`;

      const lastAppendTime = dedupCache.get(dedupKey);
      if (lastAppendTime && (now - lastAppendTime) < 100) {
        // Same log within 100ms window = duplicate from multiple listeners
        return; // Skip this append
      }

      // Record this append
      dedupCache.set(dedupKey, now);

      // Clean cache (keep last 50 entries to prevent memory leak)
      if (dedupCache.size > 50) {
        const entries = Array.from(dedupCache.entries()).sort(([, a], [, b]) => b - a);
        dedupCache.clear();
        entries.slice(0, 50).forEach(([k, v]) => dedupCache.set(k, v));
      }

      // Restore specId fallback (id and specId are always identical, provides resilience)
      set((state) => ({
        tasks: state.tasks.map((t) =>
          t.id === taskId || t.specId === taskId
            ? { ...t, logs: [...(t.logs || []), log] }
            : t
        )
      }));
    };
  })(),

  selectTask: (taskId) => set({ selectedTaskId: taskId }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  clearTasks: () => set({ tasks: [], selectedTaskId: null }),

  // Queue management actions
  setMaxParallelTasks: (max) => {
    saveParallelSettings(max);
    set({ maxParallelTasks: max });
    // Trigger queue processing if limit increased
    setTimeout(() => get().processQueue(), 100);
  },

  queueTask: (taskId, reason = 'slot_limit') => {
    const state = get();

    // Don't queue if already queued
    if (state.taskQueue.includes(taskId)) {
      return;
    }

    // Add to queue
    set((state2) => ({
      taskQueue: [...state2.taskQueue, taskId],
      tasks: state2.tasks.map((t) => {
        if (t.id !== taskId && t.specId !== taskId) return t;

        return {
          ...t,
          queuedAt: new Date(),
          queuePosition: state2.taskQueue.length + 1,
          queueReason: reason,
          // Keep status as backlog when queued
          status: 'backlog' as TaskStatus,
          updatedAt: new Date()
        };
      })
    }));
  },

  dequeueTask: (taskId) => {
    set((state) => ({
      taskQueue: state.taskQueue.filter(id => id !== taskId),
      tasks: state.tasks.map((t) => {
        if (t.id !== taskId && t.specId !== taskId) return t;

        return {
          ...t,
          queuedAt: undefined,
          queuePosition: undefined,
          queueReason: undefined,
          updatedAt: new Date()
        };
      })
    }));

    // Update queue positions for remaining tasks
    const state = get();
    set({
      tasks: state.tasks.map((t) => {
        const queueIndex = state.taskQueue.indexOf(t.id);
        if (queueIndex >= 0) {
          return { ...t, queuePosition: queueIndex + 1 };
        }
        return t;
      })
    });
  },

  processQueue: async () => {
    const state = get();

    if (state.taskQueue.length === 0) {
      return;
    }

    try {
      const runningCount = await getRunningTaskCount();
      const availableSlots = state.maxParallelTasks - runningCount;

      if (availableSlots <= 0) {
        return;
      }

      // Start as many queued tasks as we have available slots
      const tasksToStart = state.taskQueue.slice(0, availableSlots);

      console.log(`[processQueue] Processing ${tasksToStart.length} queued tasks (${availableSlots} slots available)`);

      for (const taskId of tasksToStart) {
        // Dequeue the task first
        state.dequeueTask(taskId);

        // Look up the task to get projectId and specId
        const task = state.tasks.find((t) => t.id === taskId || t.specId === taskId);

        // Start the task directly (we've already checked slots above)
        console.log(`[processQueue] Starting queued task:`, taskId);
        window.electronAPI.startTask(taskId, {
          projectId: task?.projectId,
          specId: task?.specId,
        });
      }
    } catch (error) {
      console.error('Failed to process task queue:', error);
    }
  },

  // Selectors
  getSelectedTask: () => {
    const state = get();
    return state.tasks.find((t) => t.id === state.selectedTaskId);
  },

  getTasksByStatus: (status) => {
    const state = get();
    return state.tasks.filter((t) => t.status === status);
  }
}));

/**
 * Load tasks for a project
 */
export async function loadTasks(projectId: string): Promise<void> {
  const store = useTaskStore.getState();
  store.setLoading(true);
  store.setError(null);

  try {
    const result = await window.electronAPI.getTasks(projectId);
    if (result.success && result.data) {
      store.setTasks(result.data);
    } else {
      store.setError(result.error || 'Failed to load tasks');
    }
  } catch (error) {
    store.setError(error instanceof Error ? error.message : 'Unknown error');
  } finally {
    store.setLoading(false);
  }
}

/**
 * Create a new task
 */
export async function createTask(
  projectId: string,
  title: string,
  description: string,
  metadata?: TaskMetadata
): Promise<Task | null> {
  const store = useTaskStore.getState();

  try {
    const result = await window.electronAPI.createTask(projectId, title, description, metadata);
    if (result.success && result.data) {
      store.addTask(result.data);
      return result.data;
    } else {
      store.setError(result.error || 'Failed to create task');
      return null;
    }
  } catch (error) {
    store.setError(error instanceof Error ? error.message : 'Unknown error');
    return null;
  }
}

/**
 * Start a task with slot checking
 */
export async function startTask(taskId: string, options?: { parallel?: boolean; workers?: number }): Promise<void> {
  const state = useTaskStore.getState();

  // Look up the task to get projectId and specId
  const task = state.tasks.find((t) => t.id === taskId || t.specId === taskId);
  const enrichedOptions = {
    ...options,
    projectId: task?.projectId,
    specId: task?.specId,
  };

  try {
    // Check if we have available slots
    const runningCount = await getRunningTaskCount();
    if (runningCount >= state.maxParallelTasks) {
      // No slots available - queue the task
      console.log(`[startTask] Slot limit reached (${runningCount}/${state.maxParallelTasks}), queueing task:`, taskId);
      state.queueTask(taskId, 'slot_limit');
      return;
    }

    // Slot available - start the task
    console.log(`[startTask] Starting task (${runningCount + 1}/${state.maxParallelTasks}):`, taskId);
    window.electronAPI.startTask(taskId, enrichedOptions);
  } catch (error) {
    console.error('Failed to check slots before starting task:', error);
    // Fallback: allow task to start if check fails
    window.electronAPI.startTask(taskId, enrichedOptions);
  }
}

/**
 * Stop a task
 */
export function stopTask(taskId: string): void {
  window.electronAPI.stopTask(taskId);
}

/**
 * Submit review for a task
 */
export async function submitReview(
  taskId: string,
  approved: boolean,
  feedback?: string
): Promise<boolean> {
  const store = useTaskStore.getState();

  try {
    const result = await window.electronAPI.submitReview(taskId, approved, feedback);
    if (result.success) {
      store.updateTaskStatus(taskId, approved ? 'done' : 'in_progress');
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Update task status and persist to file
 */
export async function persistTaskStatus(
  taskId: string,
  status: TaskStatus
): Promise<boolean> {
  const store = useTaskStore.getState();

  try {
    // Update local state first for immediate feedback
    store.updateTaskStatus(taskId, status);

    // Persist to file
    const result = await window.electronAPI.updateTaskStatus(taskId, status);
    if (!result.success) {
      console.error('Failed to persist task status:', result.error);
      return false;
    }
    return true;
  } catch (error) {
    console.error('Error persisting task status:', error);
    return false;
  }
}

/**
 * Update task title/description/metadata and persist to file
 */
export async function persistUpdateTask(
  taskId: string,
  updates: { title?: string; description?: string; metadata?: Partial<TaskMetadata> }
): Promise<boolean> {
  const store = useTaskStore.getState();

  try {
    // Call the IPC to persist changes to spec files
    const result = await window.electronAPI.updateTask(taskId, updates);

    if (result.success && result.data) {
      // Update local state with the returned task data
      store.updateTask(taskId, {
        title: result.data.title,
        description: result.data.description,
        metadata: result.data.metadata,
        updatedAt: new Date()
      });
      return true;
    }

    console.error('Failed to persist task update:', result.error);
    return false;
  } catch (error) {
    console.error('Error persisting task update:', error);
    return false;
  }
}

/**
 * Check if a task has an active running process
 */
export async function checkTaskRunning(taskId: string): Promise<boolean> {
  try {
    const result = await window.electronAPI.checkTaskRunning(taskId);
    return result.success && result.data === true;
  } catch (error) {
    console.error('Error checking task running status:', error);
    return false;
  }
}

/**
 * Get the count of currently running tasks
 */
export async function getRunningTaskCount(): Promise<number> {
  try {
    const result = await window.electronAPI.getRunningTaskCount();
    return result.success && typeof result.data === 'number' ? result.data : 0;
  } catch (error) {
    console.error('Error getting running task count:', error);
    return 0;
  }
}

/**
 * Recover a stuck task (status shows in_progress but no process running)
 * @param taskId - The task ID to recover
 * @param options - Recovery options (autoRestart defaults to true)
 */
export async function recoverStuckTask(
  taskId: string,
  options: { targetStatus?: TaskStatus; autoRestart?: boolean } = { autoRestart: true }
): Promise<{ success: boolean; message: string; autoRestarted?: boolean }> {
  const store = useTaskStore.getState();

  try {
    const result = await window.electronAPI.recoverStuckTask(taskId, options);

    if (result.success && result.data) {
      // Update local state
      store.updateTaskStatus(taskId, result.data.newStatus);
      return {
        success: true,
        message: result.data.message,
        autoRestarted: result.data.autoRestarted
      };
    }

    return {
      success: false,
      message: result.error || 'Failed to recover task'
    };
  } catch (error) {
    console.error('Error recovering stuck task:', error);
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Delete a task and its spec directory
 */
export async function deleteTask(
  taskId: string
): Promise<{ success: boolean; error?: string }> {
  const store = useTaskStore.getState();

  try {
    const result = await window.electronAPI.deleteTask(taskId);

    if (result.success) {
      // Remove from local state
      store.setTasks(store.tasks.filter(t => t.id !== taskId && t.specId !== taskId));
      // Clear selection if this task was selected
      if (store.selectedTaskId === taskId) {
        store.selectTask(null);
      }
      return { success: true };
    }

    return {
      success: false,
      error: result.error || 'Failed to delete task'
    };
  } catch (error) {
    console.error('Error deleting task:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Archive tasks
 * Marks tasks as archived by adding archivedAt timestamp to metadata
 */
export async function archiveTasks(
  projectId: string,
  taskIds: string[],
  version?: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const result = await window.electronAPI.archiveTasks(projectId, taskIds, version);

    if (result.success) {
      // Reload tasks to update the UI (archived tasks will be filtered out by default)
      await loadTasks(projectId);
      return { success: true };
    }

    return {
      success: false,
      error: result.error || 'Failed to archive tasks'
    };
  } catch (error) {
    console.error('Error archiving tasks:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

// ============================================
// Task Creation Draft Management
// ============================================

const DRAFT_KEY_PREFIX = 'task-creation-draft';

/**
 * Get the localStorage key for a project's draft
 */
function getDraftKey(projectId: string): string {
  return `${DRAFT_KEY_PREFIX}-${projectId}`;
}

/**
 * Save a task creation draft to localStorage
 * Note: For large images, we only store thumbnails in the draft to avoid localStorage limits
 */
export function saveDraft(draft: TaskDraft): void {
  try {
    const key = getDraftKey(draft.projectId);
    // Create a copy with thumbnails only to avoid localStorage size limits
    const draftToStore = {
      ...draft,
      images: draft.images.map(img => ({
        ...img,
        data: undefined // Don't store full image data in localStorage
      })),
      savedAt: new Date().toISOString()
    };
    localStorage.setItem(key, JSON.stringify(draftToStore));
  } catch (error) {
    console.error('Failed to save draft:', error);
  }
}

/**
 * Load a task creation draft from localStorage
 */
export function loadDraft(projectId: string): TaskDraft | null {
  try {
    const key = getDraftKey(projectId);
    const stored = localStorage.getItem(key);
    if (!stored) return null;

    const draft = JSON.parse(stored);
    // Convert savedAt back to Date
    draft.savedAt = new Date(draft.savedAt);
    return draft as TaskDraft;
  } catch (error) {
    console.error('Failed to load draft:', error);
    return null;
  }
}

/**
 * Clear a task creation draft from localStorage
 */
export function clearDraft(projectId: string): void {
  try {
    const key = getDraftKey(projectId);
    localStorage.removeItem(key);
  } catch (error) {
    console.error('Failed to clear draft:', error);
  }
}

/**
 * Check if a draft exists for a project
 */
export function hasDraft(projectId: string): boolean {
  const key = getDraftKey(projectId);
  return localStorage.getItem(key) !== null;
}

/**
 * Check if a draft has any meaningful content (title, description, or images)
 */
export function isDraftEmpty(draft: TaskDraft | null): boolean {
  if (!draft) return true;
  return (
    !draft.title.trim() &&
    !draft.description.trim() &&
    draft.images.length === 0 &&
    !draft.category &&
    !draft.priority &&
    !draft.complexity &&
    !draft.impact
  );
}

// ============================================
// GitHub Issue Linking Helpers
// ============================================

/**
 * Find a task by GitHub issue number
 * Used to check if a task already exists for a GitHub issue
 */
export function getTaskByGitHubIssue(issueNumber: number): Task | undefined {
  const store = useTaskStore.getState();
  return store.tasks.find(t => t.metadata?.githubIssueNumber === issueNumber);
}

// ============================================
// Task State Detection Helpers
// ============================================

/**
 * Check if a task is in human_review but has no completed subtasks.
 * This indicates the task crashed/exited before implementation completed
 * and should be resumed rather than reviewed.
 */
export function isIncompleteHumanReview(task: Task): boolean {
  if (task.status !== 'human_review') return false;

  // If no subtasks defined, task hasn't been planned yet (shouldn't be in human_review)
  if (!task.subtasks || task.subtasks.length === 0) return true;

  // Check if any subtasks are completed
  const completedSubtasks = task.subtasks.filter(s => s.status === 'completed').length;

  // If 0 completed subtasks, this task crashed before implementation
  return completedSubtasks === 0;
}

/**
 * Get the count of completed subtasks for a task
 */
export function getCompletedSubtaskCount(task: Task): number {
  if (!task.subtasks || task.subtasks.length === 0) return 0;
  return task.subtasks.filter(s => s.status === 'completed').length;
}

/**
 * Get task progress info
 */
export function getTaskProgress(task: Task): { completed: number; total: number; percentage: number } {
  const total = task.subtasks?.length || 0;
  const completed = task.subtasks?.filter(s => s.status === 'completed').length || 0;
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
  return { completed, total, percentage };
}
