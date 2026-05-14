from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import AgentFindingsList, AgentType
from services.llm import get_llm

async def logic_agent(state: dict) -> dict[str, Any]:
    """
    Analyzes code diffs for logical bugs and unhandled edge cases.
    Returns findings to be appended to the global state.
    """
    diff = state.get("diff", "")
    if not diff:
        return {"findings": []}

    llm = get_llm()
    structured_llm = llm.with_structured_output(AgentFindingsList)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Software Engineer and Code Reviewer.
Your task is to analyze the following pull request diff for logical errors and bugs.

IMPORTANT RULES:
- Focus ONLY on lines starting with `+` (added lines). These are the NEW code changes.
- IGNORE lines starting with `-` (removed lines) — those are being deleted.
- For the `file` field, use the exact filename from the diff header (the line starting with `+++ b/`).
- For the `line` field, calculate the actual line number in the new file using the hunk header (@@ ... +start,count @@).

Look for:
- Missing null/None checks before accessing attributes or methods
- Off-by-one errors in loops or array indexing
- Unhandled exceptions (bare try/except or catching too broadly)
- Incorrect conditional branches (if/else logic errors, inverted conditions)
- Race conditions in concurrent code
- Unreachable code after return/break/continue
- Missing return statements in functions
- Type mismatches (comparing string to int, etc.)

If you find issues, categorize them appropriately.
If you find no logical issues, return an empty list of findings.
Do NOT invent issues if the logic is sound.
"""),
        ("user", "Review the following pull request diff for logical errors:\n\n{diff}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({"diff": diff})
        findings = result.findings if result else []
        for f in findings:
            f.agent = AgentType.LOGIC
        
        print(f"[Logic Agent] Found {len(findings)} issues.")
        return {"findings": findings}
    except Exception as e:
        print(f"[Logic Agent] Error analyzing diff: {e}")
        return {"findings": []}
