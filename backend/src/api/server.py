import logging
import uuid
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv(override=True)

from backend.src.api.telemetry import setup_telemetry

setup_telemetry()

from backend.src.graph.workflow import app as compliance_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-server")

app = FastAPI(
    title="Brand Guardian AI API",
    description="API for auditing video content against brand compliance rules.",
    version="1.0.0",
)


class AuditRequest(BaseModel):
    """Request payload for a video compliance audit."""

    video_url: str


class ComplianceIssue(BaseModel):
    """A compliance issue identified during an audit."""

    category: str
    severity: str
    description: str


class AuditResponse(BaseModel):
    """Response returned after a video compliance audit."""

    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]


@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest) -> AuditResponse:
    """Run the compliance workflow for the submitted video URL."""
    session_id = str(uuid.uuid4())
    video_id = f"vid_{session_id[:8]}"

    logger.info(
        "Received audit request for %s (session: %s)",
        request.video_url,
        session_id,
    )

    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id,
        "compliance_results": [],
        "errors": [],
    }

    try:
        final_state = compliance_graph.invoke(initial_inputs)
        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id"),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get(
                "final_report",
                "No report generated.",
            ),
            compliance_results=final_state.get("compliance_results", []),
        )
    except Exception as error:
        logger.exception("Audit failed for session %s", session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Workflow Execution Failed: {str(error)}",
        ) from error


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report that the API process is running."""
    return {"status": "healthy", "service": "Brand Guardian AI"}
