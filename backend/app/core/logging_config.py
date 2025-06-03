import logging
import sys
from app.core.config import settings

def setup_logging():
    """
    Configures basic logging for the application.
    Outputs to stdout with a defined format and level.
    """
    # This print goes directly to stdout, bypassing logging system, for initial check
    print(f"--- LOGGING_CONFIG: Entered setup_logging(). LOG_LEVEL from settings: '{settings.LOG_LEVEL}' ---", flush=True)

    log_level_name = settings.LOG_LEVEL
    log_level = getattr(logging, log_level_name, logging.INFO) # Default to INFO if invalid

    # Forcing a specific format that includes module and line number for better debugging
    log_format = "%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    root_logger = logging.getLogger() # Get the root logger
    
    # Clear any existing handlers from the root logger to avoid duplicate messages
    # or conflicts if this function (or basicConfig) was called elsewhere.
    if root_logger.hasHandlers():
        print(f"--- LOGGING_CONFIG: Root logger already had {len(root_logger.handlers)} handlers. Clearing them. ---", flush=True)
        root_logger.handlers.clear()
    
    root_logger.setLevel(log_level) # Set the level on the root logger

    # Create a stream handler to output to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level) # Set the level on the handler itself

    # Create a formatter and add it to the handler
    formatter = logging.Formatter(log_format, datefmt=date_format)
    handler.setFormatter(formatter)

    # Add the handler to the root logger
    root_logger.addHandler(handler)
    
    # Test message using a logger obtained after setup
    # This will now use the configured root logger and handler
    test_logger = logging.getLogger("app.core.logging_config_test")
    print(f"--- LOGGING_CONFIG: About to log test messages. Root logger level: {root_logger.level}, Handler level: {handler.level} ---", flush=True)
    test_logger.debug(f"TEST DEBUG from logging_config: Logging initialized. Effective level for this logger: {test_logger.getEffectiveLevel()}")
    test_logger.info(f"TEST INFO from logging_config: Logging initialized. Effective level for this logger: {test_logger.getEffectiveLevel()}")
    
    if log_level <= logging.DEBUG:
        print(f"--- LOGGING_CONFIG: setup_logging() finished. Configured for DEBUG or lower. ---", flush=True)
    else:
        print(f"--- LOGGING_CONFIG: setup_logging() finished. Configured for level {log_level_name} ({log_level}). ---", flush=True)