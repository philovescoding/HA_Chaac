from __future__ import annotations

import json
import logging
import hashlib
import os
import re
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from yarl import URL

LOGGER = logging.getLogger(__name__)
def _parse_digest_challenge(h: str) -> dict[str, str]:
    if not h:
        return {}
    s = h.strip()
    if s.lower().startswith("digest "):
        s = s[7:]
    out: dict[str, str] = {}
    for m in re.finditer(r'(\w+)=(?:"([^"]*)"|([^,]*))(?:,\s*)?', s):
        k = m.group(1)
        v = m.group(2) if m.group(2) is not None else (m.group(3) or "")
        out[k] = v.strip()
    return out

def _hash_hex(algo: str, data: bytes) -> str:
    a = (algo or "MD5").upper()
    if a in ("SHA-256", "SHA256"):
        return hashlib.sha256(data).hexdigest()
    return hashlib.md5(data).hexdigest()

def _digest_authorization(*, username: str, password: str, method: str, url: str, challenge: dict[str, str], nc: int, cnonce: str) -> str:
    realm = challenge.get("realm", "")
    nonce = challenge.get("nonce", "")
    qop = (challenge.get("qop", "auth") or "auth").split(",")[0].strip()
    algo = challenge.get("algorithm", "SHA-256")
    opaque = challenge.get("opaque", "")

    uri = URL(url).raw_path_qs  # includes query string

    ha1 = _hash_hex(algo, f"{username}:{realm}:{password}".encode("utf-8"))
    ha2 = _hash_hex(algo, f"{method}:{uri}".encode("utf-8"))

    nc_str = f"{nc:08x}"
    response = _hash_hex(algo, f"{ha1}:{nonce}:{nc_str}:{cnonce}:{qop}:{ha2}".encode("utf-8"))

    parts = [
        f'Digest username="{username.replace(chr(34), "")}"',
        f'realm="{realm.replace(chr(34), "")}"',
        f'nonce="{nonce.replace(chr(34), "")}"',
        f'uri="{uri.replace(chr(34), "")}"',
        f'response="{response}"',
        f'algorithm={algo}',
        f'qop={qop}',
        f'nc={nc_str}',
        f'cnonce="{cnonce.replace(chr(34), "")}"',
    ]
    if opaque:
        parts.append(f'opaque="{opaque.replace(chr(34), "")}"')
    return ", ".join(parts)


def _ssl_kw(url: str):
    # Shelly https is often self-signed; behave like ESP (insecure).
    return False if (url or "").startswith("https://") else None

async def _request_shelly(session: aiohttp.ClientSession, method: str, url: str, *, json_body=None, username: str = "", password: str = "", timeout_s: int = 5) -> tuple[int, str]:
    # 1) try without auth
    try:
        async with session.request(method, url, json=json_body, timeout=aiohttp.ClientTimeout(total=timeout_s), ssl=_ssl_kw(url)) as resp:
            txt = await resp.text()
            if resp.status != 401 or not username or not password:
                return resp.status, txt
            www = resp.headers.get("WWW-Authenticate", "")
    except Exception as e:
        return 0, str(e)

    # 2) digest retry
    chal = _parse_digest_challenge(www)
    if not chal.get("nonce"):
        return 401, txt

    nc = 1
    cnonce = _hash_hex("MD5", os.urandom(16))
    auth = _digest_authorization(
        username=username,
        password=password,
        method=method.upper(),
        url=url,
        challenge=chal,
        nc=nc,
        cnonce=cnonce,
    )

    try:
        async with session.request(
            method,
            url,
            json=json_body,
            headers={"Authorization": auth},
            timeout=aiohttp.ClientTimeout(total=timeout_s),
        ) as resp2:
            txt2 = await resp2.text()
            return resp2.status, txt2
    except Exception as e:
        return 0, str(e)


from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .api import SenseCapCloudClient
from .const import MEASUREMENT_IDS


def _is_time_in_window_minutes(start_min: int, end_min: int, now_min: int) -> bool:
    start_min = max(0, min(1439, int(start_min)))
    end_min = max(0, min(1439, int(end_min)))
    now_min = max(0, min(1439, int(now_min)))
    if start_min == end_min:
        return False
    if start_min < end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min  # wrap


async def _http_get_ok(session: aiohttp.ClientSession, url: str, timeout_s: int = 3) -> bool:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_s)) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _normalize_host_url(host: str) -> str:
    h = (host or "").strip()
    if not h:
        return ""
    # common misconfig: http://...:443  -> https://...
    if h.startswith("http://") and ":443" in h:
        h = h.replace("http://", "https://", 1).replace(":443", "")
    if h.startswith("http://") or h.startswith("https://"):
        return h.rstrip("/")
    return ("http://" + h).rstrip("/")


async def shelly_set_switch(session: aiohttp.ClientSession, host: str, plug_id: int, on: bool, user: str = "", password: str = "") -> bool:
    base = _normalize_host_url(host)
    if not base:
        return False

    plug_id_i = int(plug_id)

    # 1) EXACTLY like your ESP SenseCap controller: Gen2/Gen3 RPC via HTTP GET
    url_get = f"{base}/rpc/Switch.Set?id={plug_id_i}&on={'true' if on else 'false'}"
    st, body = await _request_shelly(session, "GET", url_get, username=(user or ""), password=(password or ""), timeout_s=5)
    if 200 <= st < 300:
        return True
    if st:
        LOGGER.debug("Shelly RPC GET failed: %s status=%s body=%s", url_get, st, (body or "").replace("\n", " ")[:160])

    # 2) Additional: RPC POST JSON (some firmwares prefer it)
    url_post = f"{base}/rpc/Switch.Set"
    st, body = await _request_shelly(
        session,
        "POST",
        url_post,
        json_body={"id": plug_id_i, "on": bool(on)},
        username=(user or ""),
        password=(password or ""),
        timeout_s=5,
    )
    if 200 <= st < 300:
        return True
    if st:
        LOGGER.debug("Shelly RPC POST failed: %s status=%s body=%s", url_post, st, (body or "").replace("\n", " ")[:160])

    # 3) Gen1 legacy fallback
    url1 = f"{base}/relay/{plug_id_i}?turn={'on' if on else 'off'}"
    st, body = await _request_shelly(session, "GET", url1, username=(user or ""), password=(password or ""), timeout_s=5)
    if 200 <= st < 300:
        return True
    if st:
        LOGGER.debug("Shelly Gen1 GET failed: %s status=%s body=%s", url1, st, (body or "").replace("\n", " ")[:160])

    LOGGER.debug("Shelly switch failed host=%s id=%s on=%s", base, plug_id_i, on)
    return False

    plug_id_i = int(plug_id)

    # Gen2 RPC (FIRST) — prefer POST JSON (works reliably on Gen2)
    url2 = f"{base}/rpc/Switch.Set"
    try:
        async with session.post(
            url2,
            json={"id": plug_id_i, "on": bool(on)},
            timeout=aiohttp.ClientTimeout(total=4),
        ) as resp:
            if 200 <= resp.status < 300:
                return True
            body = (await resp.text()).replace("\n", " ").replace("\r", " ")[:160]
            LOGGER.debug("Shelly Gen2 POST failed: %s status=%s body=%s", url2, resp.status, body)
    except Exception as e:
        LOGGER.debug("Shelly Gen2 POST error: %s err=%s", url2, e)

    # Gen2 RPC fallback via querystring GET (some firmwares accept it)
    url2g = f"{base}/rpc/Switch.Set?id={plug_id_i}&on={'true' if on else 'false'}"
    if await _http_get_ok(session, url2g):
        return True

    # Gen1 legacy fallback
    url1 = f"{base}/relay/{plug_id_i}?turn={'on' if on else 'off'}"
    if await _http_get_ok(session, url1):
        return True

    LOGGER.debug("Shelly switch failed (Gen2+Gen1) host=%s id=%s on=%s", base, plug_id_i, on)
    return False


    # Gen2 RPC (first) – like SenseCapESP.cpp
    url2 = f"{base}/rpc/Switch.Set?id={int(plug_id)}&on={'true' if on else 'false'}"
    if await _http_get_ok(session, url2):
        return True

    # Gen1 legacy fallback
    url1 = f"{base}/relay/{int(plug_id)}?turn={'on' if on else 'off'}"
    if await _http_get_ok(session, url1):
        return True

    return False


@dataclass
class PumpEvent:
    ts_ms: int
    ml: float
    sec: int
    phase: str  # "P1"|"P2"
    mode: str   # "auto"|"manual"


class _JsonlFiles:
    def __init__(self, hass: HomeAssistant, base_dir_parts: list[str], keep_days: int) -> None:
        self.hass = hass
        self.keep_days = max(2, min(7, int(keep_days)))
        self.base_dir = hass.config.path(*base_dir_parts)

    def _ensure_dirs(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)

    async def async_cleanup(self, match_suffix: str, parse_stem) -> None:
        self._ensure_dirs()
        cutoff = dt_util.as_local(dt_util.utcnow()) - timedelta(days=self.keep_days)

        def _cleanup():
            for root, _dirs, files in os.walk(self.base_dir):
                for name in files:
                    if not name.endswith(match_suffix):
                        continue
                    stem = name.replace(match_suffix, "")
                    dt_file = parse_stem(stem)
                    if dt_file is None:
                        continue
                    if dt_file < cutoff.replace(tzinfo=None):
                        try:
                            os.remove(os.path.join(root, name))
                        except Exception:
                            pass

        await self.hass.async_add_executor_job(_cleanup)


class PumpLogger(_JsonlFiles):
    def __init__(self, hass: HomeAssistant, keep_days: int) -> None:
        super().__init__(hass, ["chaac_vwc_logs", "pumps"], keep_days)

    def _file_for(self, dt_local: datetime) -> str:
        return os.path.join(self.base_dir, f"{dt_local.strftime('%Y%m%d')}_pumps.jsonl")

    async def async_append(self, ev: PumpEvent) -> None:
        self._ensure_dirs()
        dt_local = dt_util.as_local(datetime.fromtimestamp(ev.ts_ms / 1000, tz=dt_util.UTC))
        line = json.dumps({"ts": ev.ts_ms, "ml": ev.ml, "sec": ev.sec, "phase": ev.phase, "mode": ev.mode}, separators=(",", ":"))
        path = self._file_for(dt_local)

        def _write():
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        await self.hass.async_add_executor_job(_write)

        def _parse(stem: str):
            try:
                return datetime.strptime(stem, "%Y%m%d")
            except Exception:
                return None

        await self.async_cleanup("_pumps.jsonl", _parse)

    async def async_sum_ml(self, days: int) -> float:
        self._ensure_dirs()
        days = max(1, int(days))
        now_local = dt_util.as_local(dt_util.utcnow()).replace(hour=0, minute=0, second=0, microsecond=0)
        start = now_local - timedelta(days=days - 1)
        files = [self._file_for(start + timedelta(days=i)) for i in range((now_local - start).days + 1)]

        def _sum():
            total = 0.0
            for p in files:
                if not os.path.exists(p):
                    continue
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                obj = json.loads(line)
                                total += float(obj.get("ml", 0.0) or 0.0)
                            except Exception:
                                continue
                except Exception:
                    continue
            return total

        return float(await self.hass.async_add_executor_job(_sum))


class SampleLogger(_JsonlFiles):
    def __init__(self, hass: HomeAssistant, keep_days: int) -> None:
        super().__init__(hass, ["chaac_vwc_logs", "samples"], keep_days)

    def _file_for(self, dt_local: datetime) -> str:
        return os.path.join(self.base_dir, f"{dt_local.strftime('%Y%m%d_%H')}_sensecap.jsonl")

    async def async_append(self, sample: dict[str, Any]) -> None:
        self._ensure_dirs()
        ts_ms = int(sample.get("t", 0) or 0)
        dt_local = dt_util.as_local(datetime.fromtimestamp(ts_ms / 1000, tz=dt_util.UTC))
        line = json.dumps(sample, separators=(",", ":"))
        path = self._file_for(dt_local)

        def _write():
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        await self.hass.async_add_executor_job(_write)

        def _parse(stem: str):
            try:
                return datetime.strptime(stem, "%Y%m%d_%H")
            except Exception:
                return None

        await self.async_cleanup("_sensecap.jsonl", _parse)


class SenseCapVwcControllerSingle:
    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        station: str,
        access_id: str,
        access_key: str,
        poll_seconds: int,
        keep_days: int,
        enabled: bool,
        cfg: dict[str, Any],
        persisted_state,
    ) -> None:
        self.hass = hass
        self.session = session
        self.station = station
        self.sensor_source = str(cfg.get('sensorSource', 'sensecap_cloud'))
        self.client = None
        if self.sensor_source != 'ha_entity':
            self.client = SenseCapCloudClient(session=session, station=station, access_id=access_id, access_key=access_key)

        self.poll_seconds = max(10, int(poll_seconds))
        self.enabled = bool(enabled)
        self.cfg = cfg
        self.persisted_state = persisted_state

        self.sample_logger = SampleLogger(hass, keep_days)
        self.pump_logger = PumpLogger(hass, keep_days)
        self._pending_off: Any = None

        self._totals_dirty = True
        self.pump_totals: dict[str, Any] = {"1d": 0.0, "7d": 0.0}

    async def schedule_off(self, host: str, plug_id: int, seconds: int) -> None:
        seconds = max(1, int(seconds))
        if callable(self._pending_off):
            self._pending_off()
            self._pending_off = None

        async def _do_off(_now):
            await shelly_set_switch(self.session, host, plug_id, False, user=str(self.cfg.get('plugUser','') or ''), password=str(self.cfg.get('plugPass','') or ''))
            self._pending_off = None

        self._pending_off = async_call_later(self.hass, seconds, _do_off)

    async def _update_totals_if_dirty(self) -> None:
        if not self._totals_dirty:
            return
        self.pump_totals["1d"] = float(await self.pump_logger.async_sum_ml(1))
        self.pump_totals["7d"] = float(await self.pump_logger.async_sum_ml(7))
        self._totals_dirty = False

    async def _pump_auto_if_needed(self, sample: dict[str, Any]) -> bool:
        cfg = self.cfg
        if not cfg.get("plugEnabled"):
            return False
        host = (cfg.get("plugHost") or "").strip()
        if not host:
            return False

        now_utc = dt_util.utcnow()
        now_local = dt_util.as_local(now_utc)
        now_min = now_local.hour * 60 + now_local.minute
        now_ms = int(now_utc.timestamp() * 1000)

        p1s = int(cfg.get("p1StartHour", 0)) * 60 + int(cfg.get("p1StartMinute", 0))
        p1e = int(cfg.get("p1EndHour", 0)) * 60 + int(cfg.get("p1EndMinute", 0))
        p2s = int(cfg.get("p2StartHour", 0)) * 60 + int(cfg.get("p2StartMinute", 0))
        p2e = int(cfg.get("p2EndHour", 0)) * 60 + int(cfg.get("p2EndMinute", 0))

        in_p1 = _is_time_in_window_minutes(p1s, p1e, now_min)
        in_p2 = _is_time_in_window_minutes(p2s, p2e, now_min)
        in_any = in_p1 or in_p2
        if cfg.get("checkOnlyInPlantTimes", True) and not in_any:
            # only log if it WOULD water (moisture low) but is outside time window
            vwc_dbg = sample.get("moist")
            try:
                if isinstance(vwc_dbg, (int, float)) and float(vwc_dbg) <= float(cfg.get("thresholdP1", 35.0) or 35.0) and float(vwc_dbg) <= float(cfg.get("thresholdP2", 35.0) or 35.0):
                    LOGGER.debug("AutoDecision: moisture low but outside P1/P2 window (nowMin=%s)", now_min)
            except Exception:
                pass
            return False

        plant_interval = int(cfg.get("plantIntervalMinutes", 5) or 0)
        if plant_interval > 0 and self.persisted_state.last_pump_ts_ms > 0:
            if now_ms - self.persisted_state.last_pump_ts_ms < plant_interval * 60_000:
                LOGGER.debug("AutoDecision: interval blocked (last_pump=%sms ago, interval=%smin)", (now_ms - self.persisted_state.last_pump_ts_ms), plant_interval)
                return False

        vwc = sample.get("moist")
        if vwc is None or not isinstance(vwc, (int, float)):
            return False

        active_p2 = bool(in_p2)
        thr = float(cfg.get("thresholdP2" if active_p2 else "thresholdP1", 35.0) or 0.0)
        if float(vwc) > thr:
            return False

        ml_per_sec = max(0.1, float(cfg.get("mlPerSec", 50.0) or 0.1))
        use_seconds = bool(cfg.get("useSeconds", False))

        if use_seconds:
            seconds = max(1, int(cfg.get("pumpSeconds", 5) or 1))
            ml = seconds * ml_per_sec
        else:
            ml = max(0.0, float(cfg.get("pumpMl", 200.0) or 0.0))
            seconds = max(1, int(math.ceil(ml / ml_per_sec)))

        plug_id = int(cfg.get("plugId", 0) or 0)

        ok = await shelly_set_switch(self.session, host, plug_id, True, user=str(cfg.get('plugUser','') or ''), password=str(cfg.get('plugPass','') or ''))
        if not ok:
            return False

        await self.schedule_off(host, plug_id, seconds)

        ev = PumpEvent(ts_ms=now_ms, ml=float(ml), sec=int(seconds), phase=("P2" if active_p2 else "P1"), mode="auto")
        await self.pump_logger.async_append(ev)
        self._totals_dirty = True

        self.persisted_state.last_pump_ts_ms = now_ms
        return True


async def on_external_sample(self, sample: dict[str, Any]) -> None:
    """Accept external sample (e.g. from HA entity) and run decision."""
    try:
        self.persisted_state.last_sample = dict(sample)
    except Exception:
        pass
    try:
        await self.sample_logger.async_append(sample)
    except Exception:
        pass
    try:
        await self._pump_auto_if_needed(sample)
    except Exception:
        pass
    try:
        await self._update_totals_if_dirty()
    except Exception:
        pass

    async def poll_once(self) -> dict[str, Any]:
        cfg = self.cfg

        # HA entity mode: no cloud fetch, just return last sample + totals
        if getattr(self, 'sensor_source', 'sensecap_cloud') == 'ha_entity':
            await self._update_totals_if_dirty()
            last = dict(getattr(self.persisted_state, 'last_sample', {}) or {})
            return {
                'enabled': True,
                'station': 'ha_entity',
                'pollSeconds': self.poll_seconds,
                'epoch': int(dt_util.utcnow().timestamp()),
                'slot': {'status': 'ok', 'last': last, 'pumpTotals': self.pump_totals},
            }

        if not self.enabled:
            await self._update_totals_if_dirty()
            return {
                "enabled": False,
                "station": (self.client.station if self.client else getattr(self, "station", "")),
                "pollSeconds": self.poll_seconds,
                "epoch": int(dt_util.utcnow().timestamp()),
                "slot": {"status": "disabled", "last": {}, "pumpTotals": self.pump_totals},
            }

        device_eui = (cfg.get("deviceEui") or "").strip()
        if not device_eui:
            await self._update_totals_if_dirty()
            return {
                "enabled": True,
                "station": (self.client.station if self.client else getattr(self, "station", "")),
                "pollSeconds": self.poll_seconds,
                "epoch": int(dt_util.utcnow().timestamp()),
                "slot": {"status": "missing deviceEui", "last": {}, "pumpTotals": self.pump_totals},
            }

        channel_index = int(cfg.get("channelIndex", 1) or 1)

        results = {}
        errs = []
        for key, mid in MEASUREMENT_IDS.items():
            fr = await self.client.fetch_latest(device_eui, channel_index, mid)
            results[key] = fr
            if fr.err:
                errs.append(fr.err)

        if not any(fr.ok for fr in results.values()):
            err = errs[0] if errs else "no data"
            await self._update_totals_if_dirty()
            return {
                "enabled": True,
                "station": (self.client.station if self.client else getattr(self, "station", "")),
                "pollSeconds": self.poll_seconds,
                "epoch": int(dt_util.utcnow().timestamp()),
                "slot": {"status": err, "last": {}, "pumpTotals": self.pump_totals},
            }

        ts = 0
        for fr in results.values():
            if fr.ok:
                ts = max(ts, int(fr.ts_ms))

        last = {
            "t": ts,
            "temp": results["soilTemp"].value if results["soilTemp"].ok else None,
            "moist": results["soilMoist"].value if results["soilMoist"].ok else None,
            "ec": results["soilEc"].value if results["soilEc"].ok else None,
            "wec": results["waterEc"].value if results["waterEc"].ok else None,
            "eps": results["epsilon"].value if results["epsilon"].ok else None,
            "ch": channel_index,
        }

        if ts > 0 and ts > self.persisted_state.last_written_ts_ms:
            self.persisted_state.last_written_ts_ms = ts
            self.persisted_state.last_sample = dict(last)
            await self.sample_logger.async_append(last)
            await self._pump_auto_if_needed(last)

        await self._update_totals_if_dirty()

        return {
            "enabled": True,
            "station": (self.client.station if self.client else getattr(self, "station", "")),
            "pollSeconds": self.poll_seconds,
            "epoch": int(dt_util.utcnow().timestamp()),
            "slot": {"status": "ok", "last": last, "pumpTotals": self.pump_totals},
        }
