"""
github_api.py — GitHub API Service
====================================

This file handles all communication WITH GitHub's API.

Two main jobs:
1. FETCH the diff (code changes) from a Pull Request
2. POST review comments back to the PR (Week 2+)

How GitHub diffs work:
When you open a PR, GitHub creates a "diff" — a text showing exactly 
what lines were added (+) and removed (-). Example:

    --- a/app.py
    +++ b/app.py
    @@ -10,6 +10,8 @@
     def login(username, password):
    -    if password == "admin":        ← removed this line
    +    if verify_hash(password):      ← added this line
         return True

We fetch this diff and send it to the AI agents for analysis.
"""

import httpx
import os
import base64
from dotenv import load_dotenv
from pathlib import Path

# Load .env from backend directory
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Headers that GitHub requires for API calls
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


async def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """
    Fetches the raw diff of a Pull Request.
    
    Args:
        repo_full_name: "username/repo-name" (e.g., "yourname/EcoFeast")
        pr_number: The PR number (e.g., 1)
    
    Returns:
        The raw diff as a string (the +/- format shown above)
    
    How it works:
        GitHub API endpoint: GET /repos/{owner}/{repo}/pulls/{pr_number}
        With Accept header set to "application/vnd.github.v3.diff"
        This returns the raw diff instead of JSON.
    """
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    
    # We override the Accept header to get raw diff format
    diff_headers = {
        **HEADERS,
        "Accept": "application/vnd.github.v3.diff",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=diff_headers, timeout=30.0)
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"[CodeSense] ERROR fetching diff: {response.status_code}")
            print(f"[CodeSense] Response: {response.text}")
            return ""


async def fetch_pr_files(repo_full_name: str, pr_number: int) -> list[dict]:
    """
    Fetches the list of changed files in a PR with their patches.
    
    This gives us structured data about each file:
    - filename: which file changed
    - status: "added", "modified", "removed"
    - additions: number of lines added
    - deletions: number of lines removed
    - patch: the actual diff for that specific file
    
    This is MORE useful than the raw diff because it's already
    broken down per-file, which is what the agents need.
    """
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, timeout=30.0)
        
        if response.status_code == 200:
            files = response.json()
            # Return only the fields we care about
            return [
                {
                    "filename": f["filename"],
                    "status": f["status"],
                    "additions": f["additions"],
                    "deletions": f["deletions"],
                    "patch": f.get("patch", ""),  # .get() because binary files don't have patches
                }
                for f in files
            ]
        else:
            print(f"[CodeSense] ERROR fetching PR files: {response.status_code}")
            return []

async def fetch_user_email(repo_full_name: str, pr_number: int, username: str) -> str:
    """
    Attempts to find the email address of the PR author.
    First tries their public profile, then falls back to extracting it from their PR commits.
    """
    async with httpx.AsyncClient() as client:
        # Strategy 1: Check user's public profile
        try:
            profile_url = f"https://api.github.com/users/{username}"
            profile_res = await client.get(profile_url, headers=HEADERS, timeout=10.0)
            if profile_res.status_code == 200:
                email = profile_res.json().get("email")
                if email:
                    return email
        except Exception:
            pass
            
        # Strategy 2: Check commit history of the PR
        try:
            commits_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/commits"
            commits_res = await client.get(commits_url, headers=HEADERS, timeout=10.0)
            if commits_res.status_code == 200:
                commits = commits_res.json()
                for commit in commits:
                    # Look for a commit author email that is not a GitHub noreply email
                    author_email = commit.get("commit", {}).get("author", {}).get("email")
                    if author_email and "noreply.github.com" not in author_email:
                        return author_email
        except Exception:
            pass
            
    return None


async def post_review(
    repo_full_name: str,
    pr_number: int,
    body: str,
    comments: list[dict],
    event: str = "COMMENT",
) -> bool:
    """
    Posts a review with inline comments to a GitHub PR.
    
    This is what makes CodeSense feel like a real reviewer —
    comments appear directly on the PR, attached to specific lines.
    
    Args:
        repo_full_name: "username/repo-name"
        pr_number: PR number
        body: The top-level review summary (appears at the top of the review)
        comments: List of inline comments, each with:
            - path: file path (e.g., "src/auth.py")
            - position: line offset within the diff hunk (NOT the absolute line number)
            - body: the comment text
        event: Review action — "COMMENT", "APPROVE", or "REQUEST_CHANGES"
    
    Returns:
        True if the review was posted successfully
    """
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    
    payload = {
        "body": body,
        "event": event,
        "comments": comments,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url, headers=HEADERS, json=payload, timeout=30.0
        )
        
        # GitHub returns 200 for successful review creation
        if response.status_code == 200:
            print(f"[CodeSense] ✅ Review posted successfully on PR #{pr_number}")
            return True
        elif response.status_code == 422:
            # 422 usually means a comment pointed to an invalid diff position
            # Fall back to posting without inline comments
            print(f"[CodeSense] ⚠️ Inline comments failed (invalid positions). Falling back...")
            print(f"[CodeSense] GitHub response: {response.text[:300]}")
            
            # Retry with just the summary body (no inline comments)
            fallback_payload = {
                "body": body,
                "event": "COMMENT",
                "comments": [],
            }
            fallback_response = await client.post(
                url, headers=HEADERS, json=fallback_payload, timeout=30.0
            )
            if fallback_response.status_code == 200:
                print(f"[CodeSense] ✅ Fallback review (summary only) posted on PR #{pr_number}")
                return True
            else:
                print(f"[CodeSense] ❌ Fallback also failed: {fallback_response.status_code}")
                return False
        else:
            print(f"[CodeSense] ❌ Failed to post review: {response.status_code}")
            print(f"[CodeSense] Response: {response.text[:300]}")
            return False


async def post_pr_comment(
    repo_full_name: str,
    pr_number: int,
    body: str,
) -> bool:
    """
    Posts a simple comment on a PR (not a review, just an issue comment).
    
    This is the ultimate fallback — if the review API fails entirely,
    we can still leave a regular comment with all findings formatted
    as a markdown table.
    
    This uses the Issues API (PRs are issues in GitHub's data model).
    """
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    
    payload = {"body": body}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url, headers=HEADERS, json=payload, timeout=30.0
        )
        
        if response.status_code == 201:
            print(f"[CodeSense] ✅ Comment posted on PR #{pr_number}")
            return True
        else:
            print(f"[CodeSense] ❌ Failed to post comment: {response.status_code}")
            print(f"[CodeSense] Response: {response.text[:300]}")
            return False

async def fetch_file_content(repo_full_name: str, file_path: str) -> dict:
    """
    Fetches the content of a file from a GitHub repository.
    Returns a dict with 'content' (decoded) and 'sha' (needed for updating).
    """
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, timeout=30.0)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "content": base64.b64decode(data["content"]).decode("utf-8"),
                "sha": data["sha"]
            }
        elif response.status_code == 404:
            # File doesn't exist yet
            return None
        else:
            print(f"[CodeSense] ERROR fetching file {file_path}: {response.status_code}")
            return None

async def update_file_in_repo(
    repo_full_name: str, 
    file_path: str, 
    new_content: str, 
    commit_message: str, 
    sha: str = None
) -> bool:
    """
    Creates or updates a file in the repository.
    If the file exists, 'sha' must be provided.
    """
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
    
    encoded_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": commit_message,
        "content": encoded_content
    }
    
    if sha:
        payload["sha"] = sha
        
    async with httpx.AsyncClient() as client:
        response = await client.put(url, headers=HEADERS, json=payload, timeout=30.0)
        
        if response.status_code in [200, 201]:
            print(f"[CodeSense] ✅ File {file_path} updated successfully.")
            return True
        else:
            print(f"[CodeSense] ❌ Failed to update {file_path}: {response.status_code}")
            print(f"[CodeSense] Response: {response.text[:300]}")
            return False
