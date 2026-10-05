import logging
import os
import time

import requests
import yt_dlp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")


class VideoIndexerService:
    """Integrate YouTube video downloads with Azure Video Indexer."""

    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv(
            "AZURE_VI_NAME",
            "project-brand-guardian-001",
        )
        self.credential = DefaultAzureCredential()

    def get_access_token(self):
        """Generate an Azure Resource Manager access token."""
        try:
            token_object = self.credential.get_token(
                "https://management.azure.com/.default"
            )
            return token_object.token
        except Exception as error:
            logger.error("Failed to get Azure token: %s", error)
            raise

    def get_account_token(self, arm_access_token):
        """Exchange an ARM token for an Azure Video Indexer account token."""
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            "/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"******"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")

    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """Download a YouTube video to a local file."""
        logger.info("Downloading YouTube video: %s", url)

        ydl_options = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": False,
            "no_warnings": False,
            "extractor_args": {
                "youtube": {"player_client": ["android", "web"]},
            },
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                ),
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_options) as youtube_dl:
                youtube_dl.download([url])
            logger.info("Download complete.")
            return output_path
        except Exception as error:
            raise Exception(f"YouTube Download Failed: {str(error)}")

    def upload_video(self, video_path, video_name):
        """Upload a local video file to Azure Video Indexer."""
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = (
            f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        )
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }

        logger.info("Uploading file %s to Azure...", video_path)

        with open(video_path, "rb") as video_file:
            files = {"file": video_file}
            response = requests.post(api_url, params=params, files=files)

        if response.status_code != 200:
            raise Exception(f"Azure Upload Failed: {response.text}")

        return response.json().get("id")

    def wait_for_processing(self, video_id):
        """Poll Azure Video Indexer until processing completes."""
        logger.info("Waiting for video %s to process...", video_id)

        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)
            url = (
                f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            )
            params = {"accessToken": vi_token}
            response = requests.get(url, params=params)
            data = response.json()

            state = data.get("state")
            if state == "Processed":
                return data
            if state == "Failed":
                raise Exception("Video Indexing Failed in Azure.")
            if state == "Quarantined":
                raise Exception(
                    "Video Quarantined (Copyright/Content Policy Violation)."
                )

            logger.info("Status: %s... waiting 30s", state)
            time.sleep(30)

    def extract_data(self, vi_json):
        """Parse Azure Video Indexer insights into the audit state format."""
        transcript_lines = []
        for video in vi_json.get("videos", []):
            transcript = video.get("insights", {}).get("transcript", [])
            for insight in transcript:
                transcript_lines.append(insight.get("text"))

        ocr_lines = []
        for video in vi_json.get("videos", []):
            ocr_insights = video.get("insights", {}).get("ocr", [])
            for insight in ocr_insights:
                ocr_lines.append(insight.get("text"))

        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration", {}).get("seconds"),
                "platform": "youtube",
            },
        }
