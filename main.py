"""Command-line entry point for running a sample ClaimCheck AI audit."""

import json
import logging
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("brand-guardian-runner")


def run_cli_simulation() -> None:
    """Run the sample video through the compliance audit workflow."""
    session_id = str(uuid.uuid4())
    logger.info("Starting audit session: %s", session_id)

    initial_inputs: dict[str, Any] = {
        "video_url": "https://youtu.be/dT7S75eYhcQ",
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": [],
    }

    print("\n--- Input Payload: Initializing Workflow ---")
    print(json.dumps(initial_inputs, indent=2))

    try:
        final_state = app.invoke(initial_inputs)

        print("\n--- Workflow Execution Complete ---")
        print("\n=== Compliance Audit Report ===")
        print(f"Video ID:    {final_state.get('video_id')}")
        print(f"Status:      {final_state.get('final_status')}")

        print("\n[ Violations Detected ]")
        results = final_state.get("compliance_results", [])

        if results:
            for issue in results:
                print(
                    f"- [{issue.get('severity')}] "
                    f"{issue.get('category')}: {issue.get('description')}"
                )
        else:
            print("No violations found.")

        print("\n[ Final Summary ]")
        print(final_state.get("final_report"))

    except Exception:
        logger.exception("Workflow execution failed for session %s", session_id)
        raise


if __name__ == "__main__":
    run_cli_simulation()
