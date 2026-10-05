"""Build and expose the video compliance audit LangGraph workflow."""

from langgraph.graph import END, StateGraph

from backend.src.graph.nodes import audit_content_node, index_video_node
from backend.src.graph.state import VideoAuditState


def create_graph():
    """Create and compile the index-then-audit workflow."""
    workflow = StateGraph(VideoAuditState)
    workflow.add_node("indexer", index_video_node)
    workflow.add_node("auditor", audit_content_node)

    workflow.set_entry_point("indexer")
    workflow.add_edge("indexer", "auditor")
    workflow.add_edge("auditor", END)

    return workflow.compile()


app = create_graph()
