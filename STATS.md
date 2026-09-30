# Claro gateway prevalence — WiGLE survey stats

Aggregate statistics from a metropolitan WiGLE survey, showing how common
factory-default (and therefore derivable-key) ISP gateways are in the field —
`CLARO_`/`NET_` (derivable off the beacon) and `VIVO-`/`VIVOFIBRA-` (Telefónica,
detect-only). **Counts only** — this file contains no passwords, no BSSIDs, and no
GPS coordinates. Generated with [`tools/analyze_wigle.py`](tools/analyze_wigle.py)
from local WiGLE database exports (two collectors, one metro area).

_Snapshot: 2026-09-30._

## Dataset

| Metric | Value |
|---|--:|
| Unique APs surveyed | 187,206 |
| OUI vendor blocks catalogued (ISP-CPE) | 222 |
| Distinct hardware vendors | 14 |

The OUI catalogue is a **pure ISP-CPE** list. Consumer/3rd-party blocks that were
merely *seen on* a `CLARO_`/`NET_` SSID — renamed routers or added APs cloning the
name — are tracked separately in
[`data/consumer_ouis.csv`](data/consumer_ouis.csv) and **excluded** from every figure
below (see [Consumer clones](#consumer-clones-excluded)).

## Default-SSID gateways by ISP prefix

| ISP prefix | Default gateways | Key recoverability |
|---|--:|---|
| `CLARO_` | 5,993 | derivable off the beacon |
| `NET_` | 1,085 | derivable off the beacon (same scheme) |
| `VIVO-` | 22 | detect-only (Telefónica) |
| `VIVOFIBRA-` | 2,968 | detect-only (Telefónica) |

## Default-key gateway population (CLARO_ / NET_)

`CLARO_` and its cable sibling `NET_` share the octet-3 + SSID-tail scheme, so they
are counted together for derivability and split out here.

| Metric | Count |
|---|--:|
| Default `CLARO_` / `NET_` BSSIDs | 7,078 |
| &nbsp;&nbsp;— `CLARO_` | 5,993 |
| &nbsp;&nbsp;— `NET_` | 1,085 |
| &nbsp;&nbsp;— primary (physical gateways) | 5,430 |
| &nbsp;&nbsp;— secondary / virtual (locally-administered) | 1,648 |
| Renamed `CLARO_` / `NET_` (non-default SSID) | 878 |

A further **30 BSSIDs** carried a default-form `CLARO_`/`NET_` SSID but sit on
**consumer/3rd-party OUIs** (a renamed router or added AP cloning the name, not ISP
CPE). They are excluded from the counts above and from derivability, and tracked in
[`data/consumer_ouis.csv`](data/consumer_ouis.csv).

## Derivability — the core finding

Nearly every default-SSID ISP gateway observed is recoverable straight from the
broadcast beacon, with no handshake required. (Consumer clones are excluded from this
population, so the figure is honest rather than optimistic.)

| Class | Count | Share |
|---|--:|--:|
| single-OUI — 1 guess off the beacon | 7,062 | 99.8% |
| full-8 in SSID — key fully determined | 15 | 0.2% |
| split-OUI — 256-guess vs a handshake | 1 | 0.0% |
| **Derivable off the beacon** | **7,077** | **99.98%** |

6,761 of the single-OUI gateways had a BSSID tail that differs from the SSID tail
(the benign same-OUI "Compal case") — still a single guess, because the leading
byte is BSSID octet 3. 1,648 were secondary/virtual radios: the locally-administered
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
| no-band | 2,887 |
| banded 5 GHz | 1,539 |
| banded 2.4 GHz | 1,330 |
| mesh backhaul (`-5G-BH`) | 1,161 |
| IoT (`-IoT`) | 161 |

## Split-OUI hardware (ARRIS/CommScope)

14 BSSIDs were seen on the catalogued `C8:52:61` router block — 1 on a default
`CLARO_` SSID and 13 renamed. Because only that one block is catalogued as split,
and split cannot be seen from a beacon, this is a floor, not a full count.

## Consumer clones excluded

30 BSSIDs broadcast a default-form `CLARO_`/`NET_` SSID from a **consumer/3rd-party
OUI** — almost certainly renamed routers or added APs cloning the SSID. A non-Claro
device does not run the MAC-derived default-key scheme, so its key is **not
derivable**; counting it as an ISP gateway would over-state the numbers. These blocks
(TP-Link, Tenda, Xiaomi, D-Link, NETGEAR, a Broadcom reference design, plus one unregistered block) are catalogued
separately in [`data/consumer_ouis.csv`](data/consumer_ouis.csv) as a durable
"already-triaged, not ISP CPE" record, so they are excluded from the counts above and
never resurface as newly-seen blocks. This replaces the earlier ~0.3% estimate with a
measured figure.

## OUI vendor table (222 blocks)

One vendor holds many OUI blocks: each block covers ~16.7M addresses, so
high-volume makers exhaust blocks and register more, and acquisitions carry legacy
blocks (Vantiva is the renamed Technicolor; CommScope acquired ARRIS). So 222
blocks map to only 14 actual companies.

| Vendor | Blocks |
|---|--:|
| Sagemcom | 64 |
| Vantiva/Technicolor | 46 |
| ZTE | 41 |
| Huawei | 28 |
| Arris/CommScope | 15 |
| Kaon | 7 |
| Humax | 6 |
| Intelbras | 6 |
| Tellescom | 3 |
| Compal | 2 |
| Hitron | 1 |
| MitraStar | 1 |
| SEI Robotics | 1 |
| WNC | 1 |

## VIVO / VIVOFIBRA (Telefónica — detect-only)

Telefónica's `VIVO-` / `VIVOFIBRA-` default SSIDs use a different construction
(key = MAC minus its first octet). Unlike Claro, the derivation is **confirmed only
on specific weak-firmware MitraStar OUIs captured on the base (2.4 GHz) MAC** — so
the survey reports these **detect-only**: identified and gated, but a key is claimed
only in the one provable case. Emitting a "likely key" for the rest would be a
confidently-wrong guess.

| Metric | Count |
|---|--:|
| Detected (default + renamed) | 3,203 |
| &nbsp;&nbsp;— `VIVO-` | 85 |
| &nbsp;&nbsp;— `VIVOFIBRA-` | 3,118 |
| Default-form SSIDs | 2,990 |
| &nbsp;&nbsp;— weak MitraStar OUI | 16 |
| &nbsp;&nbsp;— hardened ODM (random factory key) | 326 |
| &nbsp;&nbsp;— OUI not yet researched | 2,648 |
| **Derivable** (weak OUI + base-MAC capture) | **10** |
| Detect-only (identified, no key off the beacon) | 2,980 |

The ~89% "not yet researched" share (2,648 of 2,990) reflects that VIVOFIBRA's ODM
mix is largely uncatalogued — each label/handshake that confirms a weak OUI moves a
whole block from detect-only into derivable. No VIVO OUI research is folded into this
survey; the gate comes from `schemes.py`'s existing weak/hardened sets.

---

_Figures are a point-in-time snapshot from one metro survey and drift as coverage
and the contributing collector databases change. Regenerate with
`python tools/analyze_wigle.py <backup>.sqlite [more...]`._
