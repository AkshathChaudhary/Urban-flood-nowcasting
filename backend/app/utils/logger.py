"""
Structured Logging Utility
==========================

Configures consistent, structured logging across all backend modules and engines.
"""

import logging
import sys
from typing import Optional


def get_logger(name: str = "urban_flood", level: int = logging.INFO) -> logging.Logger:
    """Returns a configured logger instance with formatted console output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
