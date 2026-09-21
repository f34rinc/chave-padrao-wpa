#!/usr/bin/env python3
"""
charset_mask.py
------------------------------------------------------------
General utility: read a .hc22000 file, pull each network's BSSID + SSID, and
build a hashcat mask attack whose custom charset is ONLY the (uppercase) hex
characters that appear in that network's BSSID and in the SSID's hex runs.

Why it can help: some WPA hex keys are derived from the device MAC, whose hex
digits surface in the BSSID and in the SSID. Restricting the mask alphabet to
just those characters keeps such a key inside the keyspace while making it much
smaller than the full 0-9A-F space -- when the alphabet is small. It is a generic
keyspace-reduction helper, not tied to any one vendor or scheme.

The SSID contributes its hex RUNS -- 2+ adjacent hex chars, anywhere in the name,
not just the tail. Isolated hex-valid letters in a name are skipped, and only hex
characters (0-9 A-F) are kept: a WPA hex key cannot contain anything else.

Key length: min is fixed at 8 (the WPA-PSK minimum); the max defaults to 8 and can be
raised with --max-len N / -L N (8-63), or 'len N' at the interactive prompt. A max > 8
emits a hashcat --increment command that also tries the longer keys -- note the keyspace
grows by a factor of the charset size per extra character.

Case: the charset is UPPERCASE hex by default. --case lower / --case mixed (or 'case
MODE' at the prompt) switch it. 'mixed' includes BOTH cases of every hex letter present
(digits are caseless), which roughly doubles the alphabet -- and the keyspace with it.

Known schemes: when schemes.py is importable (i.e. running in-repo), a recognised
default-key SSID seeds these defaults automatically -- VIVO-/VIVOFIBRA- keys are the MAC
minus its 1st octet (10 hex), so max-len defaults to 10 and VIVOFIBRA to lowercase (and
the --positional mask then targets 10, containing the key). An explicit --max-len or
--case always overrides the auto-default; a standalone copy (no schemes.py) skips it.

The optional --positional (-p) tier goes further: instead of one charset for all
positions, it builds a PER-POSITION charset from the aligned BSSID + SSID chars.
Where they agree (the high bytes) the position is a fixed literal; only where they
diverge (the low byte) does it vary. Measured across ~1400 real MAC-derived
gateways that collapses the keyspace from ~10^8 to a median of 4 (max 64) while
still containing the key. It's a fast heuristic, not exhaustive — the uniform mask
stays the guaranteed fallback.

Running: by default the tool only PRINTS the command(s). -y/--run launches hashcat for
you (--ask confirms each run first; -n/--no-run is the print-only default; the menu has
'run'/'ask'/'norun'). With --positional it runs as a CASCADE: the fast positional mask
first, then the exhaustive uniform mask only if the positional finishes without a hit
(hashcat exit 0 = cracked, stop). hashcat runs from its own folder so it finds its
OpenCL/ kernels/; Ctrl-C aborts a run and returns to the prompt.

Usage:
    python charset_mask.py capture.hc22000
    python charset_mask.py --positional capture.hc22000     (add the aggressive tier)
    python charset_mask.py --max-len 10 capture.hc22000      (also try lengths 9, 10)
    python charset_mask.py --case lower capture.hc22000      (lowercase hex charset)
    python charset_mask.py --case mixed capture.hc22000      (both cases; bigger keyspace)
    python charset_mask.py -y --positional capture.hc22000   (run it: positional, then uniform)
    python charset_mask.py            (no args -> prompts / drag-drop friendly)

If hashcat is on your PATH, the emitted command is prefixed with a `cd` into
hashcat's own folder -- in your shell's syntax (cmd / PowerShell / POSIX,
auto-detected from the parent process; override with the HASHCAT_SHELL env var =
cmd|powershell|posix) -- so it finds its OpenCL/kernels and runs exactly as pasted
(hashcat looks for those relative to the launch dir, not to hashcat.exe).

For authorised auditing of your own / consented equipment only.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys


def _load_schemes():
    """Import the repo's schemes.py for VIVO/VIVOFIBRA SSID detection, if reachable.
    charset_mask lives in utils/, so schemes.py sits one directory up in-repo; a
    standalone copy of this file won't find it and the vendor auto-defaults just
    don't fire (the tool stays fully usable, only without that convenience)."""
    try:
        import schemes
        return schemes
    except ImportError:
        pass
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent not in sys.path:
        sys.path.insert(0, parent)
    try:
        import schemes
        return schemes
    except ImportError:
        return None


_SCHEMES = _load_schemes()

HASH_MODE       = 22000    # WPA/WPA2 (hashcat mode 22000)
MIN_LEN         = 8        # shortest key length to try; WPA-PSK minimum (fixed)
DEFAULT_MAX_LEN = 8        # default longest length; raise with --max-len N / 'len N'
MAX_WPA_LEN     = 63       # WPA-PSK maximum passphrase length (upper bound for max-len)
MIN_RUN         = 2        # min length of an SSID hex run to include (2 = "adjacent")
HEX             = set("0123456789ABCDEF")
CASES           = ("upper", "lower", "mixed")   # hex-letter case modes for the charset
RATES           = (150_000,)   # H/s baseline for time estimates (measured -m 22000 avg)
BAR             = "=" * 70


# ---- color (ANSI, cross-platform, stdlib only) ------------------------------
class _Palette:
    """ANSI colors, or empty strings when color is off. Mirrors chave_padrao's palette
    so the two tools' menus look alike; kept local to keep this file standalone."""
    def __init__(self, on):
        self.on = bool(on)            # a real ANSI terminal -> safe to clear-screen
        e = (lambda c: c) if on else (lambda c: "")
        self.reset  = e("\033[0m")
        self.bold   = e("\033[1m")
        self.dim    = e("\033[90m")   # bright-black (gray)
        self.cyan   = e("\033[36m")
        self.yellow = e("\033[33m")
        self.green  = e("\033[32m")
        self.red    = e("\033[31m")


C = _Palette(False)   # replaced in main() once we know the terminal


def _enable_windows_ansi():
    """Turn on ANSI/VT processing in the Windows console. No-op elsewhere."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        h = k.GetStdHandle(-11)                        # STD_OUTPUT_HANDLE
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        k.SetConsoleMode(h, mode.value | 0x0004)       # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return True
    except Exception:
        return False


def setup_color(enabled):
    """Return a _Palette. `enabled` False (or NO_COLOR set) -> no color. Otherwise color
    is auto: on only when writing to a real terminal that can render ANSI."""
    if not enabled or os.environ.get("NO_COLOR") is not None:
        return _Palette(False)
    on = sys.stdout.isatty()
    if on and os.name == "nt" and not _enable_windows_ansi():
        on = any(os.environ.get(v) for v in ("WT_SESSION", "MSYSTEM", "TERM"))
    return _Palette(on)


def parse_22000(path):
    """[{essid, bssid}] for each unique network in a .hc22000 file."""
    seen = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.upper().startswith("WPA"):
                continue
            parts = line.split("*")
            if len(parts) < 6:
                continue
            bssid = parts[3].lower()
            if len(bssid) != 12 or any(c not in "0123456789abcdef" for c in bssid):
                continue
            try:
                essid = bytes.fromhex(parts[5]).decode("utf-8", "replace")
            except ValueError:
                essid = ""
            key = (bssid, parts[5])
            if key not in seen:
                seen[key] = {"essid": essid, "bssid": bssid}
    return list(seen.values())


def ssid_hex_runs(essid):
    """All contiguous hex runs in the SSID with length >= MIN_RUN (anywhere).

    We take runs of ADJACENT hex chars, not just the trailing tail and not every
    hex-valid char in the name. A run (2+ in a row) is likely MAC-derived data;
    isolated hex-valid letters in a NAME (e.g. the single A in "CLARO") are skipped
    so they don't bloat the charset. Including a run only ever WIDENS the alphabet,
    never drops a needed char, so this is a safe superset of the tail-only rule.
    """
    return re.findall(r'[0-9A-Fa-f]{%d,}' % MIN_RUN, essid or "")


def _apply_case(chars, case):
    """Map canonical hex chars to the requested letter-case mode. 'upper' uppercases,
    'lower' lowercases, 'mixed' emits BOTH cases of each hex letter (A-F) while digits,
    which have no case, stay single. Returns a set."""
    out = set()
    for c in chars:
        if case == "lower":
            out.add(c.lower())
        elif case == "mixed":
            out.add(c.upper())
            if c.isalpha():
                out.add(c.lower())
        else:  # "upper"
            out.add(c.upper())
    return out


def hex_charset(bssid, essid, case="upper"):
    """Distinct hex chars in the BSSID + the SSID's hex runs, in the requested letter
    case ('upper' default, 'lower', or 'mixed' = both cases of each letter), sorted."""
    pool = set((bssid + "".join(ssid_hex_runs(essid))).upper()) & HEX
    return "".join(sorted(_apply_case(pool, case)))


# Shells recognised when walking the parent-process chain (Windows).
_SHELLS = {"cmd.exe", "powershell.exe", "pwsh.exe", "bash.exe", "sh.exe",
           "zsh.exe", "fish.exe", "wt.exe", "windowsterminal.exe",
           "mintty.exe", "conemu.exe", "conemu64.exe", "code.exe",
           "cursor.exe", "alacritty.exe", "wezterm-gui.exe"}


def _win_parent_chain():
    """Ordered exe names of this process's ancestors (nearest parent first),
    lowercased, via a Toolhelp snapshot. [] on non-Windows or on any failure.

    Used both to tell a GUI launch from a terminal one, and to sniff which shell the
    user is in. The whole chain is walked (not just the immediate parent) because the
    Windows .py association goes Explorer -> py.exe -> python.exe, so the real
    launcher is a grandparent."""
    if os.name != "nt":
        return []
    procs = {}
    try:
        import ctypes
        from ctypes import wintypes

        class _PE32(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_char * 260)]

        k = ctypes.windll.kernel32
        snap = k.CreateToolhelp32Snapshot(0x2, 0)     # TH32CS_SNAPPROCESS
        if snap in (-1, None):
            return []
        e = _PE32(); e.dwSize = ctypes.sizeof(_PE32)
        ok = k.Process32First(snap, ctypes.byref(e))
        while ok:
            procs[e.th32ProcessID] = (e.th32ParentProcessID,
                                      e.szExeFile.decode("latin-1").lower())
            ok = k.Process32Next(snap, ctypes.byref(e))
        k.CloseHandle(snap)
    except Exception:
        return []
    chain, cur, seen = [], os.getpid(), set()
    while cur in procs and cur not in seen:
        seen.add(cur)
        ppid = procs[cur][0]
        parent = procs.get(ppid)
        if not parent:
            break
        chain.append(parent[1])
        cur = ppid
    return chain


def _detect_shell():
    """Which shell the emitted `cd`+run one-liner should target, so it pastes back
    into the shell the user is actually in. Honours an explicit HASHCAT_SHELL override
    (cmd|powershell|posix). On POSIX -> 'posix'. On Windows, sniff the parent-process
    chain for PowerShell vs cmd; default to 'cmd' -- the Windows norm, and its
    `cd /d ... &&` is what most hashcat-on-Windows guides use -- when the walk is
    inconclusive (e.g. a drag-and-drop launch with no shell ancestor)."""
    override = os.environ.get("HASHCAT_SHELL", "").strip().lower()
    if override in ("cmd", "powershell", "posix"):
        return override
    if os.name != "nt":
        return "posix"
    for name in _win_parent_chain():
        if name in ("powershell.exe", "pwsh.exe"):
            return "powershell"
        if name == "cmd.exe":
            return "cmd"
        if name in ("bash.exe", "sh.exe", "zsh.exe", "fish.exe", "mintty.exe"):
            return "posix"        # Git Bash / MSYS on Windows -> POSIX `cd ... &&`
    return "cmd"


def _hashcat_prefix():
    """Locate hashcat on PATH and return (cd_prefix, program_name) so the emitted
    command is copy-paste RUNNABLE from any directory.

    hashcat resolves its OpenCL/ kernels/ modules/ folders relative to the *current
    working directory*, not to hashcat.exe -- so a portable/extracted install (data
    folders sitting next to the binary) must be launched from its own folder, or it
    dies with "./OpenCL/: No such file or directory". When hashcat is on PATH and its
    folder holds those data dirs, we prepend a `cd` into it, in the DETECTED shell's
    syntax (cmd `cd /d ... &&`, PowerShell `cd ... ;`, POSIX `cd ... &&`). A system
    install (no data folders beside the binary -- it finds its own) or a hashcat not
    on PATH gets a bare `hashcat` call."""
    d = _hashcat_dir()
    if not d:
        return "", "hashcat"
    shell = _detect_shell()
    if shell == "powershell":
        return f'cd "{d}"; ', "hashcat"        # PowerShell: `;` sequences; cd switches drive
    if shell == "cmd":
        return f'cd /d "{d}" && ', "hashcat"   # cmd: /d switches drive, && chains
    return f'cd "{d}" && ', "hashcat"          # POSIX (bash/zsh/sh)


def _hashcat_dir():
    """The directory hashcat must be launched from -- its own folder, when it's a
    portable/extracted install whose OpenCL/ kernels/ data dirs sit beside the binary --
    else None (a system install finds its own; a not-on-PATH hashcat has no dir). Shared
    by the printed `cd` prefix and the actual run (as the subprocess cwd)."""
    exe = shutil.which("hashcat")
    if not exe:
        return None
    d = os.path.dirname(os.path.abspath(exe))
    needs_cd = any(os.path.isdir(os.path.join(d, sub)) for sub in ("OpenCL", "kernels"))
    return d if needs_cd else None


def _hc_command(path, tail):
    """A full, runnable hashcat command: the launch prefix (see _hashcat_prefix) + the
    program + `tail` (everything after the program name), whitespace-tidied."""
    prefix, hc = _hashcat_prefix()
    return re.sub(r"\s{2,}", " ",
                  f'{prefix}{hc} -m {HASH_MODE} -a 3 "{path}" {tail}').strip()


def _build_argv(exe, path, tail):
    """argv list for a hashcat run: program + fixed mode/attack + hash file + the tail's
    tokens (charset/mask flags). Pure -- the tail carries no quoting, so a plain split is
    exact. Running from argv (not a shell string) sidesteps cmd/PowerShell quoting."""
    return [exe, "-m", str(HASH_MODE), "-a", "3", path] + shlex.split(tail)


def _run_hashcat(path, tail, label):
    """Execute one hashcat command (built from `tail`) and return its exit code, or None
    if it can't be run / was aborted. Launches from hashcat's own folder when it's a
    portable install so it finds its OpenCL/ kernels/. Ctrl-C aborts just this run."""
    exe = shutil.which("hashcat")
    if not exe:
        print("  !! hashcat not on PATH -- can't run; copy the command above instead.")
        return None
    print(f"  >> running {label} ...  (Ctrl-C aborts this run)")
    try:
        return subprocess.run(_build_argv(exe, path, tail), cwd=_hashcat_dir()).returncode
    except KeyboardInterrupt:
        print("\n  (run aborted)")
        return None
    except OSError as e:
        print(f"  !! could not launch hashcat: {e}")
        return None


def _confirm(msg):
    """Yes/No prompt defaulting to No. EOF / Ctrl-C -> No."""
    try:
        return input(f"  {msg} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def positional_candidates(bssid, essid, keylen, case="upper"):
    """Per-position candidate chars for a MAC-derived hex key: align the BSSID's
    last <keylen> hex to the key, and the SSID's longest hex run to the key's tail.
    Returns a list of <keylen> sets. Where BSSID and SSID agree at a position the
    set is 1 char (a literal); where they diverge — typically the low byte — it's 2.

    Each set is emitted in the requested letter case (see _apply_case); 'mixed'
    doubles every letter-bearing position.

    This is the basis of the aggressive --positional mask. It collapses the
    keyspace enormously (measured median 4, max 64 across ~1400 real gateways),
    but it ASSUMES each key char comes from that position's BSSID/SSID char — true
    for MAC-derived schemes, NOT guaranteed for an unknown one."""
    b = bssid.upper()
    bpart = b[-keylen:] if len(b) >= keylen else b.rjust(keylen, "0")
    runs = [r.upper() for r in ssid_hex_runs(essid)]
    tail = (max(runs, key=len) if runs else "")[-keylen:]
    tstart = keylen - len(tail)
    cand = []
    for i in range(keylen):
        s = set()
        if i < len(bpart) and bpart[i] in HEX:
            s.add(bpart[i])
        if tstart <= i < keylen and tail[i - tstart] in HEX:
            s.add(tail[i - tstart])
        cand.append(_apply_case(s or set(HEX), case))
    return cand


def _positional_mask(cand, case="upper"):
    """Build the hashcat mask TAIL from per-position candidate sets: size-1 positions
    become literal mask chars, multi-char positions get custom charsets (-1..-4). Rare
    overflow (>4 distinct multi-char sets) widens a position to a built-in all-hex class
    (?H upper, ?h lower), which keeps the key in-keyspace. Returns (tail, keyspace).

    In 'mixed' mode there is no single built-in covering both cases, so an overflowing
    position can't be widened -- the tail is unrepresentable and this returns
    (None, keyspace); callers then fall back to the uniform command."""
    charsets, mask, ks = [], "", 1
    mixed_overflow = False
    for s in cand:
        ks *= len(s)
        if len(s) == 1:
            mask += next(iter(s))
            continue
        cs = "".join(sorted(s))
        if cs in charsets:
            mask += f"?{charsets.index(cs) + 1}"
        elif len(charsets) < 4:
            charsets.append(cs)
            mask += f"?{len(charsets)}"
        elif case == "lower":
            mask += "?h"                       # overflow: lowercase built-in hex
        elif case == "mixed":
            mixed_overflow = True              # no built-in covers both cases
        else:
            mask += "?H"                       # overflow: uppercase built-in hex
    if mixed_overflow:
        return None, ks
    args = " ".join(f"-{i + 1} {c}" for i, c in enumerate(charsets))
    return f"{args} {mask}", ks


def positional_command(path, cand, case="upper"):
    """Full runnable hashcat command from per-position candidate sets, or (None, keyspace)
    when the mask is unrepresentable (mixed-case overflow). Thin wrapper over
    _positional_mask + _hc_command."""
    tail, ks = _positional_mask(cand, case)
    if tail is None:
        return None, ks
    return _hc_command(path, tail), ks


def human_time(seconds):
    if seconds < 1:      return "< 1 s"
    if seconds < 90:     return f"{seconds:.1f} s"
    if seconds < 5400:   return f"{seconds/60:.1f} min"
    if seconds < 172800: return f"{seconds/3600:.1f} h"
    return f"{seconds/86400:.1f} days"


def scheme_defaults(essid):
    """(isp, max_len, case) hint for a recognised default-key SSID, else (None, None,
    None). Uses schemes.py when available (see _load_schemes). VIVO/VIVOFIBRA default
    keys are the MAC minus its 1st octet = 10 hex (VIVO uppercase, VIVOFIBRA lowercase);
    nothing else is hinted today."""
    if _SCHEMES is None:
        return None, None, None
    try:
        isp = _SCHEMES.detect(essid)
    except Exception:
        return None, None, None
    if isp == "VIVOFIBRA":
        return "VIVOFIBRA", 10, "lower"
    if isp == "VIVO":
        return "VIVO", 10, "upper"
    return None, None, None


def resolve_settings(essid, max_len, case):
    """Resolve the effective (isp, max_len, case) for one network: an explicit value
    (not None) always wins; otherwise a recognised scheme's hint applies; otherwise the
    global defaults (DEFAULT_MAX_LEN / 'upper')."""
    isp, s_len, s_case = scheme_defaults(essid)
    eff_len = max_len if max_len is not None else (s_len or DEFAULT_MAX_LEN)
    eff_case = case if case is not None else (s_case or "upper")
    return isp, eff_len, eff_case


def _maybe_run(path, uniform_tail, uniform_est, positional_tail, positional_ks, run_mode):
    """Drive the run cascade for one network: the fast positional mask first (when it's
    available), then the exhaustive uniform mask if positional finished without a hit.
    'ask' confirms each leg (the uniform prompt shows its estimate); 'auto' runs straight
    through. Stops as soon as a leg cracks (hashcat exit 0) or the user aborts."""
    if not shutil.which("hashcat"):
        return
    ask = (run_mode == "ask")
    if positional_tail is not None:
        if not ask or _confirm(f"Run the fast positional mask now? ({positional_ks} candidates)"):
            code = _run_hashcat(path, positional_tail, "positional mask")
            if code == 0:
                print("  >> cracked by the positional mask (see hashcat output / potfile).")
                return
            if code is None:
                return                          # aborted / could not launch
            print("  positional mask finished without a hit -> uniform fallback.")
    if ask and not _confirm(f"Run the exhaustive uniform mask now? (~{uniform_est})"):
        return
    if not ask:
        print(f"  (uniform mask ~{uniform_est})")
    if _run_hashcat(path, uniform_tail, "uniform mask") == 0:
        print("  >> cracked by the uniform mask (see hashcat output / potfile).")


def report(path, net, positional=False, max_len=None, case=None, run_mode="off"):
    bssid = net["bssid"]
    essid = net["essid"]
    isp, eff_len, eff_case = resolve_settings(essid, max_len, case)
    charset = hex_charset(bssid, essid, eff_case)

    bssid_fmt = ":".join(bssid[i:i+2] for i in range(0, 12, 2)).upper()
    runs = [r.upper() for r in ssid_hex_runs(essid)]
    print("-" * 70)
    print(f"  SSID     : {essid or '(hidden/none)'}")
    print(f"  BSSID    : {bssid_fmt}")
    print(f"  SSID hex : {', '.join(runs) or f'(no hex run >= {MIN_RUN})'}   (runs >= {MIN_RUN}; charset = BSSID hex + these)")
    if isp:
        auto = []
        if max_len is None:
            auto.append(f"max-len {eff_len}")
        if case is None and eff_case != "upper":
            auto.append(eff_case)
        if auto:
            print(f"  Scheme   : {isp} -> {', '.join(auto)}  (auto; override with --max-len / --case)")

    if not charset:
        print("  !! no hex characters found in BSSID/SSID -- cannot build a charset.")
        return

    n = len(charset)
    print(f"  Charset : {charset}   ({n} distinct hex chars, {eff_case}-case)")

    if MIN_LEN == eff_len:
        u_total = n ** MIN_LEN
        print(f"  Keyspace: {n}^{MIN_LEN} = {u_total:,} candidates")
        est = "   ".join(f"~{human_time(u_total/r)} @ {r//1000}K H/s" for r in RATES)
        print(f"  Est.    : {est}")
        u_tail = f"-1 {charset} {'?1' * MIN_LEN}"
    else:
        print(f"  Keyspace by length ({MIN_LEN}-{eff_len}):")
        u_total = 0
        for L in range(MIN_LEN, eff_len + 1):
            ks = n ** L
            u_total += ks
            print(f"    len {L:2}: {n}^{L} = {ks:,}   (~{human_time(ks/RATES[0])} @ {RATES[0]//1000}K)")
        print(f"    total : {u_total:,}   (~{human_time(u_total/RATES[0])} @ {RATES[0]//1000}K)")
        u_tail = (f"-1 {charset} --increment --increment-min {MIN_LEN} "
                  f"--increment-max {eff_len} {'?1' * eff_len}")
    u_est = human_time(u_total / RATES[0])
    print()
    print(f"  Command :\n    {_hc_command(path, u_tail)}")
    if not shutil.which("hashcat"):
        print("    (hashcat not on PATH -- run this from your hashcat folder so it"
              " finds its OpenCL/ kernels/, or add it to PATH.)")

    p_tail, ks_p = None, None
    if positional:
        p_tail, ks_p = _positional_mask(positional_candidates(bssid, essid, eff_len, eff_case), eff_case)
        print()
        if p_tail is None:
            print(f"  Positional (aggressive) - keyspace {ks_p} candidate(s), but needs >4")
            print("    distinct mixed-case charsets: not representable as one hashcat mask.")
            print("    Use the uniform command above (the guaranteed fallback).")
        else:
            print(f"  Positional (aggressive) - keyspace {ks_p} candidate(s):")
            print(f"    {_hc_command(path, p_tail)}")
            print(f"    ^ per-position charset from the aligned BSSID+SSID; assumes each")
            print(f"      key char sits at that position (true for MAC-derived schemes).")
            print(f"      The uniform command above is the exhaustive fallback.")

    if run_mode != "off":
        _maybe_run(path, u_tail, u_est, p_tail, ks_p, run_mode)


def _launched_standalone():
    """True when this script was double-clicked or a file was dragged onto it on
    Windows, so its console window would vanish the instant we return. False when
    run from an existing shell, where a keep-open pause would just annoy.

    Walks the parent-process chain: a shell ancestor (cmd/powershell/bash/...) ->
    run from a terminal -> False; an explorer.exe ancestor reached first -> GUI
    launch -> True. Falls back to "this process owns the console alone" when the walk
    is inconclusive."""
    if os.name != "nt":
        return False
    for name in _win_parent_chain():
        if name in _SHELLS:
            return False
        if name == "explorer.exe":
            return True
    try:
        import ctypes
        arr = (ctypes.c_uint * 4)()
        return ctypes.windll.kernel32.GetConsoleProcessList(arr, 4) <= 1
    except Exception:
        return False


def _clear():
    """Wipe the terminal (screen + scrollback) for a fresh redraw. Only on a real ANSI
    terminal; when piped it just prints the bar so output stays readable."""
    if C.on:
        sys.stdout.write("\033[2J\033[3J\033[H")   # clear screen + scrollback, cursor home
        sys.stdout.flush()
    else:
        print(f"{C.dim}{BAR}{C.reset}")


def _panel(positional, max_len, case, run_mode):
    """The launcher view: title, drop hint, the command list, and a live status line
    showing the current max-len / case / positional / run / hashcat state."""
    hc = f"{C.green}found{C.reset}" if shutil.which("hashcat") else f"{C.yellow}not found{C.reset}"
    o = C.yellow  # command tokens
    print(f"{C.dim}{BAR}{C.reset}")
    print(f"  {C.bold}charset_mask{C.reset}  {C.dim}- WPA hex-key mask builder{C.reset}")
    print(f"{C.dim}{BAR}{C.reset}")
    print("  Drag a .hc22000 file into this window (or paste its path), then Enter.")
    print(f"  {C.dim}Blank line or Ctrl-C to quit.{C.reset}")
    print()
    print(f"  {C.dim}Commands - type one here (or set at launch as a flag):{C.reset}")
    print(f"    {o}len N{C.reset}          max key length {MIN_LEN}-{MAX_WPA_LEN}  "
          f"{C.dim}(> {MIN_LEN} also tries longer keys){C.reset}")
    print(f"    {o}case MODE{C.reset}      charset case: {o}upper{C.reset} / {o}lower{C.reset} / "
          f"{o}mixed{C.reset}  {C.dim}(mixed = both cases, bigger keyspace){C.reset}")
    print(f"    {o}pos{C.reset}            toggle the aggressive per-position mask")
    print(f"    {o}run{C.reset} / {o}ask{C.reset} / {o}norun{C.reset}   run hashcat: auto / confirm each / just print "
          f"{C.dim}(positional first, then uniform){C.reset}")
    print(f"    {o}help{C.reset}           redraw this panel")
    if _SCHEMES is not None:
        print(f"  {C.dim}VIVO / VIVOFIBRA SSIDs auto-use max-len 10 (VIVOFIBRA lowercase) "
              f"unless you set len/case.{C.reset}")
    print()
    ml = max_len if max_len is not None else "auto"
    cs = case if case is not None else "auto"
    print(f"  {C.dim}max-len:{C.reset} {C.bold}{ml}{C.reset}   {C.dim}*{C.reset}   "
          f"{C.dim}case:{C.reset} {C.bold}{cs}{C.reset}   {C.dim}*{C.reset}   "
          f"{C.dim}positional:{C.reset} {C.bold}{'on' if positional else 'off'}{C.reset}   {C.dim}*{C.reset}   "
          f"{C.dim}run:{C.reset} {C.bold}{run_mode}{C.reset}   {C.dim}*{C.reset}   "
          f"{C.dim}hashcat:{C.reset} {hc}")


def _redraw(positional, max_len, case, run_mode, changed=None, note=None):
    """Clear and redraw the whole panel so a changed setting shows against a fresh view
    instead of stacking up. `changed` prints an obvious cue of what changed."""
    _clear()
    _panel(positional, max_len, case, run_mode)
    if changed:
        print(f"  {C.bold}{C.cyan}>> redrawn{C.reset}  {C.dim}({changed}){C.reset}")
    if note:
        print(note)


def _run(paths, positional, max_len=None, case=None, run_mode="off"):
    for path in paths:
        path = os.path.abspath(path)
        print("=" * 70)
        print(f"File: {path}")
        if not os.path.isfile(path):
            print("  !! not found")
            continue
        nets = parse_22000(path)
        if not nets:
            print("  !! no valid WPA*01/WPA*02 lines (is this a .hc22000?)")
            continue
        for i, net in enumerate(nets, 1):
            print(f"\nNetwork {i}/{len(nets)}")
            report(path, net, positional, max_len, case, run_mode)


def coerce_max_len(raw, current=DEFAULT_MAX_LEN):
    """Validate a max-length token: an integer in [MIN_LEN, MAX_WPA_LEN] (min is fixed).
    Returns (value, error): on any problem value is `current` (which may be None = auto)
    and error is a one-line message; on success error is None."""
    keep = current if current is not None else "auto"
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return current, (f"  !! max-len must be an integer {MIN_LEN}-{MAX_WPA_LEN} "
                         f"(got {raw!r}); keeping {keep}")
    if n < MIN_LEN or n > MAX_WPA_LEN:
        return current, f"  !! max-len must be {MIN_LEN}-{MAX_WPA_LEN} (got {n}); keeping {keep}"
    return n, None


def coerce_case(raw, current="upper"):
    """Validate a case token (upper|lower|mixed, case-insensitive). Returns (value, error)
    the same way coerce_max_len does (`current` may be None = auto)."""
    keep = current if current is not None else "auto"
    v = str(raw).strip().lower()
    if v in CASES:
        return v, None
    return current, f"  !! case must be {'|'.join(CASES)} (got {raw!r}); keeping {keep}"


# Single bare words the interactive menu accepts as commands (dash optional), so a
# user can type 'lower' / 'pos' / 'help' instead of 'case lower' / '--positional' etc.
_BARE_COMMANDS = {
    "pos": ("positional", None), "positional": ("positional", None),
    "-p": ("positional", None), "--positional": ("positional", None),
    "help": ("help", None), "h": ("help", None), "-h": ("help", None),
    "--help": ("help", None), "?": ("help", None),
    "upper": ("case", "upper"), "lower": ("case", "lower"), "mixed": ("case", "mixed"),
    "run": ("run", "auto"), "auto": ("run", "auto"), "-y": ("run", "auto"),
    "--run": ("run", "auto"), "ask": ("run", "ask"), "--ask": ("run", "ask"),
    "norun": ("run", "off"), "-n": ("run", "off"), "--no-run": ("run", "off"),
}


def parse_prompt_command(line):
    """Classify an interactive prompt line into (kind, value):
      'len N' / 'maxlen N'      -> ('len', token)
      'case MODE'               -> ('case', token)
      a bare word (see          -> ('case'|'positional'|'help', ...)
        _BARE_COMMANDS)
      anything else             -> ('path', line)   (a capture path; drag-drop stays intact)"""
    parts = line.split(None, 1)
    if len(parts) == 2:
        head = parts[0].lower()
        if head in ("len", "maxlen", "max-len"):
            return ("len", parts[1].strip())
        if head == "case":
            return ("case", parts[1].strip())
    hit = _BARE_COMMANDS.get(line.strip().lower())
    if hit:
        return hit
    return ("path", line)


def _parse_flags(argv):
    """Split argv into (positional, max_len, case, no_color, run_mode, files). Recognises
    --positional/-p, --max-len/-L N (and --max-len=N), --case MODE (and --case=MODE),
    --no-color, and the run mode -y/--run (auto) / --ask / -n/--no-run (off, the default);
    everything else is a file path. An invalid flag value prints a note and falls back."""
    positional, max_len, case, no_color, run_mode, files = False, None, None, False, "off", []
    i = 0
    while i < len(argv):
        a = argv[i]
        low = a.lower()
        if low in ("--positional", "-p"):
            positional = True
        elif low == "--no-color":
            no_color = True
        elif low in ("-y", "--run"):
            run_mode = "auto"
        elif low == "--ask":
            run_mode = "ask"
        elif low in ("-n", "--no-run"):
            run_mode = "off"
        elif low in ("--max-len", "-l"):
            i += 1
            max_len, err = coerce_max_len(argv[i] if i < len(argv) else "", max_len)
            if err:
                print(err)
        elif low.startswith("--max-len="):
            max_len, err = coerce_max_len(a.split("=", 1)[1], max_len)
            if err:
                print(err)
        elif low == "--case":
            i += 1
            case, err = coerce_case(argv[i] if i < len(argv) else "", case)
            if err:
                print(err)
        elif low.startswith("--case="):
            case, err = coerce_case(a.split("=", 1)[1], case)
            if err:
                print(err)
        else:
            files.append(a)
        i += 1
    return positional, max_len, case, no_color, run_mode, files


def main():
    global C
    argv = [a.strip().strip('"') for a in sys.argv[1:]]
    positional, max_len, case, no_color, run_mode, args = _parse_flags(argv)
    C = setup_color(not no_color)

    if args:
        # Files given on the command line (incl. dragged onto the .py icon).
        _run(args, positional, max_len, case, run_mode)
        if _launched_standalone():
            try:
                input("\nDone. Press Enter to close...")
            except (EOFError, KeyboardInterrupt):
                pass
        return

    # No files given: interactive menu that KEEPS THE WINDOW OPEN. Drop a file (or paste
    # a path) to analyse it; type a command (len / case / pos / run / help) to change
    # settings, which clears and redraws the panel with a cue. Blank line / Ctrl-C quits.
    _panel(positional, max_len, case, run_mode)
    while True:
        try:
            line = input(f"\n{C.dim}>{C.reset} ").strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        kind, val = parse_prompt_command(line)
        if kind == "path":
            _run([val], positional, max_len, case, run_mode)   # output stays below the panel
            continue
        changed = note = None
        if kind == "len":
            max_len, err = coerce_max_len(val, max_len)
            changed, note = (None, err) if err else (f"max-len -> {max_len}", None)
        elif kind == "case":
            case, err = coerce_case(val, case)
            changed, note = (None, err) if err else (f"case -> {case}", None)
        elif kind == "positional":
            positional = not positional
            changed = f"positional -> {'on' if positional else 'off'}"
        elif kind == "run":
            run_mode = val
            changed = f"run -> {run_mode}"
        elif kind == "help":
            changed = "help"
        _redraw(positional, max_len, case, run_mode, changed=changed, note=note)


if __name__ == "__main__":
    main()
