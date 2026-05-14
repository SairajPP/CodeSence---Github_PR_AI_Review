"""
test_pipeline.py — End-to-End Pipeline Test
=============================================

This test runs the FULL orchestrator pipeline:
    Fake diff → 4 agents in parallel → synthesis → ReviewResult

It proves the entire system works end-to-end, not just individual agents.

How to run:
    cd d:\CodeSence\backend
    pytest tests/test_pipeline.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from models.schemas import PREvent
from graph.orchestrator import orchestrator


# A diff with multiple intentional issues across all 4 agent domains
MULTI_BUG_DIFF = """
diff --git a/app/auth.py b/app/auth.py
new file mode 100644
--- /dev/null
+++ b/app/auth.py
@@ -0,0 +1,30 @@
+import sqlite3
+import os
+
+DB_PASSWORD = "admin123"
+API_KEY = "sk-1234567890abcdef"
+
+def authenticate(request):
+    username = request.get("username")
+    password = request.get("password")
+    
+    conn = sqlite3.connect("app.db")
+    cursor = conn.cursor()
+    query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
+    cursor.execute(query)
+    user = cursor.fetchone()
+    
+    if user:
+        return True
+
+def get_all_users():
+    conn = sqlite3.connect("app.db")
+    users = conn.cursor().execute("SELECT * FROM users").fetchall()
+    result = []
+    for u in users:
+        profile = conn.cursor().execute("SELECT * FROM profiles WHERE user_id = " + str(u[0])).fetchone()
+        result.append({"user": u, "profile": profile})
+    print("DEBUG: users loaded")
+    print("TODO: remove this debug line")
+    x = len(result)
+    return result
"""


@pytest.mark.asyncio
async def test_full_pipeline():
    """
    End-to-end test: run the orchestrator on a diff with multiple bug types.
    
    Expected findings:
    - Security: hardcoded password, API key, SQL injection
    - Performance: N+1 query pattern
    - Logic: missing return in authenticate (returns None on failure)
    - Style: debug print statements, single-letter variable names
    """
    # Create a fake PREvent
    pr_event = PREvent(
        action="opened",
        pr_number=999,
        pr_title="Test PR for pipeline evaluation",
        repo_full_name="testuser/testrepo",
        repo_owner="testuser",
        repo_name="testrepo",
        diff_url="https://github.com/testuser/testrepo/pull/999.diff",
        sender="testuser",
    )
    
    # Build the initial state
    initial_state = {
        "pr_event": pr_event,
        "files": [{"filename": "app/auth.py", "status": "added", "additions": 30, "deletions": 0, "patch": MULTI_BUG_DIFF}],
        "diff": MULTI_BUG_DIFF,
        "findings": [],
        "review_result": None,
    }
    
    # Run the full orchestrator
    result_state = await orchestrator.ainvoke(initial_state)
    
    # Validate the result
    review = result_state.get("review_result")
    assert review is not None, "Pipeline should produce a ReviewResult"
    
    # Check the summary
    assert review.summary, "ReviewResult should have a non-empty summary"
    assert len(review.summary) > 20, f"Summary too short: '{review.summary}'"
    
    # Check findings
    assert len(review.findings) >= 1, "Pipeline should find at least 1 issue in this buggy diff"
    
    # Check counts are reasonable
    total_issues = review.total_critical + review.total_warnings + review.total_info
    assert total_issues >= 1, "Should have at least 1 issue counted"
    
    # Check PR metadata is correct
    assert review.pr_number == 999
    assert review.repo_full_name == "testuser/testrepo"
    
    # Print results for manual inspection
    print(f"\n{'='*60}")
    print(f"PIPELINE TEST RESULTS")
    print(f"{'='*60}")
    print(f"Summary: {review.summary[:200]}...")
    print(f"Total findings: {len(review.findings)}")
    print(f"  🔴 Critical: {review.total_critical}")
    print(f"  🟡 Warning:  {review.total_warnings}")
    print(f"  🔵 Info:     {review.total_info}")
    print(f"\nAll findings:")
    for i, f in enumerate(review.findings, 1):
        print(f"  {i}. [{f.severity.value.upper()}] {f.title} ({f.file}:{f.line}) — by {f.agent.value}")
    print(f"{'='*60}\n")


@pytest.mark.asyncio
async def test_pipeline_clean_diff():
    """
    Test that the pipeline returns LGTM for clean code.
    """
    clean_diff = """
diff --git a/utils/math.py b/utils/math.py
new file mode 100644
--- /dev/null
+++ b/utils/math.py
@@ -0,0 +1,10 @@
+def add(a: int, b: int) -> int:
+    \"\"\"Returns the sum of two integers.\"\"\"
+    return a + b
+
+
+def multiply(a: int, b: int) -> int:
+    \"\"\"Returns the product of two integers.\"\"\"
+    return a * b
"""
    
    pr_event = PREvent(
        action="opened",
        pr_number=1000,
        pr_title="Clean PR for testing",
        repo_full_name="testuser/testrepo",
        repo_owner="testuser",
        repo_name="testrepo",
        diff_url="https://github.com/testuser/testrepo/pull/1000.diff",
        sender="testuser",
    )
    
    initial_state = {
        "pr_event": pr_event,
        "files": [{"filename": "utils/math.py", "status": "added", "additions": 10, "deletions": 0, "patch": clean_diff}],
        "diff": clean_diff,
        "findings": [],
        "review_result": None,
    }
    
    result_state = await orchestrator.ainvoke(initial_state)
    review = result_state.get("review_result")
    
    assert review is not None, "Pipeline should produce a ReviewResult even for clean code"
    assert review.summary, "Should have a summary"
    
    # Clean code should have very few or zero critical issues
    assert review.total_critical == 0, f"Clean code should have 0 critical issues, got {review.total_critical}"
    
    print(f"\n✅ Clean diff test passed!")
    print(f"   Summary: {review.summary[:150]}")
    print(f"   Findings: {len(review.findings)} (Critical: {review.total_critical}, Warning: {review.total_warnings}, Info: {review.total_info})")
