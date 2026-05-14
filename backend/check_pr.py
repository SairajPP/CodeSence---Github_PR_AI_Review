import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

async def check_comments():
    # We need the user's repo name. We can find it by getting the authenticated user's repos
    # and looking for the one that has PR #2 recently updated.
    # First, let's get the authenticated user
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.github.com/user", headers=HEADERS)
        user_login = r.json().get("login")
        print("User:", user_login)
        
        # Get repos
        r = await client.get(f"https://api.github.com/users/{user_login}/repos?sort=updated", headers=HEADERS)
        repos = r.json()
        if not repos:
            print("No repos found.")
            return
            
        repo_name = repos[0]["full_name"]
        print("Most recently updated repo:", repo_name)
        
        # Check PR #2 comments
        r = await client.get(f"https://api.github.com/repos/{repo_name}/issues/2/comments", headers=HEADERS)
        comments = r.json()
        print(f"Found {len(comments)} comments on PR #2:")
        for c in comments:
            print("-" * 20)
            print(f"User: {c['user']['login']}")
            print(f"Body: {c['body'][:200]}...")

if __name__ == "__main__":
    asyncio.run(check_comments())
