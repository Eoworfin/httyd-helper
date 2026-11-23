"""Self-updater for the built program: checks GitHub releases, installs a newer version and keeps local data.

Folder of the built program:
    Drachenreiter/
        Drachenreiter.exe, _internal/   program (replaced by an update)
        daten/                          editable data (merged, never wiped)

Merging rules for daten/:
    Drachenliste.md, items.json  the new release is the base; species and items the user added
                                 (names not in the release) are kept and appended
    other shipped files          replaced by the new version (e.g. the rulebook)
    everything else              untouched (settings.json, own files)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from httyd_sheet import APP_DIR, DATA_DIR, FROZEN

REPO = "Eoworfin/httyd-helper"
ASSET = "Drachenreiter-windows.zip"
EXE = "Drachenreiter.exe"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


def current_version():
    """Version the build was made from (written by the GitHub workflow), 'dev' when run as a script."""
    path = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "version.txt"
    try:
        return path.read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


def parse_version(tag):
    """'v1.10.2' -> (1, 10, 2); anything unparsable sorts lowest."""
    parts = []
    for part in tag.lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def latest_release(timeout=8):
    """Latest GitHub release as dict(tag, notes, url) of the zip asset, or None."""
    request = urllib.request.Request(API, headers={"User-Agent": "Drachenreiter-Updater",
                                                   "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET), None)
    if not asset:
        return None
    return dict(tag=data.get("tag_name", ""), notes=(data.get("body") or "").strip(),
                url=asset["browser_download_url"])


def is_newer(tag, current=None):
    """True if the release tag is newer. Test builds ('dev', 'dev-1a2b3c4' from a manual workflow run)
    count as older than any release."""
    current = current or current_version()
    return current.lower().startswith("dev") or parse_version(tag) > parse_version(current)


# --- data merge ---------------------------------------------------------------
def _species_rows(text):
    """{name: line} of the species table rows (lines starting with '| ' and a numeric W column)."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) > 3 and cells[3].isdigit():
            rows[cells[0]] = line
    return rows


def merge_species(new_text, local_text):
    """New list as base, plus rows of species only the local list has (user additions)."""
    new_rows, local_rows = _species_rows(new_text), _species_rows(local_text)
    extra = [line for name, line in local_rows.items() if name not in new_rows]
    if not extra:
        return new_text
    lines = new_text.splitlines()
    last = max(i for i, line in enumerate(lines) if line in new_rows.values())
    return "\n".join(lines[:last + 1] + extra + lines[last + 1:]) + "\n"


def merge_items(new_text, local_text):
    """New items.json as base, plus items only the local file has."""
    new, local = json.loads(new_text), json.loads(local_text)
    names = {item["name"] for item in new.get("items", [])}
    new["items"] = new.get("items", []) + [i for i in local.get("items", []) if i["name"] not in names]
    rows = ",\n".join("    " + json.dumps(i, ensure_ascii=False) for i in new["items"])
    return (f'{{\n  "_info": {json.dumps(new.get("_info", ""), ensure_ascii=False)},\n'
            f'  "items": [\n{rows}\n  ]\n}}\n')


def merge_enemies(new_text, local_text):
    """New gegner.json as base, plus enemies only the local file has."""
    new, local = json.loads(new_text), json.loads(local_text)
    names = {e["name"] for e in new.get("gegner", [])}
    rows = new.get("gegner", []) + [e for e in local.get("gegner", []) if e["name"] not in names]
    lines = ",\n".join("    " + json.dumps(e, ensure_ascii=False) for e in rows)
    return (f'{{\n  "_info": {json.dumps(new.get("_info", ""), ensure_ascii=False)},\n'
            f'  "gegner": [\n{lines}\n  ]\n}}\n')


def merge_data(new_dir, data_dir=DATA_DIR):
    """Bring the data of a new release into data_dir without losing local additions. Returns notes."""
    data_dir.mkdir(parents=True, exist_ok=True)
    notes = []
    for new_file in Path(new_dir).iterdir():
        if not new_file.is_file():
            continue
        target = data_dir / new_file.name
        new_text = new_file.read_text(encoding="utf-8")
        if target.exists() and new_file.name == "Drachenliste.md":
            merged = merge_species(new_text, target.read_text(encoding="utf-8"))
            kept = len(_species_rows(merged)) - len(_species_rows(new_text))
            notes.append(f"Drachenliste aktualisiert, {kept} eigene Arten behalten")
        elif target.exists() and new_file.name == "items.json":
            merged = merge_items(new_text, target.read_text(encoding="utf-8"))
            kept = len(json.loads(merged)["items"]) - len(json.loads(new_text)["items"])
            notes.append(f"Items aktualisiert, {kept} eigene Items behalten")
        elif target.exists() and new_file.name == "gegner.json":
            merged = merge_enemies(new_text, target.read_text(encoding="utf-8"))
            kept = len(json.loads(merged)["gegner"]) - len(json.loads(new_text)["gegner"])
            notes.append(f"Gegner aktualisiert, {kept} eigene Gegner behalten")
        elif target.exists() and new_file.name == "settings.json":
            continue  # personal settings stay
        else:
            merged = new_text
            notes.append(f"{new_file.name} aktualisiert")
        target.write_text(merged, encoding="utf-8")
    return notes


# --- install ------------------------------------------------------------------
def download_and_prepare(url):
    """Download and unpack a release; merge its data. Returns (folder with the new program, notes)."""
    work = Path(tempfile.mkdtemp(prefix="drachenreiter_update_"))
    archive = work / ASSET
    request = urllib.request.Request(url, headers={"User-Agent": "Drachenreiter-Updater"})
    with urllib.request.urlopen(request, timeout=60) as response, open(archive, "wb") as fh:
        shutil.copyfileobj(response, fh)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(work / "neu")
    program = next((p.parent for p in (work / "neu").rglob(EXE)), None)
    if not program:
        raise RuntimeError(f"{EXE} fehlt im Download.")
    notes = merge_data(program / "daten") if (program / "daten").is_dir() else []
    return work, program, notes


def _ps(path):
    """Path as a single-quoted PowerShell string."""
    return "'" + str(path).replace("'", "''") + "'"


def launch_swap_and_restart(work, program):
    """Start a hidden PowerShell script that waits for this program to exit, swaps exe and _internal and
    restarts it. A log is written; if the swap fails it is copied to daten/update_fehler.log and the
    old version is started again. The caller must quit right after this."""
    script, log = work / "update.ps1", work / "update.log"
    exe_new, exe_app = program / EXE, APP_DIR / EXE
    script.write_text("\r\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"Start-Transcript -Path {_ps(log)} | Out-Null",
        "try {",
        f"  Wait-Process -Id {os.getpid()} -Timeout 60 -ErrorAction SilentlyContinue",
        "  Start-Sleep -Milliseconds 800",
        # the exe can stay locked for a moment after exit (virus scanner): retry
        "  $done = $false",
        "  for ($i = 0; $i -lt 30 -and -not $done; $i++) {",
        f"    try {{ Copy-Item -LiteralPath {_ps(exe_new)} -Destination {_ps(exe_app)} -Force; $done = $true }}",
        "    catch { Start-Sleep -Milliseconds 500 }",
        "  }",
        "  if (-not $done) { throw 'Drachenreiter.exe ist noch gesperrt.' }",
        f"  robocopy {_ps(program / '_internal')} {_ps(APP_DIR / '_internal')} /MIR /R:10 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null",
        "  if ($LASTEXITCODE -ge 8) { throw \"robocopy Fehler $LASTEXITCODE\" }",
        "  Stop-Transcript | Out-Null",
        f"  Start-Process -FilePath {_ps(exe_app)} -WorkingDirectory {_ps(APP_DIR)}",
        f"  Remove-Item -LiteralPath {_ps(work)} -Recurse -Force -ErrorAction SilentlyContinue",
        "} catch {",
        "  Write-Output $_",
        "  Stop-Transcript | Out-Null",
        f"  Copy-Item -LiteralPath {_ps(log)} -Destination {_ps(DATA_DIR / 'update_fehler.log')} -Force",
        f"  Start-Process -FilePath {_ps(exe_app)} -WorkingDirectory {_ps(APP_DIR)}",
        "}",
    ]) + "\r\n", encoding="utf-8-sig")  # BOM: Windows PowerShell 5 then reads umlauts in paths correctly
    # hidden: no window, and robocopy runs in the same invisible console instead of opening its own
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                      "-File", str(script)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def can_self_update():
    """Only the built Windows program can replace itself."""
    return FROZEN and sys.platform == "win32"
