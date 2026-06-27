"""Milestone 0 proof: a two-agent Domino Cascade handshake.

Two stand-in agents complete the canonical Synapse handshake over the bus:

    Orchestrator --TRIGGER(DO_WORK)--> Worker
    Worker       --STATE_CHANGE: TASK_ACCEPTED-->        (handshake ACK)
    Worker       --EVENT(WORK_COMPLETE)-->               (result broadcast)
    Orchestrator --STATE_CHANGE: TASK_ACCEPTED-->        (handshake ACK)
    Orchestrator --STATE_CHANGE: TASK_COMPLETE-->        (cascade finished)

Every hop is recorded in the Cascade Log (the Glass Box). Run it with
``python main.py`` or ``python -m aletheia.demo.handshake_demo``.

These are deliberately *dummy* agents — they carry no LLM and no real work. They
exist only to prove the nervous system (protocol + bus + SIL + log) is wired
correctly. The real Family (Nexus-Mind, Archivist, Narrator, ...) lands in
Milestone 1+.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aletheia.agents.family_member import FamilyMember
from aletheia.bus.in_process import InProcessBus
from aletheia.log.cascade_log import CascadeLog
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.sil.interest_profile import InterestProfile, InterestRule

ORCHESTRATOR_UID = "MODEL:Orchestrator:0x0001"
WORKER_UID = "MODEL:Worker:0x00A1"


class Worker(FamilyMember):
    """Reacts to a DO_WORK trigger and broadcasts a WORK_COMPLETE event."""

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "DO_WORK":
            return
        print(f"  · {self.name} executing '{action}' ...")
        # (Step 4) broadcast the result; downstream Listeners may react.
        await self.broadcaster.broadcast_event(
            event_name="WORK_COMPLETE",
            asset_type="WORK_RESULT",
            description="Worker finished the requested unit of work.",
            confidence_score=0.97,
        )


class Orchestrator(FamilyMember):
    """Kicks off the cascade, then finalizes when the Worker is done."""

    async def kick_off(self) -> None:
        print(f"  · {self.name} sending TRIGGER(DO_WORK) -> {WORKER_UID}")
        await self.broadcaster.send_trigger(
            target_uid=WORKER_UID, action_to_trigger="DO_WORK"
        )

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "FINALIZE":
            return
        print(
            f"  · {self.name} received '{data.get('event_name')}' "
            f"(confidence {data.get('confidence_score')}); finalizing."
        )
        await self.broadcaster.report_state(
            target_uid=WORKER_UID,
            status_code="TASK_COMPLETE",
            reason="Cascade finished; result accepted.",
        )


async def run() -> CascadeLog:
    """Run the demo cascade and return the populated Cascade Log."""
    cascade_log = CascadeLog(path=None)  # in-memory for a clean, repeatable demo
    bus = InProcessBus(cascade_log=cascade_log)

    worker = Worker(name="Worker", uid=WORKER_UID, bus=bus)
    orchestrator = Orchestrator(
        name="Orchestrator",
        uid=ORCHESTRATOR_UID,
        bus=bus,
        interest_profile=InterestProfile(
            [
                InterestRule(
                    action_to_trigger="FINALIZE",
                    source_model_uid=WORKER_UID,
                    message_type=MessageType.EVENT,
                    event_name="WORK_COMPLETE",
                )
            ]
        ),
    )

    worker.connect()
    orchestrator.connect()

    print("\nDomino Cascade — live:")
    await orchestrator.kick_off()

    return cascade_log


def main() -> None:
    cascade_log = asyncio.run(run())
    print("\nCascade Log (the Glass Box audit trail):")
    print(cascade_log.pretty())
    print(f"\n{len(cascade_log.entries)} messages recorded, append-only.\n")


if __name__ == "__main__":
    main()
