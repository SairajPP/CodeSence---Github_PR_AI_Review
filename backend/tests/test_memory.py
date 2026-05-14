"""
test_memory.py — Tests for Qdrant Vector DB Long-Term Memory
=============================================================

This file tests the memory storage and retrieval mechanisms.
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.memory import save_findings, find_similar_issues, COLLECTION_NAME, client
from models.schemas import AgentFinding, AgentType, Severity

@pytest.fixture(autouse=True)
def clean_memory():
    """Wipe the specific test repository from memory before tests."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="repo",
                        match=MatchValue(value="test_repo/memory_test")
                    )
                ]
            )
        )
    except Exception:
        pass


def test_memory_save_and_retrieve():
    """
    Test that we can save a finding into Qdrant and retrieve it when searching
    for a similar issue.
    """
    repo = "test_repo/memory_test"
    
    # 1. Create a fake finding
    finding1 = AgentFinding(
        title="Hardcoded API Key",
        explanation="You have hardcoded an AWS secret key. AWS_SECRET = 'AKIAIOSFODNN7EXAMPLE'",
        file="config.py",
        line=10,
        severity=Severity.CRITICAL,
        agent=AgentType.SECURITY
    )
    
    # 2. Save it
    save_findings(repo, [finding1])
    
    # 3. Create a second finding that is very similar
    finding2 = AgentFinding(
        title="AWS Key leaked",
        explanation="An AWS secret key is present in the source code. SECRET_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
        file="auth.py",
        line=5,
        severity=Severity.CRITICAL,
        agent=AgentType.SECURITY
    )
    
    # 4. Search for similar issues
    similar_issues = find_similar_issues(repo, finding2)
    
    # Assert we found the matching issue from finding1
    assert len(similar_issues) > 0, "Memory failed to retrieve similar issue"
    assert similar_issues[0]["title"] == "Hardcoded API Key"
    print(f"Found similar issue with score: {similar_issues[0]['score']}")


def test_memory_repo_isolation():
    """
    Test that issues from one repo do not show up in searches for another repo.
    """
    repo_a = "repo_a/project"
    repo_b = "repo_b/project"
    
    # Bug in Repo A
    finding_a = AgentFinding(
        title="Missing Null Check",
        explanation="Variable could be null causing AttributeError. x = user.get('name')",
        file="utils.py",
        line=5,
        severity=Severity.WARNING,
        agent=AgentType.LOGIC
    )
    save_findings(repo_a, [finding_a])
    
    # Same exact bug in Repo B
    finding_b = AgentFinding(
        title="Unchecked Null",
        explanation="Calling method on potential null value. name = data.get('name')",
        file="parser.py",
        line=12,
        severity=Severity.WARNING,
        agent=AgentType.LOGIC
    )
    
    # Search for similar issues within Repo B
    # Should be empty because Repo B doesn't have it yet!
    similar_issues = find_similar_issues(repo_b, finding_b)
    assert len(similar_issues) == 0, "Memory should strictly isolate by repository"
    
    print("Memory properly isolates repositories")
