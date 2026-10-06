#!/usr/bin/env python3
"""Aggiornamenti: server locale che trova le app da aggiornare e le aggiorna in silenzio.

Fonti:
  - Homebrew (cask installate con brew, formule CLI)
  - Catalogo Homebrew per app installate a mano (sostituite con `brew install --cask --force`)
  - Mac App Store tramite `mas`
  - Feed Sparkle per le app che non stanno in nessuno dei precedenti

Solo libreria standard. Ascolta soltanto su 127.0.0.1.
"""

import concurrent.futures as cf
import datetime as dt
import glob
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = "1.6.0"   # tenere allineata con CHANGELOG.md
HOST, PORT = "127.0.0.1", 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser("~/Library/Caches/AggiornamentiMac")
CASK_API = "https://formulae.brew.sh/api/cask.json"
KEYCHAIN_SERVICE = "aggiornamenti-mac"
ASKPASS = os.path.join(ROOT, "askpass.sh")
SPARKLE_NS = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"
APP_DIRS = ["/Applications", "/Applications/Utilities", os.path.expanduser("~/Applications")]

SUPPORT = os.path.expanduser("~/Library/Application Support/AggiornamentiMac")
EXCLUDED_FILE = os.path.join(SUPPORT, "esclusi.json")
SETTINGS_FILE = os.path.join(SUPPORT, "impostazioni.json")
LAUNCH_LABEL = "com.aggiornamenti-mac"
LAUNCH_PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LAUNCH_LABEL}.plist")
PAGE_URL = f"http://{HOST}:{PORT}"

os.makedirs(CACHE, exist_ok=True)
os.makedirs(SUPPORT, exist_ok=True)

BREW = shutil.which("brew") or "/opt/homebrew/bin/brew"
MAS = shutil.which("mas") or "/opt/homebrew/bin/mas"
BREW_CACHE = os.environ.get("HOMEBREW_CACHE") or os.path.expanduser("~/Library/Caches/Homebrew")

ENV = dict(os.environ)
ENV.update({
    "HOMEBREW_NO_AUTO_UPDATE": "1",
    "HOMEBREW_NO_ENV_HINTS": "1",
    "HOMEBREW_NO_INSTALL_CLEANUP": "1",
    "HOMEBREW_COLOR": "0",
    "NONINTERACTIVE": "1",
    "SUDO_ASKPASS": ASKPASS,
    "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
})

lock = threading.Lock()
state = {
    "scanning": False,
    "scanned_at": None,
    "scan_error": None,
    "items": [],          # elenco aggiornamenti disponibili
    "jobs": {},           # id -> {status, log}
    "running": False,
    "batch": None,        # {total, done} del giro di aggiornamenti in corso
    "unchecked": [],      # app che nessuna fonte sa controllare
    "macos": [],          # aggiornamenti di sistema disponibili
    "cleaning": False,
}


# ---------------------------------------------------------------- esclusioni

def item_key(item):
    """Chiave stabile: un'app installata a mano e poi adottata da brew resta la stessa."""
    if item["kind"] in ("cask", "adopt"):
        return "cask:" + item["token"]
    return item["id"]


def load_excluded():
    try:
        with open(EXCLUDED_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_excluded(data):
    tmp = EXCLUDED_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, EXCLUDED_FILE)


# ---------------------------------------------------------------- impostazioni e pianificazione

DEFAULT_SETTINGS = {
    "daily_check": True,     # controllo giornaliero con notifica
    "check_time": "09:00",
    "auto_update": False,    # aggiornamento automatico notturno
    "auto_time": "03:00",
    "last_check_day": None,
    "last_auto_day": None,
    "last_auto": None,       # {at, updated, failed, postponed}
    "last_cleanup": None,    # {at, freed}
}


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return {**DEFAULT_SETTINGS, **json.load(f)}
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(data):
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_FILE)


def login_enabled():
    return os.path.exists(LAUNCH_PLIST)


def set_login(enabled):
    """Avvio all'accesso tramite LaunchAgent dell'utente."""
    domain = f"gui/{os.getuid()}"
    if not enabled:
        run(["launchctl", "bootout", f"{domain}/{LAUNCH_LABEL}"], timeout=30)
        if os.path.exists(LAUNCH_PLIST):
            os.remove(LAUNCH_PLIST)
        return
    log_path = os.path.expanduser("~/Library/Logs/AggiornamentiMac.log")
    plist = {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": [sys.executable, os.path.join(ROOT, "server.py")],
        "RunAtLoad": True,
        # riavvia solo se il server cade; se la porta è già occupata esce con 0 e si ferma
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
    }
    os.makedirs(os.path.dirname(LAUNCH_PLIST), exist_ok=True)
    with open(LAUNCH_PLIST, "wb") as f:
        plistlib.dump(plist, f)
    run(["launchctl", "bootout", f"{domain}/{LAUNCH_LABEL}"], timeout=30)
    run(["launchctl", "bootstrap", domain, LAUNCH_PLIST], timeout=30)


def notify(title, message):
    tn = shutil.which("terminal-notifier", path=ENV["PATH"])
    if tn:
        run([tn, "-title", title, "-message", message, "-open", PAGE_URL,
             "-group", "aggiornamenti-mac"], timeout=30)
    else:
        esc = lambda t: t.replace("\\", "\\\\").replace('"', '\\"')
        run(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}"'], timeout=30)


def visible_pending():
    excluded = load_excluded()
    with lock:
        return [i for i in state["items"] if not i.get("updated") and i.get("key") not in excluded]


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def start_scan_sync():
    """Esegue una scansione e aspetta che finisca; se ne è già in corso una, ne attende l'esito."""
    with lock:
        if state["running"]:
            return False
        already = state["scanning"]
        state["scanning"] = True
    if not already:
        do_scan()
        return True
    while True:
        time.sleep(2)
        with lock:
            if not state["scanning"]:
                return True


def scheduled_check():
    if not start_scan_sync():
        return
    todo = visible_pending()
    if todo:
        names = ", ".join(i["name"] for i in todo[:3]) + ("…" if len(todo) > 3 else "")
        notify(plural(len(todo), "aggiornamento disponibile", "aggiornamenti disponibili"), names)


def auto_update():
    if not start_scan_sync():
        return
    candidates = [i for i in visible_pending() if not i.get("major") and i.get("verified") is not False]
    ids, postponed = [], []
    for i in candidates:
        if i["kind"] in ("cask", "adopt", "sparkle") and running_app(i.get("bundle_id")):
            postponed.append(i["name"])   # mai chiudere un'app mentre la stai usando
        else:
            ids.append(i["id"])
    if ids:
        with lock:
            if state["running"] or state["scanning"]:
                return
            state["running"] = True
        do_updates(set(ids))
    with lock:
        updated = [i["name"] for i in state["items"] if i["id"] in ids and i.get("updated")]
        failed = [i["name"] for i in state["items"] if i["id"] in ids and not i.get("updated")]
    s = load_settings()
    s["last_auto"] = {"at": time.time(), "updated": updated, "failed": failed, "postponed": postponed}
    save_settings(s)
    if updated or failed or postponed:
        parts = []
        if updated:
            parts.append(plural(len(updated), "app aggiornata", "app aggiornate"))
        if failed:
            parts.append(plural(len(failed), "non riuscita", "non riuscite"))
        if postponed:
            parts.append(plural(len(postponed), "rimandata perché aperta", "rimandate perché aperte"))
        lc = load_settings().get("last_cleanup") or {}
        if ids and lc.get("freed"):
            parts.append(f"liberati {human(lc['freed'])}")
        notify("Aggiornamento automatico", ", ".join(parts))


def due(hhmm, last_day, now):
    try:
        h, m = map(int, hhmm.split(":"))
    except Exception:
        return False
    return last_day != now.date().isoformat() and now >= now.replace(hour=h, minute=m, second=0, microsecond=0)


def scheduler():
    """Controlla ogni 30 secondi se è ora del controllo o dell'aggiornamento automatico.
    Se il Mac dormiva all'ora prevista, recupera appena si risveglia."""
    while True:
        time.sleep(30)
        try:
            now = dt.datetime.now()
            today = now.date().isoformat()
            s = load_settings()
            if s["auto_update"] and due(s["auto_time"], s["last_auto_day"], now):
                s["last_auto_day"] = today
                s["last_check_day"] = today   # l'aggiornamento include già il controllo
                save_settings(s)
                auto_update()
            elif s["daily_check"] and due(s["check_time"], s["last_check_day"], now):
                s["last_check_day"] = today
                save_settings(s)
                scheduled_check()
        except Exception as e:
            print("scheduler:", e, flush=True)


# ---------------------------------------------------------------- utilità

def run(cmd, timeout=1800, env=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env or ENV)
    return p.returncode, re.sub(r"\x1b\[[0-9;]*m", "", (p.stdout or "") + (p.stderr or ""))


def run_stream(cmd, on_line, timeout=3600):
    """Come run(), ma passa ogni riga di output a on_line mentre il comando gira."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=ENV)
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    out, buf = [], b""
    try:
        while True:
            chunk = p.stdout.read1(4096)
            if not chunk:
                break
            buf += chunk
            *parts, buf = re.split(rb"[\r\n]", buf)
            for part in parts:
                line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", part.decode("utf-8", "replace")).rstrip()
                if line.strip():
                    out.append(line)
                    on_line(line)
        if buf.strip():
            out.append(buf.decode("utf-8", "replace"))
        return p.wait(), "\n".join(out)
    finally:
        timer.cancel()


def set_progress(jid, **kw):
    with lock:
        job = state["jobs"].get(jid)
        if job is not None:
            job.update(kw)


def remote_size(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AggiornamentiMac"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return int(r.headers.get("Content-Length") or 0) or None
    except Exception:
        return None


# fasi riconosciute nell'output di brew e mas: (espressione, fase, percentuale minima)
PHASES = [
    (r"==> (Fetching|Downloading)|Bottle Manifest|Downloading ", "Download", 3),
    (r"==> (Installing|Pouring|Upgrading)|Moving App|Moving Generic|Running installer|Installing ", "Installazione", 75),
    (r"Removing App|Backing App|Uninstalling|overwriting|Purging", "Sostituzione della versione precedente", 85),
    (r"==> (Linking|Caveats|Summary)|successfully|Upgraded|Installed ", "Rifinitura", 95),
]


def bottle_size(downloads, incomplete):
    """Dimensione di una bottle in download, letta dal manifest che brew scarica prima."""
    m = re.search(r"--(.+?)--(.+)\.bottle\.tar\.gz\.incomplete$", os.path.basename(incomplete))
    if not m:
        return None
    name, ref = m.groups()
    manifests = sorted(glob.glob(os.path.join(downloads, f"*--{glob.escape(name)}-*.bottle_manifest.json")),
                       key=os.path.getmtime, reverse=True)
    for path in manifests[:1]:
        try:
            with open(path) as f:
                for entry in json.load(f).get("manifests", []):
                    ann = entry.get("annotations", {})
                    if ann.get("org.opencontainers.image.ref.name") == ref:
                        return int(ann.get("sh.brew.bottle.size") or 0) or None
        except Exception:
            pass
    return None


def brew_progress(jid, total=None):
    """Segue le righe di brew e il file in download nella cache di Homebrew."""
    start = time.time()
    stop = threading.Event()
    cur = {"phase": "Preparazione", "floor": 1}
    downloads = os.path.join(BREW_CACHE, "downloads")

    def watch():
        while not stop.wait(0.5):
            if cur["phase"] != "Download":
                continue
            newest = None
            for f in glob.glob(os.path.join(downloads, "*.incomplete")):
                try:
                    st = os.stat(f)
                except OSError:
                    continue
                if st.st_mtime >= start - 1 and (newest is None or st.st_mtime > newest[0]):
                    newest = (st.st_mtime, st.st_size, f)
            if not newest:
                continue
            got = newest[1]
            size = total or bottle_size(downloads, newest[2])
            if size and got <= size:
                set_progress(jid, bytes=got, total=size, pct=round(3 + 67 * got / size, 1))
            elif total and got <= total:
                set_progress(jid, bytes=got, total=total, pct=round(3 + 67 * got / total, 1))
            else:
                set_progress(jid, bytes=got, total=None, pct=None)

    def on_line(line):
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s?%", line)
        for rx, phase, floor in PHASES:
            if re.search(rx, line):
                if floor >= cur["floor"]:
                    cur.update(phase=phase, floor=floor)
                    set_progress(jid, phase=phase, pct=floor if phase != "Download" else None,
                                 bytes=None, total=None)
                break
        if m and cur["phase"] == "Download" and float(m.group(1)) <= 100:
            set_progress(jid, pct=round(3 + 0.67 * float(m.group(1)), 1))

    threading.Thread(target=watch, daemon=True).start()
    return on_line, stop


def vparts(v):
    return [int(x) for x in re.findall(r"\d+", v or "")]


def newer(candidate, installed):
    a, b = vparts(candidate), vparts(installed)
    if not a or not b:
        return False
    return a > b


def is_major(candidate, installed):
    a, b = vparts(candidate), vparts(installed)
    return bool(a and b and a[0] != b[0])


def has_password():
    rc, _ = run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE], timeout=10)
    return rc == 0


def read_info(app):
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
            return plistlib.load(f)
    except Exception:
        return None


def installed_apps():
    apps = []
    for d in APP_DIRS:
        for app in sorted(glob.glob(os.path.join(d, "*.app"))):
            info = read_info(app)
            if not info:
                continue
            apps.append({
                "path": app,
                "file": os.path.basename(app),
                "name": os.path.basename(app)[:-4],
                "bundle_id": info.get("CFBundleIdentifier", ""),
                "version": str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""),
                "build": str(info.get("CFBundleVersion") or ""),
                "feed": info.get("SUFeedURL"),
                "mas": os.path.exists(os.path.join(app, "Contents", "_MASReceipt")),
            })
    return apps


_blobs = []   # (cask, testo json minuscolo) per cercare i bundle id


def cask_by_bundle_id(app):
    """Per le cask che installano un .pkg il nome dell'app non compare: cerco il bundle id
    nella definizione (uninstall, zap). Se ci sono più candidati scelgo quello col nome giusto."""
    bid = (app["bundle_id"] or "").lower()
    if not bid:
        return None
    rx = re.compile(r'["/]' + re.escape(bid) + r'["/.]')
    cands = [c for c, blob in _blobs if bid in blob and rx.search(blob)]
    if len(cands) == 1:
        return cands[0]
    slug = re.sub(r"[^a-z0-9]+", "-", app["name"].lower()).strip("-")
    named = [c for c in cands if c["token"] == slug or app["name"].lower() in [n.lower() for n in c.get("name", [])]]
    return named[0] if len(named) == 1 else None


def installed_for_compare(latest, a):
    """Alcune app (Microsoft) mostrano 16.113.3 ma il catalogo usa la build 16.113.26092714:
    se la build ha lo stesso formato della versione del catalogo, confronto con quella."""
    lp, bp = vparts(latest), vparts(a["build"])
    if bp and len(bp) == len(lp) and bp[0] == lp[0]:
        return a["build"]
    return a["version"]


def cask_catalog():
    path = os.path.join(CACHE, "cask.json")
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < 6 * 3600
    if not fresh:
        try:
            req = urllib.request.Request(CASK_API, headers={"User-Agent": "AggiornamentiMac"})
            with urllib.request.urlopen(req, timeout=60) as r, open(path + ".tmp", "wb") as f:
                shutil.copyfileobj(r, f)
            os.replace(path + ".tmp", path)
        except Exception:
            if not os.path.exists(path):
                return {}
    with open(path) as f:
        data = json.load(f)
    by_app = {}
    _blobs.clear()
    for c in data:
        if c.get("disabled"):
            continue
        _blobs.append((c, json.dumps(c).lower()))
        for art in c.get("artifacts", []):
            for x in art.get("app", []) if isinstance(art, dict) else []:
                if isinstance(x, str):
                    by_app.setdefault(os.path.basename(x), c)
    return by_app


# ---------------------------------------------------------------- scansione

def scan_brew():
    items, managed = [], set()
    rc, out = run([BREW, "list", "--cask", "-1"], timeout=120)
    if rc == 0:
        managed = set(out.split())
    rc, out = run([BREW, "outdated", "--json=v2", "--greedy"], timeout=300)
    try:
        data = json.loads(out[out.index("{"):])
    except Exception:
        return items, managed
    for c in data.get("casks", []):
        items.append({
            "id": "cask:" + c["name"], "kind": "cask", "token": c["name"],
            "name": c["name"], "installed": ", ".join(c["installed_versions"]),
            "latest": c["current_version"], "source": "Homebrew",
        })
    for f in data.get("formulae", []):
        if f.get("pinned"):
            continue
        items.append({
            "id": "formula:" + f["name"], "kind": "formula", "token": f["name"],
            "name": f["name"], "installed": ", ".join(f["installed_versions"]),
            "latest": f["current_version"], "source": "Riga di comando",
        })
    return items, managed


def scan_mas():
    items = []
    if not os.path.exists(MAS):
        return items
    rc, out = run([MAS, "outdated"], timeout=180)
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+?)\s+\((.+?)\s+->\s+(.+?)\)", line)
        if m:
            items.append({
                "id": "mas:" + m.group(1), "kind": "mas", "token": m.group(1),
                "name": m.group(2), "installed": m.group(3), "latest": m.group(4),
                "source": "App Store",
            })
    return items


def sparkle_latest(feed):
    req = urllib.request.Request(feed, headers={"User-Agent": "AggiornamentiMac"})
    with urllib.request.urlopen(req, timeout=20) as r:
        root = ET.fromstring(r.read())
    best = None
    for item in root.iter("item"):
        if item.find(SPARKLE_NS + "channel") is not None:
            continue  # beta e simili
        enc = item.find("enclosure")
        if enc is None or not enc.get("url"):
            continue
        build = enc.get(SPARKLE_NS + "version") or (item.findtext(SPARKLE_NS + "version") or "")
        short = enc.get(SPARKLE_NS + "shortVersionString") or (item.findtext(SPARKLE_NS + "shortVersionString") or build)
        if not build:
            continue
        if best is None or vparts(build) > vparts(best["build"]):
            best = {"build": build, "short": short, "url": enc.get("url")}
    return best


def scan_apps(managed_casks):
    catalog = cask_catalog()
    items, sparkle, unchecked = [], [], []

    def skip(a, reason):
        if not a["bundle_id"].startswith("com.apple."):   # le app Apple arrivano con macOS
            unchecked.append({"name": a["name"], "path": a["path"], "version": a["version"],
                              "bundle_id": a["bundle_id"], "reason": reason})

    for a in installed_apps():
        if a["mas"] or a["bundle_id"].startswith(("com.google.Chrome.app.", "com.google.drivefs.shortcuts.")):
            continue   # App Store a parte; web app di Chrome e scorciatoie di Drive seguono l'app madre
        cask = catalog.get(a["file"]) or cask_by_bundle_id(a)
        if cask and cask["token"] in managed_casks:
            continue  # già coperta da `brew outdated`
        if cask:
            latest = str(cask["version"]).split(",")[0]
            if latest == "latest" or not vparts(latest):
                if a["feed"] and str(a["feed"]).startswith("https://"):
                    sparkle.append(a)
                else:
                    skip(a, "Il catalogo Homebrew non indica il numero di versione")
                continue
            current = installed_for_compare(latest, a)
            if not current or not vparts(current):
                skip(a, "L'app non dichiara la sua versione")
                continue
            if newer(latest, current):
                items.append({
                    "id": "adopt:" + cask["token"], "kind": "adopt", "token": cask["token"],
                    "name": a["name"], "installed": current, "latest": latest,
                    "source": "Homebrew", "path": a["path"], "bundle_id": a["bundle_id"],
                    "major": is_major(latest, current),
                    # il bundle id compare nella definizione della cask: abbinamento affidabile
                    "verified": bool(a["bundle_id"]) and a["bundle_id"].lower() in json.dumps(cask).lower(),
                })
            continue
        if a["feed"] and str(a["feed"]).startswith("https://"):
            sparkle.append(a)
        elif a["feed"]:
            skip(a, "Canale di aggiornamento non sicuro (http)")
        else:
            skip(a, "Nessuna fonte di aggiornamento conosciuta")

    def check(a):
        try:
            best = sparkle_latest(a["feed"])
        except Exception:
            skip(a, "Il sito dello sviluppatore non ha risposto")
            return None
        if not best:
            skip(a, "Il canale di aggiornamento non contiene versioni leggibili")
            return None
        if best and newer(best["build"], a["build"]):
            return {
                "id": "sparkle:" + a["bundle_id"], "kind": "sparkle", "token": a["bundle_id"],
                "name": a["name"], "installed": a["version"], "latest": best["short"],
                "source": "Sito dello sviluppatore", "path": a["path"], "bundle_id": a["bundle_id"],
                "url": best["url"], "major": is_major(best["short"], a["version"]),
            }
        return None

    with cf.ThreadPoolExecutor(8) as ex:
        items += [r for r in ex.map(check, sparkle) if r]
    unchecked.sort(key=lambda u: u["name"].lower())
    return items, unchecked


def attach_paths(items):
    """Associa a ogni voce il percorso dell'app (per l'icona) quando manca."""
    by_file = {a["file"]: a for a in installed_apps()}
    by_id = {a["bundle_id"]: a for a in by_file.values()}
    catalog = None
    for it in items:
        if it.get("path"):
            continue
        if it["kind"] == "mas":
            for a in by_file.values():
                if a["mas"] and a["name"] == it["name"]:
                    it["path"] = a["path"]
        elif it["kind"] == "cask":
            catalog = catalog or cask_catalog_by_token()
            c = catalog.get(it["token"])
            for art in (c or {}).get("artifacts", []):
                for x in art.get("app", []) if isinstance(art, dict) else []:
                    if isinstance(x, str) and os.path.basename(x) in by_file:
                        a = by_file[os.path.basename(x)]
                        it["path"], it["name"], it["bundle_id"] = a["path"], a["name"], a["bundle_id"]
    return items


_by_token = {}


def cask_by_token(token):
    if not _by_token:
        _by_token.update(cask_catalog_by_token())
    return _by_token.get(token) or {}


def cask_catalog_by_token():
    path = os.path.join(CACHE, "cask.json")
    try:
        with open(path) as f:
            return {c["token"]: c for c in json.load(f)}
    except Exception:
        return {}


def scan_macos():
    rc, out = run(["softwareupdate", "-l"], timeout=180)
    return [m.group(1).strip() for m in re.finditer(r"Title:\s*([^,]+(?:, Version: [^,]+)?)", out)]


def do_scan():
    _by_token.clear()
    try:
        run([BREW, "update", "--quiet"], timeout=300, env={**ENV, "HOMEBREW_NO_AUTO_UPDATE": ""})
        with cf.ThreadPoolExecutor(3) as ex:
            f_brew = ex.submit(scan_brew)
            f_mas = ex.submit(scan_mas)
            f_os = ex.submit(scan_macos)
            brew_items, managed = f_brew.result()
            mas_items = f_mas.result()
            app_items, unchecked = scan_apps(managed)
            macos = f_os.result()
        items = brew_items + mas_items + app_items
        items = attach_paths(items)
        for it in items:
            it["key"] = item_key(it)
        order = {"cask": 0, "adopt": 0, "sparkle": 0, "mas": 0, "formula": 1}
        items.sort(key=lambda i: (order[i["kind"]], i["name"].lower()))
        with lock:
            state["unchecked"] = unchecked
            state["macos"] = macos
            state["items"] = items
            state["scan_error"] = None
            state["jobs"] = {k: v for k, v in state["jobs"].items() if v["status"] == "running"}
    except Exception as e:
        with lock:
            state["scan_error"] = str(e)
    finally:
        with lock:
            state["scanning"] = False
            state["scanned_at"] = time.time()


# ---------------------------------------------------------------- aggiornamento

def running_app(bundle_id):
    if not bundle_id:
        return False
    rc, out = run(["osascript", "-e", f'application id "{bundle_id}" is running'], timeout=15)
    return out.strip() == "true"


def quit_app(bundle_id):
    run(["osascript", "-e", f'tell application id "{bundle_id}" to quit'], timeout=30)
    for _ in range(20):
        if not running_app(bundle_id):
            return
        time.sleep(0.5)


def team_id(app):
    rc, out = run(["codesign", "-dv", app], timeout=30)
    m = re.search(r"TeamIdentifier=(\S+)", out)
    return m.group(1) if m and m.group(1) != "not" else None


def install_pkg(pkg, old_team, jid, log):
    """Installa un .pkg solo se firmato da Apple Developer ID dello stesso sviluppatore dell'app."""
    set_progress(jid, phase="Verifica della firma", pct=76)
    rc, out = run(["pkgutil", "--check-signature", pkg], timeout=120)
    m = re.search(r"Developer ID Installer: .*\((\w+)\)", out)
    if rc != 0 or not m:
        log("Pacchetto senza firma Developer ID valida: annullato per sicurezza\n" + out)
        return False
    if old_team and m.group(1) != old_team:
        log(f"Pacchetto firmato da {m.group(1)} invece di {old_team}: annullato per sicurezza")
        return False
    if not has_password():
        log("Questo aggiornamento è un pacchetto di installazione e serve la password di amministratore: impostala in basso nella pagina.")
        return False
    set_progress(jid, phase="Installazione", pct=82)
    rc, out = run(["sudo", "-A", "installer", "-pkg", pkg, "-target", "/"])
    log(out)
    return rc == 0


def install_sparkle(item, log):
    url, dest, jid = item["url"], item["path"], item["id"]
    old_team = team_id(dest)
    work = tempfile.mkdtemp(prefix="agg-", dir=CACHE)
    try:
        fname = os.path.basename(urlparse(url).path) or "download"
        archive = os.path.join(work, fname)
        log(f"Scarico {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "AggiornamentiMac"})
        with urllib.request.urlopen(req, timeout=600) as r, open(archive, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0) or None
            got, last = 0, 0
            set_progress(jid, phase="Download", pct=None if not total else 3, bytes=0, total=total)
            while chunk := r.read(256 * 1024):
                f.write(chunk)
                got += len(chunk)
                if time.time() - last > 0.3:
                    last = time.time()
                    set_progress(jid, bytes=got, pct=round(3 + 67 * got / total, 1) if total else None)
        set_progress(jid, phase="Apertura del pacchetto", pct=72, bytes=None, total=None)
        lower = fname.lower()
        new_app, mount = None, None
        if lower.endswith((".pkg", ".mpkg")):
            return install_pkg(archive, old_team, jid, log)
        if lower.endswith(".dmg"):
            mount = os.path.join(work, "mnt")
            rc, out = run(["hdiutil", "attach", "-nobrowse", "-noautoopen", "-mountpoint", mount, archive])
            if rc != 0:
                log(out)
                return False
            search = mount
        elif lower.endswith((".zip", ".tar.gz", ".tgz", ".tar.xz", ".tar.bz2")):
            out_dir = os.path.join(work, "x")
            os.makedirs(out_dir)
            cmd = ["ditto", "-x", "-k", archive, out_dir] if lower.endswith(".zip") else ["tar", "-xf", archive, "-C", out_dir]
            rc, out = run(cmd)
            if rc != 0:
                log(out)
                return False
            search = out_dir
        else:
            log("Formato non gestito: " + fname)
            return False
        try:
            target = os.path.basename(dest)
            cands = glob.glob(os.path.join(search, "*.app")) + glob.glob(os.path.join(search, "*", "*.app"))
            new_app = next((c for c in cands if os.path.basename(c) == target), cands[0] if cands else None)
            if not new_app:
                # alcuni sviluppatori (es. NordVPN) mettono nell'archivio un installer .pkg
                pkgs = glob.glob(os.path.join(search, "*.pkg")) + glob.glob(os.path.join(search, "*", "*.pkg"))
                if pkgs:
                    return install_pkg(pkgs[0], old_team, jid, log)
                log("Nessuna app né pacchetto di installazione trovati nell'archivio")
                return False
            set_progress(jid, phase="Verifica della firma", pct=78)
            new_team = team_id(new_app)
            if old_team and new_team != old_team:
                log(f"Firma diversa ({new_team} invece di {old_team}): annullato per sicurezza")
                return False
            rc, out = run(["codesign", "--verify", "--deep", "--strict", new_app], timeout=300)
            if rc != 0:
                log("Firma non valida: " + out)
                return False
            set_progress(jid, phase="Installazione", pct=88)
            staged = os.path.join(work, "staged.app")
            run(["ditto", new_app, staged])
            backup = os.path.join(work, "old.app")
            os.rename(dest, backup)
            rc, out = run(["ditto", staged, dest])
            if rc != 0:
                os.rename(backup, dest)
                log(out)
                return False
            run(["xattr", "-dr", "com.apple.quarantine", dest])
            return True
        finally:
            if mount:
                run(["hdiutil", "detach", "-force", mount])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def update_one(item):
    jid = item["id"]
    lines = []

    def log(text):
        text = text.rstrip()
        if text.strip():
            lines.append(text)
            with lock:
                state["jobs"][jid]["log"] = "\n".join(lines)[-6000:]

    bid = item.get("bundle_id")
    was_running = item["kind"] in ("cask", "adopt", "sparkle") and running_app(bid)
    if was_running:
        set_progress(jid, phase=f"Chiusura di {item['name']}", pct=1)
        log(f"Chiudo {item['name']}")
        quit_app(bid)

    kind, token = item["kind"], item["token"]
    cmds = {
        "cask": [BREW, "upgrade", "--cask", "--greedy", token],
        "formula": [BREW, "upgrade", "--formula", token],
        "adopt": [BREW, "install", "--cask", "--force", token],
        "mas": ["sudo", "-A", MAS, "update", token],
    }
    ok = False
    try:
        if kind == "sparkle":
            ok = install_sparkle(item, log)
        else:
            total = None
            if kind in ("cask", "adopt"):
                total = remote_size(cask_by_token(token).get("url") or "")
            on_line, stop = brew_progress(jid, total)
            try:
                rc, _ = run_stream(cmds[kind], lambda l: (log(l), on_line(l)))
            finally:
                stop.set()
            ok = rc == 0
    except Exception as e:
        log(str(e))

    if was_running and bid:
        set_progress(jid, phase=f"Riapertura di {item['name']}", pct=98)
        run(["open", "-g", "-b", bid], timeout=30)

    if not ok and "sudo" in "\n".join(lines).lower() and not has_password():
        log("Serve la password di amministratore: impostala in basso nella pagina.")
    with lock:
        state["jobs"][jid]["status"] = "done" if ok else "error"
        if ok:
            state["items"] = [i for i in state["items"] if i["id"] != jid] + [{**item, "updated": True}]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}".replace(".0 ", " ") if unit != "B" else f"{n} B"
        n /= 1024


def cleanup():
    """Cancella installer scaricati, vecchie versioni e file temporanei. Restituisce i byte liberati."""
    with lock:
        state["cleaning"] = True
    freed = 0
    try:
        rc, out = run([BREW, "cleanup", "--prune=all", "-s"], timeout=1800)
        m = re.search(r"freed approximately ([\d.]+)\s*([KMGT]?B)", out)
        if m:
            freed += int(float(m.group(1)) * 1024 ** "BKMGT".index(m.group(2)[0]))
        # file temporanei lasciati da aggiornamenti interrotti
        for d in glob.glob(os.path.join(CACHE, "agg-*")):
            size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs
                       if not os.path.islink(os.path.join(r, f)))
            shutil.rmtree(d, ignore_errors=True)
            freed += size
        # icone di versioni ormai sostituite: si rigenerano al bisogno
        icons = os.path.join(CACHE, "icons")
        if os.path.isdir(icons):
            for f in glob.glob(os.path.join(icons, "*.png")):
                if time.time() - os.path.getmtime(f) > 7 * 86400:
                    freed += os.path.getsize(f)
                    os.remove(f)
    except Exception as e:
        print("cleanup:", e, flush=True)
    s = load_settings()
    s["last_cleanup"] = {"at": time.time(), "freed": freed}
    save_settings(s)
    with lock:
        state["cleaning"] = False
    return freed


def do_updates(ids):
    with lock:
        todo = [i for i in state["items"] if i["id"] in ids and not i.get("updated")]
        for i in todo:
            state["jobs"][i["id"]] = {"status": "queued", "log": "", "phase": None,
                                      "pct": None, "bytes": None, "total": None}
        state["batch"] = {"total": len(todo), "done": 0}
    for item in todo:
        with lock:
            state["jobs"][item["id"]].update(status="running", phase="Preparazione", pct=0)
        update_one(item)
        with lock:
            state["batch"]["done"] += 1
    if todo:
        cleanup()
    with lock:
        state["running"] = False


# ---------------------------------------------------------------- icone

def icon_png(app):
    app = os.path.realpath(app)
    if not any(app.startswith(os.path.realpath(d) + "/") for d in APP_DIRS) or not app.endswith(".app"):
        return None
    key = hashlib.sha1((app + str(os.path.getmtime(app))).encode()).hexdigest()
    out = os.path.join(CACHE, "icons", key + ".png")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    info = read_info(app) or {}
    name = info.get("CFBundleIconFile") or ""
    if name and not name.endswith(".icns"):
        name += ".icns"
    icns = os.path.join(app, "Contents", "Resources", name) if name else ""
    if not os.path.exists(icns):
        found = glob.glob(os.path.join(app, "Contents", "Resources", "*.icns"))
        icns = found[0] if found else ""
    if not icns:
        return None
    rc, _ = run(["sips", "-s", "format", "png", "-Z", "96", icns, "--out", out], timeout=30)
    return out if rc == 0 and os.path.exists(out) else None


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def snapshot(self):
        with lock:
            return {
                "scanning": state["scanning"], "scanned_at": state["scanned_at"],
                "scan_error": state["scan_error"], "items": state["items"],
                "jobs": state["jobs"], "running": state["running"], "batch": state["batch"],
                "cleaning": state["cleaning"],
                "version": VERSION,
                "password": has_password(),
                "excluded": load_excluded(),
                "unchecked": state["unchecked"], "macos": state["macos"],
                "settings": {**load_settings(), "login": login_enabled(),
                             "notifier": bool(shutil.which("terminal-notifier", path=ENV["PATH"]))},
            }

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/api/state":
            return self.send(200, self.snapshot())
        if u.path == "/api/icon":
            p = parse_qs(u.query).get("path", [""])[0]
            png = icon_png(p) if p else None
            if not png:
                return self.send(404, b"", "image/png")
            with open(png, "rb") as f:
                return self.send(200, f.read(), "image/png")
        self.send(404, {"error": "not found"})

    def do_POST(self):
        # solo richieste dalla pagina stessa
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            return self.send(403, {"error": "forbidden"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        u = urlparse(self.path)
        if u.path == "/api/scan":
            with lock:
                if not state["scanning"] and not state["running"]:
                    state["scanning"] = True
                    threading.Thread(target=do_scan, daemon=True).start()
            return self.send(200, self.snapshot())
        if u.path == "/api/update":
            ids = set(body.get("ids") or [])
            with lock:
                if state["running"] or state["scanning"] or not ids:
                    return self.send(409, {"error": "busy"})
                state["running"] = True
            threading.Thread(target=do_updates, args=(ids,), daemon=True).start()
            return self.send(200, self.snapshot())
        if u.path == "/api/settings":
            s = load_settings()
            now = dt.datetime.now()
            for flag, tkey, dkey in (("daily_check", "check_time", "last_check_day"),
                                     ("auto_update", "auto_time", "last_auto_day")):
                changed = False
                if flag in body and bool(body[flag]) != s[flag]:
                    s[flag] = bool(body[flag])
                    changed = True
                if tkey in body and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(body[tkey])):
                    changed = changed or s[tkey] != body[tkey]
                    s[tkey] = body[tkey]
                if changed:
                    # se l'orario di oggi è già passato si parte domani, mai subito
                    h, m = map(int, s[tkey].split(":"))
                    passed = now >= now.replace(hour=h, minute=m, second=0, microsecond=0)
                    s[dkey] = now.date().isoformat() if passed else None
            save_settings(s)
            if "login" in body:
                set_login(bool(body["login"]))
            return self.send(200, self.snapshot())
        if u.path == "/api/cleanup":
            with lock:
                if state["running"] or state["scanning"] or state["cleaning"]:
                    return self.send(409, {"error": "Attendi la fine dell'operazione in corso"})
                state["running"] = True
            def job():
                try:
                    cleanup()
                finally:
                    with lock:
                        state["running"] = False
            threading.Thread(target=job, daemon=True).start()
            return self.send(200, self.snapshot())
        if u.path == "/api/notify-test":
            notify("Aggiornamenti", "Le notifiche funzionano. Un clic qui apre la pagina.")
            return self.send(200, self.snapshot())
        if u.path == "/api/open-software-update":
            run(["open", "x-apple.systempreferences:com.apple.Software-Update-Settings.extension"], timeout=15)
            return self.send(200, self.snapshot())
        if u.path == "/api/exclude":
            key = str(body.get("key") or "")
            if not key:
                return self.send(400, {"error": "chiave mancante"})
            with lock:
                excluded = load_excluded()
                if body.get("exclude"):
                    excluded[key] = {
                        "name": str(body.get("name") or key),
                        "path": body.get("path") or None,
                        "kind": body.get("kind") or None,
                        "since": time.time(),
                    }
                else:
                    excluded.pop(key, None)
                save_excluded(excluded)
            return self.send(200, self.snapshot())
        if u.path == "/api/password":
            pw = body.get("password") or ""
            if not pw:
                run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE], timeout=10)
                return self.send(200, self.snapshot())
            # verifica la password prima di salvarla
            p = subprocess.run(["sudo", "-S", "-k", "-p", "", "true"], input=pw + "\n",
                               capture_output=True, text=True, timeout=20)
            if p.returncode != 0:
                return self.send(400, {"error": "Password non corretta"})
            # via stdin, così la password non compare nella lista dei processi
            esc = pw.replace("\\", "\\\\").replace('"', '\\"')
            cmd = (f'add-generic-password -U -s {KEYCHAIN_SERVICE} '
                   f'-a {os.environ.get("USER", "user")} -w "{esc}"\n')
            subprocess.run(["security", "-i"], input=cmd, capture_output=True, text=True, timeout=10)
            return self.send(200, self.snapshot())
        self.send(404, {"error": "not found"})


def main():
    os.chmod(ASKPASS, 0o755)
    with lock:
        state["scanning"] = True
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print("Porta già in uso: Aggiornamenti è già attivo.", flush=True)
        sys.exit(0)
    threading.Thread(target=do_scan, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    for d in glob.glob(os.path.join(CACHE, "agg-*")):
        shutil.rmtree(d, ignore_errors=True)
    print(f"Aggiornamenti su http://{HOST}:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
