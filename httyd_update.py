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


def launch_swap_and_restart(work, program):
    """Start a small batch script that waits for this program to close, swaps exe and _internal, restarts.
    The caller must quit right after this."""
    script = work / "update.bat"
    script.write_text("\r\n".join([
        "@echo off", "chcp 65001 >NUL",
        ":wait",  # wait until the running program has released its files
        f'tasklist /FI "PID eq {os.getpid()}" 2>NUL | find "{os.getpid()}" >NUL && '
        "(ping -n 2 127.0.0.1 >NUL & goto wait)",  # 1 s pause; timeout.exe needs a console
        f'robocopy "{program / "_internal"}" "{APP_DIR / "_internal"}" /MIR /NFL /NDL /NJH /NJS /NP >NUL',
        f'copy /Y "{program / EXE}" "{APP_DIR / EXE}" >NUL',
        f'start "" "{APP_DIR / EXE}"',
        f'rmdir /S /Q "{work}"',
    ]) + "\r\n", encoding="utf-8")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=flags, close_fds=True)


def can_self_update():
    """Only the built Windows program can replace itself."""
    return FROZEN and sys.platform == "win32"
