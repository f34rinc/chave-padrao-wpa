# Claro gateway prevalence — WiGLE survey stats

Aggregate statistics from a metropolitan WiGLE survey, showing how common
factory-default (and therefore derivable-key) Claro cable/fibre gateways are in
the field. **Counts only** — this file contains no passwords, no BSSIDs, and no
GPS coordinates. Generated with [`tools/analyze_wigle.py`](tools/analyze_wigle.py)
from local WiGLE database exports (two collectors, one metro area).

_Snapshot: 2026-09-12._

## Dataset

| Metric | Value |
|---|--:|
| Unique APs surveyed | 124,380 |
| OUI vendor blocks catalogued | 177 |
| Distinct hardware vendors | 16 |

## Claro gateway population

| Metric | Count |
|---|--:|
| Default `CLARO_` BSSIDs | 3,316 |
| &nbsp;&nbsp;— primary (physical gateways) | 2,413 |
| &nbsp;&nbsp;— secondary / virtual (locally-administered) | 903 |
| Renamed `CLARO_` (non-default SSID) | 321 |

## Derivability — the core finding

Nearly every default-SSID gateway observed is recoverable straight from the
broadcast beacon, with no handshake required.

| Class | Count | Share |
|---|--:|--:|
| single-OUI — 1 guess off the beacon | 3,308 | 99.8% |
| full-8 in SSID — key fully determined | 7 | 0.2% |
| split-OUI — 256-guess vs a handshake | 1 | 0.0% |
| **Derivable off the beacon** | **3,315** | **99.97%** |

3,164 of the single-OUI gateways had a BSSID tail that differs from the SSID tail
(the benign same-OUI "Compal case") — still a single guess, because the leading
byte is BSSID octet 3. 903 were secondary/virtual radios: the locally-administered
bit flips octet 1, never octet 3, so the leading byte still reads off the beacon.

The lone exception is a single **split-OUI** unit seen on a default SSID —
recoverable, but as a sub-second 256-guess against a captured handshake rather than
directly off the beacon.

> **Note on split-OUI.** This population counts default-SSID gateways only. An
> ARRIS/CommScope split unit that has been renamed drops out of the count entirely,
> and split cannot be detected from a beacon alone — it needs a sticker MAC or a
> handshake. A low split percentage here is *not* evidence that split hardware is
> rare; it is under-counted by passive scans.

## Default-SSID variants

| Variant | Count |
|---|--:|
| no-band | 1,011 |
| banded 5 GHz | 875 |
| banded 2.4 GHz | 705 |
| mesh backhaul (`-5G-BH`) | 641 |
| IoT (`-IoT`) | 84 |

## Split-OUI hardware (ARRIS/CommScope)

8 BSSIDs were seen on the catalogued `C8:52:61` router block — 1 on a default
`CLARO_` SSID and 7 renamed. Because only that one block is catalogued as split,
and split cannot be seen from a beacon, this is a floor, not a full count.

## OUI vendor table (177 blocks)

One vendor holds many OUI blocks: each block covers ~16.7M addresses, so
high-volume makers exhaust blocks and register more, and acquisitions carry legacy
blocks (Vantiva is the renamed Technicolor; CommScope acquired ARRIS). So 177
blocks map to only 16 actual companies.

| Vendor | Blocks |
|---|--:|
| Sagemcom | 57 |
| ZTE | 39 |
| Vantiva/Technicolor | 27 |
| Huawei | 19 |
| Kaon | 7 |
| TP-Link | 7 |
| Arris/CommScope | 6 |
| Intelbras | 4 |
| Humax | 3 |
| Compal | 2 |
| D-Link | 1 |
| Hitron | 1 |
| MitraStar | 1 |
| SEI Robotics | 1 |
| Tellescom | 1 |
| Epigram/Broadcom | 1 |

---

_Figures are a point-in-time snapshot from one metro survey and will drift as
coverage grows. Regenerate with `python tools/analyze_wigle.py <export>.kml`._
