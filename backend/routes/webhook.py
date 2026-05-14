"""
webhook.py — GitHub Webhook Receiver
=======================================

This is the URL that GitHub calls every time a PR is opened on your repo.

The flow:
1. Developer opens a PR on GitHub
2. GitHub sends an HTTP POST to this endpoint with all the PR details
3. We verify the request is really from GitHub (signature check)
4. We extract the PR info (number, title, repo, etc.)
5. We fetch the actual code diff from GitHub's API
6. We log everything (Week 1) → later: send to AI agents (Week 2+)

Security: Why do we check signatures?
Without the signature check, anyone could send fake requests to your
server pretending to be GitHub. The signature proves the request is legit.

How it works:
- When you set up the webhook on GitHub, you enter a "secret" (a password)
- GitHub uses that secret to create a hash (SHA-256) of the request body
- GitHub sends that hash in the X-Hub-Signature-256 header
- We compute the same hash using OUR copy of the secret
- If they match → it's really from GitHub. If not → reject it.
"""

import hmac
import hashlib
import json
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from dotenv import load_dotenv
import os
from pathlib import Path

# Import our custom modules
from services.github_api import fetch_pr_diff, fetch_pr_files, post_review, post_pr_comment, fetch_file_content, update_file_in_repo
from services.diff_utils import parse_diff_positions, find_closest_position, format_finding_as_comment
from models.schemas import PREvent
from graph.orchestrator import orchestrator

# Load .env from the backend directory (explicit path so it always finds it)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Create a router — this groups related endpoints together
# Think of it like a chapter in a book. main.py is the book, this is one chapter.
router = APIRouter()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verifies that the webhook request actually came from GitHub.
    
    Args:
        payload: The raw request body (bytes)
        signature: The signature GitHub sent in the header
    
    Returns:
        True if the signature matches (request is legit)
    
    How:
        1. Take our secret (from .env)
        2. Use it to compute SHA-256 hash of the payload
        3. Compare our hash with GitHub's hash
        4. hmac.compare_digest() does a timing-safe comparison
           (prevents a sneaky attack called "timing attack")
    """
    if not WEBHOOK_SECRET:
        print("[CodeSense] WARNING: No GITHUB_WEBHOOK_SECRET set! Skipping verification.")
        return True  # Skip verification during initial testing
    
    expected = "sha256=" + hmac.HMAC(
        WEBHOOK_SECRET.encode(),   # Our secret as bytes
        payload,                   # The request body
        hashlib.sha256             # The hashing algorithm
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


async def handle_pr_event(pr_event: PREvent):
    """
    Processes a Pull Request event. This is where the magic happens.
    
    The flow:
    1. Fetch the diff and file list from GitHub
    2. Run the LangGraph orchestrator (4 agents in parallel → synthesis)
    3. Convert the AI findings into GitHub review comments
    4. Post the review directly on the PR
    
    This runs as a BACKGROUND TASK — meaning we respond to GitHub
    immediately ("got it!") and do the heavy work in the background.
    Why? Because GitHub has a 10-second timeout on webhook responses.
    """
    print("\n" + "=" * 60)
    print(f"[CodeSense] REVIEWING PR #{pr_event.pr_number}")
    print(f"   Repo: {pr_event.repo_full_name}")
    print(f"   Title: '{pr_event.pr_title}'")
    print(f"   Action: {pr_event.action}")
    print(f"   By: {pr_event.sender}")
    print("=" * 60)
    
    # Step 1: Fetch the list of changed files
    print("\n>> Fetching changed files...")
    files = await fetch_pr_files(pr_event.repo_full_name, pr_event.pr_number)
    
    if not files:
        print("[ERROR] No files found or error fetching diff.")
        return
    
    print(f"   Found {len(files)} changed file(s):\n")
    
    for f in files:
        print(f"   - {f['filename']}")
        print(f"      Status: {f['status']} | +{f['additions']} -{f['deletions']}")
        
        # Show the first 20 lines of the patch (diff) for each file
        patch = f.get("patch", "")
        if patch:
            patch_lines = patch.split("\n")
            for line in patch_lines[:20]:
                print(f"      {line}")
            if len(patch_lines) > 20:
                print(f"      ... ({len(patch_lines) - 20} more lines)")
        print()
    
    # Step 2: Fetch the full raw diff (needed for position mapping)
    print(">> Fetching full diff...")
    full_diff = await fetch_pr_diff(pr_event.repo_full_name, pr_event.pr_number)
    
    if full_diff:
        diff_lines = full_diff.count("\n")
        print(f"   Full diff: {diff_lines} lines, {len(full_diff)} characters")
        # Prevent LLM Context Crashing on massive diffs (e.g. deleting whole directories)
        # Groq's llama-3.1-8b-instant has a 6,000 Tokens-Per-Minute (TPM) limit.
        # Since we run 4 agents in parallel, the diff must be small enough so that
        # Diff * 4 < 6000 TPM. Truncating to 3,000 characters guarantees safety.
        if len(full_diff) > 3000:
            print("   [WARNING] Diff too large! Truncating to 3,000 characters to fit TPM limit.")
            full_diff = full_diff[:3000] + "\n\n[CodeSense Note: Diff was truncated because it was too large.]"
    
    # ===== WEEK 2: AI Orchestration =====
    print(">> Starting AI Orchestration...")
    initial_state = {
        "pr_event": pr_event,
        "files": files,
        "diff": full_diff,
        "findings": [],
        "review_result": None
    }
    
    try:
        # Run the graph — 4 agents in parallel, then synthesis
        result_state = await orchestrator.ainvoke(initial_state)
        review = result_state.get("review_result")
        
        if review:
            print("\n=== FINAL AI REVIEW ===")
            print(f"Summary: {review.summary}")
            print(f"Issues Found: {len(review.findings)} (Critical: {review.total_critical}, Warnings: {review.total_warnings}, Info: {review.total_info})")
            print("=======================\n")
            
            # ===== WEEK 3: Post the review to GitHub =====
            await post_review_to_github(pr_event, review, full_diff)
            
            # ===== WEEK 4: Save findings to Long-Term Memory =====
            print(">> Saving findings to Qdrant Memory...")
            from services.memory import save_findings
            import asyncio
            # Run in a separate thread so it doesn't block the main event loop
            await asyncio.to_thread(save_findings, pr_event.repo_full_name, review.findings)
            print("   Findings saved successfully.")
            
            # ===== Phase 2: Send Email Summary =====
            print(">> Sending Email Summary...")
            from services.email_service import send_review_email
            from services.github_api import fetch_user_email
            
            author_email = await fetch_user_email(pr_event.repo_full_name, pr_event.pr_number, pr_event.sender)
            to_email = author_email or os.getenv("DEFAULT_DEV_EMAIL", "developer@example.com")
            
            print(f"   Sending email to: {to_email}")
            await asyncio.to_thread(send_review_email, pr_event, review, to_email)
            print("   Email processing completed.")
        else:
            print("\n[ERROR] AI Orchestration failed to produce a review.")
    except Exception as e:
        print(f"\n[ERROR] Orchestration pipeline failed: {e}")
        import traceback
        traceback.print_exc()


async def handle_merged_pr_event(repo_full_name: str, pr_number: int, pr_title: str):
    """
    Handles updating documentation when a PR is merged.
    """
    print("\n" + "=" * 60)
    print(f"[CodeSense] MERGED PR #{pr_number} - Auto-Documentation")
    print("=" * 60)
    
    # Step 1: Fetch diff
    full_diff = await fetch_pr_diff(repo_full_name, pr_number)
    if not full_diff:
        print("[ERROR] Could not fetch diff for merged PR.")
        return
        
    # Step 2: Fetch current README.md
    print(">> Fetching current README.md...")
    file_data = await fetch_file_content(repo_full_name, "README.md")
    
    if file_data:
        current_readme = file_data["content"]
        sha = file_data["sha"]
    else:
        print("   No README.md found. Creating a new one...")
        current_readme = "# " + repo_full_name.split("/")[-1] + "\n"
        sha = None

    # Step 3: Generate update via Agent
    print(">> Generating documentation update...")
    from agents.documentation import generate_documentation_update
    new_readme = await generate_documentation_update(full_diff, current_readme)
    
    if new_readme == current_readme:
        print("   No documentation changes needed based on diff.")
        return
        
    # Step 4: Push commit
    print(">> Pushing updated README.md to GitHub...")
    commit_msg = f"docs: Update README.md based on PR #{pr_number} ({pr_title})"
    success = await update_file_in_repo(repo_full_name, "README.md", new_readme, commit_msg, sha)
    
    if success:
        print(f"   Auto-Documentation successful!")
    else:
        print(f"   [ERROR] Failed to push documentation update.")


async def post_review_to_github(pr_event: PREvent, review, full_diff: str):
    """
    Takes the AI review result and posts it as a proper GitHub review
    with inline comments on the PR.

    Strategy:
    1. Parse the diff to build a line→position map
    2. Convert each AgentFinding to a GitHub inline comment
    3. Build a formatted summary with severity badges
    4. Post via GitHub Reviews API
    5. If inline comments fail → fall back to a simple PR comment
    """
    print(">> Posting review to GitHub...")
    
    # Step 1: Build the diff position map
    position_map = {}
    if full_diff:
        position_map = parse_diff_positions(full_diff)
        print(f"   Diff position map built for {len(position_map)} file(s)")
    
    # Step 2: Convert findings to inline comments
    inline_comments = []
    unmapped_findings = []  # Findings we couldn't map to diff positions
    
    for finding in review.findings:
        file_positions = position_map.get(finding.file, {})
        position = find_closest_position(file_positions, finding.line)
        
        if position:
            inline_comments.append({
                "path": finding.file,
                "position": position,
                "body": format_finding_as_comment(finding),
            })
        else:
            # Can't anchor this comment — will include it in the summary instead
            unmapped_findings.append(finding)
    
    print(f"   Inline comments: {len(inline_comments)}, Unmapped: {len(unmapped_findings)}")
    
    # Step 3: Build the formatted summary body
    summary_body = _build_review_summary(review, unmapped_findings)
    
    # Step 4: Post the review
    review_event = review.review_action.value if hasattr(review, 'review_action') else "COMMENT"
    
    success = await post_review(
        repo_full_name=pr_event.repo_full_name,
        pr_number=pr_event.pr_number,
        body=summary_body,
        comments=inline_comments,
        event=review_event,
    )
    
    # Step 5: If review API failed entirely, fall back to a simple comment
    if not success:
        print(">> Review API failed. Falling back to simple PR comment...")
        fallback_body = _build_fallback_comment(review)
        await post_pr_comment(
            repo_full_name=pr_event.repo_full_name,
            pr_number=pr_event.pr_number,
            body=fallback_body,
        )


def _build_review_summary(review, unmapped_findings: list) -> str:
    """
    Builds the top-level review body with severity badges and stats.
    Also includes any findings that couldn't be mapped to inline comments.
    """
    lines = []
    lines.append("## 🤖 CodeSense AI Review\n")
    lines.append(review.summary)
    lines.append("")
    
    # Severity breakdown
    lines.append("### 📊 Summary")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| 🔴 Critical | {review.total_critical} |")
    lines.append(f"| 🟡 Warning | {review.total_warnings} |")
    lines.append(f"| 🔵 Info | {review.total_info} |")
    lines.append("")
    
    # Detailed Findings Table for all issues
    if review.findings:
        lines.append("### 📝 Detailed Findings")
        lines.append("| Severity | Category | File | Line | Issue |")
        lines.append("|----------|----------|------|------|-------|")
        for f in review.findings:
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity.value, "⚪")
            clean_explanation = f.explanation.replace('\n', '<br>')
            lines.append(f"| {icon} {f.severity.value.capitalize()} | {f.agent.value.capitalize()} | `{f.file}` | {f.line} | **{f.title}**: {clean_explanation} |")
        lines.append("")
        
    # If there are unmapped findings, we don't need to list them twice since the table above includes all of them.
    # However, we can add suggestions below the table if needed, but the table is comprehensive enough.
    if unmapped_findings:
        lines.append("### 📝 Additional Findings")
        lines.append("*These findings could not be anchored to specific diff lines:*\n")
        for f in unmapped_findings:
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity.value, "⚪")
            lines.append(f"- {icon} **{f.title}** (`{f.file}:{f.line}`)")
            lines.append(f"  {f.explanation}")
            if f.suggestion:
                lines.append(f"  💡 *{f.suggestion}*")
            lines.append("")
    
    lines.append("---")
    lines.append("*Powered by [CodeSense](https://github.com) — AI-powered code review*")
    
    return "\n".join(lines)


def _build_fallback_comment(review) -> str:
    """
    Builds a full markdown comment with ALL findings listed as a table.
    Used when the Review API fails entirely.
    """
    lines = []
    lines.append("## 🤖 CodeSense AI Review\n")
    lines.append(review.summary)
    lines.append("")
    lines.append(f"**🔴 {review.total_critical} Critical** · **🟡 {review.total_warnings} Warnings** · **🔵 {review.total_info} Info**\n")
    
    if review.findings:
        lines.append("| # | Severity | Agent | File | Line | Issue |")
        lines.append("|---|----------|-------|------|------|-------|")
        for i, f in enumerate(review.findings, 1):
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity.value, "⚪")
            lines.append(f"| {i} | {icon} {f.severity.value.capitalize()} | {f.agent.value.capitalize()} | `{f.file}` | {f.line} | **{f.title}** |")
        lines.append("")
        
        # Detailed explanations
        lines.append("### Details\n")
        for i, f in enumerate(review.findings, 1):
            lines.append(f"**{i}. {f.title}** (`{f.file}:{f.line}`)")
            lines.append(f"{f.explanation}")
            if f.suggestion:
                lines.append(f"💡 *{f.suggestion}*")
            lines.append("")
    
    lines.append("---")
    lines.append("*Powered by [CodeSense](https://github.com) — AI-powered code review*")
    
    return "\n".join(lines)


@router.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Main webhook endpoint. GitHub sends POST requests here.
    
    This endpoint:
    1. Reads the raw request body
    2. Verifies the signature (is this really from GitHub?)
    3. Checks what type of event it is (we only care about PRs)
    4. Extracts the PR data into our PREvent model
    5. Kicks off the review in the background
    6. Returns immediately so GitHub doesn't timeout
    
    GitHub sends a header called X-GitHub-Event that tells us
    what happened: "pull_request", "push", "issues", etc.
    We only care about "pull_request".
    
    For pull_request events, GitHub also sends an "action" field:
    - "opened": A new PR was created
    - "synchronize": New commits were pushed to an existing PR
    - "closed": PR was closed or merged
    We process "opened" and "synchronize" (new PR or updated PR).
    """
    # Step 1: Read the raw body
    payload_bytes = await request.body()
    
    # Step 2: Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Step 3: Parse JSON and check event type
    event_type = request.headers.get("X-GitHub-Event", "")
    
    # GitHub can send payloads as application/json or application/x-www-form-urlencoded
    content_type = request.headers.get("content-type", "")
    try:
        if "application/x-www-form-urlencoded" in content_type:
            import urllib.parse
            parsed_form = urllib.parse.parse_qs(payload_bytes.decode('utf-8'))
            if 'payload' not in parsed_form:
                raise ValueError("Missing 'payload' field in form-encoded data")
            payload = json.loads(parsed_form['payload'][0])
        else:
            payload = json.loads(payload_bytes)
    except Exception as e:
        print(f"[CodeSense] Error decoding payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {e}")
    
    # GitHub sends a "ping" event when you first set up the webhook
    # We respond with success so GitHub knows our endpoint works
    if event_type == "ping":
        print("[CodeSense] Received ping from GitHub -- webhook is connected!")
        return {"message": "pong"}
    
    # Step 4: Handle pull_request events
    if event_type == "pull_request":
        action = payload.get("action")
        
        if action in ["opened", "synchronize"]:
            try:
                # Extract the data we need into our clean PREvent model
                pr_event = PREvent(
                    action=action,
                    pr_number=payload["number"],
                    pr_title=payload["pull_request"]["title"],
                    repo_full_name=payload["repository"]["full_name"],
                    repo_owner=payload["repository"]["owner"]["login"],
                    repo_name=payload["repository"]["name"],
                    diff_url=payload["pull_request"]["diff_url"],
                    sender=payload["sender"]["login"],
                )
            except KeyError as e:
                print(f"[CodeSense] Missing expected field in PR event payload: {e}")
                raise HTTPException(status_code=422, detail=f"Missing expected field in payload: {e}")
            
            # Run the review in the background
            # (so we can respond to GitHub quickly)
            background_tasks.add_task(handle_pr_event, pr_event)
            
            return {
                "message": f"PR #{pr_event.pr_number} received, review started",
                "pr_title": pr_event.pr_title,
            }
        elif action == "closed" and payload.get("pull_request", {}).get("merged") == True:
            # PR was merged -> trigger Auto-Documentation Companion
            print(f"[CodeSense] PR #{payload['number']} merged! Triggering Auto-Documentation...")
            
            repo_full_name = payload["repository"]["full_name"]
            pr_number = payload["number"]
            pr_title = payload["pull_request"]["title"]
            
            background_tasks.add_task(handle_merged_pr_event, repo_full_name, pr_number, pr_title)
            
            return {
                "message": f"PR #{pr_number} merged, auto-documentation started",
            }
        else:
            # PR was closed, merged, labeled, etc. — we don't care
            return {"message": f"PR action '{action}' ignored"}
    
    # Some other event type we don't handle (push, issues, etc.)
    return {"message": f"Event '{event_type}' ignored"}
