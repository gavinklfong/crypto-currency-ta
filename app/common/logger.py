import json
import logging

# Configure root logger to output to stdout (handled by Lambda CloudWatch)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_logger = logging.getLogger(__name__)


def log_info(message: str, **kwargs) -> None:
    """Log an info level message with JSON context."""
    _logger.info(f"{message} | {json.dumps(kwargs)}")


def log_error(message: str, **kwargs) -> None:
    """Log an error level message with JSON context."""
    _logger.error(f"{message} | {json.dumps(kwargs)}")
