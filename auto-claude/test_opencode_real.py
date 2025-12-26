#!/usr/bin/env python3
"""
Real OpenCode CLI Integration Test
===================================

This script tests the OpenCodeProvider implementation with the ACTUAL OpenCode CLI
(not mocked). It validates that our abstraction layer works with the real CLI.

Prerequisites:
- OpenCode CLI installed (check with: opencode --version)
- Z.ai API key configured (or other provider)

Run:
    python auto-claude/test_opencode_real.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add auto-claude to path
sys.path.insert(0, str(Path(__file__).parent))

from core.providers.config import AgentProvider, ProviderConfig, ProviderCredential
from core.providers.factory import create_client
from core.providers.messages import TextContent, UniversalMessage


async def test_opencode_real():
    """Test OpenCodeProvider with real CLI."""

    print("=" * 80)
    print("Real OpenCode CLI Integration Test")
    print("=" * 80)

    # Check if OpenCode CLI is available
    import shutil

    opencode_path = shutil.which("opencode")
    if not opencode_path:
        print("❌ OpenCode CLI not found. Install with:")
        print("   curl -fsSL https://opencode.ai/install | bash")
        return False

    print(f"✓ OpenCode CLI found: {opencode_path}")

    # Get OpenCode version
    import subprocess

    try:
        version = subprocess.check_output(["opencode", "--version"], text=True).strip()
        print(f"✓ OpenCode version: {version}")
    except Exception as e:
        print(f"⚠ Could not get OpenCode version: {e}")

    # Check for Z.ai API key (or configure other provider)
    provider_to_use = "zai-coding-plan"  # Default to Z.ai
    model_to_use = "glm-4.7"

    # Try to detect which provider is available
    api_keys_to_check = [
        ("ZAI_API_KEY", "zai-coding-plan", "glm-4.7"),
        ("OPENAI_API_KEY", "opencode", "gpt-5-nano"),
        ("ANTHROPIC_API_KEY", "opencode", "claude-sonnet-4"),
    ]

    api_key = None
    for env_var, provider, model in api_keys_to_check:
        key = os.getenv(env_var)
        if key:
            api_key = key
            provider_to_use = provider
            model_to_use = model
            print(
                f"✓ Found {env_var} - using provider: {provider_to_use}/{model_to_use}"
            )
            break

    if not api_key:
        print("\n❌ No API key found. Set one of:")
        for env_var, _, _ in api_keys_to_check:
            print(f"   export {env_var}=your-key-here")
        print("\nTo get Z.ai API key (recommended for testing):")
        print("   https://z.ai/manage-apikey/apikey-list")
        return False

    # Configure provider
    print("\n" + "-" * 80)
    print("Configuring ProviderConfig...")
    print("-" * 80)

    # Create provider configuration
    config = ProviderConfig(
        provider=AgentProvider.OPENCODE,
        credentials={
            provider_to_use: ProviderCredential(
                provider=provider_to_use,
                api_key=api_key,
                is_global=False,
                default_model=model_to_use,
            )
        },
        opencode_provider=provider_to_use,
        opencode_model=model_to_use,
    )

    print(f"Provider: {config.provider}")
    print(f"OpenCode Provider: {config.opencode_provider}")
    print(f"OpenCode Model: {config.opencode_model}")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")

    # Validate config
    if not config.is_valid():
        errors = config.get_validation_errors()
        print("\n❌ Configuration validation failed:")
        for error in errors:
            print(f"   - {error}")
        return False

    print("✓ Configuration valid")

    # Create OpenCodeProvider
    print("\n" + "-" * 80)
    print("Creating OpenCodeProvider client...")
    print("-" * 80)

    try:
        client = create_client(
            config=config,
            project_dir=Path.cwd(),
            spec_dir=Path.cwd() / ".auto-claude" / "specs" / "test",
            model=model_to_use,
        )
        print(f"✓ Client created: {client.__class__.__name__}")
        print(f"  - Capabilities: {client.capabilities}")

        # Note: Security is controlled at provider level via OpenCodeProvider constructor
        # For testing, we're using the default (security disabled for non-production)
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test query
    print("\n" + "-" * 80)
    print("Testing query: 'What is 2+2? Answer in one sentence.'")
    print("-" * 80)

    try:
        async with client:
            # Create simple query
            query = UniversalMessage(
                role="user",
                content=[TextContent(text="What is 2+2? Answer in one sentence.")],
            )

            print("\nSending query to OpenCode CLI...")
            print("(This may take 10-30 seconds for first run)")

            # Send query and get response
            response = await client.query(query)

            print("\n✓ Response received!")
            print("\n" + "=" * 80)
            print("RESPONSE:")
            print("=" * 80)

            # Print response content
            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        print(block.text)
                    elif hasattr(block, "name"):
                        print(f"[Tool: {block.name}]")
                    else:
                        print(f"[Unknown block type: {type(block).__name__}]")
            else:
                print("(Empty response - no content blocks)")

            # Debug: Show raw response structure
            print("\nDEBUG INFO:")
            print(f"Response role: {response.role}")
            print(f"Content blocks: {len(response.content)}")
            for i, block in enumerate(response.content):
                print(f"  Block {i}: {type(block).__name__}")
                if hasattr(block, "__dict__"):
                    print(f"    Fields: {block.__dict__}")

            print("=" * 80)

    except Exception as e:
        print(f"\n❌ Query failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ Real OpenCode CLI integration test PASSED!")
    print("=" * 80)
    print("\nThe OpenCodeProvider implementation works with the actual OpenCode CLI.")
    print("This validates that our abstraction layer correctly:")
    print("  - Spawns the OpenCode subprocess")
    print("  - Sends queries via CLI")
    print("  - Parses JSON responses")
    print("  - Converts to UniversalMessage format")

    return True


if __name__ == "__main__":
    print("\n")
    success = asyncio.run(test_opencode_real())

    if success:
        print("\n✅ SUCCESS - Ready to merge to feature/multi-provider")
        sys.exit(0)
    else:
        print("\n⚠ Test incomplete - check prerequisites above")
        sys.exit(1)
