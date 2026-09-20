# Claro gateway prevalence — WiGLE survey stats

Aggregate statistics from a metropolitan WiGLE survey, showing how common
factory-default (and therefore derivable-key) Claro cable/fibre gateways are in
the field. **Counts only** — this file contains no passwords, no BSSIDs, and no
GPS coordinates. Generated with [`tools/analyze_wigle.py`](tools/analyze_wigle.py)
from local WiGLE database exports (two collectors, one metro area).

_Snapshot: 2026-09-20._

## Dataset

| Metric | Value |
|---|--:|
| Unique APs surveyed | 150,796 |
| OUI vendor blocks catalogued | 191 |
| Distinct hardware vendors | 17 |

## Claro gateway population

| Metric | Count |
|---|--:|
| Default `CLARO_` BSSIDs | 4,939 |
| &nbsp;&nbsp;— primary (physical gateways) | 3,569 |
| &nbsp;&nbsp;— secondary / virtual (locally-administered) | 1,370 |
| Renamed `CLARO_` (non-default SSID) | 555 |

## Derivability — the core finding

Nearly every default-SSID gateway observed is recoverable straight from the
broadcast beacon, with no handshake required.

| Class | Count | Share |
|---|--:|--:|
| single-OUI — 1 guess off the beacon | 4,928 | 99.8% |
| full-8 in SSID — key fully determined | 10 | 0.2% |
| split-OUI — 256-guess vs a handshake | 1 | 0.0% |
| **Derivable off the beacon** | **4,938** | **99.98%** |

4,674 of the single-OUI gateways had a BSSID tail that differs from the SSID tail
(the benign same-OUI "Compal case") — still a single guess, because the leading
byte is BSSID octet 3. 1,370 were secondary/virtual radios: the locally-administered
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
| no-band | 1,479 |
| banded 5 GHz | 1,287 |
| banded 2.4 GHz | 1,072 |
| mesh backhaul (`-5G-BH`) | 969 |
| IoT (`-IoT`) | 132 |

## Split-OUI hardware (ARRIS/CommScope)

11 BSSIDs were seen on the catalogued `C8:52:61` router block — 1 on a default
`CLARO_` SSID and 10 renamed. Because only that one block is catalogued as split,
and split cannot be seen from a beacon, this is a floor, not a full count.

## OUI vendor table (191 blocks)

One vendor holds many OUI blocks: each block covers ~16.7M addresses, so
high-volume makers exhaust blocks and register more, and acquisitions carry legacy
blocks (Vantiva is the renamed Technicolor; CommScope acquired ARRIS). So 191
blocks map to only 17 actual companies.

> **Observed-on-pattern, not confirmed-issued.** These are OUIs *seen on a `CLARO_`
> SSID* — a superset of the blocks Claro actually issues. About **0.3%** of the
> default gateways sit on consumer-brand blocks (TP-Link, D-Link, a Broadcom
> reference OUI) that are most likely **renamed routers or added APs cloning the
> SSID**: a non-Claro device doesn't run the MAC-derived key scheme, so it isn't
> derivable and slightly over-counts the figures above. They're kept for
> completeness and flagged in [`data/claro_ouis.csv`](data/claro_ouis.csv).

| Vendor | Blocks |
|---|--:|
| Sagemcom | 58 |
| ZTE | 40 |
| Vantiva/Technicolor | 27 |
| Huawei | 25 |
| TP-Link | 9 |
| Kaon | 7 |
| Arris/CommScope | 6 |
| Intelbras | 5 |
| Humax | 3 |
| Tellescom | 3 |
| Compal | 2 |
| D-Link | 1 |
| Hitron | 1 |
| MitraStar | 1 |
| SEI Robotics | 1 |
| Epigram/Broadcom | 1 |
| WNC | 1 |

---

_Figures are a point-in-time snapshot from one metro survey and drift as coverage
and the contributing collector databases change. Regenerate with
`python tools/analyze_wigle.py <backup>.sqlite [more...]`._
