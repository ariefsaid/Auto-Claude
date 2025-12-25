# Epic: Multi-Provider CLI Support for Auto-Claude

**Quick MVP: Claude Code + OpenCode Integration**

---

## Executive Summary

Transform Auto-Claude from a Claude Code SDK-exclusive framework into a provider-agnostic platform that supports multiple agentic coding CLIs. This epic focuses on a **Quick MVP** delivering Claude Code + OpenCode support with zero breaking changes to existing workflows.

### MVP Scope
- **Primary Provider**: Claude Code (default, existing integration)
- **New Provider**: OpenCode (Go-based, multi-provider CLI)
- **Configuration**: CLI flags, environment variables, AND UI-based selection
- **Timeline**: 3-4 weeks
- **Backward Compatibility**: 100% (zero breaking changes)
- **Local Models**: Not in scope (cloud providers only)

### Business Value
- **Cost Flexibility**: Use OpenCode with OpenAI/Google/AWS Bedrock for cost optimization
  - **Z.ai GLM 4.7**: $3/month for advanced thinking (vs $100s with Claude)
  - **OpenRouter**: Auto-fallback to cheapest of 400+ models
- **Competition**: Position Auto-Claude as provider-agnostic vs Claude-only frameworks
- **Resilience**: Eliminate single-provider dependency
- **User Choice**: Let developers use their preferred AI provider
- **Advanced Features**: Access Z.ai's turn-level thinking and "Vibe Coding" capabilities

### Recommended Provider Combinations

**For Budget-Conscious Development:**
- Primary: Z.ai GLM 4.7 ($3/month unlimited coding)
- Fallback: OpenRouter (auto-select cheapest model)

**For Production Quality:**
- Primary: Claude Code (Sonnet 4.5)
- Secondary: Z.ai GLM 4.7 (complex tasks with thinking)

**For Maximum Flexibility:**
- OpenRouter as primary (access to 400+ models)
- Auto-fallback between providers based on cost/availability

---

## Current State Analysis

### Deep Claude SDK Integration (17+ Files)

Auto-Claude is tightly coupled to Claude Code SDK through:

**Core Dependencies:**
1. **client.py** (`auto-claude/core/client.py:19,132-364`) - Primary integration point using `ClaudeSDKClient`
2. **session.py** (`auto-claude/agents/session.py:12,314-551`) - Message handling using `AssistantMessage`, `TextBlock`, `ToolUseBlock`
3. **auth.py** - OAuth-only authentication (`CLAUDE_CODE_OAUTH_TOKEN`)
4. **hooks.py** (`auto-claude/security/hooks.py:20-104`) - Security hooks using `HookMatcher` pattern
5. **17+ additional files** - Direct imports of `claude_agent_sdk`

**Message Flow:**
```
User Prompt → ClaudeSDKClient.query()
    ↓
client.receive_response() (async generator)
    ↓
AssistantMessage.content → [TextBlock | ToolUseBlock]
    ↓
UserMessage.content → [ToolResultBlock]
```

**Security Model:**
- JSON settings file (`.claude_settings.json`)
- Sandbox with `autoAllowBashIfSandboxed`
- Permissions array with glob patterns
- Hook system: `PreToolUse` with `HookMatcher`
- Bash command allowlist validation

**MCP Integration:**
- Multiple servers: context7, linear, graphiti, puppeteer, electron
- Server format: `{"command": "npx", "args": [...]}`
- Tool names: `mcp__<server>__<tool>`

---

## OpenCode Research Findings

**What is OpenCode?**
- Open-source CLI alternative to Claude Code (github.com/sst/opencode)
- Go-based with TUI (Terminal User Interface)
- **Provider-agnostic**: supports OpenAI, Anthropic, Google Gemini, AWS Bedrock, Groq, Azure OpenAI, Z.ai, OpenRouter
- **Flexible Authentication**: API key-based (simplifies multi-provider setup)
- **Custom Provider Support**: Can configure additional providers via `~/.config/opencode/.opencode.json`
- SQLite storage for sessions
- LSP integration
- Two built-in agents: Build and Plan
- Non-interactive run mode for scripting

**Notable Providers:**

1. **Z.ai GLM 4.7** (Released Dec 2025)
   - 200K context window, 128K output capacity
   - Advanced thinking modes: Interleaved, Preserved, Turn-level
   - 73.8% SWE-bench score (state-of-the-art for open models)
   - "Vibe Coding" for modern UI generation
   - **$0.40/1M tokens** or **$3/month** GLM Coding Plan
   - Auth: API key from [Z.AI API Console](https://z.ai/manage-apikey/apikey-list)

2. **OpenRouter** (Meta-Provider)
   - Unified API for 400+ models
   - OpenAI-compatible endpoint
   - Auto-fallback and cost optimization
   - Variable pricing based on selected model
   - Auth: API key from [OpenRouter Dashboard](https://openrouter.ai/)

**Key Differences from Claude Code:**
| Feature | Claude Code | OpenCode |
|---------|-------------|----------|
| Language | TypeScript (SDK) | Go (CLI) |
| Interface | SDK + TUI | CLI/TUI |
| Authentication | OAuth | API Keys |
| Sandbox | OS-level | None (relies on command validation) |
| MCP Support | Native | LSP-based |
| Hooks | PreToolUse | None (validate via tool wrappers) |
| Thinking | 16K tokens | Model-dependent |
| Session Storage | In-memory | SQLite |

---

## Technical Architecture (MVP)

### Layer 1: Provider Abstraction (Core)

```
┌─────────────────────────────────────────────────────────┐
│              Auto-Claude Core Logic                     │
│  (agents, spec, qa, orchestration - NO CHANGES)        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│         Provider Abstraction Layer (NEW)                │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ AgentClient │  │   Message    │  │    Tool       │ │
│  │  Protocol   │  │  Normalizer  │  │   Registry    │ │
│  └─────────────┘  └──────────────┘  └───────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │        Provider Factory                             ││
│  │   create_client(config) -> AgentClient             ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          ↓
         ┌────────────────┴────────────────┐
         │                                  │
┌────────▼────────┐             ┌──────────▼─────────┐
│ ClaudeProvider  │             │  OpenCodeProvider  │
│ (SDK wrapper)   │             │  (CLI wrapper)     │
└─────────────────┘             └────────────────────┘
```

### Layer 2: Configuration & Provider Selection

**Configuration Architecture: Global + Project-Level Inheritance**

Auto-Claude uses a **two-tier configuration system** following the existing credential management pattern:

```
┌─────────────────────────────────────────────────────────┐
│  Global Settings (User-Level Defaults)                  │
│  Location: ~/.config/auto-claude-ui/settings.json      │
│                                                          │
│  - Set credentials ONCE at user level                   │
│  - Default provider for all projects                    │
│  - Never committed to git                               │
│  - Secure local storage                                 │
└─────────────────────────────────────────────────────────┘
                          ↓ (inherits by default)
┌─────────────────────────────────────────────────────────┐
│  Project Settings (Per-Project Overrides)               │
│  Location: <project>/.auto-claude/.env (gitignored)    │
│                                                          │
│  - Override global defaults for specific projects       │
│  - Project-specific integrations (Linear, GitHub)       │
│  - Tracks inheritance with "isGlobal" flags             │
│  - Allows different providers per project               │
└─────────────────────────────────────────────────────────┘
```

**Configuration Precedence (Priority Order):**
1. **CLI Flags**: `--provider opencode` (highest priority, temporary override)
2. **Project-Level Override**: `.auto-claude/.env` file (project-specific config)
3. **Global Defaults**: `~/.config/auto-claude-ui/settings.json` (user defaults)
4. **Hardcoded Default**: `claude_code` (backward compatibility)

**Environment Variables (Project-Level .env):**
```bash
# Project-Level Configuration (.auto-claude/.env)
# ------------------------------------------------
# These override global defaults for this project only

# Provider selection (if not set, inherits from global)
AGENT_PROVIDER=opencode  # Override: use OpenCode for this project
AGENT_PROVIDER_IS_GLOBAL=false  # Tracks that this is a project-specific override

# OpenCode Provider Selection
OPENCODE_PROVIDER=zai  # Which provider OpenCode should route to

# ✅ Generic Credential Store (JSON format)
# Maps provider → credential config with inheritance tracking
PROVIDER_CREDENTIALS='{"zai":{"isGlobal":true}}'  # Use global zai credential

# OR Project-Specific Override:
# PROVIDER_CREDENTIALS='{"zai":{"isGlobal":false,"apiKey":"project-zai-key","model":"glm-4.7"}}'

# Claude Code (for backward compatibility when using claude_code provider)
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...  # OR leave empty to use global
CLAUDE_TOKEN_IS_GLOBAL=true  # Inherits from global settings

# Example Scenarios:
# ------------------

# Scenario 1: Use Global Z.ai Key (Inherits Everything)
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=zai
PROVIDER_CREDENTIALS='{"zai":{"isGlobal":true}}'
# → Uses zai credential from global providerCredentials store

# Scenario 2: Client-Specific OpenRouter Account (Project Override)
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openrouter
PROVIDER_CREDENTIALS='{"openrouter":{"isGlobal":false,"apiKey":"sk-or-client-xxxxx"}}'
# → Uses project-specific OpenRouter key, overrides global

# Scenario 3: Multiple Providers in One Project (Advanced)
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=zai
PROVIDER_CREDENTIALS='{"zai":{"isGlobal":true},"openai":{"isGlobal":false,"apiKey":"sk-test-key"}}'
# → Uses global zai, project-specific openai (for testing different providers)

# Scenario 4: Inherit Everything from Global (minimal .env)
# Leave .env empty or minimal → all credentials from global settings
AGENT_PROVIDER_IS_GLOBAL=true
# → Uses global default provider + global credentials
```

**Global Configuration (User-Level Defaults):**
```typescript
// ~/.config/auto-claude-ui/settings.json
{
  "globalDefaultProvider": "opencode",  // Default for all new projects

  // ✅ Dynamic Credential Store (ANY provider supported via normalization)
  "providerCredentials": {
    // Standard providers (normalized IDs)
    "claude": {
      "provider": "claude",
      "displayName": "Claude (Anthropic)",
      "apiKey": "sk-ant-oat01-xxxxx",
      "defaultModel": "claude-sonnet-4-5"
    },
    "openai": {
      "provider": "openai",
      "displayName": "OpenAI",
      "apiKey": "sk-xxxxx",
      "defaultModel": "gpt-5o"
    },
    // Multi-word providers (normalized: "Z.ai GLM" → "zai-glm")
    "zai-glm": {
      "provider": "zai-glm",
      "displayName": "Z.ai GLM 4.7",
      "apiKey": "zai-xxxxx",
      "defaultModel": "glm-4.7",
      "metadata": {
        "subscription": "premium",
        "advancedThinking": true,
        "vibeCoding": true
      }
    },
    // OpenRouter (normalized: "OpenRouter" → "openrouter")
    "openrouter": {
      "provider": "openrouter",
      "displayName": "OpenRouter (400+ Models)",
      "apiKey": "sk-or-xxxxx",
      "defaultModel": "auto",
      "metadata": {
        "autoFallback": true,
        "costOptimization": true
      }
    },
    // AWS Bedrock (normalized: "AWS Bedrock" → "aws-bedrock")
    "aws-bedrock": {
      "provider": "aws-bedrock",
      "displayName": "AWS Bedrock",
      "apiKey": "aws-access-key",
      "defaultModel": "anthropic.claude-v3-5",
      "metadata": {
        "region": "us-east-1",
        "awsSecretKey": "encrypted-secret"
      }
    },
    // Custom self-hosted LLM (normalized: "Company LLM" → "company-llm")
    "company-llm": {
      "provider": "company-llm",
      "displayName": "Company Internal LLM",
      "apiKey": "internal-key",
      "baseUrl": "https://llm.company.com/v1",
      "defaultModel": "company-model-v2",
      "metadata": {
        "protocol": "openai-compatible",
        "vpnRequired": true
      }
    }
  },

  // OpenCode Default Configuration
  "globalOpencodeProvider": "zai-glm",  // Default provider (normalized ID)
  "globalOpencodeModel": "glm-4.7"  // Default model (optional override)
}
```

**Provider Addition Flow (Fully Dynamic):**
```
User enters provider name: "Z.ai GLM"
    ↓
Normalize: normalize_provider_id("Z.ai GLM") → "zai-glm"
    ↓
Store in providerCredentials["zai-glm"]
    ↓
Available in OpenCode provider dropdown as "Z.ai GLM 4.7"
    ↓
No code changes needed!
```

**Custom Provider Configuration (Advanced):**

OpenCode supports custom providers via `~/.config/opencode/.opencode.json`:

```json
{
  "providers": {
    "custom-provider": {
      "apiKey": "your-api-key",
      "baseURL": "https://api.custom-provider.com/v1",
      "models": ["custom-model-1", "custom-model-2"]
    }
  }
}
```

This enables integration with:
- Self-hosted LLM endpoints
- Enterprise API gateways
- Regional AI providers
- Custom model deployments

**UI Integration Flow:**
```
User selects provider in UI Settings
    ↓
UI saves to ProjectEnvConfig (TypeScript)
    ↓
IPC handler writes to .auto-claude/.env
    ↓
Backend reads AGENT_PROVIDER from .env
    ↓
ProviderFactory creates appropriate client
```

**Provider Normalization (Dynamic, No Hardcoded Lists):**
```python
# auto-claude/core/providers/utils.py (NEW)
def normalize_provider_id(name: str) -> str:
    """Normalize provider name to a consistent key format.

    Rules:
    - Lowercase
    - Spaces → hyphens
    - Remove special chars except hyphens
    - Trim whitespace

    Examples:
    - "OpenAI" → "openai"
    - "Z.ai GLM" → "zai-glm"
    - "My Custom LLM" → "my-custom-llm"
    - "AWS Bedrock" → "aws-bedrock"
    """
    import re
    # Lowercase and replace spaces with hyphens
    normalized = name.lower().strip().replace(' ', '-')
    # Remove special chars except hyphens and alphanumeric
    normalized = re.sub(r'[^a-z0-9-]', '', normalized)
    # Remove consecutive hyphens
    normalized = re.sub(r'-+', '-', normalized)
    # Trim leading/trailing hyphens
    return normalized.strip('-')
```

**Configuration Pattern (with Global/Project Inheritance):**
```python
# auto-claude/core/providers/config.py (NEW)
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import os
from .utils import normalize_provider_id

class AgentProvider(str, Enum):
    CLAUDE_CODE = "claude_code"
    OPENCODE = "opencode"

@dataclass
class ProviderCredential:
    """Generic credential for any provider with inheritance support.

    Provider IDs are auto-normalized via normalize_provider_id():
    - "OpenAI" → "openai"
    - "Z.ai GLM" → "zai-glm"
    - "My Custom LLM" → "my-custom-llm"

    This allows ANY provider to be added without code changes.
    """
    provider: str  # Normalized provider ID (auto-generated from display name)
    display_name: str = ""  # Human-readable name (e.g., "Z.ai GLM 4.7")
    api_key: str = ""
    is_global: bool = True  # True = inherit from global, False = project-specific
    base_url: Optional[str] = None  # For custom endpoints (OpenAI-compatible APIs)
    default_model: Optional[str] = None
    metadata: dict = None  # Extensible for provider-specific config

    def __post_init__(self):
        # Auto-generate display name from provider if not set
        if not self.display_name:
            self.display_name = self.provider.replace('-', ' ').title()

@dataclass
class ProviderConfig:
    """Provider configuration with global/project-level inheritance support.

    Follows the existing Auto-Claude pattern where:
    - Global settings provide defaults (set once, use everywhere)
    - Project settings override when needed
    - Inheritance is tracked with is_global flags
    """

    provider: AgentProvider = AgentProvider.CLAUDE_CODE
    provider_is_global: bool = True  # Tracks if provider is from global settings

    # ✅ Generic credential store (replaces individual API key fields)
    credentials: dict[str, ProviderCredential] = None  # Maps provider ID → credential

    # OpenCode-specific settings (which provider to route to)
    opencode_provider: str = "openai"
    opencode_model: str = "gpt-5o-mini"

    def __post_init__(self):
        if self.credentials is None:
            self.credentials = {}

    @classmethod
    def from_env(cls, global_settings: Optional[dict] = None) -> "ProviderConfig":
        """Load config from environment variables with global fallback.

        Priority:
        1. Project .env file (highest)
        2. Global settings dict (from ~/.config/auto-claude-ui/settings.json)
        3. Hardcoded defaults

        Args:
            global_settings: Optional dict of global user settings
        """
        global_settings = global_settings or {}

        # Provider selection with fallback
        project_provider = os.getenv("AGENT_PROVIDER")
        if project_provider:
            provider = AgentProvider(project_provider)
            provider_is_global = os.getenv("AGENT_PROVIDER_IS_GLOBAL", "false").lower() == "true"
        else:
            # Fall back to global default
            provider = AgentProvider(global_settings.get("globalDefaultProvider", "claude_code"))
            provider_is_global = True

        # OpenCode provider selection
        opencode_provider = os.getenv("OPENCODE_PROVIDER",
                                     global_settings.get("globalOpencodeProvider", "openai"))
        opencode_model = os.getenv("OPENCODE_MODEL",
                                  global_settings.get("globalOpencodeModel", "gpt-5o-mini"))

        # ✅ Load credentials from generic store
        credentials = cls._load_credentials(global_settings)

        return cls(
            provider=provider,
            provider_is_global=provider_is_global,
            credentials=credentials,
            opencode_provider=opencode_provider,
            opencode_model=opencode_model
        )

    @classmethod
    def _load_credentials(cls, global_settings: dict) -> dict[str, ProviderCredential]:
        """Load credentials from PROVIDER_CREDENTIALS env var with global fallback.

        Returns:
            dict mapping provider ID → ProviderCredential
        """
        import json

        credentials = {}

        # 1. Load project-level credentials (from .env)
        project_creds_json = os.getenv("PROVIDER_CREDENTIALS", "{}")
        try:
            project_creds = json.loads(project_creds_json)
            for provider_id, cred_data in project_creds.items():
                is_global = cred_data.get("isGlobal", True)

                if is_global:
                    # Inherit from global settings
                    global_cred = global_settings.get("providerCredentials", {}).get(provider_id)
                    if global_cred:
                        credentials[provider_id] = ProviderCredential(
                            provider=global_cred.get("provider", provider_id),
                            api_key=global_cred.get("apiKey", ""),
                            is_global=True,
                            base_url=global_cred.get("baseUrl"),
                            default_model=global_cred.get("defaultModel"),
                            metadata=global_cred.get("metadata", {})
                        )
                else:
                    # Project-specific credential
                    credentials[provider_id] = ProviderCredential(
                        provider=provider_id,
                        api_key=cred_data.get("apiKey", ""),
                        is_global=False,
                        base_url=cred_data.get("baseUrl"),
                        default_model=cred_data.get("model"),  # Note: "model" in project, "defaultModel" in global
                        metadata=cred_data.get("metadata", {})
                    )
        except json.JSONDecodeError:
            pass  # Invalid JSON, fall back to empty credentials

        # 2. Load legacy Claude token if present (backward compatibility)
        claude_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        claude_is_global = os.getenv("CLAUDE_TOKEN_IS_GLOBAL", "true").lower() == "true"
        if claude_token or claude_is_global:
            if claude_is_global and not claude_token:
                # Use global providerCredentials for claude
                global_claude = global_settings.get("providerCredentials", {}).get("claude", {})
                claude_token = global_claude.get("apiKey", "")

            if claude_token:
                credentials["claude"] = ProviderCredential(
                    provider="claude",
                    api_key=claude_token,
                    is_global=claude_is_global
                )

        return credentials

    def get_credential(self, provider_id: str) -> Optional[ProviderCredential]:
        """Get credential for a specific provider.

        Args:
            provider_id: Provider ID (e.g., 'openai', 'zai', 'claude')

        Returns:
            ProviderCredential or None if not found
        """
        return self.credentials.get(provider_id)

    def is_valid(self) -> bool:
        """Validate configuration has required credentials."""
        if self.provider == AgentProvider.CLAUDE_CODE:
            claude_cred = self.get_credential("claude")
            return bool(claude_cred and claude_cred.api_key)
        elif self.provider == AgentProvider.OPENCODE:
            # Check if credential exists for selected OpenCode provider
            provider_cred = self.get_credential(self.opencode_provider)
            return bool(provider_cred and provider_cred.api_key and self.opencode_provider)
        return False

    def get_validation_errors(self) -> list[str]:
        """Get list of validation errors."""
        errors = []

        if self.provider == AgentProvider.CLAUDE_CODE:
            claude_cred = self.get_credential("claude")
            if not claude_cred or not claude_cred.api_key:
                errors.append("Claude Code requires 'claude' credential in providerCredentials")
        elif self.provider == AgentProvider.OPENCODE:
            if not self.opencode_provider:
                errors.append("OpenCode requires OPENCODE_PROVIDER to be set")
            else:
                provider_cred = self.get_credential(self.opencode_provider)
                if not provider_cred or not provider_cred.api_key:
                    errors.append(
                        f"OpenCode with {self.opencode_provider} requires credential "
                        f"in providerCredentials (global or project-level)"
                    )

        return errors

    def get_credential_source_info(self) -> dict:
        """Return info about where credentials came from (for UI display)."""
        cred_info = {}

        for provider_id, cred in self.credentials.items():
            cred_info[provider_id] = {
                "provider": cred.provider,
                "configured": bool(cred.api_key),
                "source": "global" if cred.is_global else "project",
                "hasCustomEndpoint": bool(cred.base_url),
                "defaultModel": cred.default_model
            }

        return {
            "provider": {
                "value": self.provider.value,
                "source": "global" if self.provider_is_global else "project"
            },
            "credentials": cred_info
        }
```

### Layer 3: UI Integration Layer

**Auto-Claude UI (Electron App) Integration:**

The Electron app provides a visual interface for provider configuration:

**Architecture:**
```
┌─────────────────────────────────────────────────────────┐
│        Electron Renderer (React + TypeScript)          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Settings Dialog → Project Settings              │  │
│  │    └── AgentProviderSection.tsx                  │  │
│  │        - Provider dropdown (Claude Code/OpenCode)│  │
│  │        - Conditional credential fields           │  │
│  │        - Provider status badge                   │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────┘
                            │ IPC (invoke)
┌───────────────────────────▼─────────────────────────────┐
│          Electron Main Process (Node.js)                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  env-handlers.ts                                 │  │
│  │    - generateEnvContent()                        │  │
│  │    - Writes AGENT_PROVIDER to .env              │  │
│  │    - Writes provider credentials                 │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────┘
                            │ File Write
┌───────────────────────────▼─────────────────────────────┐
│         .auto-claude/.env (Project Config)              │
│  AGENT_PROVIDER=opencode                                │
│  OPENCODE_PROVIDER=openai                               │
│  OPENCODE_API_KEY=sk-...                                │
│  OPENCODE_MODEL=gpt-5o                                  │
└───────────────────────────┬─────────────────────────────┘
                            │ Read
┌───────────────────────────▼─────────────────────────────┐
│       Python Backend (Auto-Claude CLI)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  core/providers/config.py                        │  │
│  │    - ProviderConfig.from_env()                   │  │
│  │    - Loads AGENT_PROVIDER from .env              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**UI Component Patterns (Following Existing Architecture):**

1. **Settings Dialog**: Full-screen with sidebar navigation
   - App Settings (global defaults)
   - Project Settings (per-project overrides)
     - **New Section**: Agent Provider

2. **Provider Selection Pattern**: Card-based or dropdown
   - Visual provider cards with features/icons
   - Conditional credential fields (PasswordInput)
   - Real-time validation with status badges

3. **State Management**: Zustand stores
   - `useProjectSettingsStore` - Project-level config
   - IPC sync to main process

4. **Persistence**: IPC → env-handlers.ts → .env file

**Key Files (UI):**
- `auto-claude-ui/src/renderer/components/settings/AgentProviderSection.tsx`
- `auto-claude-ui/src/main/ipc-handlers/env-handlers.ts`
- `auto-claude-ui/src/shared/types/project.ts`
- `auto-claude-ui/src/shared/constants/providers.ts`

---

### Layer 4: Message Normalization

**Universal Message Format (Internal):**
```python
# auto-claude/core/providers/messages.py (NEW)
from dataclasses import dataclass
from typing import Any, Literal, Union

@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""

@dataclass
class ToolUseContent:
    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, Any] = None

@dataclass
class ToolResultContent:
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: str | dict = ""
    is_error: bool = False

@dataclass
class UniversalMessage:
    """Provider-agnostic message format."""
    role: Literal["assistant", "user"]
    content: list[Union[TextContent, ToolUseContent, ToolResultContent]]
```

---

## Implementation Stories (8 Stories for MVP)

### Story 1: Provider Configuration Foundation
**Complexity**: Medium | **Dependencies**: None | **Files**: 4 new

**Description:** Create configuration system with **generic credential store** and **dynamic provider normalization** for provider selection and validation with global/project-level inheritance.

**Tasks:**
1. Create `auto-claude/core/providers/__init__.py`
2. Create `auto-claude/core/providers/utils.py` with:
   - `normalize_provider_id(name: str) -> str` - Normalize provider names
     * Lowercase, spaces → hyphens
     * Remove special chars except hyphens
     * Examples: "Z.ai GLM" → "zai-glm", "AWS Bedrock" → "aws-bedrock"
3. Create `auto-claude/core/providers/config.py` with:
   - `AgentProvider` enum (CLAUDE_CODE, OPENCODE)
   - `ProviderCredential` dataclass (generic credential with inheritance):
     * `provider: str` - Provider ID (e.g., 'openai', 'zai', 'claude')
     * `api_key: str` - API key for this provider
     * `is_global: bool` - Tracks if inherited from global settings
     * `base_url: Optional[str]` - Custom endpoint support
     * `default_model: Optional[str]` - Provider-specific default model
     * `metadata: dict` - Extensible provider-specific config
   - `ProviderConfig` dataclass with generic credential store:
     * `provider_is_global: bool` - Tracks if provider selection is from global
     * `credentials: dict[str, ProviderCredential]` - Maps provider ID → credential
     * `opencode_provider: str` - Which provider OpenCode should route to
   - `from_env(global_settings: Optional[dict])` - Loads with global fallback
   - `_load_credentials(global_settings)` - Loads credentials from PROVIDER_CREDENTIALS JSON
   - `get_credential(provider_id)` - Helper to get specific credential
   - `is_valid()` - Validates configuration
   - `get_validation_errors()` - Returns error list
   - `get_credential_source_info()` - Returns source info for UI display
3. Implement generic credential inheritance logic:
   - Priority: Project PROVIDER_CREDENTIALS → Global providerCredentials → Defaults
   - Parse JSON credential store from environment variables
   - Support legacy CLAUDE_CODE_OAUTH_TOKEN for backward compatibility
   - Track inheritance per credential with `is_global` flag
4. Add comprehensive unit tests:
   - Test `normalize_provider_id()` with various inputs:
     * Standard: "OpenAI" → "openai"
     * Multi-word: "Z.ai GLM" → "zai-glm"
     * Special chars: "AWS Bedrock 2.0" → "aws-bedrock-20"
     * Edge cases: "  My-Custom  LLM!  " → "my-custom-llm"
   - Test global credential fallback
   - Test project credential override
   - Test mixed inheritance (some global, some project)
   - Test custom endpoints (self-hosted LLMs)
   - Test legacy Claude token compatibility
   - Test JSON parsing edge cases

**Acceptance Criteria:**
- ✅ `normalize_provider_id()` produces consistent IDs (lowercase, hyphens, no special chars)
- ✅ Python and TypeScript normalization produce IDENTICAL results
- ✅ `ProviderConfig.from_env(global_settings)` loads credentials from generic store
- ✅ Default provider is `claude_code` (backward compatibility)
- ✅ Validates credentials using `get_credential(provider_id)` method
- ✅ `PROVIDER_CREDENTIALS` JSON parsing works correctly
- ✅ Inheritance flags correctly track credential sources per provider
- ✅ Global providerCredentials properly fall back when project .env is empty
- ✅ Project credential overrides work when `{"provider":{"isGlobal":false}}`
- ✅ Legacy `CLAUDE_CODE_OAUTH_TOKEN` still works (backward compatibility)
- ✅ Custom endpoints supported via `baseUrl` field
- ✅ Display names stored and retrieved correctly
- ✅ Comprehensive validation error messages
- ✅ `get_credential_source_info()` returns UI-friendly source information for all providers
- ✅ No schema changes needed to add new providers (fully dynamic & scalable)

**Files Created:**
- `auto-claude/core/providers/__init__.py`
- `auto-claude/core/providers/utils.py` (normalization logic)
- `auto-claude/core/providers/config.py`
- `tests/test_provider_config.py`
- `tests/test_provider_utils.py` (normalization tests)

**Environment Variables Supported:**
```bash
# Project-level (.auto-claude/.env)
AGENT_PROVIDER=claude_code|opencode
AGENT_PROVIDER_IS_GLOBAL=true|false

# ✅ Generic Credential Store (JSON format)
PROVIDER_CREDENTIALS='{"zai":{"isGlobal":true},"openai":{"isGlobal":false,"apiKey":"sk-..."}}'

# OpenCode Provider Selection
OPENCODE_PROVIDER=openai|anthropic|google|zai|openrouter|...
OPENCODE_MODEL=<model-name>

# Legacy (backward compatibility)
CLAUDE_CODE_OAUTH_TOKEN=<token>
CLAUDE_TOKEN_IS_GLOBAL=true|false
```

**Global Settings Schema** (for reference):
```typescript
{
  "globalDefaultProvider": "claude_code|opencode",

  // ✅ Generic Credential Store (replaces individual global*ApiKey fields)
  "providerCredentials": {
    "claude": {
      "provider": "claude",
      "apiKey": "<token>",
      "defaultModel": "claude-sonnet-4-5"
    },
    "openai": {
      "provider": "openai",
      "apiKey": "<key>",
      "defaultModel": "gpt-5o"
    },
    "zai": {
      "provider": "zai",
      "apiKey": "<key>",
      "defaultModel": "glm-4.7"
    },
    // ... other providers
  },

  "globalOpencodeProvider": "openai|zai|...",
  "globalOpencodeModel": "<model>"
}
```

**Risk Mitigation:**
- Follow proven Graphiti pattern exactly
- Generic credential store avoids schema changes for new providers
- Backward compatible with legacy CLAUDE_CODE_OAUTH_TOKEN
- Extensive unit tests for inheritance logic and JSON parsing

---

### Story 2: Message Abstraction Protocol
**Complexity**: Medium | **Dependencies**: Story 1 | **Files**: 4 new, 1 modified

**Description:** Define provider-agnostic message protocol and implement Claude adapter.

**Tasks:**
1. Create `auto-claude/core/providers/messages.py` with `UniversalMessage` format
2. Create `auto-claude/core/providers/adapters/__init__.py`
3. Create `auto-claude/core/providers/adapters/claude_adapter.py`
4. Implement bidirectional message translation (Claude SDK ↔ Universal)
5. Add comprehensive unit tests

**Acceptance Criteria:**
- ✅ `TextContent`, `ToolUseContent`, `ToolResultContent` defined
- ✅ `UniversalMessage` dataclass created
- ✅ `ClaudeMessageAdapter.to_universal()` converts Claude SDK messages
- ✅ `ClaudeMessageAdapter.from_universal()` converts to Claude SDK format
- ✅ All Claude SDK message types supported (AssistantMessage, UserMessage, TextBlock, ToolUseBlock, ToolResultBlock)

**Files Created:**
- `auto-claude/core/providers/messages.py`
- `auto-claude/core/providers/adapters/__init__.py`
- `auto-claude/core/providers/adapters/claude_adapter.py`
- `tests/test_message_adapter.py`

**Files Modified:**
- None (pure abstraction layer)

**Risk Mitigation:** Extensive unit tests before integration

---

### Story 3: Provider Client Interface
**Complexity**: Large | **Dependencies**: Story 2 | **Files**: 3 new, 1 modified

**Description:** Create provider-agnostic client interface and implement Claude wrapper.

**Tasks:**
1. Create `auto-claude/core/providers/client.py` with `AgentClient` Protocol
2. Create `auto-claude/core/providers/adapters/claude_provider.py`
3. Wrap existing `ClaudeSDKClient` with `AgentClient` interface
4. Create factory: `create_client(config) -> AgentClient`
5. Update `auto-claude/core/client.py` to use factory (backward compatible)

**Acceptance Criteria:**
- ✅ `AgentClient` Protocol defines: `query()`, `receive_response()`, `close()`, `__aenter__`, `__aexit__`
- ✅ `ClaudeProvider` implements `AgentClient` by wrapping `ClaudeSDKClient`
- ✅ `create_client(config)` factory returns appropriate provider
- ✅ Existing `create_client()` function works unchanged (default to Claude)
- ✅ All async context manager methods work
- ✅ Message streaming works via `receive_response()`

**Files Created:**
- `auto-claude/core/providers/client.py`
- `auto-claude/core/providers/adapters/claude_provider.py`
- `auto-claude/core/providers/factory.py`

**Files Modified:**
- `auto-claude/core/client.py` (backward-compatible refactor)

**Backward Compatibility Strategy:**
```python
# OLD (still works):
from core.client import create_client
client = create_client(project_dir, spec_dir, model)  # Returns ClaudeSDKClient wrapper

# NEW (opt-in):
from core.providers.factory import create_client
from core.providers.config import ProviderConfig
config = ProviderConfig.from_env()
client = create_client(config, project_dir, spec_dir, model)  # Returns AgentClient
```

**Risk Mitigation:** Comprehensive integration tests with existing code

---

### Story 4: OpenCode Provider Implementation
**Complexity**: Large | **Dependencies**: Stories 1-3 | **Files**: 5 new

**Description:** Implement OpenCode provider adapter as first non-Claude integration.

**Tasks:**
1. Create `auto-claude/core/providers/adapters/opencode_provider.py`
2. Implement CLI subprocess management (run `opencode` commands)
3. Implement message parsing (OpenCode JSON output → UniversalMessage)
4. Handle OpenCode session management (SQLite coordination)
5. Map Auto-Claude tools to OpenCode built-in tools
6. Add comprehensive error handling

**Technical Details:**
- OpenCode CLI: `opencode build --non-interactive --api-key=... --provider=... --model=...`
- Output format: JSON-based message stream
- Session storage: SQLite (`~/.opencode/sessions.db`)
- Tools: Map Auto-Claude tools to OpenCode equivalents (Read → file_read, Write → file_write, etc.)

**Acceptance Criteria:**
- ✅ `OpenCodeProvider` implements `AgentClient` Protocol
- ✅ Subprocess spawns `opencode` CLI successfully
- ✅ Messages parsed from OpenCode JSON output to `UniversalMessage`
- ✅ Tool calls translated bidirectionally (Auto-Claude ↔ OpenCode)
- ✅ Error handling for CLI crashes, timeouts, invalid output
- ✅ Session cleanup on exit

**Files Created:**
- `auto-claude/core/providers/adapters/opencode_provider.py`
- `auto-claude/core/providers/adapters/opencode_messages.py`
- `auto-claude/core/providers/adapters/opencode_tools.py`
- `auto-claude/core/providers/adapters/opencode_subprocess.py`
- `tests/test_opencode_provider.py`

**Risk Mitigation:**
- Mock OpenCode CLI for testing
- Graceful degradation if CLI not installed
- Clear error messages for setup issues

---

### Story 5: Security Adapter for OpenCode
**Complexity**: Medium | **Dependencies**: Story 4 | **Files**: 2 new, 1 modified

**Description:** Adapt security model to work with OpenCode (no native hooks).

**Tasks:**
1. Create `auto-claude/core/providers/adapters/opencode_security.py`
2. Implement bash command validation as pre-execution wrapper
3. Integrate with existing `bash_security_hook` logic
4. Add provider capability detection (`supports_hooks: false`)
5. Update `security/hooks.py` to support provider-agnostic validation

**Approach:**
- **Claude Code**: Use native `PreToolUse` hooks (existing)
- **OpenCode**: Validate bash commands before passing to CLI (new)
- **Shared Logic**: Reuse `bash_security_hook` validation logic from `auto-claude/security/hooks.py`

**Acceptance Criteria:**
- ✅ OpenCode bash commands validated against allowlist
- ✅ Blocked commands return clear error messages
- ✅ Validation logic shared between Claude and OpenCode
- ✅ Provider capability flags: `supports_hooks`, `supports_sandbox`
- ✅ Security profile applies to both providers

**Files Created:**
- `auto-claude/core/providers/adapters/opencode_security.py`
- `tests/test_opencode_security.py`

**Files Modified:**
- `auto-claude/security/hooks.py` (extract validation logic for reuse)

**Risk Mitigation:** Security-critical - extensive testing required

---

### Story 6: UI-Based Provider Selection
**Complexity**: Medium | **Dependencies**: Stories 1-5 | **Files**: 8 new, 4 modified

**Description:** Add provider selection UI to Electron app with global/project-level credential inheritance support.

**Tasks:**
1. Add `AgentProviderConfig` types to UI shared types with inheritance flags
2. Create `AgentProviderSection.tsx` component for Project Settings
3. Implement provider dropdown with conditional credential fields
4. Add global/project credential toggle (use global vs set project-specific)
5. Add visual indicators for credential source (global inherited vs project override)
6. Add IPC handlers for reading global settings and writing project .env
7. Map UI config to .env variables in `env-handlers.ts` with inheritance flags
8. Add provider status validation and health checks
9. Create provider setup wizard for first-time users

**UI Component Structure:**
```tsx
// auto-claude-ui/src/renderer/components/settings/AgentProviderSection.tsx
<SettingsSection title="Agent Provider">
  {/* Provider Selection Dropdown */}
  <Select value={providerType} onValueChange={handleProviderChange}>
    <SelectItem value="claude_code">Claude Code (Default)</SelectItem>
    <SelectItem value="opencode">OpenCode (Multi-Provider)</SelectItem>
  </Select>

  {/* Claude Code Configuration */}
  {providerType === 'claude_code' && (
    <div className="space-y-4">
      {/* Global/Project Toggle */}
      <div className="flex items-center justify-between">
        <Label>Claude OAuth Token</Label>
        <CredentialSourceBadge
          isGlobal={claudeTokenIsGlobal}
          globalValue={globalSettings.globalClaudeOAuthToken}
        />
      </div>

      {/* Toggle: Use Global vs Project-Specific */}
      <RadioGroup value={claudeTokenIsGlobal ? 'global' : 'project'} onValueChange={...}>
        <RadioGroupItem value="global">
          Use Global Token {globalSettings.globalClaudeOAuthToken ? '✓' : '(not set)'}
        </RadioGroupItem>
        <RadioGroupItem value="project">
          Set Project-Specific Token
        </RadioGroupItem>
      </RadioGroup>

      {/* Show credential input only if project-specific selected */}
      {!claudeTokenIsGlobal && (
        <>
          <PasswordInput value={claudeToken} onChange={...} />
          <Button onClick={handleClaudeOAuth}>Authenticate with Claude</Button>
        </>
      )}
    </div>
  )}

  {/* OpenCode Configuration */}
  {providerType === 'opencode' && (
    <>
      {/* ✅ DYNAMIC Provider Selection - loaded from providerCredentials */}
      <div className="space-y-2">
        <Label>Provider</Label>
        <Select value={opencodeProvider} onValueChange={handleProviderChange}>
          {/* Show ALL configured providers from global settings */}
          {getConfiguredProviders(globalSettings).map(cred => (
            <SelectItem key={cred.provider} value={cred.provider}>
              {cred.displayName || getProviderDisplayName(globalSettings, cred.provider)}
              {cred.metadata?.advancedThinking && ' 🧠'}
              {cred.metadata?.autoFallback && ' 🔀'}
            </SelectItem>
          ))}
          {/* Add Provider button */}
          <SelectItem value="__add_new__">+ Add Provider...</SelectItem>
        </Select>

        {/* Credential info for selected provider */}
        {opencodeProvider && opencodeProvider !== '__add_new__' && (
          <ProviderCredentialSection
            providerId={opencodeProvider}
            globalSettings={globalSettings}
            projectCredentials={config.providerCredentials}
            onUpdate={handleCredentialUpdate}
          />
        )}
      </div>

      {/* Model Selection (optional override) */}
      {opencodeProvider && (
        <div className="space-y-2">
          <Label>Model (optional override)</Label>
          <Input
            value={opencodeModel}
            onChange={(e) => setOpencodeModel(e.target.value)}
            placeholder={getGlobalCredential(globalSettings, opencodeProvider)?.defaultModel || 'auto'}
          />
        </div>
      )}
    </>
  )}

  {/* Provider Status Indicator */}
  <ProviderStatusBadge provider={providerType} config={config} />
</SettingsSection>

{/* CredentialSourceBadge Component */}
const CredentialSourceBadge = ({ isGlobal, globalValue }) => {
  if (isGlobal && globalValue) {
    return <Badge variant="secondary">Using Global ✓</Badge>;
  } else if (isGlobal && !globalValue) {
    return <Badge variant="destructive">Global Not Set</Badge>;
  } else {
    return <Badge variant="default">Project Override</Badge>;
  }
};

{/* ✅ ProviderCredentialSection Component - handles global/project toggle */}
const ProviderCredentialSection = ({
  providerId,
  globalSettings,
  projectCredentials,
  onUpdate
}) => {
  const globalCred = getGlobalCredential(globalSettings, providerId);
  const projectCred = projectCredentials?.[providerId];
  const isGlobal = projectCred?.isGlobal !== false;

  return (
    <div className="space-y-2 pl-4 border-l-2">
      {/* Credential Source Badge */}
      <div className="flex items-center justify-between">
        <Label>Credentials</Label>
        <CredentialSourceBadge
          isGlobal={isGlobal}
          globalValue={globalCred?.apiKey}
        />
      </div>

      {/* Toggle: Use Global vs Project-Specific */}
      <RadioGroup
        value={isGlobal ? 'global' : 'project'}
        onValueChange={(value) => {
          onUpdate(providerId, { isGlobal: value === 'global' });
        }}
      >
        <RadioGroupItem value="global">
          Use Global {globalCred?.displayName || providerId} Credential
          {globalCred?.apiKey ? ' ✓' : ' (not set in global settings)'}
        </RadioGroupItem>
        <RadioGroupItem value="project">
          Set Project-Specific Credential
        </RadioGroupItem>
      </RadioGroup>

      {/* Show credential input only if project-specific selected */}
      {!isGlobal && (
        <div className="space-y-2">
          <PasswordInput
            label="API Key"
            value={projectCred?.apiKey || ''}
            onChange={(value) => onUpdate(providerId, { apiKey: value, isGlobal: false })}
            placeholder="Enter API key..."
          />

          {/* Optional: Custom Endpoint */}
          <Input
            label="Custom Endpoint (optional)"
            value={projectCred?.baseUrl || ''}
            onChange={(e) => onUpdate(providerId, { baseUrl: e.target.value, isGlobal: false })}
            placeholder="https://api.custom-provider.com/v1"
          />
        </div>
      )}
    </div>
  );
};
```

**Type Definitions:**
```typescript
// auto-claude-ui/src/shared/types/project.ts
export type AgentProviderType = 'claude_code' | 'opencode';

// ✅ NO HARDCODED PROVIDER ENUM - fully dynamic!
// Provider IDs are auto-normalized from display names via normalizeProviderId()

// ✅ Generic provider credential (matches Python ProviderCredential)
export interface ProviderCredential {
  provider: string;  // Normalized provider ID (e.g., "zai-glm", "aws-bedrock")
  displayName: string;  // Human-readable name (e.g., "Z.ai GLM 4.7")
  apiKey: string;
  isGlobal: boolean;  // True = inherited from global, False = project override
  baseUrl?: string;  // For custom endpoints (OpenAI-compatible APIs)
  defaultModel?: string;
  metadata?: Record<string, any>;
}

export interface AgentProviderConfig {
  providerType: AgentProviderType;
  providerIsGlobal?: boolean;  // Tracks if provider selection is inherited from global

  // ✅ Generic credential store (maps provider ID → credential)
  credentials?: Record<string, ProviderCredential>;

  // OpenCode-specific settings (which provider to route to)
  opencodeProvider?: string;  // ✅ CHANGED: Any provider ID from credentials store
  opencodeModel?: string;

  // Status
  providerStatus?: 'configured' | 'not_configured' | 'error';
  providerStatusMessage?: string;
}

// Add to ProjectEnvConfig interface (follows existing pattern)
interface ProjectEnvConfig {
  // ... existing fields

  // Agent Provider Configuration
  agentProvider?: AgentProviderType;  // 'claude_code' or 'opencode'
  agentProviderIsGlobal?: boolean;

  // ✅ Generic credential store (JSON string in .env, parsed to object in UI)
  providerCredentials?: Record<string, ProviderCredential>;

  // OpenCode-specific settings
  opencodeProvider?: string;  // ✅ CHANGED: Normalized provider ID from credentials
  opencodeModel?: string;

  // Legacy (backward compatibility)
  claudeOAuthToken?: string;
  claudeTokenIsGlobal?: boolean;
}

// Global Settings (already exists in settings.ts)
interface AppSettings {
  // ... existing fields
  globalDefaultProvider?: AgentProviderType;

  // ✅ Generic Credential Store (replaces individual global*ApiKey fields)
  providerCredentials?: Record<string, ProviderCredential>;

  // OpenCode defaults
  globalOpencodeProvider?: string;  // ✅ CHANGED: Normalized provider ID
  globalOpencodeModel?: string;

  // Legacy global keys (keep for backward compatibility during migration)
  globalClaudeOAuthToken?: string;  // Will be migrated to providerCredentials.claude
  globalOpenAIApiKey?: string;      // Will be migrated to providerCredentials.openai
  globalAnthropicApiKey?: string;   // Will be migrated to providerCredentials.anthropic
  globalGoogleApiKey?: string;      // Will be migrated to providerCredentials.google
  globalGroqApiKey?: string;        // Will be migrated to providerCredentials.groq
}
```

**Environment Variable Mapping:**
```typescript
// auto-claude-ui/src/main/ipc-handlers/env-handlers.ts

// In generateEnvContent():
// Provider selection (with inheritance tracking)
if (config.agentProvider) {
  existingVars['AGENT_PROVIDER'] = config.agentProvider || 'claude_code';
  existingVars['AGENT_PROVIDER_IS_GLOBAL'] = config.agentProviderIsGlobal !== undefined
    ? String(config.agentProviderIsGlobal)
    : 'true';
}

// ✅ Generic Credential Store - serialize to JSON
if (config.providerCredentials && Object.keys(config.providerCredentials).length > 0) {
  const credentialsJson: Record<string, any> = {};

  for (const [providerId, cred] of Object.entries(config.providerCredentials)) {
    if (cred.isGlobal) {
      // Inheriting from global - only store the flag
      credentialsJson[providerId] = { isGlobal: true };
    } else {
      // Project-specific - store the full credential
      credentialsJson[providerId] = {
        isGlobal: false,
        apiKey: cred.apiKey,
        ...(cred.baseUrl && { baseUrl: cred.baseUrl }),
        ...(cred.defaultModel && { model: cred.defaultModel }),
        ...(cred.metadata && { metadata: cred.metadata })
      };
    }
  }

  existingVars['PROVIDER_CREDENTIALS'] = JSON.stringify(credentialsJson);
}

// OpenCode configuration
if (config.agentProvider === 'opencode') {
  existingVars['OPENCODE_PROVIDER'] = config.opencodeProvider || 'openai';

  if (config.opencodeModel) {
    existingVars['OPENCODE_MODEL'] = config.opencodeModel;
  }
}

// Legacy Claude Code token (backward compatibility)
if (config.claudeTokenIsGlobal === false && config.claudeOAuthToken) {
  // Project-specific token - write to .env
  existingVars['CLAUDE_CODE_OAUTH_TOKEN'] = config.claudeOAuthToken;
  existingVars['CLAUDE_TOKEN_IS_GLOBAL'] = 'false';
} else if (config.claudeTokenIsGlobal === true) {
  // Using global token - set flag but don't write token value
  existingVars['CLAUDE_TOKEN_IS_GLOBAL'] = 'true';
}
```

**Helper Functions for UI:**
```typescript
// auto-claude-ui/src/renderer/utils/providerCredentials.ts

/**
 * ✅ Normalize provider name to consistent ID format
 * Matches Python's normalize_provider_id() logic
 *
 * Examples:
 * - "OpenAI" → "openai"
 * - "Z.ai GLM" → "zai-glm"
 * - "My Custom LLM" → "my-custom-llm"
 */
export function normalizeProviderId(name: string): string {
  // Lowercase and replace spaces with hyphens
  let normalized = name.toLowerCase().trim().replace(/\s+/g, '-');
  // Remove special chars except hyphens and alphanumeric
  normalized = normalized.replace(/[^a-z0-9-]/g, '');
  // Remove consecutive hyphens
  normalized = normalized.replace(/-+/g, '-');
  // Trim leading/trailing hyphens
  return normalized.replace(/^-+|-+$/g, '');
}

/**
 * Get global credential for a specific provider from AppSettings
 */
export function getGlobalCredential(
  globalSettings: AppSettings,
  providerId: string
): ProviderCredential | null {
  return globalSettings.providerCredentials?.[providerId] || null;
}

/**
 * Check if global credential exists and is configured for a provider
 */
export function hasGlobalCredential(
  globalSettings: AppSettings,
  providerId: string
): boolean {
  const cred = getGlobalCredential(globalSettings, providerId);
  return !!(cred && cred.apiKey);
}

/**
 * ✅ Get ALL configured provider IDs from global settings
 * Used to populate OpenCode provider dropdown dynamically
 */
export function getConfiguredProviders(
  globalSettings: AppSettings
): ProviderCredential[] {
  const credentials = globalSettings.providerCredentials || {};
  return Object.values(credentials).filter(cred => cred.apiKey);
}

/**
 * ✅ Get provider display name (with fallback to normalized ID)
 */
export function getProviderDisplayName(
  globalSettings: AppSettings,
  providerId: string
): string {
  const cred = getGlobalCredential(globalSettings, providerId);
  if (cred?.displayName) {
    return cred.displayName;
  }
  // Fallback: Convert normalized ID to title case
  return providerId.split('-').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
}
```

**Constants:**
```typescript
// auto-claude-ui/src/shared/constants/providers.ts (NEW)

// ✅ Only agent provider types are hardcoded (Claude Code vs OpenCode)
export const AGENT_PROVIDERS = [
  {
    value: 'claude_code',
    label: 'Claude Code',
    description: 'Official Claude SDK with advanced features',
    features: ['MCP Servers', 'OS Sandbox', 'Extended Thinking', 'OAuth']
  },
  {
    value: 'opencode',
    label: 'OpenCode',
    description: 'Multi-provider CLI supporting 20+ providers',
    features: ['Multi-Provider', 'Local Models', 'LSP Integration', 'SQLite Storage', 'Fully Extensible']
  }
];

// ✅ NO HARDCODED PROVIDER LIST!
// OpenCode providers are DYNAMICALLY loaded from providerCredentials
// This supports ANY provider without code changes:
// - Standard: OpenAI, Anthropic, Google, Groq, AWS Bedrock, Azure
// - Specialized: Z.ai GLM, OpenRouter, DeepSeek, Mistral
// - Custom: Self-hosted LLMs, enterprise endpoints
// - Future: Any new provider OpenCode adds (20+, 50+, 100+ providers)

/**
 * ✅ Suggested providers for quick setup (UI can show these as templates)
 * Users can add ANY provider beyond this list
 */
export const SUGGESTED_PROVIDERS = [
  { name: 'OpenAI', defaultModel: 'gpt-5o', requiresApiKey: true },
  { name: 'Z.ai GLM', defaultModel: 'glm-4.7', requiresApiKey: true },
  { name: 'OpenRouter', defaultModel: 'auto', requiresApiKey: true },
  { name: 'Google Gemini', defaultModel: 'gemini-2.0-flash', requiresApiKey: true },
  { name: 'Anthropic', defaultModel: 'claude-sonnet-4-5', requiresApiKey: true },
  { name: 'AWS Bedrock', defaultModel: 'anthropic.claude-v3-5', requiresApiKey: true },
  { name: 'Groq', defaultModel: 'llama-3.3-70b', requiresApiKey: true },
  { name: 'Custom Provider', defaultModel: '', requiresApiKey: true, allowCustomEndpoint: true }
];
```

**Acceptance Criteria:**
- ✅ Provider selection dropdown in Project Settings
- ✅ Conditional UI fields based on selected provider
- ✅ Global/project credential toggle (use global vs set project-specific)
- ✅ Visual badges showing credential source (global inherited vs project override)
- ✅ Automatic provider-to-global-key mapping (e.g., OpenAI → globalOpenAIApiKey)
- ✅ Real-time validation of API keys (both global and project-level)
- ✅ Provider status badge (configured/error/inherited)
- ✅ Settings saved to `.auto-claude/.env` with inheritance flags
- ✅ Reads from global settings (~/.config/auto-claude-ui/settings.json)
- ✅ Follows existing Auto-Claude inheritance pattern (claudeTokenIsGlobal, etc.)
- ✅ Backward compatibility: existing projects default to `claude_code`
- ✅ Visual feedback for provider switching (requires rebuild)
- ✅ Help text and tooltips for each provider
- ✅ First-time setup wizard for new projects

**Files Created:**
- `auto-claude-ui/src/renderer/components/settings/AgentProviderSection.tsx`
- `auto-claude-ui/src/renderer/components/settings/ProviderStatusBadge.tsx`
- `auto-claude-ui/src/renderer/components/settings/ProviderSetupWizard.tsx`
- `auto-claude-ui/src/shared/types/provider.ts`
- `auto-claude-ui/src/shared/constants/providers.ts`
- `auto-claude-ui/src/preload/api/provider-api.ts`

**Files Modified:**
- `auto-claude-ui/src/shared/types/project.ts` (add `AgentProviderConfig`)
- `auto-claude-ui/src/main/ipc-handlers/env-handlers.ts` (add provider env mapping)
- `auto-claude-ui/src/renderer/components/settings/ProjectSettings.tsx` (add provider section)
- `auto-claude-ui/src/shared/constants/ipc.ts` (add provider IPC channels)

**UI/UX Features:**
1. **Visual Provider Cards**: Large, clickable cards with icons and feature lists
2. **Global/Project Toggle**: Radio buttons for "Use Global" vs "Set Project-Specific"
3. **Credential Source Badges**: Visual indicators showing where credentials come from
   - "Using Global ✓" (green) - inherited from global settings
   - "Global Not Set" (red) - trying to inherit but no global key exists
   - "Project Override" (blue) - project-specific credential set
4. **Inline Validation**: API key validation with green checkmark or red error
5. **Model Recommendations**: Highlight recommended models for each provider
6. **Cost Indicators**: Show relative cost per provider (💰, 💰💰, 💰💰💰)
7. **Setup Wizard**: Step-by-step guide for first-time provider setup
8. **Migration Warning**: Alert when switching providers mid-project
9. **Quick Test Button**: "Test Provider" to validate configuration
10. **Smart Defaults**: Auto-select global credentials if available when switching providers

**Risk Mitigation:**
- Comprehensive input validation
- Clear error messages for misconfiguration
- Rollback mechanism if provider switch fails
- Preserve existing .env comments when updating

---

### Story 7: CLI & Backend Integration
**Complexity**: Medium | **Dependencies**: Stories 1-6 | **Files**: 5 new, 2 modified

**Description:** Integrate provider system with CLI and backend agent execution.

**Tasks:**
1. Update `auto-claude/agents/session.py` to use `AgentClient` interface
2. Update `auto-claude/agents/coder.py` to support provider selection
3. Add provider selection to `auto-claude/run.py` (CLI flag: `--provider`)
4. Add provider detection from .env in workspace
5. Create end-to-end integration tests

**Acceptance Criteria:**
- ✅ `run_agent_session()` works with both Claude Code and OpenCode
- ✅ CLI flag `--provider opencode` works
- ✅ Reads `AGENT_PROVIDER` from `.auto-claude/.env` automatically
- ✅ UI-configured provider settings work in CLI execution
- ✅ All existing tests pass without modification (zero breaking changes)
- ✅ New integration tests for OpenCode provider
- ✅ Default behavior unchanged (Claude Code)
- ✅ Error messages helpful for provider setup issues

**Files Modified:**
- `auto-claude/agents/session.py` (use `AgentClient` instead of `ClaudeSDKClient`)
- `auto-claude/run.py` (add `--provider` flag + .env detection)

**Files Created:**
- `tests/integration/test_claude_provider.py`
- `tests/integration/test_opencode_provider.py`
- `tests/integration/test_provider_switching.py`
- `.env.example` (add OpenCode configuration examples)
- `docs/PROVIDERS.md` (setup guide)

**Provider Loading Priority:**
```python
# auto-claude/run.py
def get_provider_config() -> ProviderConfig:
    """Load provider config with priority: CLI flag > Project .env > Global settings > Default

    Priority chain (highest to lowest):
    1. CLI flag (--provider)
    2. Project .env file with inheritance
    3. Global settings (~/.config/auto-claude-ui/settings.json)
    4. Hardcoded default (claude_code)
    """

    # 1. CLI flag (highest priority)
    if args.provider:
        # CLI override - still loads credentials from .env or global settings
        config = ProviderConfig.from_env(load_global_settings())
        config.provider = args.provider
        return config

    # 2. Project .env file (with global fallback)
    env_file = project_dir / ".auto-claude" / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        provider = os.getenv("AGENT_PROVIDER")
        if provider:
            # Load from .env with global settings fallback
            global_settings = load_global_settings()
            return ProviderConfig.from_env(global_settings)

    # 3. Global settings only (no project .env)
    global_settings = load_global_settings()
    if global_settings:
        return ProviderConfig.from_env(global_settings)

    # 4. Default (Claude Code, no credentials)
    return ProviderConfig(provider="claude_code")


def load_global_settings() -> dict:
    """Load global settings from Electron app config.

    Returns:
        dict: Global settings with keys like globalClaudeOAuthToken, etc.
    """
    settings_path = Path.home() / ".config" / "auto-claude-ui" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load global settings: {e}")
    return {}
```

**Risk Mitigation:**
- Run full test suite before merging
- Add regression tests for backward compatibility
- Clear precedence rules for config sources

---

### Story 8: Documentation & Polish
**Complexity**: Small | **Dependencies**: Stories 6-7 | **Files**: 4 modified/new

**Description:** Create comprehensive documentation and polish user experience.

**Tasks:**
1. Update `README.md` with provider overview
2. Create `docs/PROVIDERS.md` with setup guides
3. Add provider validation errors to startup output
4. Create troubleshooting guide
5. Add cost comparison examples

**Deliverables:**
- **README.md**: Overview of multi-provider support
- **docs/PROVIDERS.md**: Detailed setup for Claude Code and OpenCode
- **docs/COST_COMPARISON.md**: Cost analysis per provider
- **Startup Banner**: Show selected provider and validation status

**Acceptance Criteria:**
- ✅ Documentation covers both providers
- ✅ Setup instructions clear and tested
- ✅ Troubleshooting section addresses common issues
- ✅ Cost comparison helps users choose provider
- ✅ Startup output shows provider validation

**Files Modified:**
- `README.md`

**Files Created:**
- `docs/PROVIDERS.md`
- `docs/COST_COMPARISON.md`
- `examples/opencode_config.env`

---

## Feature Parity Matrix (MVP)

| Feature | Claude Code | OpenCode |
|---------|-------------|----------|
| Read/Write/Edit | ✅ | ✅ |
| Extended Thinking | ✅ (16K) | ⚠️ (model-dependent: Z.ai GLM 4.7 ✅) |
| MCP Servers | ✅ | ⚠️ (LSP only) |
| Sandbox | ✅ | ❌ (use validation) |
| OAuth | ✅ | ❌ (API keys) |
| Hooks | ✅ | ❌ (pre-validation) |
| Local Models | ❌ | ✅ (not in MVP) |
| Provider Flexibility | ❌ (Claude only) | ✅ (8+ providers + custom) |

## Cost Comparison (OpenCode Providers)

**Per 1M Tokens** (Input/Output pricing may vary):

| Provider | Cost Range | Notes |
|----------|------------|-------|
| **Claude Code (Anthropic)** | OAuth billing | Usage-based, variable |
| **Z.ai GLM 4.7** | $0.40/1M or $3/month plan | **Best value for advanced thinking** ⭐ |
| **Groq** | $0.10-0.27/1M | Fast inference, good value |
| **Google Gemini** | $0.50-7.50/1M | 2.0 Flash cheapest, 2.5 Pro premium |
| **OpenAI** | $2.50-30.00/1M | GPT-5o-mini cheapest, o3 most expensive |
| **Anthropic (via OpenCode)** | $3.00-15.00/1M | API key billing |
| **AWS Bedrock** | $3.00-15.00/1M | Enterprise features |
| **Azure OpenAI** | $2.50-30.00/1M | Similar to OpenAI |
| **OpenRouter** | Variable | Auto-selects cheapest, access to 400+ models |

**Cost Optimization Strategies:**

1. **Development/Testing**: Use Z.ai GLM 4.7 ($3/month plan) or Groq
2. **Production Coding**: Z.ai GLM 4.7 (advanced thinking) or Claude Sonnet 4.5
3. **High-Volume**: OpenRouter with auto-fallback to cheapest models
4. **Prototyping**: Google Gemini 2.0 Flash (fast + affordable)
5. **Complex Tasks**: Claude Opus 4.5 or Z.ai GLM 4.7 (turn-level thinking)

**Graceful Degradation (MVP):**
- **MCP Tools**: Available for Claude Code only (OpenCode uses built-in LSP)
- **Thinking Tokens**: Auto-configured based on model capabilities
- **Hooks**: Claude uses native hooks, OpenCode uses pre-execution validation
- **Sandbox**: Claude uses OS sandbox, OpenCode uses bash allowlist only

---

## Critical Files for Implementation

### Top 5 High-Risk Files (Require Careful Refactoring)

1. **`auto-claude/agents/session.py`** (lines 12, 314-551)
   - Core message handling loop
   - Must be refactored to use `AgentClient` interface instead of `ClaudeSDKClient`
   - **Risk**: Breaking changes affect all agent sessions
   - **Mitigation**: Extensive unit tests, incremental refactor, backward-compatible wrapper

2. **`auto-claude/core/client.py`** (lines 19, 132-364)
   - Primary integration point for `ClaudeSDKClient`
   - Must be transformed into factory returning provider-agnostic client
   - **Risk**: 17+ files import this function
   - **Mitigation**: Maintain existing function signature, use adapter pattern

3. **`auto-claude/core/auth.py`**
   - OAuth-only authentication
   - Must support both OAuth (Claude) and API keys (OpenCode)
   - **Risk**: Security vulnerabilities if API keys mishandled
   - **Mitigation**: Follow Graphiti auth pattern, secure key storage

4. **`auto-claude/security/hooks.py`** (lines 20-104)
   - Security enforcement using Claude SDK's `HookMatcher`
   - Must extract validation logic for reuse with OpenCode
   - **Risk**: Security bypass if refactored incorrectly
   - **Mitigation**: Security audit, extensive testing, fail-safe defaults

5. **`auto-claude/agents/auto_claude_tools.py`**
   - Custom MCP server creation for Claude SDK
   - Must map to OpenCode tool equivalents
   - **Risk**: Feature loss if tools don't map cleanly
   - **Mitigation**: Tool compatibility matrix, graceful degradation

### Reference Patterns (Low-Risk, Use as Templates)

1. **`auto-claude/integrations/graphiti/config.py`** (lines 104-413)
   - Perfect blueprint for `ProviderConfig` implementation
   - Use `from_env()`, `is_valid()`, `get_validation_errors()` patterns

2. **`auto-claude/integrations/graphiti/providers_pkg/factory.py`** (lines 33-94)
   - Factory pattern for provider creation
   - Use as template for `create_client()` factory

3. **`auto-claude/integrations/linear/config.py`**
   - Configuration validation and state management
   - Use for provider state tracking

---

## Risk Assessment

### High-Risk Areas

**1. Message Handling Refactor (Story 2-3)**
- **Risk**: Breaking `session.py` affects all agent sessions
- **Impact**: HIGH - Could break entire framework
- **Mitigation**:
  - Comprehensive unit tests before integration
  - Adapter pattern preserves existing behavior
  - Incremental rollout (Claude wrapper first, then OpenCode)
  - Regression test suite

**2. Security Model Adaptation (Story 5)**
- **Risk**: OpenCode has no native sandbox or hooks
- **Impact**: HIGH - Security vulnerabilities
- **Mitigation**:
  - Reuse existing bash allowlist validation
  - Pre-execution validation (fail-safe)
  - Capability flags prevent assuming features
  - Security audit before release

**3. OpenCode CLI Instability (Story 4)**
- **Risk**: OpenCode is young, API may change
- **Impact**: MEDIUM - Adapter may break on updates
- **Mitigation**:
  - Version-pin OpenCode CLI
  - Health checks detect API changes
  - Clear error messages for version mismatches
  - Isolated adapter (easy to update)

---

## Implementation Sequence

### Week 1: Foundation
- ✅ Story 1: Provider Configuration (2 days)
- ✅ Story 2: Message Abstraction (3 days)

### Week 2: Core Integration
- ✅ Story 3: Provider Client Interface (4 days)
- ✅ Story 4: OpenCode Provider (3 days)

### Week 3: Security & UI
- ✅ Story 5: Security Adapter (2 days)
- ✅ Story 6: UI Provider Selection (3 days)

### Week 4: Testing & Documentation
- ✅ Story 7: CLI & Backend Integration (3 days)
- ✅ Story 8: Documentation & Polish (2 days)

**Total**: ~22 development days (3-4 weeks)

---

## Success Criteria

### Must-Have (MVP)
- ✅ Claude Code works exactly as before (zero breaking changes)
- ✅ OpenCode integration works with at least 1 provider (OpenAI)
- ✅ Security model enforced for both providers
- ✅ UI provider selection in Project Settings (Electron app)
- ✅ Provider settings saved to `.auto-claude/.env` via UI
- ✅ CLI respects UI-configured provider settings
- ✅ All existing tests pass
- ✅ Clear documentation for setup (CLI + UI)

### Nice-to-Have (Post-MVP)
- ⏭️ **Z.ai GLM 4.7 thinking mode controls** - Per-task thinking level (turn-level thinking API)
- ⏭️ **OpenRouter smart routing** - Auto-fallback based on task complexity and cost
- ⏭️ **Custom provider templates** - UI wizard for adding custom OpenCode providers
- ⏭️ **Cost tracking dashboard** - Real-time spend monitoring per provider
- ⏭️ **Provider auto-selection** - AI-powered provider recommendation based on task type
- ⏭️ **Hybrid provider sessions** - Use different providers per agent role (Planner: Claude, Coder: Z.ai)
- ⏭️ **Local model support** - Ollama integration via OpenCode
- ⏭️ **Gemini CLI integration** - Direct Gemini CLI provider (alternative to OpenCode)

---

## References

### Research Sources
- [OpenCode GitHub](https://github.com/sst/opencode)
- [OpenCode Official Site](https://opencode.ai/)
- [OpenCode Providers Documentation](https://opencode.ai/docs/providers/)
- [Z.ai GLM 4.7 Documentation](https://docs.z.ai/devpack/tool/opencode)
- [Z.ai GLM 4.7 Analysis](https://llm-stats.com/blog/research/glm-4.7-launch)
- [Z.ai API Console](https://z.ai/manage-apikey/apikey-list)
- [OpenRouter Documentation](https://openrouter.ai/docs/quickstart)
- [OpenRouter Models](https://openrouter.ai/models)
- [Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [OpenAI Codex CLI](https://github.com/openai/codex)
- [Agentic CLI Tools Comparison](https://research.aimultiple.com/agentic-cli/)

### Internal Patterns
- Graphiti Multi-Provider: `auto-claude/integrations/graphiti/` (lines 104-648)
- Linear Configuration: `auto-claude/integrations/linear/config.py`
- Security Profile: `auto-claude/security/` (lines 20-147)

---

## Next Steps After MVP

### Phase 2 (Future Stories)
1. **Story 8**: Gemini CLI Provider (Medium complexity)
2. **Story 9**: Cost Tracking & Analytics (Small complexity)
3. **Story 10**: Provider Auto-Selection (Medium complexity)
4. **Story 11**: Local Model Support via OpenCode (Medium complexity)
5. **Story 12**: Multi-Provider Benchmark Suite (Small complexity)

### Extension Points
- **Tool Registry**: Generic tool registration beyond MCP
- **Provider Plugins**: Community-contributed providers
- **Hybrid Sessions**: Use different providers per agent role (e.g., Claude for Planner, OpenAI for Coder)
- **Cost Optimization**: Auto-switch to cheapest provider for task type

---

## Appendix: Alternative Approaches Considered

### Alternative 1: Direct API Integration (Rejected)
**Approach**: Integrate with Anthropic/OpenAI APIs directly instead of CLI wrappers
**Pros**: More control, no CLI dependency
**Cons**:
- Reinvent tool calling, message handling
- No TUI/interactive mode
- Lose OpenCode's multi-provider benefit
**Decision**: Use CLI wrappers (OpenCode) for faster MVP

### Alternative 2: Fork Claude Code SDK (Rejected)
**Approach**: Fork Claude Code SDK and add provider support internally
**Pros**: Keep existing architecture
**Cons**:
- Maintenance burden
- Diverge from official SDK
- No benefit from Claude Code updates
**Decision**: Abstract instead of fork

### Alternative 3: OpenAI SDK Direct (Rejected for MVP)
**Approach**: Integrate OpenAI SDK directly instead of via OpenCode
**Pros**: One less dependency
**Cons**:
- Only supports OpenAI (not Google, AWS, etc.)
- Requires implementing TUI ourselves
- Lose OpenCode's non-interactive mode
**Decision**: Use OpenCode for multi-provider benefit

---

**Plan Status**: Ready for Implementation
**Last Updated**: 2025-12-25

---

## Summary of UI Improvements

The plan now includes comprehensive UI-based provider selection with global/project inheritance:

✅ **Story 6: UI-Based Provider Selection** - New story with inheritance support
- Visual provider selection in Electron app Project Settings
- **Global/Project credential toggle** (use global vs set project-specific)
- **Credential source badges** (inherited vs override indicators)
- Dropdown with conditional credential fields
- Provider status badges and validation
- **Automatic provider-to-global-key mapping** (OpenAI → globalOpenAIApiKey)
- IPC handlers for reading global settings + writing project .env
- Backward compatible with existing UI architecture

✅ **Updated Timeline**: 3-4 weeks (was 2-3 weeks)
- Added 3 days for UI implementation with inheritance support

✅ **Configuration Flow**: CLI → Project .env → Global Settings → Default
- CLI flags (highest priority, temporary override)
- Project .env file (project-specific overrides with inheritance flags)
- Global settings (~/.config/auto-claude-ui/settings.json)
- Hardcoded default (claude_code)

✅ **UI Patterns**: Following existing Auto-Claude credential inheritance
- Follows `claudeTokenIsGlobal`, `openaiKeyIsGlobal` pattern
- Radix UI Select components + RadioGroup for global/project toggle
- Conditional field rendering (hide input when using global)
- PasswordInput for credentials
- Type-safe TypeScript interfaces with `*_is_global` flags

✅ **Key Architecture Decisions**

**1. Fully Dynamic Provider System** (Zero Hardcoding)
- **✅ NO Provider Enums**: No `OpenCodeProviderType = 'openai' | 'zai' | ...`
- **✅ Normalization Logic**: `normalizeProviderId("Z.ai GLM") → "zai-glm"`
  - Lowercase, spaces → hyphens, remove special chars
  - **Same logic in Python and TypeScript** (consistent normalization)
- **✅ Runtime Discovery**: UI dropdown populated from `providerCredentials` store
- **✅ Infinite Scalability**: Supports 20, 50, 100+ providers without code changes
- **✅ User-Extensible**: Users can add ANY provider via "+ Add Provider" button
- **Examples**:
  - "Z.ai GLM 4.7" → `zai-glm-47`
  - "My Company LLM" → `my-company-llm`
  - "AWS Bedrock Claude" → `aws-bedrock-claude`

**2. Generic Credential Store** (Scalable & Extensible)
- **Single Dictionary**: `providerCredentials: Record<string, ProviderCredential>`
- **No Schema Changes**: Add new providers without touching type definitions
- **Display Names**: Human-readable names stored alongside normalized IDs
- **Custom Endpoints**: Self-hosted LLMs via `baseUrl` field
- **Backward Compatible**: Legacy `CLAUDE_CODE_OAUTH_TOKEN` still works
- **Metadata Support**: Provider-specific config (subscription, features, region, etc.)

**3. Two-Tier Configuration** (Global + Project Inheritance)
- **Global Settings** (~/.config/auto-claude-ui/settings.json)
  - User-level defaults for all projects
  - Set credentials ONCE in `providerCredentials`, use everywhere
  - Never committed to git
- **Project Settings** (.auto-claude/.env)
  - Per-project overrides when needed
  - `PROVIDER_CREDENTIALS` JSON with per-credential `isGlobal` flags
  - Supports different providers per project
  - Mixed inheritance (some global, some project-specific)
