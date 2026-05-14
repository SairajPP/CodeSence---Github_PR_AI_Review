import pytest
from agents.documentation import generate_documentation_update

from langchain_core.runnables import RunnableLambda

@pytest.mark.asyncio
async def test_generate_documentation_update(monkeypatch):
    """
    Test that the documentation agent correctly formats the prompt and returns cleaned output.
    We mock the LLM call to avoid hitting the Groq API during tests.
    """
    class MockResponse:
        def __init__(self, content):
            self.content = content

    def mock_llm_invoke(inputs):
        return MockResponse("```markdown\n# Updated Docs\nAdded a new feature.\n```")

    def mock_get_llm():
        return RunnableLambda(mock_llm_invoke)

    # Apply mock
    monkeypatch.setattr("agents.documentation.get_llm", mock_get_llm)

    diff = "+++ b/src/main.py\n+def new_feature():\n+    pass"
    current_readme = "# Project"
    
    result = await generate_documentation_update(diff, current_readme)
    
    assert result == "# Updated Docs\nAdded a new feature."
    assert not result.startswith("```")
