"""Vercel entry point: the same portal, served as one Python (WSGI) function."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal import app  # noqa: E402,F401
