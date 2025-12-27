# Auto Claude UI

A desktop application for managing AI-driven development tasks using the Auto Claude autonomous coding framework.

## Quick Start

```bash
# 1. Clone the repo (if you haven't already)
git clone https://github.com/AndyMik90/Auto-Claude.git
cd Auto-Claude/auto-claude-ui

# 2. Install dependencies
npm install

# 3. Build the desktop app
npm run package:win    # Windows
npm run package:mac    # macOS
npm run package:linux  # Linux

# 4. Run the app
# Windows: .\dist\win-unpacked\Auto Claude.exe
# macOS:   open dist/mac-arm64/Auto\ Claude.app
# Linux:   ./dist/linux-unpacked/auto-claude
```

## Prerequisites

- Node.js 18+
- npm or pnpm
- Python 3.10+ (for auto-claude backend)
- **Windows only**: Visual Studio Build Tools 2022 with "Desktop development with C++" workload
- **Windows only**: Developer Mode enabled (Settings → System → For developers)

## How to Run

### Building for Production (Recommended)

Build the Electron desktop app for your platform:

```bash
# Build for Windows
npm run package:win

# Build for macOS
npm run package:mac

# Build for Linux
npm run package:linux
```

### Running the Production Build

After building, run the application from the `dist` folder:

```bash
# Windows - run the executable
.\dist\win-unpacked\Auto Claude.exe

# Windows - or use the installer
.\dist\Auto Claude Setup X.X.X.exe

# macOS
open dist/mac-arm64/Auto\ Claude.app

# Linux
./dist/linux-unpacked/auto-claude
```

### Development Mode

Auto Claude UI supports three development modes for different workflows:

#### 1. Electron Mode (Desktop Development)

Full desktop app with hot reload and IPC communication to Python backend:

```bash
npm run dev
```

This is the primary development mode that includes all features like auto-updates, native menus, and system integration.

#### 2. Browser Mode with Live Backend (Full-Stack Development)

Run the UI in a browser with real FastAPI backend for faster iteration without building Electron:

```bash
# Prerequisites: Install Python dependencies first
cd ../auto-claude
pip install -r requirements.txt

# Start both API server and Vite dev server
cd ../auto-claude-ui
npm run dev:browser:live
```

This mode provides:
- **API Server**: http://localhost:8766 (FastAPI with WebSocket support)
- **UI**: http://localhost:5173 (Vite dev server)
- **API Docs**: http://localhost:8766/docs (auto-generated)
- Real-time events via WebSocket
- Full backend functionality without Electron overhead

**Alternative: Manual Start (separate terminals)**
```bash
# Terminal 1: Start API server only
npm run start:api:live

# Terminal 2: Start Vite dev server
npm run dev:browser
```

#### 3. Browser Mode with Mocks (Offline UI Development)

Develop UI in browser with mocked backend data (no Python backend required):

```bash
npm run dev:browser
```

This mode is useful for:
- Frontend-only development
- UI testing without backend
- Offline development
- Upstream testing

**Runtime Detection**: The app automatically detects which mode to use:
1. If `window.electronAPI` exists → Use Electron IPC
2. If API server responds at port 8766 → Use HTTP Live API
3. Otherwise → Fall back to browser mocks

> **Note**: Some features like auto-updates and native integrations only work in packaged Electron builds.

## Distribution Files

After packaging, the `dist` folder contains:

| Platform | Files |
|----------|-------|
| macOS | `Auto Claude.app`, `.dmg`, `.zip` |
| Windows | `Auto Claude Setup X.X.X.exe` (installer), `.zip`, `win-unpacked/` |
| Linux | `.AppImage`, `.deb`, `linux-unpacked/` |

## Testing

```bash
# Run tests
npm run test
```

## Linting

```bash
# Run ESLint
npm run lint

# Run type checking
npm run typecheck
```

## Features

- **Project Management**: Add, configure, and switch between multiple projects
- **Kanban Board**: Visual task board with columns for Backlog, In Progress, AI Review, Human Review, and Done
- **Task Creation Wizard**: Form-based interface for creating new tasks
- **Real-Time Progress**: Live updates during agent execution via WebSocket
- **Human Review Workflow**: Review QA results and provide feedback
- **Theme Support**: Light and dark mode
- **Auto Updates**: Automatic update notifications
- **Multi-Runtime Support**: Run as Electron desktop app, browser with live API, or browser with mocks

## Tech Stack

### Frontend
- **Framework**: Electron + React 18 (TypeScript)
- **Build Tool**: electron-vite + electron-builder (Electron), Vite (browser)
- **UI Components**: Radix UI (shadcn/ui pattern)
- **Styling**: TailwindCSS
- **State Management**: Zustand

### Backend API (Browser Live Mode)
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn with WebSocket support
- **Real-Time**: WebSocket manager for event streaming
- **Documentation**: Auto-generated OpenAPI docs
- **IPC Bridge**: Subprocess management for CLI integration

## Environment Variables

### Electron Mode
- `CLAUDE_CODE_OAUTH_TOKEN`: OAuth token for Claude Code SDK (from auto-claude/.env)
- `FALKORDB_URL`: FalkorDB connection URL (optional)

### Browser Live Mode
Configure in `.env.development` for browser mode with live backend:

- `VITE_API_URL`: HTTP API base URL (default: `http://localhost:8766`)
- `VITE_WS_URL`: WebSocket server URL (default: `ws://localhost:8766`)

Example `.env.development`:
```env
VITE_API_URL=http://localhost:8766
VITE_WS_URL=ws://localhost:8766
```

## Architecture

### Three Runtime Modes

Auto Claude UI uses intelligent runtime detection to support multiple development workflows:

1. **Electron IPC Mode** (Desktop)
   - Full desktop application
   - IPC channels for backend communication
   - Native OS integration

2. **HTTP Live API Mode** (Browser + Backend)
   - FastAPI server on port 8766
   - WebSocket for real-time events
   - HTTP REST endpoints
   - Full backend functionality

3. **Browser Mock Mode** (Browser Only)
   - No backend required
   - Mocked API responses
   - UI-only development

The detection flow:
```
Check window.electronAPI exists?
  ├─ Yes → Use Electron IPC
  └─ No → Try HTTP health check at localhost:8766
      ├─ Success → Use HTTP Live API
      └─ Fail → Use Browser Mocks
```

### Backend API Structure

```
auto-claude/api/
├── server.py              # FastAPI app entry point
├── websocket/
│   └── manager.py         # WebSocket connection manager
├── routes/
│   ├── task.py           # Task execution endpoints
│   ├── project.py        # Project management
│   ├── workspace.py      # Git worktree operations
│   └── settings.py       # Settings management
└── utils/
    └── ipc_bridge.py     # Bridge to CLI logic
```

## Troubleshooting

### Browser Live Mode Issues

**Port 8766 already in use:**
```bash
# Kill process using port 8766
lsof -ti:8766 | xargs kill -9
```

**WebSocket connection fails:**
- Check Content Security Policy in `src/renderer/index.html`
- Ensure `connect-src` includes `http://localhost:8766 ws://localhost:8766`

**API server not starting:**
```bash
# Install Python dependencies
cd auto-claude
pip install -r requirements.txt

# Check for errors
python3 api/server.py --port 8766
```

**Browser shows mock mode instead of live API:**
- Verify API server is running: `curl http://localhost:8766/health`
- Check browser console for connection errors
- Ensure `.env.development` has correct URLs

## License

AGPL-3.0
