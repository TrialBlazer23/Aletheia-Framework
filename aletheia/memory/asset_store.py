"""The Asset Store — large assets live here, messages carry only a pointer.

NSAP-0003: never embed big payloads in Synapse messages. An agent stores its
output as an asset (addressed by a ``Data-Asset-UID``) and broadcasts only the
UID; downstream agents resolve the UID here. In Milestone 0/1 this is a simple
in-process dict; later it can become a real object store behind the same tiny
interface, with no change to the agents.
"""

from __future__ import annotations

from typing import Any


class AssetStore:
    def __init__(self) -> None:
        self._assets: dict[str, Any] = {}

    def put(self, uid: str, asset: Any) -> str:
        self._assets[uid] = asset
        return uid

    def get(self, uid: str) -> Any:
        return self._assets[uid]

    def __contains__(self, uid: str) -> bool:
        return uid in self._assets
