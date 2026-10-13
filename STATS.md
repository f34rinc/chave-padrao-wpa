# Claro gateway prevalence — WiGLE survey stats

Aggregate statistics from a metropolitan WiGLE survey, showing how common
factory-default (and therefore derivable-key) ISP gateways are in the field —
`CLARO_`/`NET_` (derivable off the beacon) and `VIVO-`/`VIVOFIBRA-` (Telefónica,
detect-only). **Counts only** — this file contains no passwords, no BSSIDs, and no
GPS coordinates. Generated with [`tools/analyze_wigle.py`](tools/analyze_wigle.py)
from local WiGLE database exports (two collectors, one metro area).

_Snapshot: 2026-10-13._

## Dataset

| Metric | Value |
|---|--:|
| Unique APs surveyed | 249,452 |
| OUI vendor blocks catalogued (ISP-CPE) | 233 |
| Distinct hardware vendors | 14 |

The OUI catalogue is a **pure ISP-CPE** list. Consumer/3rd-party blocks that were
merely *seen on* a `CLARO_`/`NET_` SSID — renamed routers or added APs cloning the
name — are tracked separately in
[`data/consumer_ouis.csv`](data/consumer_ouis.csv) and **excluded** from every figure
below (see [Consumer clones](#consumer-clones-excluded)).

## Default-SSID gateways by ISP prefix

| ISP prefix | Default gateways | Key recoverability |
|---|--:|---|
| `CLARO_` | 7,778 | derivable off the beacon |
| `NET_` | 1,450 | derivable off the beacon (same scheme) |
| `VIVO-` | 22 | detect-only (Telefónica) |
| `VIVOFIBRA-` | 3,829 | detect-only (Telefónica) |

## Default-key gateway population (CLARO_ / NET_)

`CLARO_` and its cable sibling `NET_` share the octet-3 + SSID-tail scheme, so they
are counted together for derivability and split out here.

| Metric | Count |
|---|--:|
| Default `CLARO_` / `NET_` BSSIDs | 9,228 |
| &nbsp;&nbsp;— `CLARO_` | 7,778 |
| &nbsp;&nbsp;— `NET_` | 1,450 |
| &nbsp;&nbsp;— primary (physical gateways) | 7,064 |
| &nbsp;&nbsp;— secondary / virtual (locally-administered) | 2,164 |
| Renamed `CLARO_` / `NET_` (non-default SSID) | 1,198 |

A further **58 BSSIDs** carried a default-form `CLARO_`/`NET_` SSID but sit on
**consumer/3rd-party OUIs** (a renamed router or added AP cloning the name, not ISP
CPE). They are excluded from the counts above and from derivability, and tracked in
[`data/consumer_ouis.csv`](data/consumer_ouis.csv).

## Derivability — the core finding

Nearly every default-SSID ISP gateway observed is recoverable straight from the
broadcast beacon, with no handshake required. (Consumer clones are excluded from this
population, so the figure is honest rather than optimistic.)

| Class | Count | Share |
|---|--:|--:|
| single-OUI — 1 guess off the beacon | 9,209 | 99.8% |
| full-8 in SSID — key fully determined | 18 | 0.2% |
| split-OUI — 256-guess vs a handshake | 1 | 0.0% |
| **Derivable off the beacon** | **9,227** | **99.99%** |

8,801 of the single-OUI gateways had a BSSID tail that differs from the SSID tail
(the benign same-OUI "Compal case") — still a single guess, because the leading
byte is BSSID octet 3. 2,164 were secondary/virtual radios: the locally-administered
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
| no-band | 3,792 |
| banded 5 GHz | 1,976 |
| banded 2.4 GHz | 1,730 |
| mesh backhaul (`-5G-BH`) | 1,516 |
| IoT (`-IoT`) | 214 |

## Split-OUI hardware (ARRIS/CommScope)

17 BSSIDs were seen on the catalogued `C8:52:61` router block — 1 on a default
`CLARO_` SSID and 16 renamed. Because only that one block is catalogued as split,
and split cannot be seen from a beacon, this is a floor, not a full count.

## Consumer clones excluded

58 BSSIDs broadcast a default-form `CLARO_`/`NET_` SSID from a **consumer/3rd-party
OUI** — almost certainly renamed routers or added APs cloning the SSID. A non-Claro
device does not run the MAC-derived default-key scheme, so its key is **not
derivable**; counting it as an ISP gateway would over-state the numbers. These blocks
(TP-Link, Tenda, Xiaomi, D-Link, NETGEAR, a Broadcom reference design, plus one unregistered block) are catalogued
separately in [`data/consumer_ouis.csv`](data/consumer_ouis.csv) as a durable
"already-triaged, not ISP CPE" record, so they are excluded from the counts above and
never resurface as newly-seen blocks. This replaces the earlier ~0.3% estimate with a
measured figure.

## OUI vendor table (233 blocks)

One vendor holds many OUI blocks: each block covers ~16.7M addresses, so
high-volume makers exhaust blocks and register more, and acquisitions carry legacy
blocks (Vantiva is the renamed Technicolor; CommScope acquired ARRIS). So 222
blocks map to only 14 actual companies. The 2026-10-09 survey added three
IEEE-verified ISP-CPE blocks to existing families (`1C:9E:CC` Vantiva, `FC:2D:5E`
ZTE, `D4:2C:0F` Arris/CommScope), so the block total rose 222 → 225 with no new
vendor; the 2026-10-10 survey added two more (`80:E1:BF`, `20:AB:48`, both
Huawei), taking it to 227; the 2026-10-11 survey added five more (`38:17:B1`,
`08:7B:12` Sagemcom, `E8:13:6E`, `B0:EC:DD` Huawei, `C4:92:D9` ZTE) → 232;
the 2026-10-13 survey added one more (`80:29:94` Vantiva) → 233.

| Vendor | Blocks |
|---|--:|
| Sagemcom | 66 |
| Vantiva/Technicolor | 48 |
| ZTE | 43 |
| Huawei | 32 |
| Arris/CommScope | 16 |
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
| Detected (default + renamed) | 4,138 |
| &nbsp;&nbsp;— `VIVO-` | 102 |
| &nbsp;&nbsp;— `VIVOFIBRA-` | 4,036 |
| Default-form SSIDs | 3,851 |
| &nbsp;&nbsp;— weak MitraStar OUI | 23 |
| &nbsp;&nbsp;— hardened ODM (random factory key) | 423 |
| &nbsp;&nbsp;— OUI not yet researched | 3,405 |
| **Derivable** (weak OUI + base-MAC capture) | **12** |
| Detect-only (identified, no key off the beacon) | 3,839 |

The ~88% "not yet researched" share (3,405 of 3,851) reflects that VIVOFIBRA's ODM
mix is largely uncatalogued — each label/handshake that confirms a weak OUI moves a
whole block from detect-only into derivable. No VIVO OUI research is folded into this
survey; the gate comes from `schemes.py`'s existing weak/hardened sets.

---

_Figures are a point-in-time snapshot from one metro survey and drift as coverage
and the contributing collector databases change. Regenerate with
`python tools/analyze_wigle.py <backup>.sqlite [more...]`._
