from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, METRICS


def _slot(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    s = data.get("slot") if isinstance(data, dict) else None
    return s if isinstance(s, dict) else None


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []

    entities.append(StatusSensor(coordinator, entry))
    entities.append(LastUpdateSensor(coordinator, entry))

    for k in METRICS.keys():
        entities.append(MetricSensor(coordinator, entry, k))

    entities.append(PumpTotalSensor(coordinator, entry, days=1))
    entities.append(PumpTotalSensor(coordinator, entry, days=7))

    async_add_entities(entities)


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="Chaac VWC",
            manufacturer="Chaac",
            model="SenseCAP VWC (Single Slot)",
        )


class MetricSensor(_Base):
    def __init__(self, coordinator, entry: ConfigEntry, metric: str):
        super().__init__(coordinator, entry)
        meta = METRICS[metric]
        self.metric = metric
        self._attr_name = meta["name"]
        self._attr_unique_id = f"{entry.entry_id}_{metric}"
        self._attr_native_unit_of_measurement = meta.get("unit")
        self._attr_device_class = meta.get("device_class")
        self._attr_state_class = meta.get("state_class")

    @property
    def native_value(self):
        s = _slot(self.coordinator.data)
        last = s.get("last") if isinstance(s, dict) else None
        if not isinstance(last, dict):
            return None
        key = {"temp": "temp", "moist": "moist", "ec": "ec", "wec": "wec", "eps": "eps"}[self.metric]
        return last.get(key)


class StatusSensor(_Base):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self):
        s = _slot(self.coordinator.data)
        return s.get("status") if isinstance(s, dict) else None


class LastUpdateSensor(_Base):
    _attr_device_class = "timestamp"

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_name = "Last Update"
        self._attr_unique_id = f"{entry.entry_id}_last_update"

    @property
    def native_value(self):
        s = _slot(self.coordinator.data)
        last = s.get("last") if isinstance(s, dict) else None
        if not isinstance(last, dict):
            return None
        t = last.get("t")
        if not isinstance(t, (int, float)) or t <= 0:
            return None
        return datetime.fromtimestamp(float(t) / 1000.0, tz=timezone.utc)


class PumpTotalSensor(_Base):
    _attr_state_class = "total"
    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "ml"

    def __init__(self, coordinator, entry: ConfigEntry, days: int):
        super().__init__(coordinator, entry)
        self.days = int(days)
        self._attr_name = f"Watered {self.days}d"
        self._attr_unique_id = f"{entry.entry_id}_watered_{self.days}d"

    @property
    def native_value(self):
        s = _slot(self.coordinator.data)
        if not isinstance(s, dict):
            return 0.0
        pt = s.get("pumpTotals")
        if not isinstance(pt, dict):
            return 0.0
        v = pt.get(f"{self.days}d")
        try:
            return float(v or 0.0)
        except Exception:
            return 0.0
