# Feeder SenseCAP VWC (Single Slot) – Home Assistant Custom Integration

**1 Slot** (kein Slot-Spam), aber gleicher Ablauf wie dein ESP32 SenseCapESP:
- Cloud Polling (OpenAPI -> v1 fallback)
- Nur neue Samples werden geloggt (t steigt)
- Shelly: Gen2 RPC zuerst, Gen1 fallback
- Auto-Off + optional Auto-Watering (Threshold P1/P2 + Zeitfenster + plantInterval)
- Logs als JSONL unter `/config/feeder_sensecap_logs/`

## Installation
Kopiere `config/custom_components/feeder_sensecap/` nach `/config/custom_components/feeder_sensecap/` in HA.
Wenn du die 8-Slot Version installiert hattest: einfach den Ordner `feeder_sensecap` ersetzen.

## Setup
Einstellungen → Geräte & Dienste → Integration hinzufügen → Feeder SenseCAP VWC (Single Slot)
- Access ID
- Access Key
- Device EUI

Weitere Parameter (Shelly Host/Id, Thresholds, P1/P2 Zeiten, …) findest du in den **Optionen** der Integration.
