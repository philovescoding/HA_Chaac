from __future__ import annotations

DOMAIN = "chaac_vwc"

CONF_ENABLED = "enabled"
CONF_STATION = "station"           # "global" | "china"
CONF_ACCESS_ID = "accessId"
CONF_ACCESS_KEY = "accessKey"
CONF_POLL_SECONDS = "pollSeconds"
CONF_KEEP_DAYS = "keepDays"

CONF_DEVICE_EUI = "deviceEui"
CONF_CHANNEL_INDEX = "channelIndex"

CONF_PLUG_ENABLED = "plugEnabled"
CONF_PLUG_HOST = "plugHost"
CONF_PLUG_ID = "plugId"
CONF_PLUG_USER = "plugUser"
CONF_PLUG_PASS = "plugPass"

CONF_SENSOR_SOURCE = "sensorSource"
CONF_MOIST_ENTITY = "moistEntity"
CONF_TEMP_ENTITY = "tempEntity"
CONF_EC_ENTITY = "ecEntity"

CONF_THRESHOLD_P1 = "thresholdP1"
CONF_THRESHOLD_P2 = "thresholdP2"

CONF_ML_PER_SEC = "mlPerSec"
CONF_USE_SECONDS = "useSeconds"
CONF_PUMP_ML = "pumpMl"
CONF_PUMP_SECONDS = "pumpSeconds"

CONF_PLANT_INTERVAL_MIN = "plantIntervalMinutes"
CONF_CHECK_ONLY_IN_PLANT_TIMES = "checkOnlyInPlantTimes"

CONF_P1_START_H = "p1StartHour"
CONF_P1_START_M = "p1StartMinute"
CONF_P1_END_H = "p1EndHour"
CONF_P1_END_M = "p1EndMinute"
CONF_P2_START_H = "p2StartHour"
CONF_P2_START_M = "p2StartMinute"
CONF_P2_END_H = "p2EndHour"
CONF_P2_END_M = "p2EndMinute"

DEFAULT_ENABLED = True
DEFAULT_STATION = "global"
DEFAULT_POLL_SECONDS = 60
DEFAULT_KEEP_DAYS = 2

DEFAULT_CHANNEL_INDEX = 1
DEFAULT_THRESHOLD = 35.0
DEFAULT_ML_PER_SEC = 50.0
DEFAULT_PUMP_ML = 200.0
DEFAULT_PUMP_SECONDS = 5
DEFAULT_PLANT_INTERVAL_MIN = 5

# SenseCAP measurement IDs (match SenseCapESP.h)
MEASUREMENT_IDS = {
    "soilTemp": 4102,
    "soilMoist": 4103,
    "soilEc": 4108,
    "waterEc": 4204,
    "epsilon": 4205,
}

METRICS = {
    "temp":  {"name": "Soil Temperature", "unit": "°C",   "device_class": "temperature", "state_class": "measurement"},
    "moist": {"name": "Soil Moisture",    "unit": "%",    "device_class": None,          "state_class": "measurement"},
    "ec":    {"name": "Soil EC",          "unit": "dS/m", "device_class": None,          "state_class": "measurement"},
    "wec":   {"name": "Water EC",         "unit": "dS/m", "device_class": None,          "state_class": "measurement"},
    "eps":   {"name": "Epsilon",          "unit": None,   "device_class": None,          "state_class": "measurement"},
}

def default_cfg() -> dict:
    return {
        CONF_ENABLED: DEFAULT_ENABLED,
        CONF_STATION: DEFAULT_STATION,
        CONF_ACCESS_ID: "",
        CONF_ACCESS_KEY: "",
        CONF_POLL_SECONDS: DEFAULT_POLL_SECONDS,
        CONF_SENSOR_SOURCE: "sensecap_cloud",
        CONF_MOIST_ENTITY: "",
        CONF_TEMP_ENTITY: "",
        CONF_EC_ENTITY: "",
        CONF_KEEP_DAYS: DEFAULT_KEEP_DAYS,

        CONF_DEVICE_EUI: "",
        CONF_CHANNEL_INDEX: DEFAULT_CHANNEL_INDEX,

        CONF_PLUG_ENABLED: False,
        CONF_PLUG_HOST: "",
        CONF_PLUG_ID: 0,
        CONF_PLUG_USER: "",
        CONF_PLUG_PASS: "",

        CONF_THRESHOLD_P1: DEFAULT_THRESHOLD,
        CONF_THRESHOLD_P2: DEFAULT_THRESHOLD,

        CONF_ML_PER_SEC: DEFAULT_ML_PER_SEC,
        CONF_USE_SECONDS: False,
        CONF_PUMP_ML: DEFAULT_PUMP_ML,
        CONF_PUMP_SECONDS: DEFAULT_PUMP_SECONDS,

        CONF_PLANT_INTERVAL_MIN: DEFAULT_PLANT_INTERVAL_MIN,
        CONF_CHECK_ONLY_IN_PLANT_TIMES: True,

        CONF_P1_START_H: 0, CONF_P1_START_M: 0,
        CONF_P1_END_H: 0,   CONF_P1_END_M: 0,
        CONF_P2_START_H: 0, CONF_P2_START_M: 0,
        CONF_P2_END_H: 0,   CONF_P2_END_M: 0,
    }
