"""Logging configuration for Silent Disco application.

This module provides a centralized logging setup with both console and file handlers.
Replaces the custom print_log() function with proper Python logging.
"""

import logging
import os
from datetime import datetime
from typing import Optional
from collections import deque


def setup_logger(
    name: str = "silent_disco",
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    """Set up and configure logger with console and file handlers.

    Args:
        name: Logger name
        log_dir: Directory where log files will be stored
        console_level: Minimum level for console output (default: INFO)
        file_level: Minimum level for file output (default: DEBUG)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all levels, handlers will filter

    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG and above) - creates new file per day
    log_filename = datetime.now().strftime('silent_disco_%Y%m%d.log')
    log_filepath = os.path.join(log_dir, log_filename)

    file_handler = logging.FileHandler(log_filepath, mode='a')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    logger.info(f"Logger initialized - Console: {logging.getLevelName(console_level)}, File: {log_filepath}")

    return logger


def get_logger(name: str = "silent_disco") -> logging.Logger:
    """Get existing logger or create new one if it doesn't exist.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    # If logger hasn't been set up yet, set it up
    if not logger.handlers:
        logger = setup_logger(name)

    return logger


class LogCollector:
    """Collects log messages in memory for returning as API response.

    Uses a bounded deque to prevent unbounded memory growth.
    Keeps the last 500 log messages for API responses.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, max_messages: int = 500):
        """Initialize log collector.

        Args:
            logger: Logger to use (default: get_logger())
            max_messages: Maximum number of messages to keep in memory (default: 500)
        """
        self.messages = deque(maxlen=max_messages)  # Bounded to prevent memory leak
        self.logger = logger or get_logger()

    def info(self, message: str):
        """Log info message and collect it."""
        self.logger.info(message)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.messages.append(f"{timestamp}\t{message}")

    def warning(self, message: str):
        """Log warning message and collect it."""
        self.logger.warning(message)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.messages.append(f"{timestamp}\tWARNING: {message}")

    def error(self, message: str):
        """Log error message and collect it."""
        self.logger.error(message)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.messages.append(f"{timestamp}\tERROR: {message}")

    def get_logs(self):
        """Get all collected log messages.

        Returns:
            List of log message strings (last 500 messages)
        """
        return list(self.messages)
