"""
schemas.py — Data Models for CodeSense
========================================

Think of these like blueprints or contracts. They define:
"When a PR event comes in, what data does it contain?"
"When an agent finds an issue, what fields should the finding have?"

Pydantic models give us:
1. Automatic validation (if a field is missing, we get a clear error)
2. Type safety (a line number must be an int, not a string)
3. Auto-generated API docs (FastAPI uses these to build Swagger UI)
"""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


# ============================================================
# Severity Levels — how serious is the finding?
# ============================================================
class Severity(str, Enum):
    """
    Every issue found by an agent gets one of these labels.
    - CRITICAL: Must fix before merging (security hole, crash bug)
    - WARNING: Should fix (performance issue, logic bug)  
    - INFO: Nice to fix (style issue, naming)
    """
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# ============================================================
# Agent Types — which AI agent found this?
# ============================================================
class AgentType(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    LOGIC = "logic"
    STYLE = "style"
    SYNTHESIS = "synthesis"


# ============================================================
# Review Action — what should GitHub do with this review?
# ============================================================
class ReviewAction(str, Enum):
    """
    When CodeSense posts a review, it picks one of these:
    - COMMENT: Just leave feedback, no approval/rejection
    - APPROVE: Green checkmark — code looks good
    - REQUEST_CHANGES: Block merge until issues are fixed
    """
    COMMENT = "COMMENT"
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


# ============================================================
# PR Event — data we extract from GitHub's webhook payload
# ============================================================
class PREvent(BaseModel):
    """
    When GitHub sends a webhook, we extract these fields.
    This is the "input" to our entire pipeline.
    """
    action: str                  # "opened", "synchronize" (new commit pushed)
    pr_number: int               # PR #1, #2, etc.
    pr_title: str                # "Add login feature"
    repo_full_name: str          # "username/repo-name"
    repo_owner: str              # "username"
    repo_name: str               # "repo-name"
    diff_url: str                # URL to download the raw diff
    sender: str                  # Who opened the PR


# ============================================================
# Agent Finding — a single issue found by an agent
# ============================================================
class AgentFinding(BaseModel):
    """
    Each agent returns a list of these.
    Example: "Line 47 in api/auth.py has a hardcoded password (CRITICAL)"
    """
    file: str                    # Which file has the issue
    line: int                    # Which line number
    severity: Severity           # How serious is it
    agent: AgentType             # Which agent found it
    title: str                   # Short description: "Hardcoded password"
    explanation: str             # Detailed explanation of the issue
    suggestion: Optional[str] = None  # How to fix it (optional)
    confidence: Optional[float] = None  # 0.0-1.0 — how confident is the agent (for dedup)

class AgentFindingsList(BaseModel):
    """Wrapper to help the LLM return a list of findings."""
    findings: list[AgentFinding]

# ============================================================
# Review Result — the final output after synthesis
# ============================================================
class ReviewResult(BaseModel):
    """
    The synthesis agent produces this. It combines all agent findings
    into a single structured review ready to post on GitHub.
    """
    pr_number: int
    repo_full_name: str
    summary: str                 # Top-level review body (paragraph)
    findings: list[AgentFinding] # All findings, deduplicated and sorted
    total_critical: int = 0
    total_warnings: int = 0
    total_info: int = 0
    review_action: ReviewAction = ReviewAction.COMMENT  # What GitHub review event to use
