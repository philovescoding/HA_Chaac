from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_ENABLED, CONF_STATION, CONF_ACCESS_ID, CONF_ACCESS_KEY,
    CONF_POLL_SECONDS, CONF_KEEP_DAYS,
    CONF_SENSOR_SOURCE, CONF_MOIST_ENTITY, CONF_TEMP_ENTITY, CONF_EC_ENTITY,
    CONF_PLUG_ENABLED, CONF_PLUG_HOST, CONF_PLUG_ID, CONF_PLUG_USER, CONF_PLUG_PASS,
    CONF_ML_PER_SEC, CONF_PUMP_SECONDS,
)
from .controller import SenseCapVwcControllerSingle, shelly_set_switch
from .storage import SenseCapStateStore

PLATFORMS = ["sensor", "button"]

LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _to_float_from_state(state_obj):
    try:
        if state_obj is None:
            return None
        s = state_obj.state
        if s in (None, "", "unknown", "unavailable"):
            return None
        return float(s)
    except Exception:
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    d = entry.data

    store = SenseCapStateStore(hass)
    await store.async_load()

    controller = SenseCapVwcControllerSingle(
        hass=hass,
        session=session,
        station=str(d.get(CONF_STATION, "global")),
        access_id=str(d.get(CONF_ACCESS_ID, "")),
        access_key=str(d.get(CONF_ACCESS_KEY, "")),
        poll_seconds=int(d.get(CONF_POLL_SECONDS, 60)),
        keep_days=int(d.get(CONF_KEEP_DAYS, 2)),
        enabled=bool(d.get(CONF_ENABLED, True)),
        cfg=d,
        persisted_state=store.state,
    )

    # If configured to use HA entity as sensor source: listen to changes and run decision immediately.
    controller._unsub_state_listener = None  # type: ignore[attr-defined]
    if str(d.get(CONF_SENSOR_SOURCE, "sensecap_cloud")) == "ha_entity":
        moist_ent = str(d.get(CONF_MOIST_ENTITY, "")).strip()
        temp_ent = str(d.get(CONF_TEMP_ENTITY, "")).strip()
        ec_ent = str(d.get(CONF_EC_ENTITY, "")).strip()

        @callback
        def _handle(event):
            if event.data.get("entity_id") != moist_ent:
                return
            vwc = _to_float_from_state(event.data.get("new_state"))
            if vwc is None:
                return
            t = _to_float_from_state(hass.states.get(temp_ent)) if temp_ent else None
            ec = _to_float_from_state(hass.states.get(ec_ent)) if ec_ent else None
            sample = {"t": int(hass.loop.time() * 1000), "moist": vwc}
            if t is not None:
                sample["temp"] = t
            if ec is not None:
                sample["ec"] = ec
            hass.async_create_task(controller.on_external_sample(sample))

        if moist_ent:
            controller._unsub_state_listener = async_track_state_change_event(hass, [moist_ent], _handle)

    async def _async_update():
        try:
            # Some older installs had a controller without poll_once (bad cache/mix).
            if hasattr(controller, "poll_once"):
                data = await controller.poll_once()
            else:
                # fallback: return last known state if no poll_once exists
                data = {
                    "enabled": bool(d.get(CONF_ENABLED, True)),
                    "station": str(d.get(CONF_STATION, "")),
                    "pollSeconds": int(d.get(CONF_POLL_SECONDS, 60)),
                    "last": dict(getattr(store.state, "last_sample", {}) or {}),
                }
            await store.async_save()
            return data
        except Exception as e:
            raise UpdateFailed(str(e)) from e

    coordinator = DataUpdateCoordinator(
        hass,
        logger=logging.getLogger(__name__),
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=_async_update,
        update_interval=timedelta(seconds=max(10, int(d.get(CONF_POLL_SECONDS, 60) or 60))),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "controller": controller,
        "coordinator": coordinator,
        "store": store,
        "entry": entry,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _svc_pump(call: ServiceCall) -> None:
        seconds = int(call.data.get("seconds", 0) or 0)
        ml = float(call.data.get("ml", 0.0) or 0.0)

        cfg = entry.data
        if not cfg.get(CONF_PLUG_ENABLED, False):
            LOGGER.debug("Manual pump: plugEnabled=false")
            return
        host = (cfg.get(CONF_PLUG_HOST) or "").strip()
        if not host:
            LOGGER.debug("Manual pump: plugHost empty")
            return
        plug_id = int(cfg.get(CONF_PLUG_ID, 0) or 0)
        plug_user = str(cfg.get(CONF_PLUG_USER, "") or "")
        plug_pass = str(cfg.get(CONF_PLUG_PASS, "") or "")

        ml_per_sec = float(cfg.get(CONF_ML_PER_SEC, 50.0) or 50.0)
        if seconds <= 0:
            if ml > 0:
                import math
                seconds = max(1, int(math.ceil(ml / max(0.1, ml_per_sec))))
            else:
                seconds = int(cfg.get(CONF_PUMP_SECONDS, 5) or 5)

        ok = await shelly_set_switch(session, host, plug_id, True, user=plug_user, password=plug_pass)
        if ok:
            LOGGER.debug("Manual pump: switched ON ok host=%s id=%s seconds=%s", host, plug_id, seconds)
            await controller.schedule_off(host, plug_id, seconds)
            controller._totals_dirty = True  # type: ignore[attr-defined]
        else:
            LOGGER.debug("Manual pump: switch ON failed host=%s id=%s", host, plug_id)

    hass.services.async_register(DOMAIN, "pump", _svc_pump)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data and getattr(data.get("controller"), "_unsub_state_listener", None):
        try:
            data["controller"]._unsub_state_listener()  # type: ignore[attr-defined]
        except Exception:
            pass

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
