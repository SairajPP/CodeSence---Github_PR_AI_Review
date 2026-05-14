from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import AgentFindingsList, AgentType
from services.llm import get_llm

async def style_agent(state: dict) -> dict[str, Any]:
    """
    Analyzes code diffs for style, readability, and best practices.
    Returns findings to be appended to the global state.
    """
    diff = state.get("diff", "")
    if not diff:
        return {"findings": []}

    llm = get_llm()
    structured_llm = llm.with_structured_output(AgentFindingsList)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Software Engineer and Code Reviewer.
Your task is to analyze the following pull request diff for style and best practices.

IMPORTANT RULES:
- Focus ONLY on lines starting with `+` (added lines). These are the NEW code changes.
- IGNORE lines starting with `-` (removed lines) — those are being deleted.
- For the `file` field, use the exact filename from the diff header (the line starting with `+++ b/`).
- For the `line` field, calculate the actual line number in the new file using the hunk header (@@ ... +start,count @@).

Look for:
- Naming conventions (unclear or confusing variable/function names)
- Lack of docstrings or comments for complex logic
- Functions that are too long (>30 lines) or do too many things (SRP violations)
- DRY violations (duplicated code blocks)
- Overly complex logic that could be simplified
- Leftover debug statements (e.g., print(), console.log(), debugger)
- Magic numbers without named constants

Categorize all your findings as 'info' severity.
If you find no style issues, return an empty list of findings.
"""),
        ("user", "Review the following pull request diff for style and readability issues:\n\n{diff}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({"diff": diff})
        findings = result.findings if result else []
        for f in findings:
            f.agent = AgentType.STYLE
        
        print(f"[Style Agent] Found {len(findings)} issues.")
        return {"findings": findings}
    except Exception as e:
        print(f"[Style Agent] Error analyzing diff: {e}")
        return {"findings": []}
