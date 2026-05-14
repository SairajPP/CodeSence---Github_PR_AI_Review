import operator
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, START, END

from models.schemas import AgentFinding, ReviewResult, PREvent

# Import our agents
from agents.security import security_agent
from agents.performance import performance_agent
from agents.logic import logic_agent
from agents.style import style_agent
from agents.synthesis import synthesis_agent

class GraphState(TypedDict):
    """
    The state shared across all nodes in the graph.
    Every node can read this state, and any returned keys will update the state.
    """
    pr_event: PREvent
    files: List[Dict[str, Any]]
    diff: str
    
    # operator.add tells LangGraph: "when a node returns 'findings', 
    # append them to the existing list instead of overwriting it."
    # This is crucial for parallel agent execution!
    findings: Annotated[List[AgentFinding], operator.add]
    
    review_result: ReviewResult | None

def build_graph() -> StateGraph:
    """
    Builds the LangGraph orchestration pipeline.
    """
    builder = StateGraph(GraphState)
    
    # 1. Add our nodes (the agents)
    builder.add_node("security_agent", security_agent)
    builder.add_node("performance_agent", performance_agent)
    builder.add_node("logic_agent", logic_agent)
    builder.add_node("style_agent", style_agent)
    builder.add_node("synthesis_agent", synthesis_agent)
    
    # 2. Define the flow
    # Start -> Run all 4 agents in parallel
    builder.add_edge(START, "security_agent")
    builder.add_edge(START, "performance_agent")
    builder.add_edge(START, "logic_agent")
    builder.add_edge(START, "style_agent")
    
    # After agents finish -> Synthesis
    builder.add_edge("security_agent", "synthesis_agent")
    builder.add_edge("performance_agent", "synthesis_agent")
    builder.add_edge("logic_agent", "synthesis_agent")
    builder.add_edge("style_agent", "synthesis_agent")
    
    # Synthesis -> End
    builder.add_edge("synthesis_agent", END)
    
    # Compile the graph into a runnable orchestrator
    return builder.compile()

# A singleton instance of our compiled graph
orchestrator = build_graph()
