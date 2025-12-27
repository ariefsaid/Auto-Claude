/**
 * Browser mock for window.electronAPI
 * This allows the app to run in a regular browser for UI development/testing
 *
 * This module aggregates all mock implementations from separate modules
 * for better code organization and maintainability.
 *
 * Runtime Modes:
 * 1. Electron IPC - Desktop app with real backend (existing)
 * 2. HTTP Live API - Browser with FastAPI backend (NEW)
 * 3. Browser Mocks - Browser with fake data (existing, for offline dev)
 */

import type { ElectronAPI } from '../../shared/types';
import { createHttpApiClient } from './http-api-client';
import {
  projectMock,
  taskMock,
  workspaceMock,
  terminalMock,
  claudeProfileMock,
  contextMock,
  integrationMock,
  changelogMock,
  insightsMock,
  infrastructureMock,
  settingsMock
} from './mocks';

// Check if we're in a browser (not Electron)
const isElectron = typeof window !== 'undefined' && window.electronAPI !== undefined;

/**
 * Create mock electronAPI for browser
 * Aggregates all mock implementations from separate modules
 */
const browserMockAPI: ElectronAPI = {
  // Project Operations
  ...projectMock,

  // Task Operations
  ...taskMock,

  // Workspace Management
  ...workspaceMock,

  // Terminal Operations
  ...terminalMock,

  // Claude Profile Management
  ...claudeProfileMock,

  // Settings
  ...settingsMock,

  // Roadmap Operations
  getRoadmap: async () => ({
    success: true,
    data: null
  }),

  getRoadmapStatus: async () => ({
    success: true,
    data: { isRunning: false }
  }),

  saveRoadmap: async () => ({
    success: true
  }),

  generateRoadmap: (_projectId: string, _enableCompetitorAnalysis?: boolean, _refreshCompetitorAnalysis?: boolean) => {
    console.warn('[Browser Mock] generateRoadmap called');
  },

  refreshRoadmap: (_projectId: string, _enableCompetitorAnalysis?: boolean, _refreshCompetitorAnalysis?: boolean) => {
    console.warn('[Browser Mock] refreshRoadmap called');
  },

  updateFeatureStatus: async () => ({ success: true }),

  convertFeatureToSpec: async (projectId: string, _featureId: string) => ({
    success: true,
    data: {
      id: `task-${Date.now()}`,
      specId: '',
      projectId,
      title: 'Converted Feature',
      description: 'Feature converted from roadmap',
      status: 'backlog' as const,
      subtasks: [],
      logs: [],
      createdAt: new Date(),
      updatedAt: new Date()
    }
  }),

  stopRoadmap: async () => ({ success: true }),

  // Roadmap Event Listeners
  onRoadmapProgress: () => () => {},
  onRoadmapComplete: () => () => {},
  onRoadmapError: () => () => {},
  onRoadmapStopped: () => () => {},
  // Context Operations
  ...contextMock,

  // Environment Configuration & Integration Operations
  ...integrationMock,

  // Changelog & Release Operations
  ...changelogMock,

  // Insights Operations
  ...insightsMock,

  // Infrastructure & Docker Operations
  ...infrastructureMock
};

/**
 * Initialize browser API (mocks or HTTP client) if not running in Electron.
 *
 * Detection logic:
 * 1. Check if window.electronAPI exists → Electron IPC mode
 * 2. Try HTTP API health check → HTTP Live API mode
 * 3. Fall back to mocks → Browser Mock mode
 */
export async function initBrowserMock(): Promise<void> {
  // 1. Check if Electron
  if (isElectron) {
    console.log('%c[Runtime] Using Electron IPC mode', 'color: #4caf50; font-weight: bold;');
    return; // Use real IPC
  }

  // 2. Try HTTP API (NEW PORT 8766)
  try {
    const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8766';
    const response = await fetch(`${API_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000), // 2 second timeout
    });

    if (response.ok) {
      console.log('%c[Runtime] Using HTTP API mode', 'color: #2196f3; font-weight: bold;', {
        apiUrl: API_URL,
      });

      // Create HTTP client and assign to window.electronAPI
      const httpClient = createHttpApiClient();
      (window as Window & { electronAPI: any }).electronAPI = {
        ...browserMockAPI, // Spread mocks for unimplemented methods
        ...httpClient, // Override with real HTTP implementation
      };
      return;
    }
  } catch (error) {
    console.warn('[Runtime] API server not available, falling back to mock mode');
  }

  // 3. Fall back to mocks
  console.warn('%c[Browser Mock] Initializing mock electronAPI for browser preview', 'color: #f0ad4e; font-weight: bold;');
  (window as Window & { electronAPI: ElectronAPI }).electronAPI = browserMockAPI;
}

// Auto-initialize (async)
initBrowserMock();
