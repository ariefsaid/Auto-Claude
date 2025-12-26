"""
Auto Claude CLI - Main Entry Point
===================================

Command-line interface for the Auto Claude autonomous coding framework.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from ui import (
    Icons,
    icon,
)

from .build_commands import handle_build_command
from .followup_commands import handle_followup_command
from .provider_info import (
    AgentProviderType,
    ConfigSource,
    load_global_settings,
    load_project_env,
    normalize_provider_id,
    parse_provider_credentials,
)
from .qa_commands import (
    handle_qa_command,
    handle_qa_status_command,
    handle_review_status_command,
)
from .spec_commands import print_specs_list
from .utils import (
    DEFAULT_MODEL,
    find_spec,
    get_project_dir,
    print_banner,
    setup_environment,
)
from .workspace_commands import (
    handle_cleanup_worktrees_command,
    handle_discard_command,
    handle_list_worktrees_command,
    handle_merge_command,
    handle_review_command,
)

# Type alias for provider configuration
ProviderConfig = dict[str, str | bool | dict | None]


def get_provider_config(
    project_dir: Path,
    cli_provider: str | None = None,
) -> ProviderConfig:
    """
    Get provider configuration with priority: CLI flag > Project .env > Global settings > Default.

    Args:
        project_dir: Project root directory
        cli_provider: Provider specified via --provider CLI flag (optional)

    Returns:
        ProviderConfig dictionary with:
        - provider: Agent provider type ('claude_code' or 'opencode')
        - source: Configuration source ('cli_flag', 'project_env', 'global_settings', 'default')
        - opencode_provider: OpenCode LLM provider ID (if using opencode)
        - opencode_model: OpenCode model override (if using opencode)
        - is_global: Whether using global credentials
        - credentials: Credential reference information
    """
    provider: AgentProviderType = "claude_code"
    source: ConfigSource = "default"
    opencode_provider: str | None = None
    opencode_model: str | None = None
    is_global: bool = False
    credentials: dict = {}

    # Priority 1: CLI flag (highest)
    if cli_provider and cli_provider in ("claude_code", "opencode"):
        provider = cli_provider  # type: ignore
        source = "cli_flag"

    # Priority 2: Project .env
    if source == "default":
        project_env = load_project_env(project_dir)
        env_provider = project_env.get("AGENT_PROVIDER", "").strip().lower()
        if env_provider in ("claude_code", "opencode"):
            provider = env_provider  # type: ignore
            source = "project_env"

    # Priority 3: Global settings
    if source == "default":
        global_settings = load_global_settings()
        global_provider = (
            str(global_settings.get("globalDefaultProvider", "")).strip().lower()
        )
        if global_provider in ("claude_code", "opencode"):
            provider = global_provider  # type: ignore
            source = "global_settings"

    # Load additional configuration based on provider type
    if provider == "opencode":
        # Load OpenCode-specific configuration
        oc_project_env = load_project_env(project_dir)
        oc_global_settings = load_global_settings()

        # Get OpenCode provider and model
        opencode_provider = oc_project_env.get("OPENCODE_PROVIDER", "").strip() or None
        if not opencode_provider:
            opencode_provider = oc_global_settings.get("globalOpencodeProvider") or None
        if opencode_provider:
            opencode_provider = normalize_provider_id(opencode_provider)

        opencode_model = oc_project_env.get("OPENCODE_MODEL", "").strip() or None
        if not opencode_model:
            opencode_model = oc_global_settings.get("globalOpencodeModel") or None

        # Check if using global credentials
        is_global_str = oc_project_env.get("AGENT_PROVIDER_IS_GLOBAL", "").lower()
        is_global = is_global_str == "true"

        # Parse provider credentials
        provider_credentials = parse_provider_credentials(
            oc_project_env.get("PROVIDER_CREDENTIALS")
        )
        if opencode_provider and opencode_provider in provider_credentials:
            credentials = provider_credentials[opencode_provider]
            # Check credential reference's isGlobal flag
            if credentials.get("isGlobal", False):
                is_global = True

    return {
        "provider": provider,
        "source": source,
        "opencode_provider": opencode_provider,
        "opencode_model": opencode_model,
        "is_global": is_global,
        "credentials": credentials,
    }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Auto Claude Framework - Autonomous multi-session coding agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all specs
  python auto-claude/run.py --list

  # Run a specific spec (by number or full name)
  python auto-claude/run.py --spec 001
  python auto-claude/run.py --spec 001-initial-app

  # Workspace management (after build completes)
  python auto-claude/run.py --spec 001 --merge     # Add build to your project
  python auto-claude/run.py --spec 001 --review    # See what was built
  python auto-claude/run.py --spec 001 --discard   # Delete build (with confirmation)

  # Advanced options
  python auto-claude/run.py --spec 001 --direct       # Skip workspace isolation
  python auto-claude/run.py --spec 001 --isolated     # Force workspace isolation

  # Status checks
  python auto-claude/run.py --spec 001 --review-status  # Check human review status
  python auto-claude/run.py --spec 001 --qa-status      # Check QA validation status

Prerequisites:
  1. Create a spec first: claude /spec
  2. Run 'claude setup-token' and set CLAUDE_CODE_OAUTH_TOKEN

Environment Variables:
  CLAUDE_CODE_OAUTH_TOKEN  Your Claude Code OAuth token (required)
                           Get it by running: claude setup-token
  AUTO_BUILD_MODEL         Override default model (optional)
        """,
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available specs and their status",
    )

    parser.add_argument(
        "--spec",
        type=str,
        default=None,
        help="Spec to run (e.g., '001' or '001-feature-name')",
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project directory (default: current working directory)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent sessions (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    parser.add_argument(
        "--provider",
        type=str,
        choices=["claude_code", "opencode"],
        default=None,
        help="Agent provider type: 'claude_code' (official SDK) or 'opencode' (multi-provider CLI)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    # Workspace options
    workspace_group = parser.add_mutually_exclusive_group()
    workspace_group.add_argument(
        "--isolated",
        action="store_true",
        help="Force building in isolated workspace (safer)",
    )
    workspace_group.add_argument(
        "--direct",
        action="store_true",
        help="Build directly in your project (no isolation)",
    )

    # Build management commands
    build_group = parser.add_mutually_exclusive_group()
    build_group.add_argument(
        "--merge",
        action="store_true",
        help="Merge an existing build into your project",
    )
    build_group.add_argument(
        "--review",
        action="store_true",
        help="Review what an existing build contains",
    )
    build_group.add_argument(
        "--discard",
        action="store_true",
        help="Discard an existing build (requires confirmation)",
    )

    # Merge options
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="With --merge: stage changes but don't commit (review in IDE first)",
    )
    parser.add_argument(
        "--merge-preview",
        action="store_true",
        help="Preview merge conflicts without actually merging (returns JSON)",
    )

    # QA options
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Run QA validation loop on a completed build",
    )
    parser.add_argument(
        "--qa-status",
        action="store_true",
        help="Show QA validation status for a spec",
    )
    parser.add_argument(
        "--skip-qa",
        action="store_true",
        help="Skip automatic QA validation after build completes",
    )

    # Follow-up options
    parser.add_argument(
        "--followup",
        action="store_true",
        help="Add follow-up tasks to a completed spec (extends existing implementation plan)",
    )

    # Review options
    parser.add_argument(
        "--review-status",
        action="store_true",
        help="Show human review/approval status for a spec",
    )

    # Dev mode (deprecated)
    parser.add_argument(
        "--dev",
        action="store_true",
        help="[Deprecated] No longer has any effect - kept for compatibility",
    )

    # Non-interactive mode (for UI/automation)
    parser.add_argument(
        "--auto-continue",
        action="store_true",
        help="Non-interactive mode: auto-continue existing builds, skip prompts (for UI integration)",
    )

    # Worktree management
    parser.add_argument(
        "--list-worktrees",
        action="store_true",
        help="List all spec worktrees and their status",
    )
    parser.add_argument(
        "--cleanup-worktrees",
        action="store_true",
        help="Remove all spec worktrees and their branches (with confirmation)",
    )

    # Force bypass
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip approval check and start build anyway (for debugging)",
    )

    # Base branch for worktree creation
    parser.add_argument(
        "--base-branch",
        type=str,
        default=None,
        help="Base branch for creating worktrees (default: auto-detect or current branch)",
    )

    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    # Set up environment first
    setup_environment()

    # Parse arguments
    args = parse_args()

    # Import debug functions after environment setup
    from debug import debug, debug_error, debug_section, debug_success

    debug_section("run.py", "Starting Auto-Build Framework")
    debug("run.py", "Arguments parsed", args=vars(args))

    # Determine project directory
    project_dir = get_project_dir(args.project_dir)
    debug("run.py", f"Using project directory: {project_dir}")

    # Get model (with env var fallback)
    model = args.model or os.environ.get("AUTO_BUILD_MODEL", DEFAULT_MODEL)

    # Note: --dev flag is deprecated but kept for API compatibility
    if args.dev:
        print(
            f"\n{icon(Icons.GEAR)} Note: --dev flag is deprecated. All specs now use .auto-claude/specs/\n"
        )

    # Handle --list command
    if args.list:
        print_banner()
        print_specs_list(project_dir, args.dev)
        return

    # Handle --list-worktrees command
    if args.list_worktrees:
        handle_list_worktrees_command(project_dir)
        return

    # Handle --cleanup-worktrees command
    if args.cleanup_worktrees:
        handle_cleanup_worktrees_command(project_dir)
        return

    # Require --spec if not listing
    if not args.spec:
        print_banner()
        print("\nError: --spec is required")
        print("\nUsage:")
        print("  python auto-claude/run.py --list           # See all specs")
        print("  python auto-claude/run.py --spec 001       # Run a spec")
        print("\nCreate a new spec with:")
        print("  claude /spec")
        sys.exit(1)

    # Find the spec
    debug("run.py", "Finding spec", spec_identifier=args.spec, dev_mode=args.dev)
    spec_dir = find_spec(project_dir, args.spec, args.dev)
    if not spec_dir:
        debug_error("run.py", "Spec not found", spec=args.spec)
        print_banner()
        print(f"\nError: Spec '{args.spec}' not found")
        print("\nAvailable specs:")
        print_specs_list(project_dir, args.dev)
        sys.exit(1)

    debug_success("run.py", "Spec found", spec_dir=str(spec_dir))

    # Handle build management commands
    if args.merge_preview:
        from cli.workspace_commands import handle_merge_preview_command

        result = handle_merge_preview_command(
            project_dir, spec_dir.name, base_branch=args.base_branch
        )
        # Output as JSON for the UI to parse
        import json

        print(json.dumps(result))
        return

    if args.merge:
        success = handle_merge_command(
            project_dir,
            spec_dir.name,
            no_commit=args.no_commit,
            base_branch=args.base_branch,
        )
        if not success:
            sys.exit(1)
        return

    if args.review:
        handle_review_command(project_dir, spec_dir.name)
        return

    if args.discard:
        handle_discard_command(project_dir, spec_dir.name)
        return

    # Handle QA commands
    if args.qa_status:
        handle_qa_status_command(spec_dir)
        return

    if args.review_status:
        handle_review_status_command(spec_dir)
        return

    if args.qa:
        handle_qa_command(
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            verbose=args.verbose,
        )
        return

    # Handle --followup command
    if args.followup:
        handle_followup_command(
            project_dir=project_dir,
            spec_dir=spec_dir,
            model=model,
            verbose=args.verbose,
        )
        return

    # Normal build flow
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
    )


if __name__ == "__main__":
    main()
