"""Aletheia entry point.

Per the build conventions (CLAUDE.md §10): everything runs locally with one
command.

* ``python main.py``              → the Q&A console (Nexus-Mind → Archivist →
                                    Narrator → Philosopher, watched by the
                                    Diagnostician, over Aletheia's own docs).
* ``python main.py --handshake``   → the Milestone 0 two-agent handshake demo.
* ``python main.py --diagnostics`` → the Milestone 3 immune-system demo: induce
                                    a loop and a hung agent; watch the
                                    Diagnostician detect, contain, and heal.
* ``python main.py --knowledge``   → the Milestone 4 knowledge-graph demo: answer
                                    relational questions by graph traversal, each
                                    fact traceable to a source.
* ``python main.py --resonance``   → the Milestone 5 Resonance Cycle demo: replay
                                    the satire-as-fact failure; watch the system
                                    detect → analyse → propose → sandbox-verify →
                                    Human-Gavel-approve → heal → roll back.
"""

import sys


def main() -> None:
    if "--handshake" in sys.argv:
        from aletheia.demo.handshake_demo import main as run_handshake

        run_handshake()
    elif "--diagnostics" in sys.argv:
        from aletheia.demo.diagnostician_demo import main as run_diagnostics

        run_diagnostics()
    elif "--knowledge" in sys.argv:
        from aletheia.demo.knowledge_demo import main as run_knowledge

        run_knowledge()
    elif "--resonance" in sys.argv:
        from aletheia.demo.resonance_demo import main as run_resonance

        run_resonance()
    else:
        from aletheia.app.console import main as run_console

        run_console()


if __name__ == "__main__":
    main()
