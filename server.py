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
import glob
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST, PORT = "127.0.0.1", 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser("~/Library/Caches/AggiornamentiMac")
CASK_API = "https://formulae.brew.sh/api/cask.json"
KEYCHAIN_SERVICE = "aggiornamenti-mac"
ASKPASS = os.path.join(ROOT, "askpass.sh")
SPARKLE_NS = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"
APP_DIRS = ["/Applications", "/Applications/Utilities", os.path.expanduser("~/Applications")]

os.makedirs(CACHE, exist_ok=True)

BREW = shutil.which("brew") or "/opt/homebrew/bin/brew"
MAS = shutil.which("mas") or "/opt/homebrew/bin/mas"

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
}


# ---------------------------------------------------------------- utilità

def run(cmd, timeout=1800, env=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env or ENV)
    return p.returncode, re.sub(r"\x1b\[[0-9;]*m", "", (p.stdout or "") + (p.stderr or ""))


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
    for c in data:
        if c.get("disabled"):
            continue
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
    items, sparkle = [], []
    for a in installed_apps():
        if a["mas"]:
            continue
        cask = catalog.get(a["file"])
        if cask and cask["token"] in managed_casks:
            continue  # già coperta da `brew outdated`
        if cask:
            latest = str(cask["version"]).split(",")[0]
            if latest != "latest" and a["version"] and newer(latest, a["version"]):
                items.append({
                    "id": "adopt:" + cask["token"], "kind": "adopt", "token": cask["token"],
                    "name": a["name"], "installed": a["version"], "latest": latest,
                    "source": "Homebrew", "path": a["path"], "bundle_id": a["bundle_id"],
                    "major": is_major(latest, a["version"]),
                    # il bundle id compare nella definizione della cask: abbinamento affidabile
                    "verified": bool(a["bundle_id"]) and a["bundle_id"].lower() in json.dumps(cask).lower(),
                })
            continue
        if a["feed"] and str(a["feed"]).startswith("https://"):
            sparkle.append(a)

    def check(a):
        try:
            best = sparkle_latest(a["feed"])
        except Exception:
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
    return items


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


def cask_catalog_by_token():
    path = os.path.join(CACHE, "cask.json")
    try:
        with open(path) as f:
            return {c["token"]: c for c in json.load(f)}
    except Exception:
        return {}


def do_scan():
    try:
        run([BREW, "update", "--quiet"], timeout=300, env={**ENV, "HOMEBREW_NO_AUTO_UPDATE": ""})
        with cf.ThreadPoolExecutor(2) as ex:
            f_brew = ex.submit(scan_brew)
            f_mas = ex.submit(scan_mas)
            brew_items, managed = f_brew.result()
            mas_items = f_mas.result()
        items = brew_items + mas_items + scan_apps(managed)
        items = attach_paths(items)
        order = {"cask": 0, "adopt": 0, "sparkle": 0, "mas": 0, "formula": 1}
        items.sort(key=lambda i: (order[i["kind"]], i["name"].lower()))
        with lock:
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


def install_sparkle(item, log):
    url, dest = item["url"], item["path"]
    old_team = team_id(dest)
    work = tempfile.mkdtemp(prefix="agg-", dir=CACHE)
    try:
        fname = os.path.basename(urlparse(url).path) or "download"
        archive = os.path.join(work, fname)
        log(f"Scarico {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "AggiornamentiMac"})
        with urllib.request.urlopen(req, timeout=600) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        lower = fname.lower()
        new_app, mount = None, None
        if lower.endswith((".pkg", ".mpkg")):
            rc, out = run(["sudo", "-A", "installer", "-pkg", archive, "-target", "/"])
            log(out)
            return rc == 0
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
                log("Nessuna app trovata nell'archivio")
                return False
            new_team = team_id(new_app)
            if old_team and new_team != old_team:
                log(f"Firma diversa ({new_team} invece di {old_team}): annullato per sicurezza")
                return False
            rc, out = run(["codesign", "--verify", "--deep", "--strict", new_app], timeout=300)
            if rc != 0:
                log("Firma non valida: " + out)
                return False
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
        text = text.strip()
        if text:
            lines.append(text)
            with lock:
                state["jobs"][jid]["log"] = "\n".join(lines)[-6000:]

    bid = item.get("bundle_id")
    was_running = item["kind"] in ("cask", "adopt", "sparkle") and running_app(bid)
    if was_running:
        log(f"Chiudo {item['name']}")
        quit_app(bid)

    kind, token = item["kind"], item["token"]
    ok = False
    try:
        if kind == "cask":
            rc, out = run([BREW, "upgrade", "--cask", "--greedy", token]); log(out); ok = rc == 0
        elif kind == "formula":
            rc, out = run([BREW, "upgrade", "--formula", token]); log(out); ok = rc == 0
        elif kind == "adopt":
            rc, out = run([BREW, "install", "--cask", "--force", token]); log(out); ok = rc == 0
        elif kind == "mas":
            rc, out = run(["sudo", "-A", MAS, "update", token]); log(out); ok = rc == 0
        elif kind == "sparkle":
            ok = install_sparkle(item, log)
    except Exception as e:
        log(str(e))

    if was_running and bid:
        run(["open", "-g", "-b", bid], timeout=30)

    if not ok and "sudo" in "\n".join(lines).lower() and not has_password():
        log("Serve la password di amministratore: impostala in basso nella pagina.")
    with lock:
        state["jobs"][jid]["status"] = "done" if ok else "error"
        if ok:
            state["items"] = [i for i in state["items"] if i["id"] != jid] + [{**item, "updated": True}]


def do_updates(ids):
    with lock:
        todo = [i for i in state["items"] if i["id"] in ids and not i.get("updated")]
        for i in todo:
            state["jobs"][i["id"]] = {"status": "queued", "log": ""}
    for item in todo:
        with lock:
            state["jobs"][item["id"]]["status"] = "running"
        update_one(item)
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
                "jobs": state["jobs"], "running": state["running"],
                "password": has_password(),
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
    threading.Thread(target=do_scan, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Aggiornamenti su http://{HOST}:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
