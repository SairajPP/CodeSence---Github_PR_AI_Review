from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import ReviewResult, AgentFinding, AgentType, Severity
from services.llm import get_llm

async def synthesis_agent(state: dict) -> dict[str, Any]:
    """
    Takes all findings from previous agents and synthesizes them into a final ReviewResult.
    Deduplicates findings, writes a summary, and calculates totals.
    """
    pr_event = state["pr_event"]
    findings: list[AgentFinding] = state.get("findings", [])
    
    # If no findings, we can shortcut
    if not findings:
        return {
            "review_result": ReviewResult(
                pr_number=pr_event.pr_number,
                repo_full_name=pr_event.repo_full_name,
                summary="LGTM! No issues found by CodeSense agents.",
                findings=[],
                total_critical=0,
                total_warnings=0,
                total_info=0
            )
        }
    
    # Otherwise, pass findings to LLM to write a summary and deduplicate
    # We use a larger model here because 8b struggles with complex structured outputs for large lists
    llm = get_llm(model_name="llama-3.3-70b-versatile")
    structured_llm = llm.with_structured_output(ReviewResult)
    
    # Check for recurring issues in memory
    from services.memory import find_similar_issues
    
    # Convert findings to a readable string for the prompt
    findings_str = ""
    for idx, f in enumerate(findings):
        similar_past_issues = find_similar_issues(pr_event.repo_full_name, f)
        
        # Augment the explanation if similar issues were found
        if similar_past_issues:
            past_count = len(similar_past_issues)
            recurring_note = f"\n\n🔄 *Recurring Pattern: This type of issue has appeared in {past_count} previous PRs.*"
            f.explanation += recurring_note
            
        findings_str += f"{idx+1}. [{f.severity.upper()}] {f.title} (in {f.file}:{f.line})\n"
        findings_str += f"   Agent: {f.agent}\n"
        findings_str += f"   Explanation: {f.explanation}\n"
        if f.suggestion:
            findings_str += f"   Suggestion: {f.suggestion}\n"
        findings_str += "\n"
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the Lead Engineer and final approver for code reviews.
You are given a list of issues found by your team of specialized AI agents (Security, Performance, Logic, Style).

Your tasks:
1. Write a cohesive `summary` paragraph addressing the PR author. Thank them for the PR and summarize the overall quality and the most important findings.
2. Filter and deduplicate the `findings` list. If two agents reported the exact same issue, combine them or pick the best one.
3. Calculate the correct `total_critical`, `total_warnings`, and `total_info` counts based on your final `findings` list.
4. Ensure the `pr_number` and `repo_full_name` are included exactly as provided.

Maintain a polite and constructive tone.
"""),
        ("user", "PR Number: {pr_number}\nRepository: {repo_full_name}\n\nHere are the raw findings from the agents:\n\n{findings_str}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({
            "pr_number": pr_event.pr_number,
            "repo_full_name": pr_event.repo_full_name,
            "findings_str": findings_str
        })
        
        print(f"[Synthesis Agent] Synthesized {len(result.findings)} final issues.")
        return {"review_result": result}
    except Exception as e:
        print(f"[Synthesis Agent] Error during synthesis: {e}")
        # Fallback if LLM parsing fails
        critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
        info = sum(1 for f in findings if f.severity == Severity.INFO)
        
        fallback_result = ReviewResult(
            pr_number=pr_event.pr_number,
            repo_full_name=pr_event.repo_full_name,
            summary="There was an error generating the final summary, but here are the raw findings.",
            findings=findings,
            total_critical=critical,
            total_warnings=warnings,
            total_info=info
        )
        return {"review_result": fallback_result}
