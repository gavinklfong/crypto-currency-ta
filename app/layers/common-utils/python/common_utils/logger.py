import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_logger = logging.getLogger(__name__)


def log_info(message: str, *args, **kwargs) -> None:
    """Log an info level message with optional formatting and context.

    Usage:
        log_info("Fetch %s for %s", pair, interval)
        log_info("Done", status=200, count=5)
        log_info("Done | %s | %s", pair, interval, status=200)
    """
    formatted_message = message % args if args else message
    context = {k: v for k, v in kwargs.items() if k not in ("exc_info",)}
    if context:
        formatted_message = f"{formatted_message} | {json.dumps(context)}"
    _logger.info(formatted_message)


def log_error(message: str, *args, **kwargs) -> None:
    """Log an error level message with optional formatting and context.

    Usage:
        log_error("Failed %s", item, exc_info=True)
        log_error("Error", code=500, detail="bad request")
    """
    exc_info = kwargs.pop("exc_info", None)
    formatted_message = message % args if args else message
    context = {k: v for k, v in kwargs.items() if k not in ("exc_info",)}
    if context:
        formatted_message = f"{formatted_message} | {json.dumps(context)}"
    _logger.error(formatted_message, exc_info=exc_info)
