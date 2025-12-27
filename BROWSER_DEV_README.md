# Browser Development Environment + API Backend

This feature enables running the Auto Claude UI in a browser with a live FastAPI backend, providing an alternative to the Electron-based desktop app.

## Architecture

The Auto Claude UI now supports **three runtime modes**:

1. **Electron with IPC** (existing) - Desktop app with Node.js IPC communication
2. **Browser with HTTP/WebSocket** (NEW) - Browser app with FastAPI backend
3. **Browser with mocks** (existing) - Browser app with fake data for offline development

### Runtime Detection Flow

The UI automatically detects which mode to use:

```
1. Check if window.electronAPI exists → Use Electron IPC
2. Try HTTP health check (localhost:8766) → Use HTTP API client
3. Fall back to browser mocks → Use fake data
```

## Components

### FastAPI Backend (`auto-claude/api/`)

HTTP/WebSocket server that bridges browser requests to the Python backend:

```
auto-claude/api/
├── server.py              # Main FastAPI application
├── routes/
│   ├── project.py         # Project management endpoints
│   ├── task.py            # Task/spec operations
│   ├── workspace.py       # Git worktree operations
│   └── settings.py        # Settings management
├── websocket/
│   └── manager.py         # WebSocket connection manager
└── utils/
    └── ipc_bridge.py      # IPC compatibility layer
```

**Key Features:**
- RESTful API for all Auto Claude operations
- WebSocket for real-time events (logs, progress, status changes)
- CORS enabled for Vite dev server
- OpenAPI documentation at `/docs`

### HTTP Client (`auto-claude-ui/src/renderer/lib/http-api-client.ts`)

Browser-side client that implements the `ElectronAPI` interface using HTTP/WebSocket:

```typescript
// Automatically used when API server is detected
const client = createHttpApiClient();
client.getProjects(); // → GET /api/projects
client.createSpec(); // → POST /api/specs
```

### Browser Mock Layer (`auto-claude-ui/src/renderer/lib/browser-mock.ts`)

Enhanced to support runtime mode detection:

```typescript
// Checks API availability and falls back to mocks
await initBrowserMock();
```

## Setup

### 1. Install Dependencies

**Python (Backend):**
```bash
cd auto-claude
pip install -r requirements.txt
```

Required packages:
- `fastapi>=0.115.0`
- `uvicorn[standard]>=0.32.0`
- `websockets>=13.1`
- `python-multipart>=0.0.12`

**Node.js (Frontend):**
```bash
cd auto-claude-ui
pnpm install
```

Required packages:
- `concurrently` (for running API + Vite together)

### 2. Configuration

Create `.env.development` in `auto-claude-ui/`:

```env
VITE_API_URL=http://localhost:8766
```

### 3. Content Security Policy

The `index.html` CSP has been updated to allow API connections:

```html
connect-src 'self' http://localhost:8766 ws://localhost:8766
```

## Usage

### Development Scripts

**Run browser UI with live API backend:**
```bash
cd auto-claude-ui
pnpm dev:browser:live
```

This runs concurrently:
- Vite dev server on `http://localhost:5173`
- FastAPI server on `http://localhost:8766`

**Run browser UI only (uses mocks):**
```bash
cd auto-claude-ui
pnpm dev:browser
```

**Run API server separately:**
```bash
cd auto-claude
python api/server.py --port 8766 --reload
```

Options:
- `--port` - Port number (default: 8766)
- `--host` - Host to bind (default: localhost)
- `--reload` - Enable auto-reload on code changes

### API Documentation

When the server is running, visit:
- **Swagger UI:** http://localhost:8766/docs
- **ReDoc:** http://localhost:8766/redoc
- **Health Check:** http://localhost:8766/health

## API Endpoints

### Projects
- `GET /api/projects` - List all projects
- `GET /api/projects/{id}` - Get project details
- `POST /api/projects` - Create new project
- `DELETE /api/projects/{id}` - Delete project

### Tasks/Specs
- `GET /api/specs` - List all specs for a project
- `POST /api/specs` - Create new spec
- `GET /api/specs/{id}` - Get spec details
- `POST /api/specs/{id}/build` - Start autonomous build
- `GET /api/specs/{id}/status` - Get build status

### Workspace
- `POST /api/workspace/merge` - Merge worktree to main
- `POST /api/workspace/discard` - Discard worktree
- `GET /api/workspace/diff` - Get worktree changes

### Settings
- `GET /api/settings/global` - Get global settings
- `PUT /api/settings/global` - Update global settings
- `GET /api/settings/project/{id}` - Get project settings
- `PUT /api/settings/project/{id}` - Update project settings

### WebSocket Events

Connect to `ws://localhost:8766/ws/{client_id}` for real-time updates:

**Event Types:**
```typescript
{
  type: 'log',              // Task execution logs
  type: 'progress',         // Progress updates (0-100)
  type: 'error',            // Error messages
  type: 'status-change',    // Status changes (planning → coding → qa)
  type: 'execution-progress' // Phase transitions
}
```

## Benefits

### For Development
- **Faster iteration** - No Electron rebuild needed
- **Browser DevTools** - Full Chrome DevTools access
- **Hot Module Replacement** - Instant UI updates with Vite
- **API debugging** - Test backend independently via `/docs`

### For Deployment
- **Lighter weight** - No Electron bundle needed for web deployment
- **Cross-platform** - Works on any device with a browser
- **Remote access** - Can expose API for remote development
- **Container-friendly** - Easier to containerize FastAPI server

### For Testing
- **E2E testing** - Playwright tests can run against real backend
- **API testing** - Test endpoints independently
- **Integration testing** - Test frontend + backend together

## Testing

E2E tests have been added to verify browser mode:

```bash
cd auto-claude-ui
pnpm test:e2e
```

Test files:
- `e2e/provider-settings.e2e.ts` - Provider configuration UI tests
- `e2e/provider-ui-manual.e2e.ts` - Manual provider switching tests

## Architecture Decisions

### Why Port 8766?
- Avoids conflicts with common dev servers (3000, 8000, 8080)
- Easy to remember (8766 = "AUTO" on phone keypad)
- Not used by other Auto Claude components

### Why FastAPI?
- **Async by default** - Matches Claude SDK async patterns
- **Auto-generated docs** - OpenAPI/Swagger out of the box
- **Type hints** - Python type safety
- **WebSocket support** - Real-time event streaming
- **Fast** - Built on Starlette/Uvicorn

### Why not replace Electron?
- **Complementary** - Browser mode is an addition, not a replacement
- **Local file access** - Electron still better for deep OS integration
- **Desktop app** - Many users prefer native app experience
- **Both maintained** - Both modes share the same UI components

## Migration Guide

### From Electron-only Development

**Before:**
```bash
cd auto-claude-ui
pnpm dev  # Runs Electron
```

**After (Browser mode):**
```bash
cd auto-claude-ui
pnpm dev:browser:live  # Runs browser + API
```

**After (Electron - still works!):**
```bash
cd auto-claude-ui
pnpm dev  # Runs Electron (unchanged)
```

### Updating Components

Components automatically work in both modes because the `ElectronAPI` interface is implemented by both:
- **Electron:** `preload.ts` → IPC → Python subprocess
- **Browser:** `http-api-client.ts` → HTTP → FastAPI server

No component changes needed!

## Troubleshooting

### API Server Not Starting

**Error:** `Address already in use`
```bash
# Check what's using port 8766
lsof -i :8766
# Use different port
python api/server.py --port 8767
```

### WebSocket Connection Failed

**Error:** `WebSocket connection to 'ws://localhost:8766/ws/...' failed`

Check CSP in `index.html` allows WebSocket:
```html
connect-src 'self' http://localhost:8766 ws://localhost:8766
```

### API Returns 404

**Issue:** Endpoints not found

Verify API routes are mounted:
```python
app.include_router(task.router, prefix="/api", tags=["tasks"])
```

### CORS Errors

**Error:** `Access to fetch at 'http://localhost:8766' blocked by CORS`

Check Vite port is allowed in `server.py`:
```python
allow_origins=[
    "http://localhost:5173",  # Vite dev server
]
```

## Future Enhancements

- [ ] Add authentication/authorization
- [ ] Support remote API server (not just localhost)
- [ ] Add API rate limiting
- [ ] Implement request caching
- [ ] Add metrics/monitoring endpoints
- [ ] Support multiple concurrent clients
- [ ] Add API versioning (v1, v2)
- [ ] Docker container for API server
- [ ] Kubernetes deployment configs

## Contributing

When adding new features:

1. **Add to both modes** - Implement in both Electron IPC and HTTP API
2. **Update interface** - Add to `ElectronAPI` type definition
3. **Test both modes** - Verify works in Electron and browser
4. **Document endpoints** - Add to API docs if HTTP endpoint

## Related Files

### Modified
- `auto-claude-ui/package.json` - Added browser dev scripts
- `auto-claude-ui/src/renderer/index.html` - Updated CSP
- `auto-claude-ui/src/renderer/lib/browser-mock.ts` - Added HTTP detection
- `auto-claude/requirements.txt` - Added FastAPI dependencies

### New
- `auto-claude/api/` - Entire FastAPI backend
- `auto-claude-ui/src/renderer/lib/http-api-client.ts` - HTTP client
- `auto-claude-ui/vite.config.ts` - Vite configuration
- `auto-claude-ui/.env.development` - Development environment
- `auto-claude-ui/e2e/*.e2e.ts` - E2E tests

## License

Same as Auto Claude main project.
