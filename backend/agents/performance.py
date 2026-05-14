from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import AgentFindingsList, AgentType
from services.llm import get_llm

async def performance_agent(state: dict) -> dict[str, Any]:
    """
    Analyzes code diffs for performance bottlenecks.
    Returns findings to be appended to the global state.
    """
    diff = state.get("diff", "")
    if not diff:
        return {"findings": []}

    llm = get_llm()
    structured_llm = llm.with_structured_output(AgentFindingsList)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Performance Engineer and Code Reviewer.
Your task is to analyze the following pull request diff for performance bottlenecks.

IMPORTANT RULES:
- Focus ONLY on lines starting with `+` (added lines). These are the NEW code changes.
- IGNORE lines starting with `-` (removed lines) — those are being deleted.
- For the `file` field, use the exact filename from the diff header (the line starting with `+++ b/`).
- For the `line` field, calculate the actual line number in the new file using the hunk header (@@ ... +start,count @@).

Look for:
- N+1 database query problems (queries inside loops)
- Inefficient loops (e.g., O(n^2) or worse when O(n) is possible)
- Memory leaks or unnecessary large object retention
- Blocking synchronous calls in async code (e.g., time.sleep in async functions)
- Unnecessary object creation or allocation inside loops
- Missing database indexes implied by query patterns
- Unbounded queries (SELECT * without LIMIT)

If you find issues, categorize them appropriately (usually 'warning').
If you find no performance issues, return an empty list of findings.
Do NOT invent issues if the code is optimal.
"""),
        ("user", "Review the following pull request diff for performance issues:\n\n{diff}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({"diff": diff})
        findings = result.findings if result else []
        for f in findings:
            f.agent = AgentType.PERFORMANCE
        
        print(f"[Performance Agent] Found {len(findings)} issues.")
        return {"findings": findings}
    except Exception as e:
        print(f"[Performance Agent] Error analyzing diff: {e}")
        return {"findings": []}
