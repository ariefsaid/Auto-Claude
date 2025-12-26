# LLM Provider Cost Comparison

This guide helps you choose the right provider based on your budget and use case. All prices are per million tokens as of December 2025.

## Pricing Overview

### Premium Providers

| Provider | Model | Input ($/1M) | Output ($/1M) | Context Window | Best For |
|----------|-------|--------------|---------------|----------------|----------|
| **Claude Code** | Claude 3.5 Sonnet | Included¹ | Included¹ | 200K | Recommended default |
| **OpenAI** | GPT-4o | $2.50 | $10.00 | 128K | Complex coding tasks |
| **OpenAI** | o1 | $15.00 | $60.00 | 128K | Reasoning-heavy tasks |
| **OpenAI** | o1-mini | $3.00 | $12.00 | 128K | Balanced reasoning |
| **Anthropic** | Claude 3.5 Sonnet | $3.00 | $15.00 | 200K | Long context, nuanced code |
| **Anthropic** | Claude 3 Opus | $15.00 | $75.00 | 200K | Highest quality output |
| **Google** | Gemini 1.5 Pro | $1.25 | $5.00 | 2M | Very long context |
| **Mistral** | Mistral Large | $2.00 | $6.00 | 128K | European compliance |

¹ Claude Code usage is included with Claude Pro ($20/mo) or Claude Max ($100/mo) subscription.

### Budget-Friendly Providers

| Provider | Model | Input ($/1M) | Output ($/1M) | Context Window | Best For |
|----------|-------|--------------|---------------|----------------|----------|
| **OpenAI** | GPT-4o-mini | $0.15 | $0.60 | 128K | Cost-effective general use |
| **Google** | Gemini 1.5 Flash | $0.075 | $0.30 | 1M | Fast, cheap responses |
| **Google** | Gemini 2.0 Flash | $0.10 | $0.40 | 1M | Latest features, still cheap |
| **Anthropic** | Claude 3 Haiku | $0.25 | $1.25 | 200K | Quick, cheap Claude responses |
| **Mistral** | Mistral Small | $0.20 | $0.60 | 32K | Efficient European option |
| **Groq** | Llama 3.1 70B | $0.59 | $0.79 | 128K | Ultra-fast inference |
| **Groq** | Llama 3.1 8B | $0.05 | $0.08 | 128K | Fastest, cheapest cloud |
| **Together AI** | Llama 3.1 70B | $0.88 | $0.88 | 128K | Open-source quality |

### Free / Local Options

| Provider | Model | Cost | Requirements | Best For |
|----------|-------|------|--------------|----------|
| **Ollama** | Llama 3.1 8B | Free | 8GB RAM | Quick prototyping |
| **Ollama** | Llama 3.1 70B | Free | 40GB RAM | Quality local inference |
| **Ollama** | CodeLlama 34B | Free | 20GB RAM | Code-focused local |
| **OpenRouter** | Free tier | Limited free | Account required | Testing multiple models |

---

## Cost Estimates by Task Size

Understanding how much a task costs helps you choose the right provider.

### Token Usage Reference

| Task Type | Typical Input Tokens | Typical Output Tokens | Total Tokens |
|-----------|---------------------|----------------------|--------------|
| Simple bug fix | 2,000-5,000 | 500-1,500 | 2,500-6,500 |
| New function | 5,000-15,000 | 1,000-3,000 | 6,000-18,000 |
| Small feature | 20,000-50,000 | 5,000-15,000 | 25,000-65,000 |
| Large refactor | 100,000-300,000 | 30,000-80,000 | 130,000-380,000 |
| Multi-file feature | 200,000-500,000 | 50,000-150,000 | 250,000-650,000 |

### Small Feature Example (~50K tokens)

| Provider | Model | Estimated Cost |
|----------|-------|----------------|
| **Claude Code** | Claude 3.5 Sonnet | $0.00 (subscription) |
| **Ollama** | Llama 3.1 | $0.00 (local) |
| **Groq** | Llama 3.1 8B | $0.003 |
| **Google** | Gemini 1.5 Flash | $0.02 |
| **OpenAI** | GPT-4o-mini | $0.04 |
| **Anthropic** | Claude 3 Haiku | $0.05 |
| **Together AI** | Llama 3.1 70B | $0.04 |
| **Groq** | Llama 3.1 70B | $0.03 |
| **OpenAI** | GPT-4o | $0.38 |
| **Google** | Gemini 1.5 Pro | $0.19 |
| **Anthropic** | Claude 3.5 Sonnet | $0.45 |
| **OpenAI** | o1-mini | $0.45 |
| **Anthropic** | Claude 3 Opus | $2.25 |
| **OpenAI** | o1 | $2.25 |

### Large Refactor Example (~250K tokens)

| Provider | Model | Estimated Cost |
|----------|-------|----------------|
| **Claude Code** | Claude 3.5 Sonnet | $0.00 (subscription) |
| **Ollama** | Llama 3.1 | $0.00 (local) |
| **Groq** | Llama 3.1 8B | $0.02 |
| **Google** | Gemini 1.5 Flash | $0.09 |
| **OpenAI** | GPT-4o-mini | $0.19 |
| **Anthropic** | Claude 3 Haiku | $0.25 |
| **Together AI** | Llama 3.1 70B | $0.22 |
| **Groq** | Llama 3.1 70B | $0.17 |
| **OpenAI** | GPT-4o | $1.88 |
| **Google** | Gemini 1.5 Pro | $0.94 |
| **Anthropic** | Claude 3.5 Sonnet | $2.25 |
| **OpenAI** | o1-mini | $2.25 |
| **Anthropic** | Claude 3 Opus | $11.25 |
| **OpenAI** | o1 | $11.25 |

---

## Cost Optimization Strategies

### Development & Testing

**Goal:** Fast iteration with minimal cost

**Recommended Stack:**
1. **Primary:** Ollama (Llama 3.1 8B) - Free, instant responses
2. **Fallback:** Groq (Llama 3.1 8B) - $0.05/1M, ultra-fast cloud backup
3. **Review:** GPT-4o-mini - $0.75/1M, when you need quality checks

**Estimated Monthly Cost:** $0-5

**Configuration:**
```bash
# .auto-claude/.env (development)
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=ollama
OPENCODE_MODEL=llama3.1
```

**Tips:**
- Run Ollama locally for zero latency and cost
- Use cloud only when local model struggles
- Batch similar changes to reduce context overhead

---

### Production Quality

**Goal:** High-quality code for shipping

**Recommended Stack:**
1. **Primary:** Claude Code (Claude 3.5 Sonnet) - Best coding model, subscription-based
2. **Alternative:** GPT-4o - When you need fresh training data (cut-off is more recent)
3. **Long context:** Gemini 1.5 Pro - For refactors spanning many files

**Estimated Monthly Cost:** $20-100 (Claude subscription)

**Configuration:**
```bash
# .auto-claude/.env (production)
AGENT_PROVIDER=claude_code
# Claude Code handles everything automatically
```

**Tips:**
- Claude Code subscription provides unlimited use for most workflows
- Use GPT-4o for tasks requiring knowledge of very recent frameworks
- Switch to Gemini for files exceeding 100K tokens

---

### High Volume / Team Use

**Goal:** Scale across multiple developers and projects

**Recommended Stack:**
1. **Primary:** GPT-4o-mini - $0.75/1M, 90% of Claude quality at 5% of cost
2. **Quality:** GPT-4o - Use for final reviews and complex logic
3. **Batch:** Gemini 1.5 Flash - $0.375/1M, great for bulk processing

**Estimated Monthly Cost:** $50-500 (varies with team size)

**Configuration:**
```bash
# .auto-claude/.env (team)
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=openai
OPENCODE_MODEL=gpt-4o-mini

# Override for complex tasks:
# python auto-claude/run.py --spec 001 --provider opencode --model gpt-4o
```

**Tips:**
- Set up OpenRouter for single billing across providers
- Use model routing based on task complexity
- Monitor usage with provider dashboards

---

### Budget-Constrained

**Goal:** Maximum capability with minimal spend

**Recommended Stack:**
1. **Primary:** Groq (Llama 3.1 70B) - $1.38/1M, GPT-4 class at 10% cost
2. **Free:** Ollama - Zero cost for simple tasks
3. **Fallback:** Gemini 1.5 Flash - $0.375/1M, for long context needs

**Estimated Monthly Cost:** $5-20

**Configuration:**
```bash
# .auto-claude/.env (budget)
AGENT_PROVIDER=opencode
OPENCODE_PROVIDER=groq
OPENCODE_MODEL=llama-3.1-70b-versatile
```

**Tips:**
- Open-source models have caught up significantly
- Groq's speed makes iteration faster
- Consider Claude Pro if you do heavy daily use ($20/mo unlimited)

---

## Provider Selection Guide

### By Use Case

| Use Case | Recommended | Why |
|----------|-------------|-----|
| **Daily development** | Claude Code | Best coding model, included in subscription |
| **Quick prototyping** | Ollama + Llama 3.1 | Free, instant, private |
| **Complex algorithms** | o1 or Claude 3 Opus | Best reasoning capabilities |
| **Large codebase refactor** | Gemini 1.5 Pro | 2M context window |
| **Team CI/CD integration** | GPT-4o-mini | Cost-effective, reliable API |
| **Compliance-sensitive** | Mistral Large | European data residency |
| **Maximum speed** | Groq | Fastest inference available |
| **Cost-sensitive** | Groq + Llama 3.1 70B | Best value for quality |

### By Budget

| Monthly Budget | Recommended Setup |
|----------------|-------------------|
| **$0** | Ollama (local) |
| **$0-10** | Ollama + Groq fallback |
| **$20** | Claude Pro subscription |
| **$50** | GPT-4o-mini primary + GPT-4o for reviews |
| **$100+** | Claude Max + GPT-4o for variety |

### By Quality Requirements

| Quality Level | Recommended Model | Cost Level |
|---------------|-------------------|------------|
| **Highest** | Claude 3 Opus or o1 | $$$$ |
| **Excellent** | Claude 3.5 Sonnet or GPT-4o | $$$ |
| **Good** | GPT-4o-mini or Gemini 1.5 Flash | $ |
| **Acceptable** | Llama 3.1 70B (Groq/Together) | $ |
| **Basic** | Llama 3.1 8B (Groq/Ollama) | Free-$ |

---

## Cost Calculation Examples

### Scenario 1: Solo Developer (Hobbyist)

**Usage:** 3-5 coding sessions per week, ~100K tokens/week

| Option | Monthly Cost | Notes |
|--------|--------------|-------|
| Ollama | $0 | All local, requires decent hardware |
| Groq | $0.50 | 400K tokens at $1.38/1M |
| Claude Pro | $20 | Unlimited, best quality |

**Recommendation:** Claude Pro if you value quality; Ollama for zero cost.

---

### Scenario 2: Freelancer (Regular Use)

**Usage:** Daily use, ~500K tokens/week (2M/month)

| Option | Monthly Cost | Notes |
|--------|--------------|-------|
| Claude Pro | $20 | Unlimited, subscription |
| GPT-4o-mini | $1.50 | 2M tokens at $0.75/1M |
| GPT-4o | $15 | 2M tokens at $7.50/1M |
| Groq (70B) | $2.76 | 2M tokens at $1.38/1M |

**Recommendation:** Claude Pro for best value and quality.

---

### Scenario 3: Startup Team (5 developers)

**Usage:** Heavy daily use, ~10M tokens/week (40M/month)

| Option | Monthly Cost | Notes |
|--------|--------------|-------|
| Claude Pro (5 seats) | $100 | 5 x $20, unlimited per user |
| GPT-4o-mini | $30 | 40M tokens at $0.75/1M |
| GPT-4o | $300 | 40M tokens at $7.50/1M |
| Mixed (80% mini, 20% 4o) | $84 | Optimal cost/quality |

**Recommendation:** Mixed GPT-4o-mini + GPT-4o, or Claude Pro per developer.

---

### Scenario 4: Enterprise (High Volume)

**Usage:** CI/CD integration, 100M+ tokens/month

| Option | Monthly Cost | Notes |
|--------|--------------|-------|
| GPT-4o-mini | $75 | 100M tokens at $0.75/1M |
| Gemini 1.5 Flash | $37.50 | 100M tokens at $0.375/1M |
| Groq (70B) | $138 | 100M tokens at $1.38/1M |
| Self-hosted Llama | ~$500 | GPU rental, unlimited tokens |

**Recommendation:** Gemini 1.5 Flash for volume, GPT-4o-mini for reliability.

---

## Hidden Costs to Consider

### API vs Subscription

| Factor | API Billing | Subscription |
|--------|-------------|--------------|
| Predictability | Variable | Fixed |
| Unused capacity | No waste | May be wasted |
| Scaling | Linear cost increase | Add seats |
| Team sharing | Single billing | Per-user |

### Infrastructure Costs

| Self-Hosted (Ollama) | Cost Range |
|---------------------|------------|
| Consumer GPU (RTX 4090) | $0 after $1,600 purchase |
| Cloud GPU (A100) | $1-3/hour |
| Electricity (local) | ~$10-30/month |
| Setup time | 2-4 hours initial |

### Opportunity Costs

- **Faster model = faster iteration** → Ship features sooner
- **Smarter model = fewer bugs** → Less debugging time
- **Integrated model (Claude Code) = less config** → Focus on coding

---

## Pricing Changes

LLM pricing changes frequently. Check these sources for current rates:

| Provider | Pricing Page |
|----------|--------------|
| OpenAI | [platform.openai.com/pricing](https://platform.openai.com/pricing) |
| Anthropic | [anthropic.com/pricing](https://www.anthropic.com/pricing) |
| Google | [ai.google.dev/pricing](https://ai.google.dev/pricing) |
| Groq | [groq.com/pricing](https://groq.com/pricing) |
| Together AI | [together.ai/pricing](https://www.together.ai/pricing) |
| Mistral | [mistral.ai/pricing](https://mistral.ai/pricing) |
| OpenRouter | [openrouter.ai/models](https://openrouter.ai/models) |

**Last Updated:** December 2025

---

## Summary Recommendations

| Situation | Best Choice | Monthly Cost |
|-----------|-------------|--------------|
| **Just getting started** | Claude Pro | $20 |
| **Zero budget** | Ollama (local) | $0 |
| **Need variety** | OpenRouter + various | ~$10-50 |
| **Team deployment** | GPT-4o-mini | ~$0.75/1M tokens |
| **Maximum quality** | Claude 3 Opus or o1 | ~$45/1M tokens |
| **Maximum speed** | Groq | ~$1.38/1M tokens |
| **Long documents** | Gemini 1.5 Pro | ~$3.25/1M tokens |

---

## Related Resources

- [Provider Setup Guide](PROVIDERS.md) - Detailed configuration instructions
- [.env.example](../auto-claude/.env.example) - Configuration reference
- [CLI Usage](../guides/CLI-USAGE.md) - Command line options
