"""The bus + Cascade Log: broadcast delivery, the Glass Box record, error
isolation, and the full end-to-end handshake from the Milestone 0 demo.
"""

import asyncio

from aletheia.bus.in_process import InProcessBus
from aletheia.demo.handshake_demo import run as run_handshake
from aletheia.log.cascade_log import CascadeLog
from aletheia.protocol.messages import make_event


def test_publish_records_to_cascade_log_then_delivers():
    async def scenario():
        log = CascadeLog(path=None)
        bus = InProcessBus(cascade_log=log)
        received = []

        async def sub(msg):
            received.append(msg)

        bus.subscribe(sub)
        await bus.publish(
            make_event(
                source_uid="MODEL:Archivist:0x00A1",
                event_name="DATA_VALIDATED",
                data_asset_uid="ASSET:KG:0x1",
            )
        )
        return log, received

    log, received = asyncio.run(scenario())
    assert len(received) == 1
    assert len(log.entries) == 1
    assert log.entries[0]["seq"] == 1
    assert log.entries[0]["message"]["Body"]["Event-Name"] == "DATA_VALIDATED"


def test_one_failing_subscriber_does_not_break_others_or_the_bus():
    async def scenario():
        bus = InProcessBus()
        good = []

        async def boom(msg):
            raise RuntimeError("subscriber blew up")

        async def fine(msg):
            good.append(msg)

        bus.subscribe(boom)
        bus.subscribe(fine)
        await bus.publish(
            make_event(
                source_uid="MODEL:X:0x1", event_name="PING", data_asset_uid="ASSET:Y:0x2"
            )
        )
        return bus, good

    bus, good = asyncio.run(scenario())
    assert len(good) == 1  # the healthy subscriber still received it
    assert len(bus.delivery_errors) == 1  # the failure was captured, not swallowed silently


def test_cascade_log_is_append_only_and_ordered():
    async def scenario():
        log = CascadeLog(path=None)
        bus = InProcessBus(cascade_log=log)
        for i in range(5):
            await bus.publish(
                make_event(
                    source_uid="MODEL:X:0x1",
                    event_name=f"E{i}",
                    data_asset_uid=f"ASSET:R:0x{i}",
                )
            )
        return log

    log = asyncio.run(scenario())
    seqs = [e["seq"] for e in log.entries]
    assert seqs == [1, 2, 3, 4, 5]
    names = [e["message"]["Body"]["Event-Name"] for e in log.entries]
    assert names == ["E0", "E1", "E2", "E3", "E4"]


def test_end_to_end_handshake_cascade():
    log = asyncio.run(run_handshake())
    flow = [
        (e["message"]["Header"]["Message-Type"], e["message"]["Header"]["Source-UID"])
        for e in log.entries
    ]
    # The canonical domino: TRIGGER -> ACK -> EVENT -> ACK -> TASK_COMPLETE.
    assert flow == [
        ("TRIGGER", "MODEL:Orchestrator:0x0001"),
        ("STATE_CHANGE", "MODEL:Worker:0x00A1"),
        ("EVENT", "MODEL:Worker:0x00A1"),
        ("STATE_CHANGE", "MODEL:Orchestrator:0x0001"),
        ("STATE_CHANGE", "MODEL:Orchestrator:0x0001"),
    ]
    # The first worker reply is the handshake ACKNOWLEDGE.
    assert log.entries[1]["message"]["Body"]["Status-Code"] == "TASK_ACCEPTED"
    # The cascade ends cleanly with TASK_COMPLETE.
    assert log.entries[-1]["message"]["Body"]["Status-Code"] == "TASK_COMPLETE"


def test_cascade_log_writes_jsonl_file(tmp_path):
    async def scenario():
        path = tmp_path / "sub" / "cascade.jsonl"
        log = CascadeLog(path=path)
        bus = InProcessBus(cascade_log=log)
        await bus.publish(
            make_event(
                source_uid="MODEL:X:0x1", event_name="PING", data_asset_uid="ASSET:Y:0x2"
            )
        )
        return path

    path = asyncio.run(scenario())
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"Event-Name": "PING"' in lines[0]
