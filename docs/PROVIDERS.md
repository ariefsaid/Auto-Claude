# Multi-Provider Support

Auto Claude supports multiple AI agent providers, giving you flexibility in choosing the right model for your coding tasks. This guide covers setup, configuration, and troubleshooting for all supported providers.

## Overview

Auto Claude offers two agent provider modes:

| Provider | Description | Best For |
|----------|-------------|----------|
| **Claude Code** | Official Claude Code SDK with OAuth authentication | Most users - recommended default |
| **OpenCode** | Multi-provider CLI supporting 20+ LLM providers | Cost optimization, specific model preferences, local deployment |

## Quick Start

### Claude Code (Default)

Claude Code is the recommended provider for most users. It uses the official Claude Code SDK with OAuth authentication.

**Prerequisites:**
- [Claude Pro or Max](https://claude.ai/upgrade) subscription
- Claude Code CLI installed: `npm install -g @anthropic-ai/claude-code`

**Setup:**
```bash
# Authenticate with Claude
claude setup-token

# That's it! Auto Claude will use Claude Code by default
```

**Verify Setup:**
```bash
# Check authentication status
claude auth status
```

### OpenCode (Multi-Provider)

OpenCode enables you to use any of 20+ LLM providers including OpenAI, Google Gemini, Anthropic (direct API), and more.

**Prerequisites:**
- OpenCode CLI installed: `npm install -g @opencode-ai/sdk`
- API key for your chosen provider

**Setup via UI:**
1. Open Auto Claude
2. Go to **Project Settings** → **Provider** tab
3. Select **OpenCode** as the Agent Provider
4. Choose your LLM provider (e.g., OpenAI)
5. Enter your API key or toggle "Use Global Credentials"
6. Save settings

**Setup via CLI:**
```bash
# Set environment variables in your project's .auto-claude/.env
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
OPENCODE_MODEL=gpt-4o
PROVIDER_CREDENTIALS={"openai":{"isGlobal":false,"apiKey":"sk-your-api-key"}}
```

---

## Supported Providers

### OpenAI

Use GPT-4o, GPT-4 Turbo, o1, and other OpenAI models.

| Setting | Value |
|---------|-------|
| Provider ID | `openai` |
| Default Model | `gpt-4o` |
| API Key Format | `sk-...` |

**Available Models:**
- `gpt-4o` - Most capable, recommended for complex coding
- `gpt-4o-mini` - Faster, cost-effective for simpler tasks
- `gpt-4-turbo` - Previous generation flagship
- `o1` - Reasoning-optimized model
- `o1-mini` - Faster reasoning model

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
OPENCODE_MODEL=gpt-4o
PROVIDER_CREDENTIALS={"openai":{"isGlobal":false,"apiKey":"sk-..."}}
```

**Get API Key:** [OpenAI Platform](https://platform.openai.com/api-keys)

---

### Google Gemini

Use Google's Gemini Pro and Flash models.

| Setting | Value |
|---------|-------|
| Provider ID | `google-gemini` |
| Default Model | `gemini-1.5-pro` |
| API Key Format | `AIza...` |

**Available Models:**
- `gemini-1.5-pro` - Best quality, longer context
- `gemini-1.5-flash` - Faster, cost-effective
- `gemini-2.0-flash-exp` - Latest experimental

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=google-gemini
OPENCODE_MODEL=gemini-1.5-pro
PROVIDER_CREDENTIALS={"google-gemini":{"isGlobal":false,"apiKey":"AIza..."}}
```

**Get API Key:** [Google AI Studio](https://aistudio.google.com/apikey)

---

### Z.ai GLM

Use Z.ai GLM models for coding and analysis tasks.

| Setting | Value |
|---------|-------|
| Provider ID | `zai-glm` |
| Default Model | `glm-4` |
| API Key Format | `zai-...` |

**Available Models:**
- `glm-4` - Flagship model
- `glm-4-flash` - Faster inference
- `glm-4.7` - Latest version

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=zai-glm
OPENCODE_MODEL=glm-4
PROVIDER_CREDENTIALS={"zai-glm":{"isGlobal":false,"apiKey":"zai-..."}}
```

---

### OpenRouter

Access 100+ models through a single API gateway.

| Setting | Value |
|---------|-------|
| Provider ID | `openrouter` |
| Default Model | `anthropic/claude-3.5-sonnet` |
| API Key Format | `sk-or-...` |
| Base URL | `https://openrouter.ai/api/v1` |

**Available Models (examples):**
- `anthropic/claude-3.5-sonnet` - Claude 3.5 Sonnet
- `openai/gpt-4o` - GPT-4o
- `google/gemini-pro-1.5` - Gemini 1.5 Pro
- `meta-llama/llama-3.1-70b-instruct` - Llama 3.1

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openrouter
OPENCODE_MODEL=anthropic/claude-3.5-sonnet
PROVIDER_CREDENTIALS={"openrouter":{"isGlobal":false,"apiKey":"sk-or-...","baseUrl":"https://openrouter.ai/api/v1"}}
```

**Get API Key:** [OpenRouter](https://openrouter.ai/keys)

> **Tip:** OpenRouter lets you use credits across providers. Great for comparing models without managing multiple API keys.

---

### Groq

Ultra-fast inference with Llama and Mixtral models.

| Setting | Value |
|---------|-------|
| Provider ID | `groq` |
| Default Model | `llama-3.1-70b-versatile` |
| API Key Format | `gsk_...` |
| Base URL | `https://api.groq.com/openai/v1` |

**Available Models:**
- `llama-3.1-70b-versatile` - Best quality
- `llama-3.1-8b-instant` - Fastest
- `mixtral-8x7b-32768` - Mixture of experts
- `gemma2-9b-it` - Google's Gemma

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=groq
OPENCODE_MODEL=llama-3.1-70b-versatile
PROVIDER_CREDENTIALS={"groq":{"isGlobal":false,"apiKey":"gsk_...","baseUrl":"https://api.groq.com/openai/v1"}}
```

**Get API Key:** [Groq Console](https://console.groq.com/keys)

---

### Together AI

Open-source models with fast, affordable inference.

| Setting | Value |
|---------|-------|
| Provider ID | `together-ai` |
| Default Model | `meta-llama/Llama-3.1-70B-Instruct-Turbo` |
| Base URL | `https://api.together.xyz/v1` |

**Available Models:**
- `meta-llama/Llama-3.1-70B-Instruct-Turbo` - Best quality
- `meta-llama/Llama-3.1-8B-Instruct-Turbo` - Fast and affordable
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - Mixtral MoE

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=together-ai
OPENCODE_MODEL=meta-llama/Llama-3.1-70B-Instruct-Turbo
PROVIDER_CREDENTIALS={"together-ai":{"isGlobal":false,"apiKey":"...","baseUrl":"https://api.together.xyz/v1"}}
```

**Get API Key:** [Together AI](https://api.together.xyz/)

---

### Mistral AI

European AI models with excellent code generation.

| Setting | Value |
|---------|-------|
| Provider ID | `mistral-ai` |
| Default Model | `mistral-large-latest` |

**Available Models:**
- `mistral-large-latest` - Most capable
- `mistral-medium-latest` - Balanced
- `mistral-small-latest` - Fast and efficient

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=mistral-ai
OPENCODE_MODEL=mistral-large-latest
PROVIDER_CREDENTIALS={"mistral-ai":{"isGlobal":false,"apiKey":"..."}}
```

**Get API Key:** [Mistral AI Console](https://console.mistral.ai/)

---

### Fireworks AI

Fast inference for open-source models.

| Setting | Value |
|---------|-------|
| Provider ID | `fireworks-ai` |
| Default Model | `accounts/fireworks/models/llama-v3p1-70b-instruct` |
| Base URL | `https://api.fireworks.ai/inference/v1` |

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=fireworks-ai
OPENCODE_MODEL=accounts/fireworks/models/llama-v3p1-70b-instruct
PROVIDER_CREDENTIALS={"fireworks-ai":{"isGlobal":false,"apiKey":"...","baseUrl":"https://api.fireworks.ai/inference/v1"}}
```

**Get API Key:** [Fireworks AI](https://fireworks.ai/)

---

### Ollama (Local)

Run models locally on your machine. No API key required.

| Setting | Value |
|---------|-------|
| Provider ID | `ollama` |
| Default Model | `llama3.1` |
| Base URL | `http://localhost:11434/v1` |

**Prerequisites:**
1. Install Ollama: [ollama.ai](https://ollama.ai/)
2. Pull your desired model: `ollama pull llama3.1`

**Available Models:**
- `llama3.1` - Meta's Llama 3.1 (8B)
- `llama3.1:70b` - Larger variant (needs ~40GB RAM)
- `codellama` - Optimized for code
- `mistral` - Mistral 7B
- `mixtral` - Mixtral 8x7B

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=ollama
OPENCODE_MODEL=llama3.1
PROVIDER_CREDENTIALS={"ollama":{"isGlobal":false,"baseUrl":"http://localhost:11434/v1"}}
```

> **Note:** Ollama runs locally and doesn't require an API key. Ensure Ollama is running before starting Auto Claude.

---

### Custom Providers

You can add any OpenAI-compatible API as a custom provider.

**Configuration:**
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=custom-llm
OPENCODE_MODEL=custom-model-v1
PROVIDER_CREDENTIALS={"custom-llm":{"isGlobal":false,"apiKey":"...","baseUrl":"https://api.custom.ai/v1"}}
```

**UI Setup:**
1. In Project Settings → Provider, click **"Add Provider"**
2. Enter a display name (e.g., "Custom LLM")
3. The normalized ID will be shown (e.g., `custom-llm`)
4. Enter API key, model name, and base URL
5. Save

---

## Configuration Inheritance

Auto Claude supports a flexible credential inheritance system, allowing you to configure credentials once and reuse them across projects.

### Priority Order

Configuration is loaded with the following priority (highest to lowest):

1. **CLI flag** - `--provider opencode` overrides everything
2. **Project .env** - Project-specific settings in `.auto-claude/.env`
3. **Global UI settings** - Default from `~/.config/auto-claude-ui/settings.json`
4. **Default** - Falls back to `claude_code`

### Global vs Project Credentials

**Global Credentials** (recommended for personal use):
- Configured once in App Settings
- Inherited by all projects with "Use Global" toggle
- Stored in `~/.config/auto-claude-ui/settings.json`

**Project Credentials** (for team/repo-specific keys):
- Configured per-project in Project Settings
- Stored in `.auto-claude/.env` (gitignored)
- Override global credentials

### Example: Global Credential Setup

1. Open Auto Claude → **App Settings**
2. Click **"Add Provider"**
3. Enter "OpenAI", your API key, and default model
4. Save

Now in any project:
1. Open **Project Settings** → **Provider**
2. Select **OpenCode** → **OpenAI**
3. Toggle **"Use Global Credentials"** ✓
4. Save

The project will use your global OpenAI API key without storing it in the project.

### Example: Project Override

```bash
# .auto-claude/.env
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
OPENCODE_MODEL=gpt-4o-mini  # Use cheaper model for this project
PROVIDER_CREDENTIALS={"openai":{"isGlobal":true}}  # Still use global API key
```

---

## CLI Usage

### Using --provider Flag

Override the configured provider for a single run:

```bash
# Use Claude Code (default)
python auto-claude/run.py --spec 001

# Use OpenCode with project configuration
python auto-claude/run.py --spec 001 --provider opencode

# Use Claude Code explicitly
python auto-claude/run.py --spec 001 --provider claude_code
```

### Environment Variables

Set provider configuration via environment variables:

```bash
# Set for current session
export AGENT_PROVIDER=opencode
export OPENCODE_PROVIDER=openai
export OPENCODE_MODEL=gpt-4o

# Run Auto Claude
python auto-claude/run.py --spec 001
```

### Startup Banner

When Auto Claude starts, it displays the current provider configuration:

```
=== Auto Claude Build System ===
Provider: opencode (OpenAI via OpenCode)
Model: gpt-4o
Credential Source: global
================================
```

---

## Troubleshooting

### Common Errors

#### "Claude OAuth token not configured"

**Cause:** Using Claude Code provider without authentication.

**Solution:**
```bash
# Authenticate with Claude
claude setup-token

# Verify authentication
claude auth status
```

#### "OpenCode provider not selected"

**Cause:** Selected OpenCode agent but didn't specify which LLM provider.

**Solution:** Set `OPENCODE_PROVIDER` in your `.auto-claude/.env`:
```bash
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai  # Add this
```

#### "Global credential 'provider-name' not found"

**Cause:** Project configured to use global credentials, but provider not set up globally.

**Solution:**
1. Open App Settings → Add Provider
2. Configure the missing provider with API key
3. Save and retry

#### "API key is required for provider"

**Cause:** Provider configured without an API key.

**Solution:** Either:
- Add API key in Project Settings, or
- Toggle "Use Global" and configure global credentials

#### "OpenAI API keys should start with 'sk-'"

**Cause:** API key format validation failed.

**Solution:** Verify you're using the correct API key format:
| Provider | Key Format |
|----------|------------|
| OpenAI | `sk-...` |
| Anthropic | `sk-ant-...` |
| OpenRouter | `sk-or-...` |
| Groq | `gsk_...` |
| Google | `AIza...` |

#### "OpenCode CLI not found"

**Cause:** OpenCode CLI not installed.

**Solution:**
```bash
npm install -g @opencode-ai/sdk
```

### Validation Checks

Auto Claude validates provider configuration on startup. To manually validate:

```bash
# Check provider status for a project
python auto-claude/cli/provider_info.py get-status --project-dir /path/to/project

# Validate a configuration
python auto-claude/cli/provider_info.py validate --config '{"agentProvider": "opencode", "opencodeProvider": "openai"}'

# Normalize a provider name
python auto-claude/cli/provider_info.py normalize "Z.ai GLM 4.7"
# Output: {"input": "Z.ai GLM 4.7", "output": "zai-glm-47"}
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# In .auto-claude/.env
DEBUG=true
DEBUG_LEVEL=2
```

---

## Best Practices

### Security

1. **Never commit API keys** - `.auto-claude/.env` is gitignored by default
2. **Use global credentials** - Avoid storing keys in project files
3. **Rotate keys regularly** - Update via App Settings when needed

### Cost Optimization

1. **Use cheaper models for simple tasks** - `gpt-4o-mini` or `gemini-1.5-flash`
2. **Use local models for iteration** - Ollama for quick prototyping
3. **OpenRouter for flexibility** - Compare providers without managing keys

See [COST_COMPARISON.md](COST_COMPARISON.md) for detailed pricing analysis.

### Performance

1. **Claude Code** - Best integration, recommended for most workflows
2. **Groq** - Fastest inference for open models
3. **Ollama** - No network latency for local development

---

## Provider ID Normalization

Provider IDs are normalized for consistency:

| Display Name | Normalized ID |
|-------------|---------------|
| OpenAI | `openai` |
| Z.ai GLM 4.7 | `zai-glm-47` |
| Custom Provider | `custom-provider` |
| Google Gemini | `google-gemini` |

**Normalization Rules:**
1. Convert to lowercase
2. Replace spaces with dashes
3. Remove special characters (except dashes and numbers)
4. Collapse multiple dashes to single dash
5. Remove leading/trailing dashes

This ensures consistent matching between UI and CLI configurations.

---

## Further Reading

- [CLI Usage Guide](../guides/CLI-USAGE.md) - Terminal-only workflows
- [Cost Comparison](COST_COMPARISON.md) - Provider pricing analysis
- [Environment Variables](../auto-claude/.env.example) - Full configuration reference
