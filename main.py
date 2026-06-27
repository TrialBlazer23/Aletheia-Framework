"""Aletheia entry point.

Per the build conventions (CLAUDE.md §10): everything runs locally with one
command.

* ``python main.py``            → the Milestone 1 Q&A console (Nexus-Mind →
                                  Archivist → Narrator over Aletheia's own docs).
* ``python main.py --handshake`` → the Milestone 0 two-agent handshake demo.

As later milestones land (the Philosopher, the Diagnostician, ...), this grows
into the full Nexus-Mind console.
"""

import sys


def main() -> None:
    if "--handshake" in sys.argv:
        from aletheia.demo.handshake_demo import main as run_handshake

        run_handshake()
    else:
        from aletheia.app.console import main as run_console

        run_console()


if __name__ == "__main__":
    main()
