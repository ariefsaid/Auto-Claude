/**
 * Unit tests for Environment IPC handlers
 * Tests provider configuration serialization to .env files
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { EventEmitter } from 'events';
import { mkdirSync, writeFileSync, readFileSync, rmSync, existsSync } from 'fs';
import path from 'path';

// Test data directory
const TEST_DIR = '/tmp/env-handlers-test';
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

describe('Environment IPC Handlers - Provider Serialization', () => {
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

  describe('env:update handler - Provider Serialization', () => {
    it('should serialize AGENT_PROVIDER to .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      // Update env with provider config
      const result = await ipcMain.invokeHandler('env:update', {}, projectId, {
        agentProvider: 'opencode'
      });

      expect(result).toEqual({ success: true });

      // Verify .env file content
      const envPath = path.join(TEST_PROJECT_PATH, '.auto-claude', '.env');
      const content = readFileSync(envPath, 'utf-8');
      expect(content).toContain('AGENT_PROVIDER=opencode');
    });

    it('should serialize AGENT_PROVIDER_IS_GLOBAL to .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      // Update env with provider config
      await ipcMain.invokeHandler('env:update', {}, projectId, {
        agentProvider: 'opencode',
        agentProviderIsGlobal: true
      });

      // Verify .env file content
      const envPath = path.join(TEST_PROJECT_PATH, '.auto-claude', '.env');
      const content = readFileSync(envPath, 'utf-8');
      expect(content).toContain('AGENT_PROVIDER_IS_GLOBAL=true');
    });

    it('should serialize OPENCODE_PROVIDER to .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      // Update env with provider config
      await ipcMain.invokeHandler('env:update', {}, projectId, {
        agentProvider: 'opencode',
        opencodeProvider: 'openai'
      });

      // Verify .env file content
      const envPath = path.join(TEST_PROJECT_PATH, '.auto-claude', '.env');
      const content = readFileSync(envPath, 'utf-8');
      expect(content).toContain('OPENCODE_PROVIDER=openai');
    });

    it('should serialize OPENCODE_MODEL to .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      // Update env with provider config
      await ipcMain.invokeHandler('env:update', {}, projectId, {
        agentProvider: 'opencode',
        opencodeProvider: 'openai',
        opencodeModel: 'gpt-4o'
      });

      // Verify .env file content
      const envPath = path.join(TEST_PROJECT_PATH, '.auto-claude', '.env');
      const content = readFileSync(envPath, 'utf-8');
      expect(content).toContain('OPENCODE_MODEL=gpt-4o');
    });

    it('should serialize PROVIDER_CREDENTIALS as JSON to .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const credentials = {
        openai: { isGlobal: true },
        anthropic: { isGlobal: false, apiKey: 'sk-ant-test-key' }
      };

      // Update env with provider config
      await ipcMain.invokeHandler('env:update', {}, projectId, {
        agentProvider: 'opencode',
        providerCredentials: credentials
      });

      // Verify .env file content
      const envPath = path.join(TEST_PROJECT_PATH, '.auto-claude', '.env');
      const content = readFileSync(envPath, 'utf-8');
      expect(content).toContain('PROVIDER_CREDENTIALS=');

      // Extract and parse JSON
      const match = content.match(/PROVIDER_CREDENTIALS=(.+)/);
      expect(match).not.toBeNull();
      const parsed = JSON.parse(match![1]);
      expect(parsed).toEqual(credentials);
    });

    it('should serialize full provider config correctly', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const credentials = {
        'zai-glm-47': { isGlobal: false, apiKey: 'zai-test-key', model: 'glm-4.7' }
      };

      // Update env with full provider config
      await ipcMain.invokeHandler('env:update', {}, projectId, {
        agentProvider: 'opencode',
        agentProviderIsGlobal: false,
        opencodeProvider: 'zai-glm-47',
        opencodeModel: 'glm-4.7',
        providerCredentials: credentials
      });

      // Verify .env file content
      const envPath = path.join(TEST_PROJECT_PATH, '.auto-claude', '.env');
      const content = readFileSync(envPath, 'utf-8');

      expect(content).toContain('AGENT_PROVIDER=opencode');
      expect(content).toContain('AGENT_PROVIDER_IS_GLOBAL=false');
      expect(content).toContain('OPENCODE_PROVIDER=zai-glm-47');
      expect(content).toContain('OPENCODE_MODEL=glm-4.7');
      expect(content).toContain('PROVIDER_CREDENTIALS=');
    });
  });

  describe('env:get handler - Provider Parsing', () => {
    it('should parse AGENT_PROVIDER from .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'AGENT_PROVIDER=opencode\n'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { agentProvider: string } }).data;
      expect(data.agentProvider).toBe('opencode');
    });

    it('should parse AGENT_PROVIDER_IS_GLOBAL from .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'AGENT_PROVIDER=opencode\nAGENT_PROVIDER_IS_GLOBAL=true\n'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { agentProviderIsGlobal: boolean } }).data;
      expect(data.agentProviderIsGlobal).toBe(true);
    });

    it('should parse OPENCODE_PROVIDER from .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'AGENT_PROVIDER=opencode\nOPENCODE_PROVIDER=openai\n'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { opencodeProvider: string } }).data;
      expect(data.opencodeProvider).toBe('openai');
    });

    it('should parse OPENCODE_MODEL from .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'AGENT_PROVIDER=opencode\nOPENCODE_MODEL=gpt-4-turbo\n'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { opencodeModel: string } }).data;
      expect(data.opencodeModel).toBe('gpt-4-turbo');
    });

    it('should parse PROVIDER_CREDENTIALS JSON from .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const credentials = {
        openai: { isGlobal: true },
        anthropic: { isGlobal: false, apiKey: 'sk-ant-test' }
      };

      // Create project with .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        `AGENT_PROVIDER=opencode\nPROVIDER_CREDENTIALS=${JSON.stringify(credentials)}\n`
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { providerCredentials: Record<string, unknown> } }).data;
      expect(data.providerCredentials).toEqual(credentials);
    });

    it('should handle invalid PROVIDER_CREDENTIALS JSON gracefully', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with invalid JSON in .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'AGENT_PROVIDER=opencode\nPROVIDER_CREDENTIALS={invalid-json}\n'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { providerCredentials?: unknown } }).data;
      // Invalid JSON should result in undefined providerCredentials
      expect(data.providerCredentials).toBeUndefined();
    });

    it('should parse full provider config from .env file', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      const credentials = {
        'zai-glm-47': { isGlobal: false, apiKey: 'zai-key', model: 'glm-4.7' }
      };

      // Create project with full .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        `AGENT_PROVIDER=opencode
AGENT_PROVIDER_IS_GLOBAL=false
OPENCODE_PROVIDER=zai-glm-47
OPENCODE_MODEL=glm-4.7
PROVIDER_CREDENTIALS=${JSON.stringify(credentials)}
`
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: {
        agentProvider: string;
        agentProviderIsGlobal: boolean;
        opencodeProvider: string;
        opencodeModel: string;
        providerCredentials: Record<string, unknown>;
      } }).data;

      expect(data.agentProvider).toBe('opencode');
      expect(data.agentProviderIsGlobal).toBe(false);
      expect(data.opencodeProvider).toBe('zai-glm-47');
      expect(data.opencodeModel).toBe('glm-4.7');
      expect(data.providerCredentials).toEqual(credentials);
    });

    it('should default to claude_code when AGENT_PROVIDER is not set', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Create project with empty .env file
      writeFileSync(
        path.join(TEST_PROJECT_PATH, '.auto-claude', '.env'),
        'CLAUDE_CODE_OAUTH_TOKEN=test-token\n'
      );

      // Add project
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: { agentProvider?: string } }).data;
      // agentProvider should be undefined or not set (defaults handled elsewhere)
      expect(data.agentProvider).toBeUndefined();
    });
  });

  describe('Round-trip serialization', () => {
    it('should correctly serialize and deserialize provider config', async () => {
      const { setupIpcHandlers } = await import('../ipc-handlers');
      setupIpcHandlers(mockAgentManager as never, mockTerminalManager as never, () => mockMainWindow as never, mockPythonEnvManager as never);

      // Add project first
      const addResult = await ipcMain.invokeHandler('project:add', {}, TEST_PROJECT_PATH);
      const projectId = (addResult as { data: { id: string } }).data.id;

      const originalConfig = {
        agentProvider: 'opencode' as const,
        agentProviderIsGlobal: true,
        opencodeProvider: 'openai',
        opencodeModel: 'gpt-4o-mini',
        providerCredentials: {
          openai: { isGlobal: true },
          anthropic: { isGlobal: false, apiKey: 'sk-ant-test-12345' }
        }
      };

      // Write config
      await ipcMain.invokeHandler('env:update', {}, projectId, originalConfig);

      // Read config back
      const result = await ipcMain.invokeHandler('env:get', {}, projectId);

      expect(result).toHaveProperty('success', true);
      const data = (result as { data: typeof originalConfig }).data;

      expect(data.agentProvider).toBe(originalConfig.agentProvider);
      expect(data.agentProviderIsGlobal).toBe(originalConfig.agentProviderIsGlobal);
      expect(data.opencodeProvider).toBe(originalConfig.opencodeProvider);
      expect(data.opencodeModel).toBe(originalConfig.opencodeModel);
      expect(data.providerCredentials).toEqual(originalConfig.providerCredentials);
    });
  });
});
