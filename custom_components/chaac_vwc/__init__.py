from __future__ import annotations

from datetime import timedelta

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_ENABLED, CONF_STATION, CONF_ACCESS_ID, CONF_ACCESS_KEY,
    CONF_POLL_SECONDS, CONF_KEEP_DAYS,
    CONF_PLUG_ENABLED, CONF_PLUG_HOST, CONF_PLUG_ID, CONF_PLUG_USER, CONF_PLUG_PASS,
    CONF_ML_PER_SEC, CONF_PUMP_SECONDS,
)
from .controller import SenseCapVwcControllerSingle, shelly_set_switch
from .storage import SenseCapStateStore

PLATFORMS = ["sensor", "button"]

LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    d = entry.data

    store = SenseCapStateStore(hass)
    await store.async_load()

    controller = SenseCapVwcControllerSingle(
        hass=hass,
        session=session,
        station=d[CONF_STATION],
        access_id=d[CONF_ACCESS_ID],
        access_key=d[CONF_ACCESS_KEY],
        poll_seconds=int(d.get(CONF_POLL_SECONDS, 60)),
        keep_days=int(d.get(CONF_KEEP_DAYS, 2)),
        enabled=bool(d.get(CONF_ENABLED, True)),
        cfg=d,
        persisted_state=store.state,
    )

    async def _async_update():
        try:
            data = await controller.poll_once()
            await store.async_save()
            return data
        except Exception as e:
            raise UpdateFailed(str(e)) from e

    coordinator = DataUpdateCoordinator(
        hass,
        logger=__import__("logging").getLogger(__name__),
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
            controller._totals_dirty = True  # pylint: disable=protected-access
        else:
            LOGGER.debug("Manual pump: switch ON failed host=%s id=%s", host, plug_id)

    hass.services.async_register(DOMAIN, "pump", _svc_pump)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
