import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor

logger = logging.getLogger("brand-guardian-telemetry")


def setup_telemetry() -> None:
    """Configure Azure Monitor when an Application Insights connection is set."""
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logger.warning("Application Insights connection string is not set; telemetry is disabled.")
        return

    try:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="brand-guardian-tracer",
        )
    except Exception:
        logger.exception("Failed to initialize Azure Monitor.")
        return

    logger.info("Azure Monitor telemetry initialized.")
