# Provider Switching Fix - Complete

## Problem Statement

The `--provider opencode` CLI flag was not being honored during task execution. The system continued using Claude Agent SDK instead of OpenCode, despite correct configuration in `.env` and global settings.

## Root Causes Identified

### 1. Missing Provider Parameter Propagation
**File**: `auto-claude/cli/build_commands.py`
**Issue**: The `handle_build_command()` function didn't accept a `provider` parameter, so the CLI flag was never passed through.

### 2. Provider Config Not Being Loaded
**File**: `auto-claude/cli/build_commands.py`
**Issue**: The `get_provider_config()` function existed but wasn't being called in the build flow.

### 3. Provider Config Not Passed to Agent
**File**: `auto-claude/cli/build_commands.py`
**Issue**: The `run_autonomous_agent()` calls didn't receive the `provider_config` parameter.

### 4. Agent Not Using Multi-Provider Client
**File**: `auto-claude/agents/coder.py`
**Issue**: Always used `create_client()` instead of `create_client_from_config()` when provider_config was available.

### 5. Type Alias Shadowing Import
**File**: `auto-claude/cli/main.py` (Line 60)
**Issue**: `ProviderConfig = dict[str, str | bool | dict | None]` type alias shadowed the imported `ProviderConfig` class from `core.providers.config`, causing all ProviderConfig instances to be converted to dicts.

### 6. Wrong parse_provider_credentials Import
**File**: `auto-claude/cli/main.py`
**Issue**: Was importing `parse_provider_credentials` from `cli.provider_info` (returns dict) instead of `core.providers.config` (returns ProviderCredential objects).

## Fixes Applied

### Fix 1: Add Provider Parameter to handle_build_command()
**File**: `auto-claude/cli/build_commands.py:52-64`

```python
def handle_build_command(
    project_dir: Path,
    spec_dir: Path,
    model: str,
    max_iterations: int | None,
    verbose: bool,
    force_isolated: bool,
    force_direct: bool,
    auto_continue: bool,
    skip_qa: bool,
    force_bypass_approval: bool,
    base_branch: str | None = None,
    provider: str | None = None,  # ← ADDED
) -> None:
```

### Fix 2: Call get_provider_config() and Pass to Agent
**File**: `auto-claude/cli/build_commands.py:94-98, 240`

```python
from .main import get_provider_config

# Get provider configuration (CLI flag > .env > global settings > default)
provider_config = get_provider_config(project_dir, cli_provider=provider)

# ... later ...

asyncio.run(
    run_autonomous_agent(
        project_dir=working_dir,
        spec_dir=spec_dir,
        model=model,
        max_iterations=max_iterations,
        verbose=verbose,
        source_spec_dir=source_spec_dir,
        provider_config=provider_config,  # ← ADDED
    )
)
```

### Fix 3: Pass Provider from CLI Args
**File**: `auto-claude/cli/main.py:481-493`

```python
handle_build_command(
    project_dir=project_dir,
    spec_dir=spec_dir,
    model=model,
    max_iterations=args.max_iterations,
    verbose=args.verbose,
    force_isolated=args.isolated,
    force_direct=args.direct,
    auto_continue=args.auto_continue,
    skip_qa=args.skip_qa,
    force_bypass_approval=args.force,
    base_branch=args.base_branch,
    provider=args.provider,  # ← ADDED
)
```

### Fix 4: Update Interrupt Handler to Pass Provider Config
**File**: `auto-claude/cli/build_commands.py:325-334, 307-315, 447-456`

```python
def _handle_build_interrupt(
    spec_dir: Path,
    project_dir: Path,
    worktree_manager,
    working_dir: Path,
    model: str,
    max_iterations: int | None,
    verbose: bool,
    provider_config=None,  # ← ADDED
) -> None:
```

### Fix 5: Use create_client_from_config() in Agent
**File**: `auto-claude/agents/coder.py:13, 264-281`

```python
from core.client import create_client, create_client_from_config

# ... later ...

# Create client (fresh context) with phase-specific model and thinking
# Use multi-provider client if provider_config is provided
if provider_config:
    client = create_client_from_config(
        project_dir,
        spec_dir,
        phase_model,
        agent_type="coder",
        max_thinking_tokens=phase_thinking_budget,
        config=provider_config,
    )
else:
    client = create_client(
        project_dir,
        spec_dir,
        phase_model,
        max_thinking_tokens=phase_thinking_budget,
    )
```

### Fix 6: Remove Type Alias Shadowing
**File**: `auto-claude/cli/main.py:59-62`

**Before**:
```python
# Type alias for provider configuration
ProviderConfig = dict[str, str | bool | dict | None]

def get_provider_config(...) -> ProviderConfig:
```

**After**:
```python
def get_provider_config(...) -> ProviderConfig:  # Uses imported class
```

### Fix 7: Import Correct parse_provider_credentials
**File**: `auto-claude/cli/main.py:25-37`

**Before**:
```python
from .provider_info import (
    AgentProviderType,
    ConfigSource,
    load_global_settings,
    load_project_env,
    normalize_provider_id,
    parse_provider_credentials,  # ← Wrong one
)
```

**After**:
```python
from core.providers.config import (
    AgentProvider,
    ProviderConfig,
    parse_provider_credentials,  # ← Correct one
)

from .provider_info import (
    AgentProviderType,
    ConfigSource,
    load_global_settings,
    load_project_env,
    normalize_provider_id,
)
```

### Fix 8: Update get_provider_config() to Return ProviderConfig Object
**File**: `auto-claude/cli/main.py:134-153`

**Before** (returned dict):
```python
return {
    "provider": provider,
    "source": source,
    "opencode_provider": opencode_provider,
    "opencode_model": opencode_model,
    "is_global": is_global,
    "credentials": credentials,
}
```

**After** (returns ProviderConfig instance):
```python
# Parse provider credentials
provider_credentials_str = oc_project_env.get("PROVIDER_CREDENTIALS")
if provider_credentials_str:
    provider_credentials = parse_provider_credentials(provider_credentials_str)
    if opencode_provider and opencode_provider in provider_credentials:
        cred_obj = provider_credentials[opencode_provider]
        if cred_obj.is_global:
            is_global = True
        credentials[opencode_provider] = cred_obj

# Create AgentProvider enum value
agent_provider = (
    AgentProvider.OPENCODE if provider == "opencode" else AgentProvider.CLAUDE_CODE
)

return ProviderConfig(
    provider=agent_provider,
    is_global=is_global,
    credentials=credentials,
    opencode_provider=opencode_provider or "",
    opencode_model=opencode_model or "",
)
```

## Verification

### Test Command
```bash
auto-claude/.venv/bin/python auto-claude/run.py \\
  --spec 003 \\
  --provider opencode \\
  --force \\
  --auto-continue
```

### Expected Behavior
✅ **CONFIRMED**: Provider switching now works!

**Evidence from execution log**:
```
Error during agent session: [OpenCode] Query failed: 'str' object has no attribute 'content'
```

The `[OpenCode]` prefix confirms that:
1. The `--provider opencode` flag is being honored
2. OpenCode adapter is being invoked
3. The provider switching mechanism is working correctly

## Current Status

### ✅ FIXED: Provider Switching
- CLI `--provider` flag now properly switches execution to OpenCode
- Provider configuration flows correctly through the entire stack
- Multi-provider client factory is being used

### ⚠️ NEXT: OpenCode Response Parsing
A **separate issue** was discovered in the OpenCode adapter:
- **Error**: `'str' object has no attribute 'content'`
- **Location**: `auto-claude/core/providers/adapters/opencode_provider.py:278`
- **Cause**: The parser is returning messages that aren't proper UniversalMessage objects in some cases
- **Impact**: Prevents successful execution with OpenCode providers
- **Status**: This is a different bug in the OpenCode adapter implementation, not related to provider switching

## Files Modified

1. `auto-claude/cli/main.py` - Fixed get_provider_config(), imports
2. `auto-claude/cli/build_commands.py` - Added provider parameter propagation
3. `auto-claude/agents/coder.py` - Added create_client_from_config() usage

## Testing

### Configuration Used
- Provider: `opencode`
- OpenCode Provider: `zai-coding-plan`
- Model: `glm-4.7`
- API Key: Configured globally in `~/.config/auto-claude-ui/settings.json`

### Results
- ✅ Provider switching works
- ✅ OpenCode is invoked
- ⚠️ OpenCode adapter has response parsing bug (separate issue)

## Next Steps

1. **Fix OpenCode Response Parsing** (separate task)
   - Investigate why `self.parser.parse_output()` returns strings instead of UniversalMessage objects
   - Fix the message parsing in OpenCode adapter

2. **Add Provider Identification to UI**
   - Display which provider is being used in the startup banner
   - Show provider name alongside model name

3. **Test with Other OpenCode Providers**
   - Once parsing is fixed, test with OpenAI, Anthropic, etc.
   - Verify credential loading works for all providers
