import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class ComplianceIssue(TypedDict):
    """A compliance issue identified during a video audit."""

    category: str
    description: str
    severity: str
    timestamp: Optional[str]


class VideoAuditState(TypedDict):
    """State shared between nodes in the video-audit LangGraph workflow."""

    video_url: str
    video_id: str

    local_file_path: Optional[str]
    video_metadata: Dict[str, Any]
    transcript: Optional[str]
    ocr_text: List[str]

    compliance_results: Annotated[List[ComplianceIssue], operator.add]

    final_status: str
    final_report: str

    errors: Annotated[List[str], operator.add]
