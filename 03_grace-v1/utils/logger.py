"""utils/logger.py — Structured logging for Grace v3."""

import logging
import sys


def get_logger(name: str = "grace") -> logging.Logger:
    from core.config import cfg
    level = getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-14s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    log = logging.getLogger(name)
    log.setLevel(level)
    if not log.handlers:
        log.addHandler(handler)

    # Silence noisy libs
    for noisy in ("urllib3", "requests", "httpx", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log


log = get_logger("grace")
