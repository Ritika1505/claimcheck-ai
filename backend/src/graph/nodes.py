import json
import logging
import os
import re
from typing import Any, Dict

from langchain_community.vectorstores import AzureSearch
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

from backend.src.graph.state import VideoAuditState
from backend.src.services.video_indexer import VideoIndexerService

logger = logging.getLogger("brand-guardian")
logging.basicConfig(level=logging.INFO)


def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    """Download and index a YouTube video, then extract its insights."""
    video_url = state.get("video_url")
    video_id_input = state.get("video_id", "vid_demo")

    logger.info("--- [Node: Indexer] Processing: %s ---", video_url)

    local_filename = "temp_audit_video.mp4"

    try:
        vi_service = VideoIndexerService()

        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(
                video_url,
                output_path=local_filename,
            )
        else:
            raise Exception("Please provide a valid YouTube URL for this test.")

        azure_video_id = vi_service.upload_video(
            local_path,
            video_name=video_id_input,
        )
        logger.info("Upload Success. Azure ID: %s", azure_video_id)

        if os.path.exists(local_path):
            os.remove(local_path)

        raw_insights = vi_service.wait_for_processing(azure_video_id)
        clean_data = vi_service.extract_data(raw_insights)

        logger.info("--- [Node: Indexer] Extraction Complete ---")
        return clean_data

    except Exception as error:
        logger.error("Video Indexer Failed: %s", error)
        return {
            "errors": [str(error)],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": [],
        }


def audit_content_node(state: VideoAuditState) -> Dict[str, Any]:
    """Use Azure AI Search and Azure OpenAI to audit the indexed content."""
    logger.info("--- [Node: Auditor] querying Knowledge Base & LLM ---")

    transcript = state.get("transcript", "")

    if not transcript:
        logger.warning("No transcript available. Skipping Audit.")
        return {
            "final_status": "FAIL",
            "final_report": (
                "Audit skipped because video processing failed (No Transcript)."
            ),
        }

    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.0,
    )

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-3-small",
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    vector_store = AzureSearch(
        azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function=embeddings.embed_query,
    )

    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript} {' '.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text, k=3)
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])

    system_prompt = f"""
    You are a Senior Brand Compliance Auditor.
    
    OFFICIAL REGULATORY RULES:
    {retrieved_rules}
    
    INSTRUCTIONS:
    1. Analyze the Transcript and OCR text below.
    2. Identify ANY violations of the rules.
    3. Return strictly JSON in the following format:
    
    {{
        "compliance_results": [
            {{
                "category": "Claim Validation",
                "severity": "CRITICAL",
                "description": "Explanation of the violation..."
            }}
        ],
        "status": "FAIL", 
        "final_report": "Summary of findings..."
    }}

    If no violations are found, set "status" to "PASS" and "compliance_results" to [].
    """

    user_message = f"""
    VIDEO METADATA: {state.get('video_metadata', {})}
    TRANSCRIPT: {transcript}
    ON-SCREEN TEXT (OCR): {ocr_text}
    """

    try:
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
        )

        content = response.content
        if "```" in content:
            content = re.search(
                r"```(?:json)?(.*?)```",
                content,
                re.DOTALL,
            ).group(1)

        audit_data = json.loads(content.strip())

        return {
            "compliance_results": audit_data.get("compliance_results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get(
                "final_report",
                "No report generated.",
            ),
        }

    except Exception as error:
        logger.error("System Error in Auditor Node: %s", str(error))
        logger.error(
            "Raw LLM Response: %s",
            response.content if "response" in locals() else "None",
        )
        return {
            "errors": [str(error)],
            "final_status": "FAIL",
        }
