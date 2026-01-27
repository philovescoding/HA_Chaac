from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

def _as_int(v: Any, default: int = -1) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return default
            return int(float(s))
        return default
    except Exception:
        return default


def station_base(station: str) -> str:
    if (station or "").lower() == "china":
        return "https://sensecap.seeed.cn"
    return "https://sensecap.seeed.cc"


def _basic_auth_header(access_id: str, access_key: str) -> str:
    token = f"{access_id}:{access_key}".encode("utf-8")
    return "Basic " + base64.b64encode(token).decode("ascii")


def _normalize_base(base: str) -> str:
    base = (base or "").strip().rstrip("/")
    if base.endswith("/openapi"):
        base = base[: -len("/openapi")]
    return base.rstrip("/")


def _to_float_if_numberish(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            fv = float(v)
            return fv if fv == fv else None
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        if not s or s.lower() in ("none", "null", "nan", "n/a", "-", "--"):
            return None
        try:
            fv = float(s)
            return fv if fv == fv else None
        except Exception:
            return None
    if isinstance(v, list):
        for x in v:
            r = _to_float_if_numberish(x)
            if r is not None:
                return r
    if isinstance(v, dict):
        for _, x in v.items():
            r = _to_float_if_numberish(x)
            if r is not None:
                return r
    return None


def _parse_iso_to_ms_utc(iso: str) -> int:
    s = (iso or "").strip()
    if not s:
        return 0
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _normalize_telemetry_time_to_ms(v: Any) -> int:
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    if v is None:
        return now_ms

    if isinstance(v, str):
        ss = v.strip()
        if "T" in ss and "-" in ss:
            t = _parse_iso_to_ms_utc(ss)
            return t or now_ms
        try:
            d = float(ss)
            t = int(d)
        except Exception:
            return now_ms
        if t < 100_000_000_000:
            t *= 1000
        if t < 1_514_764_800_000:
            return now_ms
        return t

    if isinstance(v, (int, float)):
        t = int(v)
        if t < 100_000_000_000:
            t *= 1000
        if t < 1_514_764_800_000:
            return now_ms
        return t

    return now_ms


@dataclass
class FetchResult:
    ok: bool
    value: Optional[float]
    ts_ms: int
    err: str = ""


@dataclass
class SenseCapCloudClient:
    session: aiohttp.ClientSession
    station: str
    access_id: str
    access_key: str

    async def _get_json(self, url: str, timeout_s: int = 12) -> tuple[int, Any, str]:
        headers = {"Authorization": _basic_auth_header(self.access_id, self.access_key)}
        try:
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_s)) as resp:
                text = await resp.text()
                try:
                    return resp.status, json.loads(text), text
                except Exception:
                    return resp.status, None, text
        except Exception as e:
            return 0, None, str(e)

    async def fetch_latest_openapi(self, device_eui: str, channel_index: int, measurement_id: int) -> FetchResult:
        if not device_eui:
            return FetchResult(False, None, 0, "no eui")

        base = _normalize_base(station_base(self.station))
        url = (
            f"{base}/openapi/view_latest_telemetry_data"
            f"?device_eui={device_eui}&measurement_id={measurement_id}&channel_index={channel_index}"
        )
        http, doc, raw = await self._get_json(url)

        # Some deployments respond without /openapi prefix; try fallback on 400/404.
        if http in (400, 404):
            alt = (
                f"{base}/view_latest_telemetry_data"
                f"?device_eui={device_eui}&measurement_id={measurement_id}&channel_index={channel_index}"
            )
            http2, doc2, raw2 = await self._get_json(alt)
            if http2:
                http, doc, raw = http2, doc2, raw2

        if http != 200 or not isinstance(doc, dict):
            snip = (raw or "").replace("\n", " ").replace("\r", " ").strip()[:140]
            return FetchResult(False, None, 0, f"openapi http {http} {snip}".strip())

        code = _as_int(doc.get("code", -1), -1)
        if code != 0:
            msg = str(doc.get("msg", "")).replace("\n", " ").replace("\r", " ").strip()[:140]
            return FetchResult(False, None, 0, f"openapi code {code} msg={msg}".strip())

        data = doc.get("data")
        data_obj = None
        if isinstance(data, dict):
            data_obj = data
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            data_obj = data[0]

        if not isinstance(data_obj, dict):
            return FetchResult(False, None, 0, "")

        points = data_obj.get("points") or []
        if not points or not isinstance(points, list) or not isinstance(points[0], dict):
            return FetchResult(False, None, 0, "")

        p0 = points[0]
        val = _to_float_if_numberish(p0.get("measurement_value"))
        if val is None:
            return FetchResult(False, None, 0, "")

        ts_ms = _normalize_telemetry_time_to_ms(p0.get("time"))
        return FetchResult(True, val, ts_ms, "")

    async def fetch_latest_v1(self, device_eui: str, channel_index: int, measurement_id: int) -> FetchResult:
        base = _normalize_base(station_base(self.station))
        url = f"{base}/1.0/devices/data/{device_eui}/latest?measure_id={measurement_id}&channel={channel_index}"

        http, doc, raw = await self._get_json(url)
        if http != 200 or not isinstance(doc, dict):
            snip = (raw or "").replace("\n", " ").replace("\r", " ").strip()[:140]
            return FetchResult(False, None, 0, f"v1 http {http} {snip}".strip())

        if _as_int(doc.get("code", -1), -1) != 0:
            return FetchResult(False, None, 0, f"SenseCAP API error (v1): code={doc.get('code')}")

        data = doc.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return FetchResult(False, None, 0, "No data")

        points = data[0].get("points")
        if not isinstance(points, list) or not points or not isinstance(points[0], dict):
            return FetchResult(False, None, 0, "No points")

        p0 = points[0]
        val = _to_float_if_numberish(p0.get("value"))
        if val is None:
            return FetchResult(False, None, 0, "None")

        created = p0.get("created")
        ts_ms = _parse_iso_to_ms_utc(created) if isinstance(created, str) else 0
        if ts_ms <= 0:
            ts_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        return FetchResult(True, val, ts_ms, "")

    async def fetch_latest(self, device_eui: str, channel_index: int, measurement_id: int) -> FetchResult:
        r2 = await self.fetch_latest_openapi(device_eui, channel_index, measurement_id)
        if r2.ok:
            return r2
        r1 = await self.fetch_latest_v1(device_eui, channel_index, measurement_id)
        if r1.ok:
            return r1
        err = r2.err or r1.err or "No data"
        return FetchResult(False, None, 0, err)
