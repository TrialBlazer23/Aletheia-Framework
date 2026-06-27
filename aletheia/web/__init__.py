"""A tiny web interface for Aletheia — talk to the system in a browser.

ROADMAP "Stack decisions": *CLI first, a tiny FastAPI status page when needed.*
This is that page. It wraps the existing ``QASystem`` (no new agent code) and
exposes it over HTTP: ask a question, request a creative brief, and watch the
Domino Cascade — the Glass Box, in a browser.

Run it with ``python main.py --web`` (needs the ``web`` extra:
``pip install -e ".[web]"``).
"""

from aletheia.web.app import create_app, run

__all__ = ["create_app", "run"]
