/**
 * Ideation IPC handlers registration
 *
 * This module serves as the entry point for all ideation-related IPC handlers.
 * The actual handler implementations are organized in the ./ideation/ subdirectory:
 *
 * - session-manager.ts: CRUD operations for ideation sessions
 * - idea-manager.ts: Individual idea operations (update, dismiss, etc.)
 * - generation-handlers.ts: Start/stop ideation generation
 * - task-converter.ts: Convert ideas to tasks
 * - transformers.ts: Data transformation utilities (snake_case to camelCase)
 * - file-utils.ts: File system operations
 */

import { ipcMain } from 'electron';
import type { BrowserWindow } from 'electron';
import { existsSync, readFileSync } from 'fs';
import path from 'path';
import { IPC_CHANNELS, AUTO_BUILD_PATHS } from '../../shared/constants';
import type { AgentManager } from '../agent';
import type { IdeationGenerationStatus, IdeationSession } from '../../shared/types';
import { projectStore } from '../project-store';
import {
  getIdeationSession,
  updateIdeaStatus,
  dismissIdea,
  dismissAllIdeas,
  archiveIdea,
  deleteIdea,
  deleteMultipleIdeas,
  startIdeationGeneration,
  refreshIdeationSession,
  stopIdeationGeneration,
  convertIdeaToTask
} from './ideation';
import { transformIdeaFromSnakeCase } from './ideation/transformers';

/**
 * Register all ideation-related IPC handlers
 */
export function registerIdeationHandlers(
  agentManager: AgentManager,
  getMainWindow: () => BrowserWindow | null
): void {
  // Session management
  ipcMain.handle(
    IPC_CHANNELS.IDEATION_GET,
    getIdeationSession
  );

  // Idea operations
  ipcMain.handle(
    IPC_CHANNELS.IDEATION_UPDATE_IDEA,
    updateIdeaStatus
  );

  ipcMain.handle(
    IPC_CHANNELS.IDEATION_DISMISS,
    dismissIdea
  );

  ipcMain.handle(
    IPC_CHANNELS.IDEATION_DISMISS_ALL,
    dismissAllIdeas
  );

  ipcMain.handle(
    IPC_CHANNELS.IDEATION_ARCHIVE,
    archiveIdea
  );

  ipcMain.handle(
    IPC_CHANNELS.IDEATION_DELETE,
    deleteIdea
  );

  ipcMain.handle(
    IPC_CHANNELS.IDEATION_DELETE_MULTIPLE,
    deleteMultipleIdeas
  );

  // Generation operations
  ipcMain.on(
    IPC_CHANNELS.IDEATION_GENERATE,
    (event, projectId, config) =>
      startIdeationGeneration(event, projectId, config, agentManager, getMainWindow())
  );

  ipcMain.on(
    IPC_CHANNELS.IDEATION_REFRESH,
    (event, projectId, config) =>
      refreshIdeationSession(event, projectId, config, agentManager, getMainWindow())
  );

  ipcMain.handle(
    IPC_CHANNELS.IDEATION_STOP,
    (event, projectId) =>
      stopIdeationGeneration(event, projectId, agentManager, getMainWindow())
  );

  // Task conversion
  ipcMain.handle(
    IPC_CHANNELS.IDEATION_CONVERT_TO_TASK,
    convertIdeaToTask
  );

  // ============================================
  // Ideation Agent Events → Renderer
  // ============================================

  agentManager.on('ideation-progress', (projectId: string, status: IdeationGenerationStatus) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send(IPC_CHANNELS.IDEATION_PROGRESS, projectId, status);
    }
  });

  agentManager.on('ideation-log', (projectId: string, log: string) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send(IPC_CHANNELS.IDEATION_LOG, projectId, log);
    }
  });

  agentManager.on('ideation-complete', (projectId: string, session: IdeationSession) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send(IPC_CHANNELS.IDEATION_COMPLETE, projectId, session);
    }
  });

  agentManager.on('ideation-error', (projectId: string, error: string) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send(IPC_CHANNELS.IDEATION_ERROR, projectId, error);
    }
  });

  agentManager.on('ideation-stopped', (projectId: string) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send(IPC_CHANNELS.IDEATION_STOPPED, projectId);
    }
  });

  // Handle streaming ideation type completion - load ideas for this type immediately
  agentManager.on('ideation-type-complete', (projectId: string, ideationType: string, ideasCount: number) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      // Read the type-specific ideas file and send to renderer
      const project = projectStore.getProject(projectId);
      if (project) {
        const typeFile = path.join(
          project.path,
          AUTO_BUILD_PATHS.IDEATION_DIR,
          `${ideationType}_ideas.json`
        );
        if (existsSync(typeFile)) {
          try {
            const content = readFileSync(typeFile, 'utf-8');
            const data = JSON.parse(content);
            const rawIdeas = data[ideationType] || [];
            // Transform ideas from snake_case to camelCase
            const ideas = rawIdeas.map((idea: any) => transformIdeaFromSnakeCase(idea));
            mainWindow.webContents.send(
              IPC_CHANNELS.IDEATION_TYPE_COMPLETE,
              projectId,
              ideationType,
              ideas
            );
          } catch (err) {
            console.error(`[Ideation] Failed to read ${ideationType} ideas:`, err);
          }
        }
      }
    }
  });

  agentManager.on('ideation-type-failed', (projectId: string, ideationType: string) => {
    const mainWindow = getMainWindow();
    if (mainWindow) {
      mainWindow.webContents.send(IPC_CHANNELS.IDEATION_TYPE_FAILED, projectId, ideationType);
    }
  });
}
