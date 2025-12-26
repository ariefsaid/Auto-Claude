/**
 * Unit tests for Provider IPC handlers
 * Tests provider configuration operations between main and renderer processes
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { EventEmitter } from 'events';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import path from 'path';

// Test data directory
const TEST_DIR = '/tmp/provider-handlers-test';
const TEST_PROJECT_PATH = path.join(TEST_DIR, 'test-project');

// Mock electron-updater before importing
vi.mock('electron-updater', () => ({
  autoUpdater: {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    on: vi.fn(),
    checkForUpdates: vi.fn(() => Promise.resolve(null)),
    downloadUpdate: vi.fn(() => Promise.resolve()),
    quitAndInstall: vi.fn()
  }
}));

// Mock @electron-toolkit/utils before importing
vi.mock('@electron-toolkit/utils', () => ({
  is: {
    dev: true,
    windows: process.platform === 'win32',
    macos: process.platform === 'darwin',
    linux: process.platform === 'linux'
  },
  electronApp: {
    setAppUserModelId: vi.fn()
  },
  optimizer: {
    watchWindowShortcuts: vi.fn()
  }
}));

// Mock version-manager to return a predictable version
vi.mock('../updater/version-manager', () => ({
  getEffectiveVersion: vi.fn(() => '0.1.0'),
  getBundledVersion: vi.fn(() => '0.1.0'),
  parseVersionFromTag: vi.fn((tag: string) => tag.replace('v', '')),
  compareVersions: vi.fn(() => 0)
}));

// Mock modules before importing
vi.mock('electron', () => {
  const mockIpcMain = new (class extends EventEmitter {
    private handlers: Map<string, Function> = new Map();

    handle(channel: string, handler: Function): void {
      this.handlers.set(channel, handler);
    }

    removeHandler(channel: string): void {
      this.handlers.delete(channel);
    }

    async invokeHandler(channel: string, event: unknown, ...args: unknown[]): Promise<unknown> {
      const handler = this.handlers.get(channel);
      if (handler) {
        return handler(event, ...args);
      }
      throw new Error(`No handler for channel: ${channel}`);
    }

    getHandler(channel: string): Function | undefined {
      return this.handlers.get(channel);
    }
  })();

  return {
    app: {
      getPath: vi.fn((name: string) => {
        if (name === 'userData') return path.join(TEST_DIR, 'userData');
        return TEST_DIR;
      }),
      getAppPath: vi.fn(() => TEST_DIR),
      getVersion: vi.fn(() => '0.1.0'),
      isPackaged: false
    },
    ipcMain: mockIpcMain,
    dialog: {
      showOpenDialog: vi.fn(() => Promise.resolve({ canceled: false, filePaths: [TEST_PROJECT_PATH] }))
    },
    BrowserWindow: class {
      webContents = { send: vi.fn() };
    },
    shell: {
      openExternal: vi.fn(() => Promise.resolve())
    }
  };
});

// Setup test project structure
function setupTestProject(): void {
  mkdirSync(TEST_PROJECT_PATH, { recursive: true });
  mkdirSync(path.join(TEST_PROJECT_PATH, '.auto-claude', 'specs'), { recursive: true });
  mkdirSync(path.join(TEST_DIR, 'userData', 'store'), { recursive: true });
}

// Cleanup test directories
function cleanupTestDirs(): void {
  if (existsSync(TEST_DIR)) {
    rmSync(TEST_DIR, { recursive: true, force: true });
  }
}

describe('Provider IPC Handlers', () => {
  let ipcMain: EventEmitter & {
    handlers: Map<string, Function>;
    invokeHandler: (channel: string, event: unknown, ...args: unknown[]) => Promise<unknown>;
    getHandler: (channel: string) => Function | undefined;
  };
  let mockMainWindow: { webContents: { send: ReturnType<typeof vi.fn> } };
  let mockAgentManager: EventEmitter & {
    startSpecCreation: ReturnType<typeof vi.fn>;
    startTaskExecution: ReturnType<typeof vi.fn>;
    startQAProcess: ReturnType<typeof vi.fn>;
    killTask: ReturnType<typeof vi.fn>;
    configure: ReturnType<typeof vi.fn>;
  };
  let mockTerminalManager: {
    create: ReturnType<typeof vi.fn>;
    destroy: ReturnType<typeof vi.fn>;
    write: ReturnType<typeof vi.fn>;
    resize: ReturnType<typeof vi.fn>;
    invokeClaude: ReturnType<typeof vi.fn>;
    killAll: ReturnType<typeof vi.fn>;
  };
  let mockPythonEnvManager: {
    on: ReturnType<typeof vi.fn>;
    initialize: ReturnType<typeof vi.fn>;
    getStatus: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    cleanupTestDirs();
    setupTestProject();

    // Get mocked ipcMain
    const electron = await import('electron');
    ipcMain = electron.ipcMain as unknown as typeof ipcMain;

    // Create mock window
    mockMainWindow = {
      webContents: { send: vi.fn() }
    };

    // Create mock agent manager
    mockAgentManager = Object.assign(new EventEmitter(), {
      startSpecCreation: vi.fn(),
      startTaskExecution: vi.fn(),
      startQAProcess: vi.fn(),
      killTask: vi.fn(),
      configure: vi.fn()
    });

    // Create mock terminal manager
    mockTerminalManager = {
      create: vi.fn(() => Promise.resolve({ success: true })),
      destroy: vi.fn(() => Promise.resolve({ success: true })),
      write: vi.fn(),
      resize: vi.fn(),
      invokeClaude: vi.fn(),
      killAll: vi.fn(() => Promise.resolve())
    };

    mockPythonEnvManager = {
      on: vi.fn(),
      initialize: vi.fn(() => Promise.resolve({ ready: true, pythonPath: '/usr/bin/python3', venvExists: true, depsInstalled: true })),
      getStatus: vi.fn(() => Promise.resolve({ ready: true, pythonPath: '/usr/bin/python3', venvExists: true, depsInstalled: true }))
    };

    // Need to reset modules to re-register handlers
    vi.resetModules();
  });

  afterEach(() => {
    cleanupTestDirs();
    vi.clearAllMocks();
  });

  describe('provider:getStatus handler', () => {
    it('should return error for non-existent project', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:getStatus', {}, 'nonexistent-id');

      expect(result).toEqual({
        success: false,
        error: 'Project not found'
      });
    });

    it('should return default claude_code provider for new project', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add a project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('provider:getStatus', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { provider: string; source: string } }).data;
      expect(data.provider).toBe('claude_code');
      expect(data.source).toBe('default');
    });

    it('should read provider from project .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with .env file specifying opencode provider
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'AGENT_PROVIDER=opencode\nOPENCODE_PROVIDER=openai\nPROVIDER_CREDENTIALS={"openai":{"isGlobal":false,"apiKey":"sk-test"}}'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('provider:getStatus', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { provider: string; source: string; credentialSources: Record<string, string> } }).data;
      expect(data.provider).toBe('opencode');
      expect(data.source).toBe('project_env');
      expect(data.credentialSources.openai).toBe('project');
    });
  });

  describe('provider:validate handler', () => {
    it('should reject invalid agent provider type', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:validate', {}, {
        agentProvider: 'invalid_provider',
        agentProviderIsGlobal: false
      });

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { isValid: boolean; errors: string[] } }).data;
      expect(data.isValid).toBe(false);
      expect(data.errors).toContain("Invalid agent provider: 'invalid_provider'. Must be 'claude_code' or 'opencode'");
    });

    it('should require opencode provider when using opencode agent', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:validate', {}, {
        agentProvider: 'opencode',
        agentProviderIsGlobal: false
      });

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { isValid: boolean; errors: string[] } }).data;
      expect(data.isValid).toBe(false);
      expect(data.errors).toContain("OpenCode provider is required when using 'opencode' agent");
    });

    it('should validate successfully with valid opencode config', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:validate', {}, {
        agentProvider: 'opencode',
        agentProviderIsGlobal: false,
        opencodeProvider: 'openai',
        providerCredentials: {
          openai: { isGlobal: false, apiKey: 'sk-test-key' }
        }
      });

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { isValid: boolean; errors: string[]; warnings: string[] } }).data;
      expect(data.isValid).toBe(true);
      expect(data.errors).toHaveLength(0);
    });

    it('should validate successfully with claude_code config', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:validate', {}, {
        agentProvider: 'claude_code',
        agentProviderIsGlobal: false
      });

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { isValid: boolean; errors: string[] } }).data;
      expect(data.isValid).toBe(true);
    });

    it('should warn about invalid API key format for known providers', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:validate', {}, {
        agentProvider: 'opencode',
        agentProviderIsGlobal: false,
        opencodeProvider: 'openai',
        providerCredentials: {
          openai: { isGlobal: false, apiKey: 'invalid-key-format' }
        }
      });

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { isValid: boolean; warnings: string[] } }).data;
      // The validation should still pass but with a warning
      expect(data.isValid).toBe(true);
      expect(data.warnings).toContain('OpenAI API keys should start with "sk-"');
    });
  });

  describe('provider:addToGlobal handler', () => {
    it('should reject empty provider ID', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: '',
        displayName: 'Test',
        apiKey: 'test-key',
        isGlobal: true
      });

      expect(result).toEqual({
        success: false,
        error: 'Provider ID is required'
      });
    });

    it('should reject missing API key (except for Ollama)', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: '',
        isGlobal: true
      });

      expect(result).toEqual({
        success: false,
        error: 'API key is required'
      });
    });

    it('should allow Ollama without API key', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'ollama',
        displayName: 'Ollama (Local)',
        apiKey: '',
        isGlobal: true,
        baseUrl: 'http://localhost:11434/v1'
      });

      expect(result).toEqual({ success: true });
    });

    it('should successfully add provider to global settings', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'OpenAI',
        displayName: 'OpenAI',
        apiKey: 'sk-test-key-12345',
        isGlobal: true,
        defaultModel: 'gpt-4o'
      });

      expect(result).toEqual({ success: true });

      // Verify it was saved
      const configuredResult = await ipcMain.invokeHandler('provider:getConfigured', {});
      expect(configuredResult).toHaveProperty('success', true);
      const providers = (configuredResult as { data: { provider: string }[] }).data;
      expect(providers.some(p => p.provider === 'openai')).toBe(true);
    });

    it('should normalize provider ID when saving', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'Z.ai GLM 4.7',
        displayName: 'Z.ai GLM',
        apiKey: 'zai-test-key',
        isGlobal: true
      });

      // Verify normalized ID was used
      const configuredResult = await ipcMain.invokeHandler('provider:getConfigured', {});
      const providers = (configuredResult as { data: { provider: string }[] }).data;
      expect(providers.some(p => p.provider === 'zai-glm-47')).toBe(true);
    });
  });

  describe('provider:getConfigured handler', () => {
    it('should return empty array when no providers configured', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:getConfigured', {});

      expect(result).toHaveProperty('success', true);
      const providers = (result as { data: unknown[] }).data;
      expect(providers).toHaveLength(0);
    });

    it('should return all configured providers', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add two providers
      await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test-1',
        isGlobal: true
      });
      await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'anthropic',
        displayName: 'Anthropic',
        apiKey: 'sk-ant-test-1',
        isGlobal: true
      });

      const result = await ipcMain.invokeHandler('provider:getConfigured', {});

      expect(result).toHaveProperty('success', true);
      const providers = (result as { data: { provider: string }[] }).data;
      expect(providers).toHaveLength(2);
      expect(providers.map(p => p.provider)).toContain('openai');
      expect(providers.map(p => p.provider)).toContain('anthropic');
    });
  });

  describe('provider:removeGlobal handler', () => {
    it('should reject invalid provider ID', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:removeGlobal', {}, '');

      expect(result).toEqual({
        success: false,
        error: 'Invalid provider ID'
      });
    });

    it('should return error for non-existent provider', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const result = await ipcMain.invokeHandler('provider:removeGlobal', {}, 'nonexistent');

      expect(result).toEqual({
        success: false,
        error: "Provider 'nonexistent' not found in global settings"
      });
    });

    it('should successfully remove provider from global settings', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add a provider first
      await ipcMain.invokeHandler('provider:addToGlobal', {}, {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test-key',
        isGlobal: true
      });

      // Verify it exists
      let configuredResult = await ipcMain.invokeHandler('provider:getConfigured', {});
      let providers = (configuredResult as { data: unknown[] }).data;
      expect(providers).toHaveLength(1);

      // Remove it
      const result = await ipcMain.invokeHandler('provider:removeGlobal', {}, 'openai');
      expect(result).toEqual({ success: true });

      // Verify it's gone
      configuredResult = await ipcMain.invokeHandler('provider:getConfigured', {});
      providers = (configuredResult as { data: unknown[] }).data;
      expect(providers).toHaveLength(0);
    });
  });
});
