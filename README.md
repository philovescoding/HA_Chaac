# Chaac VWC (SenseCAP + Shelly) — Home Assistant custom integration

Single-slot SenseCAP soil sensor polling (OpenAPI + v1 fallback) with automatic irrigation control via Shelly plug (RPC + Gen1 fallback).

## Features
- 1 slot (no multi-slot UI spam)
- SenseCAP OpenAPI fetch with automatic fallback to Gen1 API
- Polling every *pollSeconds* (default 60s)
- Decision logic (P1/P2 time windows + thresholds + min interval)
- Manual **Water now** button
- Shelly switching: RPC `/rpc/Switch.Set` + legacy `/relay/<id>` fallback
- Basic logging + pump totals

## Installation (HACS)
1. Install HACS in your Home Assistant (if not already installed).
2. HACS → Integrations → menu (⋮) → **Custom repositories**
3. Add this repository URL, category **Integration**
4. Install “Chaac VWC”
5. Restart Home Assistant

## Installation (manual)
Copy `custom_components/chaac_vwc` into your Home Assistant `/config/custom_components/` folder and restart.

## Configuration
Settings → Devices & services → Add integration → **Chaac VWC**

You will be asked for:
- SenseCAP Access ID / Access Key
- Device EUI
- Shelly Host/IP (optional) + relay id
- Thresholds + P1/P2 times
- Pump amount: ml/sec calibration OR fixed seconds
