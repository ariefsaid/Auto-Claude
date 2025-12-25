# AGENTS.md

This file provides guidance for agentic coding agents working in this repository.

## Commands

### Python (auto-claude/)

```bash
# Setup
cd auto-claude && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd auto-claude && uv pip install -r requirements.txt  # faster alternative

# Linting
ruff check                    # check linting
ruff check --fix             # auto-fix issues
ruff format                   # format code
pre-commit run --all-files   # run all pre-commit hooks

# Testing
.venv/bin/pytest tests/ -v                                   # all tests
.venv/bin/pytest tests/test_security.py -v                   # single file
.venv/bin/pytest tests/test_security.py::test_name -v        # single test
.venv/bin/pytest tests/ -m "not slow"                        # skip slow tests
.venv/bin/pytest tests/ --cov=auto-claude                    # coverage
```

### TypeScript/React (auto-claude-ui/)

```bash
# Setup
pnpm install

# Linting & Type Checking
pnpm lint                      # ESLint check
pnpm lint:fix                  # ESLint auto-fix
pnpm typecheck                 # TypeScript compiler check

# Testing
pnpm test                      # run tests
pnpm test:watch                # watch mode
pnpm test:coverage             # with coverage
pnpm test:e2e                  # Playwright E2E tests

# Build
pnpm dev                       # development
pnpm build                     # production build
```

## Code Style

### Python

**Imports:**
- Use `from X import Y` for module imports (isort style)
- Group imports: stdlib → third-party → local
- Type-only imports: `from typing import TYPE_CHECKING` and use string annotations in `if TYPE_CHECKING:` blocks

**Formatting:**
- Double quotes for strings
- Space indentation (4 spaces)
- Line length: let ruff-format handle (E501 ignored in ruff.toml)
- Type hints using `|` union syntax (Python 3.10+): `str | None`

**Naming:**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`

**Error Handling:**
- Use specific exception types: `except (OSError, json.JSONDecodeError)`
- Try-except for file I/O, network calls
- Return `None` on recoverable errors, raise on critical failures
- Use context managers for resources: `with open(path) as f:`

**Documentation:**
- Module-level docstrings with triple quotes
- Docstrings for all public functions/classes using Google or reST style
- Use `__all__` to explicitly export public API

### TypeScript/React

**Imports:**
- Named imports preferred: `import { useState } from 'react'`
- Absolute imports for app code: `import { cn } from '@/lib/utils'`
- Shared imports: `import { X } from '@shared/*'`

**Formatting:**
- Double quotes for strings
- Semicolons required
- 2-space indentation
- Trailing commas in multi-line arrays/objects

**Naming:**
- Functions/variables: `camelCase`
- Components: `PascalCase`
- Types/interfaces: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Unused vars: `_prefix` (ESLint configured to allow)

**React:**
- Functional components with hooks
- Props interfaces with `extends React.HTMLAttributes<...>`
- Use `forwardRef` when needed
- No `prop-types` (TypeScript instead)
- displayName for named exports

**Error Handling:**
- TypeScript strict mode enabled
- Avoid `any` (ESLint warns)
- Use `unknown` with type guards
- Try-catch for async operations

**Documentation:**
- JSDoc for functions with `@param` and `@returns`
- Component prop interfaces with comments
- Describe complex utilities with docstrings

## Architecture Notes

- **Python**: Facade pattern in root files (e.g., `client.py`, `workspace.py`) re-exports from `core/` and `agents/` packages
- **TypeScript**: Layered architecture (main, preload, renderer, shared)
- **Security**: Dynamic command allowlisting via project analysis
- **Memory**: Dual-layer (file-based primary, Graphiti optional)
- **Testing**: Use pytest markers (`@pytest.mark.slow`) for slow tests
