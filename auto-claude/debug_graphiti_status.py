#!/usr/bin/env python3
"""
Debug script to check Graphiti memory status for a project.

Usage:
    python debug_graphiti_status.py [project_path]

If no project_path is provided, uses current directory.
"""

import asyncio
import sys
from pathlib import Path

# Add auto-claude to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file
from dotenv import load_dotenv

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded .env from: {env_file}")
    print()

from integrations.graphiti.config import (
    GraphitiConfig,
    get_graphiti_status,
    validate_graphiti_config,
)


async def check_graphiti_memory():
    """Check Graphiti memory status and configuration."""
    print("=" * 70)
    print("GRAPHITI MEMORY DIAGNOSTIC")
    print("=" * 70)
    print()

    # 1. Check environment configuration
    print("1. ENVIRONMENT CONFIGURATION")
    print("-" * 70)
    config = GraphitiConfig.from_env()
    print(f"   GRAPHITI_ENABLED: {config.enabled}")
    print(f"   LLM Provider: {config.llm_provider}")
    print(f"   Embedder Provider: {config.embedder_provider}")
    print(f"   FalkorDB: {config.falkordb_host}:{config.falkordb_port}")
    print(f"   Database: {config.database}")
    print()

    # 2. Validate configuration
    print("2. CONFIGURATION VALIDATION")
    print("-" * 70)
    is_valid, errors = validate_graphiti_config()
    if is_valid:
        print("   ✓ Configuration is VALID")
    else:
        print("   ✗ Configuration has ERRORS:")
        for error in errors:
            print(f"     - {error}")
    print()

    # 3. Check detailed status
    print("3. GRAPHITI STATUS")
    print("-" * 70)
    status = get_graphiti_status()
    print(f"   Enabled: {status['enabled']}")
    print(f"   Available: {status['available']}")
    if not status["available"]:
        print(f"   Reason: {status['reason']}")
    if status.get("errors"):
        print("   Errors:")
        for error in status["errors"]:
            print(f"     - {error}")
    print()

    # 4. Test FalkorDB connection
    print("4. FALKORDB CONNECTION TEST")
    print("-" * 70)
    if config.is_valid():
        try:
            from integrations.graphiti.memory import test_graphiti_connection

            success, message = await test_graphiti_connection()
            if success:
                print(f"   ✓ {message}")
            else:
                print(f"   ✗ {message}")
        except ImportError as e:
            print(f"   ✗ Graphiti packages not installed: {e}")
        except Exception as e:
            print(f"   ✗ Connection test failed: {e}")
    else:
        print("   ⊘ Skipped (configuration invalid)")
    print()

    # 5. Check for spec directories with memory
    print("5. MEMORY DATA CHECK")
    print("-" * 70)
    project_path = Path.cwd()
    specs_dir = project_path / ".auto-claude" / "specs"

    if specs_dir.exists():
        specs = [d for d in specs_dir.iterdir() if d.is_dir()]
        print(f"   Found {len(specs)} spec(s) in {specs_dir}")

        memory_found = False
        for spec in specs:
            memory_dir = spec / "memory"
            if memory_dir.exists():
                session_insights = memory_dir / "session_insights"
                if session_insights.exists():
                    sessions = list(session_insights.glob("session_*.json"))
                    if sessions:
                        print(f"   ✓ {spec.name}: {len(sessions)} session(s)")
                        memory_found = True

        if not memory_found:
            print("   ⊘ No memory data found in any spec")
            print(
                "   → Memory is only created after running: python auto-claude/run.py --spec XXX"
            )
    else:
        print(f"   ⊘ No specs directory found at {specs_dir}")
        print("   → Create a spec first with: python auto-claude/spec_runner.py")
    print()

    # 6. Summary
    print("6. SUMMARY")
    print("-" * 70)
    if config.enabled and is_valid:
        print("   Status: ✓ Graphiti is ENABLED and CONFIGURED")
        print()
        print("   Next steps:")
        print("   1. Run a build: python auto-claude/run.py --spec XXX")
        print("   2. Wait for first coder session to complete")
        print("   3. Check memory: docker exec auto-claude-falkordb \\")
        print(
            '         redis-cli GRAPH.QUERY "auto_claude_memory" "MATCH (n) RETURN count(n)"'
        )
    elif config.enabled and not is_valid:
        print("   Status: ⚠ Graphiti is ENABLED but MISCONFIGURED")
        print()
        print("   Action required:")
        print("   1. Fix configuration errors listed above")
        print("   2. Check your .env file in auto-claude/")
    else:
        print("   Status: ⊘ Graphiti is DISABLED")
        print()
        print("   To enable:")
        print("   1. Edit auto-claude/.env")
        print("   2. Set GRAPHITI_ENABLED=true")
        print("   3. Configure provider credentials (see .env.example)")
        print("   4. Start FalkorDB: docker-compose up -d")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_path = Path(sys.argv[1])
        import os

        os.chdir(project_path)
        print(f"Checking project: {project_path}")
        print()

    asyncio.run(check_graphiti_memory())
