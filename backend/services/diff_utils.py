"""
diff_utils.py — Diff Position Mapper
=======================================

Why this exists:
When CodeSense posts inline comments on a GitHub PR, GitHub requires a
"position" — the line's offset within the diff — NOT the absolute line
number in the file.

Example diff:
    @@ -10,6 +10,8 @@          ← hunk header
     def login():               ← position 1
    -    old_code()             ← position 2
    +    new_code()             ← position 3  (this is line 11 in the actual file)
    +    extra_code()           ← position 4  (this is line 12 in the actual file)
         return True            ← position 5

If our agent says "issue on line 12 of auth.py", we need to convert
that to "position 4 in the auth.py diff". That's what this module does.
"""

import re
from typing import Optional


def parse_diff_positions(diff_text: str) -> dict[str, dict[int, int]]:
    """
    Parses a unified diff and builds a mapping from absolute line numbers
    to diff positions for each file.

    Args:
        diff_text: The full raw diff string from GitHub

    Returns:
        A dict like:
        {
            "src/auth.py": {11: 3, 12: 4, ...},
            "src/app.py": {5: 1, 6: 2, ...},
        }
        Where keys are filenames and values map absolute_line → diff_position
    """
    result = {}
    current_file = None
    position = 0  # Position counter (resets per file)
    current_new_line = 0  # Tracks the absolute line number in the new file

    for line in diff_text.split("\n"):
        # Detect file headers: +++ b/src/auth.py
        if line.startswith("+++ b/"):
            current_file = line[6:]  # Strip the "+++ b/" prefix
            result[current_file] = {}
            position = 0
            continue

        # Skip the "--- a/..." header lines
        if line.startswith("--- "):
            continue

        # Parse hunk headers: @@ -10,6 +10,8 @@
        # The +10,8 means "starting at line 10 in the new file, 8 lines long"
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            current_new_line = int(hunk_match.group(1))
            position += 1  # The @@ line itself counts as a position
            continue

        if current_file is None:
            continue

        position += 1

        if line.startswith("-"):
            # Removed line — no new-file line number, but it does have a position
            # We don't map these since agents should focus on added lines
            continue
        elif line.startswith("+"):
            # Added line — this has both a position and a new-file line number
            result[current_file][current_new_line] = position
            current_new_line += 1
        else:
            # Context line (unchanged) — has a new-file line number
            result[current_file][current_new_line] = position
            current_new_line += 1

    return result


def find_closest_position(
    file_positions: dict[int, int], target_line: int
) -> Optional[int]:
    """
    If the exact line isn't in the diff, find the closest line that IS in the diff.
    This handles cases where the agent reports a line that's near but not exactly
    on a diff line.

    Args:
        file_positions: {absolute_line: diff_position} for one file
        target_line: The line number the agent reported

    Returns:
        The diff position of the closest line, or None if no lines are close (within 5 lines)
    """
    if not file_positions:
        return None

    if target_line in file_positions:
        return file_positions[target_line]

    # Find the closest line within a 5-line tolerance
    closest_line = None
    min_distance = float("inf")

    for line_num in file_positions:
        distance = abs(line_num - target_line)
        if distance < min_distance and distance <= 5:
            min_distance = distance
            closest_line = line_num

    return file_positions.get(closest_line) if closest_line else None


def format_finding_as_comment(finding) -> str:
    """
    Formats an AgentFinding into a nice markdown comment for GitHub.

    Example output:
        🔴 **Critical — Hardcoded Password**
        *Found by: Security Agent*

        This variable contains a hardcoded password which could be...

        💡 **Suggestion:** Use environment variables instead.
    """
    severity_icons = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
    }
    agent_names = {
        "security": "Security Agent",
        "performance": "Performance Agent",
        "logic": "Logic Agent",
        "style": "Style Agent",
    }

    icon = severity_icons.get(finding.severity.value, "⚪")
    severity_label = finding.severity.value.capitalize()
    agent_name = agent_names.get(finding.agent.value, finding.agent.value)

    comment = f"{icon} **{severity_label} — {finding.title}**\n"
    comment += f"*Found by: {agent_name}*\n\n"
    comment += f"{finding.explanation}\n"

    if finding.suggestion:
        comment += f"\n💡 **Suggestion:** {finding.suggestion}\n"

    return comment
"""
"""
