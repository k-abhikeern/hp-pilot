"""Shared helpers used by every stage: settings, folders and logging."""
import json
import logging
import sys
import time
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def load_config(path=None):
    """Read config.toml (or another settings file) into a dictionary."""
    path = Path(path) if path else PROJECT_ROOT / "config.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def stage_dirs(stage_dir):
    """Make sure a stage has outputs/ and logs/ folders, and return both."""
    stage_dir = Path(stage_dir)
    out_dir, log_dir = stage_dir / "outputs", stage_dir / "logs"
    out_dir.mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)
    return out_dir, log_dir


def get_logger(name, log_dir):
    """Log to the screen and to a new time-stamped file in log_dir, so old runs are kept."""
    log_file = Path(log_dir) / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # stop other libraries' log settings from printing our lines twice
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S")
    for handler in (logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger, log_file


def save_run_info(out_dir, info):
    """Save the settings and results of a run as run_info.json, so it can be reproduced."""
    with open(Path(out_dir) / "run_info.json", "w") as f:
        json.dump(info, f, indent=2, default=str)
