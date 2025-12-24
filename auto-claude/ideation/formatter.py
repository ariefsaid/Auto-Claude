"""
Output formatting for ideation results.

Formats and merges ideation outputs into a cohesive ideation.json file.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add auto-claude to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui import print_status


class IdeationFormatter:
    """Formats ideation output into structured JSON."""

    def __init__(self, output_dir: Path, project_dir: Path):
        self.output_dir = Path(output_dir)
        self.project_dir = Path(project_dir)

    def merge_ideation_outputs(
        self,
        enabled_types: list[str],
        context_data: dict,
        append: bool = False,
    ) -> tuple[Path, int]:
        """Merge all ideation outputs into a single ideation.json.

        Returns: (ideation_file_path, total_ideas_count)
        """
        ideation_file = self.output_dir / "ideation.json"

        # ALWAYS load existing ideas to preserve status (even when not in append mode)
        existing_ideas_by_id = {}
        existing_session = None
        if ideation_file.exists():
            try:
                with open(ideation_file) as f:
                    existing_session = json.load(f)
                    existing_ideas = existing_session.get("ideas", [])
                    # Create lookup by ID for efficient status preservation
                    for idea in existing_ideas:
                        idea_id = idea.get("id")
                        if idea_id:
                            existing_ideas_by_id[idea_id] = idea
                    if existing_ideas_by_id:
                        print_status(
                            f"Found {len(existing_ideas_by_id)} existing ideas to preserve status from",
                            "info",
                        )
            except json.JSONDecodeError:
                pass

        # Collect new ideas from the enabled types
        new_ideas = []
        output_files = []

        for ideation_type in enabled_types:
            type_file = self.output_dir / f"{ideation_type}_ideas.json"
            if type_file.exists():
                try:
                    with open(type_file) as f:
                        data = json.load(f)
                        ideas = data.get(ideation_type, [])

                        # Merge with existing ideas to preserve status and metadata
                        for idea in ideas:
                            idea_id = idea.get("id")
                            if idea_id and idea_id in existing_ideas_by_id:
                                existing = existing_ideas_by_id[idea_id]
                                # Preserve user-managed metadata from existing idea
                                idea["status"] = existing.get("status", "draft")
                                # Preserve task conversion metadata
                                if "taskId" in existing:
                                    idea["taskId"] = existing["taskId"]
                                if "task_id" in existing:
                                    idea["task_id"] = existing["task_id"]
                                # Preserve timestamp metadata
                                if "dismissedAt" in existing:
                                    idea["dismissedAt"] = existing["dismissedAt"]
                                if "dismissed_at" in existing:
                                    idea["dismissed_at"] = existing["dismissed_at"]
                                if "archivedAt" in existing:
                                    idea["archivedAt"] = existing["archivedAt"]
                                if "archived_at" in existing:
                                    idea["archived_at"] = existing["archived_at"]
                                if "convertedAt" in existing:
                                    idea["convertedAt"] = existing["convertedAt"]
                                if "converted_at" in existing:
                                    idea["converted_at"] = existing["converted_at"]

                        new_ideas.extend(ideas)
                        output_files.append(str(type_file))
                except (json.JSONDecodeError, KeyError):
                    pass

        # In append mode, also preserve ideas from types NOT being regenerated
        # (to avoid duplicates) and keep ideas from other types
        if append and existing_ideas_by_id:
            # Keep existing ideas that are NOT from the types we just generated
            preserved_ideas = [
                idea
                for idea in existing_ideas_by_id.values()
                if idea.get("type") not in enabled_types
            ]
            all_ideas = preserved_ideas + new_ideas
            print_status(
                f"Merged: {len(preserved_ideas)} preserved + {len(new_ideas)} new = {len(all_ideas)} total",
                "info",
            )
        else:
            all_ideas = new_ideas

        # Create merged ideation session
        # Preserve session ID and generated_at if appending
        session_id = (
            existing_session.get("id")
            if existing_session
            else f"ideation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        generated_at = (
            existing_session.get("generated_at")
            if existing_session
            else datetime.now().isoformat()
        )

        ideation_session = {
            "id": session_id,
            "project_id": str(self.project_dir),
            "config": context_data.get("config", {}),
            "ideas": all_ideas,
            "project_context": {
                "existing_features": context_data.get("existing_features", []),
                "tech_stack": context_data.get("tech_stack", []),
                "target_audience": context_data.get("target_audience"),
                "planned_features": context_data.get("planned_features", []),
            },
            "summary": {
                "total_ideas": len(all_ideas),
                "by_type": {},
                "by_status": {},
            },
            "generated_at": generated_at,
            "updated_at": datetime.now().isoformat(),
        }

        # Count by type and status
        for idea in all_ideas:
            idea_type = idea.get("type", "unknown")
            idea_status = idea.get("status", "draft")
            ideation_session["summary"]["by_type"][idea_type] = (
                ideation_session["summary"]["by_type"].get(idea_type, 0) + 1
            )
            ideation_session["summary"]["by_status"][idea_status] = (
                ideation_session["summary"]["by_status"].get(idea_status, 0) + 1
            )

        with open(ideation_file, "w") as f:
            json.dump(ideation_session, f, indent=2)

        action = "Updated" if append else "Created"
        print_status(
            f"{action} ideation.json ({len(all_ideas)} total ideas)", "success"
        )

        return ideation_file, len(all_ideas)

    def load_context(self) -> dict:
        """Load context data from ideation_context.json."""
        context_file = self.output_dir / "ideation_context.json"
        context_data = {}
        if context_file.exists():
            try:
                with open(context_file) as f:
                    context_data = json.load(f)
            except json.JSONDecodeError:
                pass
        return context_data
