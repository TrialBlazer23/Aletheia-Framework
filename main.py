"""Aletheia entry point.

Per the build conventions (CLAUDE.md §10): everything runs locally with one
command. Today that command runs the Milestone 0 proof — a two-agent Domino
Cascade handshake, fully recorded in the Glass Box Cascade Log. As later
milestones land, this entry point grows into the real Nexus-Mind console.
"""

from aletheia.demo.handshake_demo import main

if __name__ == "__main__":
    main()
