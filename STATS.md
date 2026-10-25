# Claro gateway prevalence — WiGLE survey stats

Aggregate statistics from a metropolitan WiGLE survey, showing how common
factory-default (and therefore derivable-key) ISP gateways are in the field —
`CLARO_`/`NET_` (derivable off the beacon) and `VIVO-`/`VIVOFIBRA-` (Telefónica,
detect-only). **Counts only** — this file contains no passwords, no BSSIDs, and no
GPS coordinates. Generated with [`tools/analyze_wigle.py`](tools/analyze_wigle.py)
from local WiGLE database exports (a household of collectors, one metro area).

_Snapshot: 2026-10-25._

## Dataset

| Metric | Value |
|---|--:|
| Unique APs surveyed | 335,015 |
| OUI vendor blocks catalogued (ISP-CPE) | 244 |
| Distinct hardware vendors | 14 |

The OUI catalogue is a **pure ISP-CPE** list. Consumer/3rd-party blocks that were
merely *seen on* a `CLARO_`/`NET_` SSID — renamed routers or added APs cloning the
name — are tracked separately in
[`data/consumer_ouis.csv`](data/consumer_ouis.csv) and **excluded** from every figure
below (see [Consumer clones](#consumer-clones-excluded)).

## Default-SSID gateways by ISP prefix

| ISP prefix | Default gateways | Key recoverability |
|---|--:|---|
| `CLARO_` | 10,461 | derivable off the beacon |
| `NET_` | 2,070 | derivable off the beacon (same scheme) |
| `VIVO-` | 34 | detect-only (Telefónica) |
| `VIVOFIBRA-` | 5,677 | detect-only (Telefónica) |

## Default-key gateway population (CLARO_ / NET_)

`CLARO_` and its cable sibling `NET_` share the octet-3 + SSID-tail scheme, so they
are counted together for derivability and split out here.

| Metric | Count |
|---|--:|
| Default `CLARO_` / `NET_` BSSIDs | 12,531 |
| &nbsp;&nbsp;— `CLARO_` | 10,461 |
| &nbsp;&nbsp;— `NET_` | 2,070 |
| &nbsp;&nbsp;— primary (physical gateways) | 9,561 |
| &nbsp;&nbsp;— secondary / virtual (locally-administered) | 2,970 |
| Renamed `CLARO_` / `NET_` (non-default SSID) | 1,656 |

A further **110 BSSIDs** carried a default-form `CLARO_`/`NET_` SSID but sit on
**consumer/3rd-party OUIs** (a renamed router or added AP cloning the name, not ISP
CPE). They are excluded from the counts above and from derivability, and tracked in
[`data/consumer_ouis.csv`](data/consumer_ouis.csv).

## Derivability — the core finding

Nearly every default-SSID ISP gateway observed is recoverable straight from the
broadcast beacon, with no handshake required. (Consumer clones are excluded from this
population, so the figure is honest rather than optimistic.)

| Class | Count | Share |
|---|--:|--:|
| single-OUI — 1 guess off the beacon | 12,501 | 99.8% |
| full-8 in SSID — key fully determined | 29 | 0.2% |
| split-OUI — 256-guess vs a handshake | 1 | 0.0% |
| **Derivable off the beacon** | **12,530** | **99.99%** |

11,978 of the single-OUI gateways had a BSSID tail that differs from the SSID tail
(the benign same-OUI "Compal case") — still a single guess, because the leading
byte is BSSID octet 3. 2,970 were secondary/virtual radios: the locally-administered
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
| no-band | 5,134 |
| banded 5 GHz | 2,702 |
| banded 2.4 GHz | 2,304 |
| mesh backhaul (`-5G-BH`) | 2,088 |
| IoT (`-IoT`) | 303 |

## Split-OUI hardware (ARRIS/CommScope)

42 BSSIDs were seen on the catalogued `C8:52:61` router block — 1 on a default
`CLARO_` SSID and 41 renamed. Because only that one block is catalogued as split,
and split cannot be seen from a beacon, this is a floor, not a full count.

## Consumer clones excluded

110 BSSIDs broadcast a default-form `CLARO_`/`NET_` SSID from a **consumer/3rd-party
OUI** — almost certainly renamed routers or added APs cloning the SSID. A non-Claro
device does not run the MAC-derived default-key scheme, so its key is **not
derivable**; counting it as an ISP gateway would over-state the numbers. These blocks
(TP-Link, Tenda, Xiaomi, D-Link, NETGEAR, a Broadcom reference design, a PIX-LINK block, a Mercusys block, plus four unregistered blocks) are catalogued
separately in [`data/consumer_ouis.csv`](data/consumer_ouis.csv) as a durable
"already-triaged, not ISP CPE" record, so they are excluded from the counts above and
never resurface as newly-seen blocks. This replaces the earlier ~0.3% estimate with a
measured figure.

## OUI vendor table (244 blocks)

One vendor holds many OUI blocks: each block covers ~16.7M addresses, so
high-volume makers exhaust blocks and register more, and acquisitions carry legacy
blocks (Vantiva is the renamed Technicolor; CommScope acquired ARRIS). So 244
blocks map to only 14 actual companies. Recent surveys kept adding IEEE-verified
ISP-CPE blocks to existing families: 2026-10-17 → 239 (`30:24:78` Sagemcom,
`3C:B7:4B` Vantiva/Technicolor, `C0:F6:C2` Huawei); the 2026-10-18 run added none;
the 2026-10-22 run added 2 (`90:3F:EA` Huawei, `80:85:44` Intelbras → 241); the
2026-10-24 run added 2 (`1C:3D:2F` Huawei, `88:9E:96` ZTE → 243); the 2026-10-25 run
added 1 (`6C:FF:CE` Sagemcom → 244). All additions have landed in existing families,
so the company count has held at 14. Consumer clones found on the same walks (e.g.
`8C:90:2D`/`18:A6:F7` TP-Link) go to `consumer_ouis.csv`, not here.

| Vendor | Blocks |
|---|--:|
| Sagemcom | 68 |
| Vantiva/Technicolor | 50 |
| ZTE | 45 |
| Huawei | 35 |
| Arris/CommScope | 16 |
| Intelbras | 7 |
| Kaon | 7 |
| Humax | 6 |
| Tellescom | 3 |
| Compal | 2 |
| WNC | 2 |
| Hitron | 1 |
| MitraStar | 1 |
| SEI Robotics | 1 |

## VIVO / VIVOFIBRA (Telefónica — detect-only)

Telefónica's `VIVO-` / `VIVOFIBRA-` default SSIDs use a different construction
(key = MAC minus its first octet). Unlike Claro, the derivation is **confirmed only
on specific weak-firmware MitraStar OUIs captured on the base (2.4 GHz) MAC** — so
the survey reports these **detect-only**: identified and gated, but a key is claimed
only in the one provable case. Emitting a "likely key" for the rest would be a
confidently-wrong guess.

| Metric | Count |
|---|--:|
| Detected (default + renamed) | 6,126 |
| &nbsp;&nbsp;— `VIVO-` | 151 |
| &nbsp;&nbsp;— `VIVOFIBRA-` | 5,975 |
| Default-form SSIDs | 5,711 |
| &nbsp;&nbsp;— weak MitraStar OUI | 40 |
| &nbsp;&nbsp;— hardened ODM (random factory key) | 622 |
| &nbsp;&nbsp;— OUI not yet researched | 5,049 |
| **Derivable** (weak OUI + base-MAC capture) | **20** |
| Detect-only (identified, no key off the beacon) | 5,691 |

The ~88% "not yet researched" share (5,049 of 5,711) reflects that VIVOFIBRA's ODM
mix is largely uncatalogued — each label/handshake that confirms a weak OUI moves a
whole block from detect-only into derivable. No VIVO OUI research is folded into this
survey; the gate comes from `schemes.py`'s existing weak/hardened sets.

---

_Figures are a point-in-time snapshot from one metro survey and drift as coverage
and the contributing collector databases change. Regenerate with
`python tools/analyze_wigle.py <backup>.sqlite [more...]`._
