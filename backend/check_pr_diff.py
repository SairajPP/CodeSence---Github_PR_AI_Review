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

async def check_pr():
    async with httpx.AsyncClient() as client:
        # Get latest PRs for SairajPP/EcoFeast
        r = await client.get(
            "https://api.github.com/repos/SairajPP/EcoFeast/pulls?state=open&sort=updated", 
            headers=HEADERS
        )
        prs = r.json()
        if not prs:
            print("No open PRs found.")
            return
            
        latest_pr = prs[0]
        pr_number = latest_pr["number"]
        print(f"Latest PR: #{pr_number} - {latest_pr['title']}")
        
        # Fetch diff
        diff_headers = HEADERS.copy()
        diff_headers["Accept"] = "application/vnd.github.v3.diff"
        r_diff = await client.get(
            f"https://api.github.com/repos/SairajPP/EcoFeast/pulls/{pr_number}",
            headers=diff_headers
        )
        
        diff = r_diff.text
        print(f"Diff length: {len(diff)} characters, {diff.count(chr(10))} lines")
        print("Diff preview:")
        print(diff[:500])

if __name__ == "__main__":
    asyncio.run(check_pr())
