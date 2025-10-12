# backend/app/core/logging_config.py
import logging
import sys

from app.core.config import settings  # For LOG_LEVEL


def setup_logging():
    """
    Configures logging for the application.
    Sets a basic configuration that logs to stdout.
    The log level is determined by the LOG_LEVEL environment variable.
    """
    print(
        f"--- LOGGING_CONFIG.PY: setup_logging() CALLED. Settings.LOG_LEVEL = '{settings.LOG_LEVEL}' ---",
        flush=True,
    )

    log_level_str = settings.LOG_LEVEL.upper()
    numeric_level = getattr(logging, log_level_str, None)

    if not isinstance(numeric_level, int):
        print(
            f"--- LOGGING_CONFIG.PY: Invalid log level: {log_level_str}. Defaulting to INFO. ---",
            flush=True,
        )
        numeric_level = logging.INFO
    else:
        print(
            f"--- LOGGING_CONFIG.PY: Valid log level: {log_level_str} ({numeric_level}) ---",
            flush=True,
        )

    # Basic configuration - this might be too simple if we have multiple handlers/formatters later
    # For now, let's ensure the root logger is set to the desired level.
    # Child loggers will inherit this unless they are explicitly set lower.

    # Create a formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    # Create a handler (StreamHandler to output to stdout/stderr)
    stream_handler = logging.StreamHandler(sys.stdout)  # Or sys.stderr
    stream_handler.setFormatter(formatter)

    # Get the root logger
    root_logger = logging.getLogger()

    # Clear any existing handlers on the root logger to avoid duplicate logs if this is called multiple times
    # (though it should only be called once at startup)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        print(
            "--- LOGGING_CONFIG.PY: Cleared existing root logger handlers. ---",
            flush=True,
        )

    root_logger.addHandler(stream_handler)
    root_logger.setLevel(numeric_level)  # Set level on the root logger

    # Test log after setup
    # We need to get a specific logger to test, not the root one directly for named loggers.
    test_logger = logging.getLogger(
        "app.core.logging_config_test"
    )  # Use a specific name for testing
    print(
        f"--- LOGGING_CONFIG.PY: Effective level for 'app.core.logging_config_test' after setup: {test_logger.getEffectiveLevel()} ({logging.getLevelName(test_logger.getEffectiveLevel())}) ---",
        flush=True,
    )
    test_logger.debug(
        "--- LOGGING_CONFIG.PY DEBUG TEST: This is a debug message from setup_logging. ---"
    )
    test_logger.info(
        "--- LOGGING_CONFIG.PY INFO TEST: This is an info message from setup_logging. ---"
    )
    test_logger.warning(
        "--- LOGGING_CONFIG.PY WARNING TEST: This is a warning message from setup_logging. ---"
    )

    # Print status of specific loggers we care about
    loggers_to_check = [
        "app.game_logic.combat.skill_resolver",
        "app.game_logic.combat.combat_round_processor",
        "app.crud.crud_mob",
        "app.main",
        "app.websocket_router",
    ]
    for logger_name in loggers_to_check:
        temp_logger = logging.getLogger(logger_name)
        effective_level = temp_logger.getEffectiveLevel()
        print(
            f"--- LOGGING_CONFIG.PY: Effective level for '{logger_name}': {effective_level} ({logging.getLevelName(effective_level)}) ---",
            flush=True,
        )

    print(
        f"--- LOGGING_CONFIG.PY: Logging setup COMPLETE. Root logger level set to {logging.getLevelName(root_logger.level)}. ---",
        flush=True,
    )


# Ensure this function is actually called at the very start of your application (e.g., in main.py)
# Example of how it's called in main.py (this is just a comment here):
#
# import logging
# from app.core.logging_config import setup_logging
# setup_logging() # Call it early!
# logger = logging.getLogger(__name__)
# logger.info("Test message from main after setup.")
