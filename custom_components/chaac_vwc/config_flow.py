from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

try:
    from .const import DOMAIN, default_cfg
except Exception:
    DOMAIN = "chaac_vwc"
    def default_cfg() -> dict:
        return {}

# Config keys (match const.py)
CONF_SENSOR_SOURCE = "sensorSource"
CONF_MOIST_ENTITY  = "moistEntity"
CONF_TEMP_ENTITY   = "tempEntity"
CONF_EC_ENTITY     = "ecEntity"

CONF_ENABLED        = "enabled"
CONF_STATION        = "station"
CONF_ACCESS_ID      = "accessId"
CONF_ACCESS_KEY     = "accessKey"
CONF_DEVICE_EUI     = "deviceEui"
CONF_POLL_SECONDS   = "pollSeconds"
CONF_KEEP_DAYS      = "keepDays"
CONF_CHANNEL_INDEX  = "channelIndex"

CONF_PLUG_ENABLED   = "plugEnabled"
CONF_PLUG_HOST      = "plugHost"
CONF_PLUG_ID        = "plugId"
CONF_PLUG_USER      = "plugUser"
CONF_PLUG_PASS      = "plugPass"

CONF_THRESHOLD_P1   = "thresholdP1"
CONF_THRESHOLD_P2   = "thresholdP2"

CONF_ML_PER_SEC     = "mlPerSec"
CONF_USE_SECONDS    = "useSeconds"
CONF_PUMP_ML        = "pumpMl"
CONF_PUMP_SECONDS   = "pumpSeconds"

CONF_PLANT_INTERVAL_MIN       = "plantIntervalMinutes"
CONF_CHECK_ONLY_IN_PLANT_TIMES = "checkOnlyInPlantTimes"

CONF_P1_START_H = "p1StartHour"
CONF_P1_START_M = "p1StartMinute"
CONF_P1_END_H   = "p1EndHour"
CONF_P1_END_M   = "p1EndMinute"
CONF_P2_START_H = "p2StartHour"
CONF_P2_START_M = "p2StartMinute"
CONF_P2_END_H   = "p2EndHour"
CONF_P2_END_M   = "p2EndMinute"

# Defaults (match const.py)
DEFAULT_STATION = "global"
DEFAULT_POLL_SECONDS = 60
DEFAULT_KEEP_DAYS = 2
DEFAULT_CHANNEL_INDEX = 1
DEFAULT_THRESHOLD = 35.0
DEFAULT_ML_PER_SEC = 50.0
DEFAULT_PUMP_ML = 200.0
DEFAULT_PUMP_SECONDS = 5
DEFAULT_PLANT_INTERVAL_MIN = 5


def _clamp_int(v, lo, hi, d):
    try:
        x = int(v)
    except Exception:
        x = int(d)
    return max(lo, min(hi, x))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 6

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            src = str(user_input.get(CONF_SENSOR_SOURCE, "sensecap_cloud"))
            self._cfg = default_cfg()
            self._cfg[CONF_SENSOR_SOURCE] = src
            if src == "ha_entity":
                return await self.async_step_ha_entity()
            return await self.async_step_sensecap()

        schema = vol.Schema({
            vol.Required(CONF_SENSOR_SOURCE, default="sensecap_cloud"): vol.In({
                "sensecap_cloud": "SenseCAP Cloud (Access ID/Key + Device EUI)",
                "ha_entity": "Home Assistant Entity (ESPHome/Modbus/etc.)",
            }),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors={})

    async def async_step_sensecap(self, user_input=None):
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
                station = str(user_input.get(CONF_STATION, DEFAULT_STATION))
                await self.async_set_unique_id(f"{DOMAIN}:{station}:{access_id[:8]}:{device_eui[-6:]}")
                self._abort_if_unique_id_configured()

                cfg = self._cfg if hasattr(self, "_cfg") else default_cfg()
                cfg.update({
                    CONF_ENABLED: bool(user_input.get(CONF_ENABLED, True)),
                    CONF_STATION: station,
                    CONF_ACCESS_ID: access_id,
                    CONF_ACCESS_KEY: access_key,
                    CONF_DEVICE_EUI: device_eui,
                    CONF_POLL_SECONDS: max(10, int(user_input.get(CONF_POLL_SECONDS, DEFAULT_POLL_SECONDS))),
                    CONF_KEEP_DAYS: _clamp_int(user_input.get(CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS), 2, 7, DEFAULT_KEEP_DAYS),

                    CONF_CHANNEL_INDEX: _clamp_int(user_input.get(CONF_CHANNEL_INDEX, DEFAULT_CHANNEL_INDEX), 0, 7, DEFAULT_CHANNEL_INDEX),

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

            vol.Optional(CONF_CHANNEL_INDEX, default=DEFAULT_CHANNEL_INDEX): vol.Coerce(int),

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
        return self.async_show_form(step_id="sensecap", data_schema=schema, errors=errors)

    async def async_step_ha_entity(self, user_input=None):
        errors = {}
        if user_input is not None:
            moist = str(user_input.get(CONF_MOIST_ENTITY, "")).strip()
            if not moist:
                errors["base"] = "missing_moist"
            else:
                await self.async_set_unique_id(f"{DOMAIN}:ha:{moist}")
                self._abort_if_unique_id_configured()

                cfg = self._cfg if hasattr(self, "_cfg") else default_cfg()
                cfg.update({
                    CONF_ENABLED: True,
                    CONF_STATION: DEFAULT_STATION,
                    CONF_ACCESS_ID: "",
                    CONF_ACCESS_KEY: "",
                    CONF_DEVICE_EUI: "",

                    CONF_MOIST_ENTITY: moist,
                    CONF_TEMP_ENTITY: str(user_input.get(CONF_TEMP_ENTITY, "") or "").strip(),
                    CONF_EC_ENTITY: str(user_input.get(CONF_EC_ENTITY, "") or "").strip(),

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
                return self.async_create_entry(title="Chaac VWC (HA Sensor)", data=cfg)

        schema = vol.Schema({
            vol.Required(CONF_MOIST_ENTITY): str,   # e.g. sensor.wcec_s1_watercontent
            vol.Optional(CONF_TEMP_ENTITY, default=""): str,
            vol.Optional(CONF_EC_ENTITY, default=""): str,

            vol.Optional(CONF_POLL_SECONDS, default=DEFAULT_POLL_SECONDS): vol.Coerce(int),
            vol.Optional(CONF_KEEP_DAYS, default=DEFAULT_KEEP_DAYS): vol.Coerce(int),

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
        return self.async_show_form(step_id="ha_entity", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChaacVwcOptionsFlow(config_entry)


class ChaacVwcOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        d = self.config_entry.data
        if user_input is not None:
            new = dict(d)
            for k, v in user_input.items():
                new[k] = v
            self.hass.config_entries.async_update_entry(self.config_entry, data=new)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Optional(CONF_SENSOR_SOURCE, default=d.get(CONF_SENSOR_SOURCE, "sensecap_cloud")): vol.In(
                {"sensecap_cloud": "SenseCAP Cloud", "ha_entity": "Home Assistant Entity"}
            ),
            vol.Optional(CONF_MOIST_ENTITY, default=d.get(CONF_MOIST_ENTITY, "")): str,
            vol.Optional(CONF_TEMP_ENTITY, default=d.get(CONF_TEMP_ENTITY, "")): str,
            vol.Optional(CONF_EC_ENTITY, default=d.get(CONF_EC_ENTITY, "")): str,

            vol.Optional(CONF_STATION, default=d.get(CONF_STATION, DEFAULT_STATION)): vol.In(["global", "china"]),
            vol.Optional(CONF_ACCESS_ID, default=d.get(CONF_ACCESS_ID, "")): str,
            vol.Optional(CONF_ACCESS_KEY, default=d.get(CONF_ACCESS_KEY, "")): str,
            vol.Optional(CONF_DEVICE_EUI, default=d.get(CONF_DEVICE_EUI, "")): str,

            vol.Optional(CONF_POLL_SECONDS, default=d.get(CONF_POLL_SECONDS, DEFAULT_POLL_SECONDS)): vol.Coerce(int),
            vol.Optional(CONF_KEEP_DAYS, default=d.get(CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS)): vol.Coerce(int),

            vol.Optional(CONF_CHANNEL_INDEX, default=d.get(CONF_CHANNEL_INDEX, DEFAULT_CHANNEL_INDEX)): vol.Coerce(int),

            vol.Optional(CONF_PLUG_ENABLED, default=d.get(CONF_PLUG_ENABLED, False)): bool,
            vol.Optional(CONF_PLUG_HOST, default=d.get(CONF_PLUG_HOST, "")): str,
            vol.Optional(CONF_PLUG_ID, default=d.get(CONF_PLUG_ID, 0)): vol.Coerce(int),
            vol.Optional(CONF_PLUG_USER, default=d.get(CONF_PLUG_USER, "")): str,
            vol.Optional(CONF_PLUG_PASS, default=d.get(CONF_PLUG_PASS, "")): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
