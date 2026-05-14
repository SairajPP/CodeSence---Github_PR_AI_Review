from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import AgentFindingsList, AgentType, Severity
from services.llm import get_llm

async def security_agent(state: dict) -> dict[str, Any]:
    """
    Analyzes code diffs for security vulnerabilities.
    Returns findings to be appended to the global state.
    """
    diff = state.get("diff", "")
    if not diff:
        return {"findings": []}

    llm = get_llm()
    structured_llm = llm.with_structured_output(AgentFindingsList)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert Security Engineer and Code Reviewer.
Your task is to analyze the following pull request diff for security vulnerabilities.

IMPORTANT RULES:
- Focus ONLY on lines starting with `+` (added lines). These are the NEW code changes.
- IGNORE lines starting with `-` (removed lines) — those are being deleted.
- For the `file` field, use the exact filename from the diff header (the line starting with `+++ b/`).
- For the `line` field, calculate the actual line number in the new file using the hunk header (@@ ... +start,count @@).

Look for:
- Hardcoded secrets, API keys, or credentials
- SQL injection vulnerabilities (string concatenation in queries)
- Cross-Site Scripting (XSS) — unescaped user input in HTML
- Missing authentication or authorization checks
- Insecure direct object references (IDOR)
- Use of eval(), exec(), or other dangerous functions
- Weak or missing cryptography

If you find issues, categorize them with 'critical' or 'warning' severity.
If you find no security issues, return an empty list of findings.
Do NOT invent issues if the code is secure.
"""),
        ("user", "Review the following pull request diff for security vulnerabilities:\n\n{diff}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({"diff": diff})
        findings = result.findings if result else []
        # Ensure the agent field is set correctly
        for f in findings:
            f.agent = AgentType.SECURITY
        
        print(f"[Security Agent] Found {len(findings)} issues.")
        return {"findings": findings}
    except Exception as e:
        print(f"[Security Agent] Error analyzing diff: {e}")
        return {"findings": []}
