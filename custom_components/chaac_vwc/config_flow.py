from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN, default_cfg,
    CONF_ENABLED, CONF_STATION, CONF_ACCESS_ID, CONF_ACCESS_KEY,
    CONF_POLL_SECONDS, CONF_KEEP_DAYS,
    CONF_DEVICE_EUI, CONF_CHANNEL_INDEX,
    CONF_PLUG_ENABLED, CONF_PLUG_HOST, CONF_PLUG_ID, CONF_PLUG_USER, CONF_PLUG_PASS,
    CONF_THRESHOLD_P1, CONF_THRESHOLD_P2,
    CONF_ML_PER_SEC, CONF_USE_SECONDS, CONF_PUMP_ML, CONF_PUMP_SECONDS,
    CONF_PLANT_INTERVAL_MIN, CONF_CHECK_ONLY_IN_PLANT_TIMES,
    CONF_P1_START_H, CONF_P1_START_M, CONF_P1_END_H, CONF_P1_END_M,
    CONF_P2_START_H, CONF_P2_START_M, CONF_P2_END_H, CONF_P2_END_M,
    DEFAULT_STATION, DEFAULT_POLL_SECONDS, DEFAULT_KEEP_DAYS,
    DEFAULT_CHANNEL_INDEX, DEFAULT_THRESHOLD, DEFAULT_ML_PER_SEC, DEFAULT_PUMP_ML, DEFAULT_PUMP_SECONDS, DEFAULT_PLANT_INTERVAL_MIN,
)

def _clamp_int(v, lo, hi, d):
    try:
        x = int(v)
    except Exception:
        x = int(d)
    return max(lo, min(hi, x))

def _clamp_float(v, lo, hi, d):
    try:
        x = float(v)
    except Exception:
        x = float(d)
    return max(lo, min(hi, x))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 4

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            access_id = str(user_input.get(CONF_ACCESS_ID, "")).strip()
            access_key = str(user_input.get(CONF_ACCESS_KEY, "")).strip()
            device_eui = str(user_input.get(CONF_DEVICE_EUI, "")).strip()
            if not access_id or not access_key:
                errors["base"] = "missing_creds"
            elif not device_eui:
                errors["base"] = "missing_eui"
            else:
                station = user_input.get(CONF_STATION, DEFAULT_STATION)
                await self.async_set_unique_id(f"{DOMAIN}:{station}:{access_id[:8]}:{device_eui[-6:]}")
                self._abort_if_unique_id_configured()

                cfg = default_cfg()
                cfg.update({
                    CONF_ENABLED: bool(user_input.get(CONF_ENABLED, True)),
                    CONF_STATION: station,
                    CONF_ACCESS_ID: access_id,
                    CONF_ACCESS_KEY: access_key,
                    CONF_DEVICE_EUI: device_eui,
                    CONF_POLL_SECONDS: max(10, int(user_input.get(CONF_POLL_SECONDS, DEFAULT_POLL_SECONDS))),
                    CONF_KEEP_DAYS: _clamp_int(user_input.get(CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS), 2, 7, DEFAULT_KEEP_DAYS),
                    CONF_PLUG_ENABLED: bool(user_input.get(CONF_PLUG_ENABLED, False)),
                    CONF_PLUG_HOST: str(user_input.get(CONF_PLUG_HOST, "")).strip(),
                    CONF_PLUG_ID: int(user_input.get(CONF_PLUG_ID, 0) or 0),
                    CONF_PLUG_USER: str(user_input.get(CONF_PLUG_USER, "")).strip(),
                    CONF_PLUG_PASS: str(user_input.get(CONF_PLUG_PASS, "")).strip(),
                    CONF_THRESHOLD_P1: float(user_input.get(CONF_THRESHOLD_P1, DEFAULT_THRESHOLD)),
                    CONF_THRESHOLD_P2: float(user_input.get(CONF_THRESHOLD_P2, DEFAULT_THRESHOLD)),

                    CONF_ML_PER_SEC: float(user_input.get(CONF_ML_PER_SEC, DEFAULT_ML_PER_SEC)),
                    CONF_USE_SECONDS: bool(user_input.get(CONF_USE_SECONDS, False)),
                    CONF_PUMP_ML: float(user_input.get(CONF_PUMP_ML, DEFAULT_PUMP_ML)),
                    CONF_PUMP_SECONDS: int(user_input.get(CONF_PUMP_SECONDS, DEFAULT_PUMP_SECONDS)),
                    CONF_PLANT_INTERVAL_MIN: int(user_input.get(CONF_PLANT_INTERVAL_MIN, DEFAULT_PLANT_INTERVAL_MIN)),
                    CONF_CHECK_ONLY_IN_PLANT_TIMES: bool(user_input.get(CONF_CHECK_ONLY_IN_PLANT_TIMES, True)),
                    CONF_P1_START_H: int(user_input.get(CONF_P1_START_H, 0)),
                    CONF_P1_START_M: int(user_input.get(CONF_P1_START_M, 0)),
                    CONF_P1_END_H: int(user_input.get(CONF_P1_END_H, 0)),
                    CONF_P1_END_M: int(user_input.get(CONF_P1_END_M, 0)),
                    CONF_P2_START_H: int(user_input.get(CONF_P2_START_H, 0)),
                    CONF_P2_START_M: int(user_input.get(CONF_P2_START_M, 0)),
                    CONF_P2_END_H: int(user_input.get(CONF_P2_END_H, 0)),
                    CONF_P2_END_M: int(user_input.get(CONF_P2_END_M, 0)),
                })
                return self.async_create_entry(title="Chaac VWC (Single Slot)", data=cfg)

        schema = vol.Schema({
            vol.Optional(CONF_ENABLED, default=True): bool,
            vol.Required(CONF_STATION, default=DEFAULT_STATION): vol.In(["global", "china"]),
            vol.Required(CONF_ACCESS_ID): str,
            vol.Required(CONF_ACCESS_KEY): str,
            vol.Required(CONF_DEVICE_EUI): str,
            vol.Optional(CONF_POLL_SECONDS, default=DEFAULT_POLL_SECONDS): vol.Coerce(int),
            vol.Optional(CONF_KEEP_DAYS, default=DEFAULT_KEEP_DAYS): vol.Coerce(int),
# Optional Shelly + watering logic (can also be changed later in Options)
vol.Optional(CONF_PLUG_ENABLED, default=False): bool,
vol.Optional(CONF_PLUG_HOST, default=""): str,
vol.Optional(CONF_PLUG_ID, default=0): vol.Coerce(int),
            vol.Optional(CONF_PLUG_USER, default=""): str,
            vol.Optional(CONF_PLUG_PASS, default=""): str,

vol.Optional(CONF_THRESHOLD_P1, default=DEFAULT_THRESHOLD): vol.Coerce(float),
vol.Optional(CONF_THRESHOLD_P2, default=DEFAULT_THRESHOLD): vol.Coerce(float),

            vol.Optional(CONF_ML_PER_SEC, default=DEFAULT_ML_PER_SEC): vol.Coerce(float),
            vol.Optional(CONF_USE_SECONDS, default=False): bool,
            vol.Optional(CONF_PUMP_ML, default=DEFAULT_PUMP_ML): vol.Coerce(float),
            vol.Optional(CONF_PUMP_SECONDS, default=DEFAULT_PUMP_SECONDS): vol.Coerce(int),

vol.Optional(CONF_PLANT_INTERVAL_MIN, default=DEFAULT_PLANT_INTERVAL_MIN): vol.Coerce(int),
vol.Optional(CONF_CHECK_ONLY_IN_PLANT_TIMES, default=True): bool,

vol.Optional(CONF_P1_START_H, default=0): vol.Coerce(int),
vol.Optional(CONF_P1_START_M, default=0): vol.Coerce(int),
vol.Optional(CONF_P1_END_H, default=0): vol.Coerce(int),
vol.Optional(CONF_P1_END_M, default=0): vol.Coerce(int),

vol.Optional(CONF_P2_START_H, default=0): vol.Coerce(int),
vol.Optional(CONF_P2_START_M, default=0): vol.Coerce(int),
vol.Optional(CONF_P2_END_H, default=0): vol.Coerce(int),
vol.Optional(CONF_P2_END_M, default=0): vol.Coerce(int),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChaacSenseCapOptionsFlow(config_entry)


class ChaacSenseCapOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        d = self.config_entry.data
        if user_input is not None:
            new = dict(d)

            # allow editing creds + device eui here too (often needed)
            new[CONF_STATION] = user_input.get(CONF_STATION, new.get(CONF_STATION, DEFAULT_STATION))
            new[CONF_ACCESS_ID] = str(user_input.get(CONF_ACCESS_ID, new.get(CONF_ACCESS_ID, ""))).strip()
            new[CONF_ACCESS_KEY] = str(user_input.get(CONF_ACCESS_KEY, new.get(CONF_ACCESS_KEY, ""))).strip()
            new[CONF_DEVICE_EUI] = str(user_input.get(CONF_DEVICE_EUI, new.get(CONF_DEVICE_EUI, ""))).strip()

            new[CONF_POLL_SECONDS] = max(10, int(user_input.get(CONF_POLL_SECONDS, new.get(CONF_POLL_SECONDS, DEFAULT_POLL_SECONDS))))
            new[CONF_KEEP_DAYS] = _clamp_int(user_input.get(CONF_KEEP_DAYS, new.get(CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS)), 2, 7, DEFAULT_KEEP_DAYS)

            new[CONF_CHANNEL_INDEX] = _clamp_int(user_input.get(CONF_CHANNEL_INDEX, new.get(CONF_CHANNEL_INDEX, DEFAULT_CHANNEL_INDEX)), 1, 8, DEFAULT_CHANNEL_INDEX)

            new[CONF_PLUG_ENABLED] = bool(user_input.get(CONF_PLUG_ENABLED, new.get(CONF_PLUG_ENABLED, False)))
            new[CONF_PLUG_HOST] = str(user_input.get(CONF_PLUG_HOST, new.get(CONF_PLUG_HOST, ""))).strip()
            new[CONF_PLUG_ID] = _clamp_int(user_input.get(CONF_PLUG_ID, new.get(CONF_PLUG_ID, 0)), 0, 10, 0)
            new[CONF_PLUG_USER] = str(user_input.get(CONF_PLUG_USER, new.get(CONF_PLUG_USER, ""))).strip()
            new[CONF_PLUG_PASS] = str(user_input.get(CONF_PLUG_PASS, new.get(CONF_PLUG_PASS, ""))).strip()

            new[CONF_THRESHOLD_P1] = _clamp_float(user_input.get(CONF_THRESHOLD_P1, new.get(CONF_THRESHOLD_P1, DEFAULT_THRESHOLD)), 0.0, 100.0, DEFAULT_THRESHOLD)
            new[CONF_THRESHOLD_P2] = _clamp_float(user_input.get(CONF_THRESHOLD_P2, new.get(CONF_THRESHOLD_P2, DEFAULT_THRESHOLD)), 0.0, 100.0, DEFAULT_THRESHOLD)

            new[CONF_ML_PER_SEC] = _clamp_float(user_input.get(CONF_ML_PER_SEC, new.get(CONF_ML_PER_SEC, DEFAULT_ML_PER_SEC)), 0.1, 100000.0, DEFAULT_ML_PER_SEC)
            new[CONF_USE_SECONDS] = bool(user_input.get(CONF_USE_SECONDS, new.get(CONF_USE_SECONDS, False)))
            new[CONF_PUMP_ML] = _clamp_float(user_input.get(CONF_PUMP_ML, new.get(CONF_PUMP_ML, DEFAULT_PUMP_ML)), 0.0, 100000.0, DEFAULT_PUMP_ML)
            new[CONF_PUMP_SECONDS] = _clamp_int(user_input.get(CONF_PUMP_SECONDS, new.get(CONF_PUMP_SECONDS, DEFAULT_PUMP_SECONDS)), 1, 3600, DEFAULT_PUMP_SECONDS)

            new[CONF_PLANT_INTERVAL_MIN] = _clamp_int(user_input.get(CONF_PLANT_INTERVAL_MIN, new.get(CONF_PLANT_INTERVAL_MIN, DEFAULT_PLANT_INTERVAL_MIN)), 0, 24*60, DEFAULT_PLANT_INTERVAL_MIN)
            new[CONF_CHECK_ONLY_IN_PLANT_TIMES] = bool(user_input.get(CONF_CHECK_ONLY_IN_PLANT_TIMES, new.get(CONF_CHECK_ONLY_IN_PLANT_TIMES, True)))

            new[CONF_P1_START_H] = _clamp_int(user_input.get(CONF_P1_START_H, new.get(CONF_P1_START_H, 0)), 0, 23, 0)
            new[CONF_P1_START_M] = _clamp_int(user_input.get(CONF_P1_START_M, new.get(CONF_P1_START_M, 0)), 0, 59, 0)
            new[CONF_P1_END_H] = _clamp_int(user_input.get(CONF_P1_END_H, new.get(CONF_P1_END_H, 0)), 0, 23, 0)
            new[CONF_P1_END_M] = _clamp_int(user_input.get(CONF_P1_END_M, new.get(CONF_P1_END_M, 0)), 0, 59, 0)

            new[CONF_P2_START_H] = _clamp_int(user_input.get(CONF_P2_START_H, new.get(CONF_P2_START_H, 0)), 0, 23, 0)
            new[CONF_P2_START_M] = _clamp_int(user_input.get(CONF_P2_START_M, new.get(CONF_P2_START_M, 0)), 0, 59, 0)
            new[CONF_P2_END_H] = _clamp_int(user_input.get(CONF_P2_END_H, new.get(CONF_P2_END_H, 0)), 0, 23, 0)
            new[CONF_P2_END_M] = _clamp_int(user_input.get(CONF_P2_END_M, new.get(CONF_P2_END_M, 0)), 0, 59, 0)

            self.hass.config_entries.async_update_entry(self.config_entry, data=new)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            # keep it "single slot": credentials + eui visible first
            vol.Optional(CONF_STATION, default=d.get(CONF_STATION, DEFAULT_STATION)): vol.In(["global", "china"]),
            vol.Optional(CONF_ACCESS_ID, default=d.get(CONF_ACCESS_ID, "")): str,
            vol.Optional(CONF_ACCESS_KEY, default=d.get(CONF_ACCESS_KEY, "")): str,
            vol.Optional(CONF_DEVICE_EUI, default=d.get(CONF_DEVICE_EUI, "")): str,

            vol.Optional(CONF_POLL_SECONDS, default=d.get(CONF_POLL_SECONDS, DEFAULT_POLL_SECONDS)): vol.Coerce(int),
            vol.Optional(CONF_KEEP_DAYS, default=d.get(CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS)): vol.Coerce(int),

            # advanced, but still one slot only
            vol.Optional(CONF_CHANNEL_INDEX, default=d.get(CONF_CHANNEL_INDEX, DEFAULT_CHANNEL_INDEX)): vol.Coerce(int),

            vol.Optional(CONF_PLUG_ENABLED, default=d.get(CONF_PLUG_ENABLED, False)): bool,
            vol.Optional(CONF_PLUG_HOST, default=d.get(CONF_PLUG_HOST, "")): str,
            vol.Optional(CONF_PLUG_ID, default=d.get(CONF_PLUG_ID, 0)): vol.Coerce(int),

            vol.Optional(CONF_PLUG_USER, default=d.get(CONF_PLUG_USER, "")): str,
            vol.Optional(CONF_PLUG_PASS, default=d.get(CONF_PLUG_PASS, "")): str,

            vol.Optional(CONF_THRESHOLD_P1, default=d.get(CONF_THRESHOLD_P1, DEFAULT_THRESHOLD)): vol.Coerce(float),
            vol.Optional(CONF_THRESHOLD_P2, default=d.get(CONF_THRESHOLD_P2, DEFAULT_THRESHOLD)): vol.Coerce(float),

            vol.Optional(CONF_ML_PER_SEC, default=d.get(CONF_ML_PER_SEC, DEFAULT_ML_PER_SEC)): vol.Coerce(float),
            vol.Optional(CONF_USE_SECONDS, default=d.get(CONF_USE_SECONDS, False)): bool,
            vol.Optional(CONF_PUMP_ML, default=d.get(CONF_PUMP_ML, DEFAULT_PUMP_ML)): vol.Coerce(float),
            vol.Optional(CONF_PUMP_SECONDS, default=d.get(CONF_PUMP_SECONDS, DEFAULT_PUMP_SECONDS)): vol.Coerce(int),

            vol.Optional(CONF_PLANT_INTERVAL_MIN, default=d.get(CONF_PLANT_INTERVAL_MIN, DEFAULT_PLANT_INTERVAL_MIN)): vol.Coerce(int),
            vol.Optional(CONF_CHECK_ONLY_IN_PLANT_TIMES, default=d.get(CONF_CHECK_ONLY_IN_PLANT_TIMES, True)): bool,

            vol.Optional(CONF_P1_START_H, default=d.get(CONF_P1_START_H, 0)): vol.Coerce(int),
            vol.Optional(CONF_P1_START_M, default=d.get(CONF_P1_START_M, 0)): vol.Coerce(int),
            vol.Optional(CONF_P1_END_H, default=d.get(CONF_P1_END_H, 0)): vol.Coerce(int),
            vol.Optional(CONF_P1_END_M, default=d.get(CONF_P1_END_M, 0)): vol.Coerce(int),

            vol.Optional(CONF_P2_START_H, default=d.get(CONF_P2_START_H, 0)): vol.Coerce(int),
            vol.Optional(CONF_P2_START_M, default=d.get(CONF_P2_START_M, 0)): vol.Coerce(int),
            vol.Optional(CONF_P2_END_H, default=d.get(CONF_P2_END_H, 0)): vol.Coerce(int),
            vol.Optional(CONF_P2_END_M, default=d.get(CONF_P2_END_M, 0)): vol.Coerce(int),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
