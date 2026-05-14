from langchain_core.prompts import ChatPromptTemplate
from services.llm import get_llm

SYSTEM_PROMPT = """
You are an expert technical writer and Auto-Documentation agent.
Your job is to update a repository's documentation (like README.md) based on the changes introduced in a newly merged Pull Request.

Instructions:
1. Review the provided CURRENT DOCUMENTATION and the PR DIFF.
2. Figure out what new features, fixes, or structural changes were introduced.
3. Update the CURRENT DOCUMENTATION to reflect these changes.
4. Ensure you DO NOT delete existing important information, but rather append or modify sections gracefully.
5. If the diff doesn't seem to warrant a documentation update (e.g. minor bug fixes or refactoring), return the original documentation unmodified.
6. OUTPUT ONLY the valid raw Markdown content for the updated file. DO NOT include any conversational text like "Here is the updated documentation:" or markdown code blocks (```markdown) at the very start or end, just output the raw markdown text.
"""

async def generate_documentation_update(diff: str, current_readme: str) -> str:
    """
    Uses the LLM to rewrite/update the repository's README.md based on the merged diff.
    """
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "CURRENT DOCUMENTATION:\n\n{current_readme}\n\n======================\n\nPR DIFF:\n\n{diff}\n\nPlease provide the updated documentation.")
    ])
    
    chain = prompt | llm
    
    response = await chain.ainvoke({
        "current_readme": current_readme,
        "diff": diff
    })
    
    # Clean up output if LLM wraps it in ```markdown ... ```
    content = response.content.strip()
    if content.startswith("```markdown"):
        content = content[11:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    return content.strip()
