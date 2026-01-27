from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

STORE_VERSION = 1
STORE_KEY = "chaac_vwc_state_single"

@dataclass
class PersistedState:
    last_written_ts_ms: int = 0
    last_pump_ts_ms: int = 0
    last_sample: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "PersistedState":
        ps = PersistedState()
        if isinstance(d, dict):
            ps.last_written_ts_ms = int(d.get("last_written_ts_ms", 0) or 0)
            ps.last_pump_ts_ms = int(d.get("last_pump_ts_ms", 0) or 0)
            ps.last_sample = dict(d.get("last_sample", {}) or {})
        return ps

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_written_ts_ms": self.last_written_ts_ms,
            "last_pump_ts_ms": self.last_pump_ts_ms,
            "last_sample": self.last_sample,
        }

class SenseCapStateStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORE_VERSION, STORE_KEY)
        self.state: PersistedState = PersistedState()

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if isinstance(data, dict):
            self.state = PersistedState.from_dict(data)

    async def async_save(self) -> None:
        await self._store.async_save(self.state.to_dict())
