"""HTTYD PnP - character sheet tool (rider + dragon).

Usage (GUI: python httyd_overlay.py):
    python httyd_sheet.py new  <file.json>                 create a new sheet (example duo)
    python httyd_sheet.py show <file.json>                 print the sheet
    python httyd_sheet.py set  <file.json> <path> <value>  change one value

Examples for 'set' (path = keys separated by dots):
    python httyd_sheet.py set sigrun.json level 2
    python httyd_sheet.py set sigrun.json rider.attributes.Kraft 3
    python httyd_sheet.py set sigrun.json dragon.species "Gronckel"
    python httyd_sheet.py set sigrun.json rider.weapon "Speer"

Species data (class, potential, combat base, taming value) is read from Drachenliste.md,
all items from items.json - both in the same folder as this script.
"""
import json
import math
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

SPECIES_FILE = Path(__file__).with_name("Drachenliste.md")
_CACHE = {}  # path -> (file stamp, parsed data); data files are parsed again only when they change


def _cached(path, parse):
    """Parse a data file once and reuse the result until its size or modification time changes.
    The returned data is shared: callers must not modify it."""
    try:
        st = path.stat()
    except OSError:
        return parse(None)
    stamp = (st.st_mtime_ns, st.st_size)
    hit = _CACHE.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    data = parse(path.read_text(encoding="utf-8"))
    _CACHE[path] = (stamp, data)
    return data
ITEMS_FILE = Path(__file__).with_name("items.json")
ITEM_TYPES = ["Waffe", "Rüstung", "Sattel", "Sonstiges"]
DRAGON_ATTRS = ["Wucht", "Tempo", "Sinne", "Wildheit"]
BOND_TIERS = ["Misstrauen", "Vertrauen", "Partner", "Seelenverwandt", "Einheit"]
PHASES = [(1, "Jungdrache"), (4, "Heranwachsend"), (8, "Ausgewachsen"), (12, "Titan")]
SHOT_LEVELS = (4, 7, 8, 11)  # levels that grant +1 shot
# All rider skills by attribute (same as the rulebook chapter "Fertigkeiten")
SKILLS = {
    "Kraft": ["Kampf", "Ringen", "Klettern", "Stemmen", "Schwimmen", "Ausdauer"],
    "Geschick": ["Reiten", "Akrobatik", "Werfen", "Schiessen", "Schleichen", "Fingerfertigkeit"],
    "Verstand": ["Drachenkunde", "Erfinden", "Schmieden", "Navigation", "Heilkunde", "Wildnis",
                 "Sagen & Geschichte"],
    "Herz": ["Zähmen", "Drachenpflege", "Wille", "Überzeugen", "Einschüchtern", "Täuschen",
             "Menschenkenntnis", "Führen"],
}
# Skill bonus granted by each origin (allows skill max + 1)
ORIGIN_BONUS = {"Berker Wikinger": "Kampf", "Schmiedelehrling": "Schmieden",
                "Drachenjäger-Überläufer": "Schleichen", "Ausgestossener (Outcast)": "Wille",
                "Handelsfahrer": "Navigation"}

ROLE_LEVEL = 3  # a role can be chosen (and takes effect) from this level on
# Each role raises the max of two attributes and all their skills by 1
ROLE_ATTRS = {"Kriegerin": ("Kraft", "Geschick"), "Tüftler": ("Verstand", "Geschick"),
              "Flüsterer": ("Herz", "Verstand"), "Späher": ("Geschick", "Verstand"),
              "Herz der Gruppe": ("Herz", "Kraft"), "Tank": ()}
TANK_TOUGH = 2  # the Tank role raises the rider's toughness max by this instead of two attributes
REST_HEAL = 2   # a rest heals toughness + REST_HEAL LP
WOUNDS = 3      # wound slots: at 0 LP each death save / hit adds wounds, the third one is final
BASE_DAMAGE = {"unarmed": 1, "dragon_melee": 2, "dragon_shot": 3}  # weapons bring their own ("Schaden" mod)
BOND_SAVE_COST = 1  # bond spent to keep rider or dragon at 1 LP (once per day per duo)
SKILL_ATTR = {skill: attr for attr, skills in SKILLS.items() for skill in skills}

# Class ability: shared by every species of that class (rulebook table "Klassen")
CLASS_ABILITIES = {
    "Stoker": "+1 Schuss; Feuer-Angriffe setzen Ziele in Brand",
    "Boulder": "Ignoriert 1 Schaden pro Treffer; frisst Gestein als Munition",
    "Tracker": "+2 W6 auf Suchen und Verfolgen, findet Spuren automatisch",
    "Sharp": "Nahkampf- und Stachelangriffe +1 Schaden",
    "Tidal": "Wasserangriffe wirken auch unter Wasser",
    "Mystery": "1× pro Tag eine verborgene Fähigkeit (Tarnung, Gift, Täuschung)",
    "Strike": "+1 Würfel auf Sturz- und Präzisionsangriffe, +1 Initiative",
}

# EP cost per step = factor x new value (e.g. skill 2 -> 3 costs 2 x 3 = 6 EP)
COSTS = {"skill": ("Reiter-Fertigkeit", 2), "rider_attr": ("Reiter-Attribut", 4),
         "training": ("Drachen-Training", 3), "dragon_attr": ("Drachen-Attribut", 5),
         "rider_tough": ("Reiter-Zähigkeit", 4), "dragon_tough": ("Drachen-Zähigkeit", 5)}
TOUGH_LP = 2  # extra max LP per point of toughness


def upgrade_cost(kind, old, new):
    """Total EP to raise a value from old to new (0 if not raised)."""
    return sum(COSTS[kind][1] * value for value in range(old + 1, new + 1))


# Max (attribute, skill/training) per level, index = level
CAPS = [None, (2, 1), (2, 2), (2, 2), (3, 2), (3, 2), (3, 3), (3, 3), (4, 3), (4, 3), (4, 4), (5, 4), (5, 4)]


@dataclass
class Rider:
    name: str = "Neuer Reiter"
    origin: str = ""
    role: str = ""
    attributes: dict = field(default_factory=lambda: {"Kraft": 1, "Geschick": 1, "Verstand": 1, "Herz": 1})
    skills: dict = field(default_factory=dict)
    gear: list = field(default_factory=list)  # normal inventory (no modifiers)
    weapon: str = ""
    armor: str = ""
    toughness: int = 0  # bought with EP, +TOUGH_LP max LP per point


@dataclass
class Dragon:
    name: str = "-"  # campaigns usually start without a dragon
    species: str = ""
    attributes: dict = field(default_factory=lambda: dict.fromkeys(DRAGON_ATTRS, 0))
    training: int = 0
    quirk: str = ""     # individual quirk of this dragon
    behavior: str = ""  # free description by player or GM: what this dragon is like
    armor: str = ""
    saddle: str = ""
    toughness: int = 0  # bought with EP, +TOUGH_LP max LP per point


@dataclass
class Sheet:
    level: int = 1
    bond: int = 0
    xp: int = 0
    notes: str = ""
    rider: Rider = field(default_factory=Rider)
    dragon: Dragon = field(default_factory=Dragon)
    # in-play tracking: points lost per resource (rider_lp, courage, dragon_lp, shots) and used abilities
    track: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        known = lambda kind, d: {k: v for k, v in d.items() if k in {f.name for f in fields(kind)}}
        data = dict(data)  # unknown keys (e.g. from older versions) are ignored
        return cls(rider=Rider(**known(Rider, data.pop("rider"))), dragon=Dragon(**known(Dragon, data.pop("dragon"))),
                   **known(cls, data))


# --- JSON ---------------------------------------------------------------------

def save(sheet, path):
    Path(path).write_text(json.dumps(asdict(sheet), indent=2, ensure_ascii=False), encoding="utf-8")


def load(path):
    return Sheet.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# --- Rules --------------------------------------------------------------------

def load_species():
    """Species table of Drachenliste.md as {name: info} (cached, read-only)."""
    return _cached(SPECIES_FILE, _parse_species)


def _parse_species(text):
    species = {}
    for line in (text or "").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 17 and cells[3].isdigit():  # skip header and separator rows
            name, original, cls, w, t, s, wi, kb, shots, zw, flies, swims, ride, shot, special, weakness, food = cells
            potential = dict(zip(DRAGON_ATTRS, map(int, (w, t, s, wi))))
            species[name] = dict(name=name, original=original, cls=cls, potential=potential, combat=int(kb),
                                 shots=int(shots), zw=zw, flies=flies == "ja", swims=swims == "ja", rideable=ride == "ja", shot=shot,
                                 special=special, weakness=weakness, food=food, class_ability=CLASS_ABILITIES.get(cls, "–"))
    return species


def wounds(sheet, who):
    """Wound note for the text sheet, empty without wounds."""
    n = sheet.track.get(f"{who}_wounds", 0)
    return "" if not n else (" (TOT)" if n >= WOUNDS else f" (Wunden {n}/{WOUNDS})")


def left(sheet, key, values):
    """Remaining points of a tracked resource (maximum minus what was lost in play)."""
    return max(0, values[key] - sheet.track.get(key, 0))


def tough_limit(sheet, rider, caps):
    """Max toughness: like skills/training, +TANK_TOUGH for a rider with the Tank role."""
    tank = rider and sheet.rider.role == "Tank" and sheet.level >= ROLE_LEVEL
    return caps[1] + (TANK_TOUGH if tank else 0)


def is_dead(sheet, who):
    return sheet.track.get(f"{who}_wounds", 0) >= WOUNDS


def rest(sheet, fed=True):
    """Tracking after a rest (once per day): abilities, shots, courage and the bond save back.
    Fed (1 Proviant eaten): heal toughness + REST_HEAL LP; healing above 0 LP clears the wounds.
    Not fed (brotlose Nacht): no healing, everyone conscious loses 1 LP but not below 1. The dead stay dead."""
    track = dict(sheet.track)
    v = derive(sheet)
    for who, toughness in (("rider", sheet.rider.toughness), ("dragon", sheet.dragon.toughness)):
        lost = track.get(f"{who}_lp", 0)
        if is_dead(sheet, who) or (who == "dragon" and not has_dragon(sheet)):
            continue
        if fed:
            track[f"{who}_lp"] = max(0, lost - toughness - REST_HEAL)
            track.pop(f"{who}_wounds", None)
        elif v[f"{who}_lp"] - lost > 1:
            track[f"{who}_lp"] = lost + 1
    for key in ("courage", "shots", "used"):
        track.pop(key, None)
    return track


def has_dragon(sheet):
    """False while the rider has no dragon yet (species empty or '-')."""
    return sheet.dragon.species.strip() not in ("", "-", "–")


def find_species(query):
    """Match German or original name, exact first, then partial (e.g. 'Nadder', 'Night Fury')."""
    species = load_species()
    if query in species:  # fast path: the editor always passes the exact German name
        return species[query]
    query = query.strip().lower()
    if not query or query in ("-", "–"):
        return None
    lowered = [(s["name"].lower(), s["original"].lower(), s) for s in species.values()]
    exact = [s for name, orig, s in lowered if query in (name, orig)]
    partial = [s for name, orig, s in lowered if query in name or query in orig]
    return (exact or partial or [None])[0]


def load_items():
    """All items from items.json as {name: item} (cached, read-only)."""
    return _cached(ITEMS_FILE, _parse_items)


def _parse_items(text):
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return {}
    return {item["name"]: item for item in data.get("items", [])}


def add_item(item):
    """Append a new item to items.json (one item per line keeps the file readable)."""
    data = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    if any(i["name"].lower() == item["name"].lower() for i in data["items"]):
        raise ValueError(f"Item '{item['name']}' gibt es schon.")
    data["items"].append(item)
    rows = ",\n".join("    " + json.dumps(i, ensure_ascii=False) for i in data["items"])
    info = json.dumps(data.get("_info", ""), ensure_ascii=False)
    ITEMS_FILE.write_text(f'{{\n  "_info": {info},\n  "items": [\n{rows}\n  ]\n}}\n', encoding="utf-8")


def add_species(row):
    """Insert a new species row (list of 17 cells) after the last row of the table in Drachenliste.md."""
    if row[0].lower() in (name.lower() for name in load_species()):
        raise ValueError(f"Art '{row[0]}' gibt es schon.")
    lines = SPECIES_FILE.read_text(encoding="utf-8").splitlines()
    last = max(i for i, line in enumerate(lines) if line.startswith("|"))
    lines.insert(last + 1, "| " + " | ".join(str(cell) for cell in row) + " |")
    SPECIES_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_mods(text):
    """'Kampf +1, Verteidigung 2' -> {'Kampf': 1, 'Verteidigung': 2}"""
    mods = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        name, _, value = part.rpartition(" ")
        try:
            mods[name.strip()] = int(value)
        except ValueError:
            raise ValueError(f"Modifikator '{part}' unklar, Format: Name +1") from None
    return mods


def fmt_mods(mods):
    """{'Kampf': 1, 'Akrobatik': -1} -> 'Kampf +1, Akrobatik -1'"""
    return ", ".join(f"{k} {v:+d}" for k, v in mods.items() if v) or "–"


def equipped_mods(names, items):
    """Sum the modifiers of equipped items; returns (totals, sources) per key."""
    totals, sources = {}, {}
    for name in names:
        for key, value in items.get(name, {}).get("mods", {}).items():
            if value:
                totals[key] = totals.get(key, 0) + value
                sources.setdefault(key, []).append(f"{name} {value:+d}")
    return totals, sources


def combat_values(sheet, spec, items=None):
    """Attack and defence of rider and dragon: base value + skill/training + equipped items."""
    items = load_items() if items is None else items
    r, d = sheet.rider, sheet.dragon
    # skill names that are not combat keys ("Kampf" is both a skill and the melee modifier)
    known = {skill for skills in SKILLS.values() for skill in skills} - {"Kampf", "Fernkampf", "Verteidigung"}
    weapon = items.get(r.weapon, {}).get("mods", {})
    # saddle skill mods (e.g. Reiten) help the rider, all other dragon mods help the dragon
    saddle = items.get(d.saddle, {}).get("mods", {})
    rider_items = [r.weapon, r.armor]
    rmods, rsrc = equipped_mods(rider_items, items)
    for key, value in saddle.items():
        if key in known and value:
            rmods[key] = rmods.get(key, 0) + value
            rsrc.setdefault(key, []).append(f"{d.saddle} {value:+d}")
    dmods, dsrc = equipped_mods([d.armor, d.saddle], items)
    dmods = {k: v for k, v in dmods.items() if k not in known}

    def total(parts, key, mods, src):
        parts = [(label, value) for label, value in parts] + [(s, None) for s in src.get(key, [])]
        value = sum(v for _, v in parts if v is not None) + mods.get(key, 0)
        text = " + ".join(f"{label} {v}" if v is not None else label for label, v in parts)
        return value, text

    sk = r.skills
    ranged_skill = max(("Schiessen", "Werfen"), key=lambda k: sk.get(k, 0))
    kb = spec["combat"] if spec else 0
    tempo = d.attributes.get("Tempo", 0)
    return dict(
        rider_melee=total([("Kraft", r.attributes.get("Kraft", 0)), ("Kampf", sk.get("Kampf", 0))],
                          "Kampf", rmods, rsrc),
        rider_ranged=total([("Geschick", r.attributes.get("Geschick", 0)), (ranged_skill, sk.get(ranged_skill, 0))],
                           "Fernkampf", rmods, rsrc),
        rider_defense=total([("Basis", 1)], "Verteidigung", rmods, rsrc),
        dragon_attack=total([("Kampfbasis", kb), ("Training", d.training)], "Kampf", dmods, dsrc),
        dragon_defense=total([("Tempo/2", math.ceil(tempo / 2))], "Verteidigung", dmods, dsrc),
        skill_mods={k: v for k, v in rmods.items() if k in known},
        # base damage of a hit; a weapon without a melee/ranged bonus does not count for that attack
        rider_melee_dmg=weapon.get("Schaden", 1) if "Kampf" in weapon else BASE_DAMAGE["unarmed"],
        rider_ranged_dmg=weapon.get("Schaden", 0) if "Fernkampf" in weapon else "–",  # "–": no ranged weapon
        dragon_melee_dmg=BASE_DAMAGE["dragon_melee"] + (1 if spec and spec["cls"] == "Sharp" else 0)
        + dmods.get("Schaden", 0),
        dragon_shot_dmg=BASE_DAMAGE["dragon_shot"],
    )


def derive(sheet):
    """Compute all derived values from the rules."""
    lvl, r, d = sheet.level, sheet.rider, sheet.dragon
    spec = find_species(d.species)
    phase_idx = max(i for i, (start, _) in enumerate(PHASES) if lvl >= start)
    if phase_idx == 3 and sheet.bond < 20:  # Titan form requires bond 20
        phase_idx = 2
    tier = min(sheet.bond // 5, 4)
    shots = 2 + sum(lvl >= l for l in SHOT_LEVELS) + bool(spec and spec["cls"] == "Stoker")
    return dict(
        spec=spec,
        caps=CAPS[max(1, min(lvl, 12))],
        phase=PHASES[phase_idx][1] if has_dragon(sheet) else "–",
        tier=tier,
        teamwork=min(tier, 3),
        # rider +1 LP per level, dragon +2 per level: a dragon always has more LP than its rider
        rider_lp=4 + r.attributes.get("Kraft", 0) + (lvl - 1) + TOUGH_LP * r.toughness,
        courage=r.attributes.get("Herz", 0) + 1,
        dragon_lp=(8 + 2 * d.attributes.get("Wucht", 0) + 2 * (lvl - 1) + TOUGH_LP * d.toughness)
        if has_dragon(sheet) else 0,
        shots=(min(shots, spec["shots"]) if spec else shots) if has_dragon(sheet) else 0,
        **combat_values(sheet, spec),
    )


def role_attrs(sheet):
    """Lead attributes of the rider's role - only active from ROLE_LEVEL on."""
    return ROLE_ATTRS.get(sheet.rider.role, ()) if sheet.level >= ROLE_LEVEL else ()


def attr_limit(sheet, attr, caps):
    """Max of a rider attribute: level cap, +1 if the role favours it."""
    return caps[0] + (attr in role_attrs(sheet))


def skill_limit(sheet, skill, caps):
    """Max of a rider skill: level cap, +1 origin skill, +1 if its attribute is a role attribute."""
    role = role_attrs(sheet)
    return caps[1] + (skill == ORIGIN_BONUS.get(sheet.rider.origin)) + (SKILL_ATTR.get(skill) in role)


def check(sheet, v):
    """Return rule warnings (values above level caps or species potential)."""
    attr_cap, skill_cap = caps = v["caps"]
    warnings = [f"{name} ist tot (3 Wunden)" for who, name in (("rider", "Reiter"), ("dragon", "Drache"))
                if is_dead(sheet, who)]
    warnings += [f"Reiter {k} {x} > Max {attr_limit(sheet, k, caps)}"
                for k, x in sheet.rider.attributes.items() if x > attr_limit(sheet, k, caps)]
    warnings += [f"Fertigkeit {k} {x} > Max {skill_limit(sheet, k, caps)}"
                 for k, x in sheet.rider.skills.items() if x > skill_limit(sheet, k, caps)]
    for k, x in sheet.dragon.attributes.items():
        limit = min(attr_cap, v["spec"]["potential"][k]) if v["spec"] else attr_cap
        if x > limit:
            warnings.append(f"Drache {k} {x} > Max {limit}")
    if sheet.dragon.training > skill_cap:
        warnings.append(f"Training {sheet.dragon.training} > Max {skill_cap}")
    for who, value in (("Reiter", sheet.rider.toughness), ("Drache", sheet.dragon.toughness)):
        limit = tough_limit(sheet, who == "Reiter", caps)
        if value > limit:
            warnings.append(f"{who} Zähigkeit {value} > Max {limit}")
    if has_dragon(sheet) and not v["spec"]:
        warnings.append(f"Art '{sheet.dragon.species}' nicht in Drachenliste.md gefunden")
    items = load_items()
    slots = [("Waffe", sheet.rider.weapon, "Waffe", "Reiter"), ("Rüstung", sheet.rider.armor, "Rüstung", "Reiter"),
             ("Drachenrüstung", sheet.dragon.armor, "Rüstung", "Drache"),
             ("Sattel", sheet.dragon.saddle, "Sattel", "Drache")]
    for slot, name, kind, owner in slots:
        item = items.get(name)
        if name and not item:
            warnings.append(f"{slot} '{name}' nicht in items.json gefunden")
        elif item and (item["type"] != kind or item["for"] != owner):
            warnings.append(f"{slot}: '{name}' ist {item['type']} für {item['for']}")
    return warnings


# --- Display ------------------------------------------------------------------

def join(d):
    return "  ".join(f"{k} {x}" for k, x in d.items()) or "-"


def render(sheet):
    """Return the sheet as plain text (used by CLI and overlay)."""
    v, r, d = derive(sheet), sheet.rider, sheet.dragon
    spec = v["spec"]
    pot = spec["potential"] if spec else {}
    dragon_attrs = "  ".join(f"{k} {x}/{pot.get(k, '?')}" for k, x in d.attributes.items())
    species = f"{spec['name']} ({spec['cls']}, ZW {spec['zw']})" if spec else d.species or "?"
    lines = [
        "=" * 48,
        f" {r.name} & {d.name}  |  Stufe {sheet.level}  |  EP {sheet.xp}",
        f" Bindung {sheet.bond}/20 ({BOND_TIERS[v['tier']]})  |  Teamwork +{v['teamwork']} W6",
        "=" * 48,
        f"REITER  {r.name} - {r.origin or '?'} / {r.role or '?'}",
        f"  {join(r.attributes)}",
        f"  Fertigkeiten: {', '.join(f'{k} {x}' for k, x in r.skills.items()) or '-'}",
        f"  LP {left(sheet, 'rider_lp', v)}/{v['rider_lp']}{wounds(sheet, 'rider')}  Mut {left(sheet, 'courage', v)}/{v['courage']}  |  Kampf {v['rider_melee'][0]} (GS {v['rider_melee_dmg']})  Fernkampf "
        f"{v['rider_ranged'][0]} (GS {v['rider_ranged_dmg']})  Verteidigung {v['rider_defense'][0]}",
        f"  Waffe: {r.weapon or '-'}  |  Rüstung: {r.armor or '-'}  |  Inventar: {', '.join(r.gear) or '-'}",
        "",
        f"DRACHE  {d.name} - {species}, {v['phase']}",
        f"  {dragon_attrs}   (Wert/Potenzial)",
        f"  LP {left(sheet, 'dragon_lp', v)}/{v['dragon_lp']}{wounds(sheet, 'dragon')}  Schüsse {left(sheet, 'shots', v)}/{v['shots']}  Training {d.training}  |  Kampf "
        f"{v['dragon_attack'][0]} (GS {v['dragon_melee_dmg']})  Schuss GS {v['dragon_shot_dmg']}  Verteidigung {v['dragon_defense'][0]}",
        f"  Rüstung: {d.armor or '-'}  |  Sattel: {d.saddle or '-'}",
        f"  Fliegt: {'ja' if spec and spec['flies'] else 'nein'}  |  Schwimmt: "
        f"{'ja' if spec and spec['swims'] else 'nein'}  |  Reitbar: "
        f"{'ja' if spec and spec['rideable'] else 'nein'}  |  Grundschuss: {spec['shot'] if spec else '-'}",
        f"  Spezial (Art): {spec['special'] if spec else '-'}  |  Klasse: {spec['class_ability'] if spec else '-'}",
        f"  Macke: {d.quirk or '-'}  |  Schwäche: {spec['weakness'] if spec else '-'}"
        f"  |  Lieblingsfutter: {spec['food'] if spec else '-'}",
        f"  Verhalten: {d.behavior or '-'}",
        "",
        f"Max. Attribut {v['caps'][0]} / Fertigkeit & Training {v['caps'][1]} auf Stufe {sheet.level}",
    ]
    if sheet.notes:
        lines.append(f"Notizen: {sheet.notes}")
    lines += [f"  ! {w}" for w in check(sheet, v)]
    return "\n".join(lines)


def show(sheet):
    print(render(sheet))


# --- CLI ----------------------------------------------------------------------

def example():
    """Sigrun & Sturmspitz from the rulebook."""
    return Sheet(
        bond=1,
        rider=Rider("Sigrun", "Berker Wikinger", "",  # role is chosen at level 3
                    {"Kraft": 2, "Geschick": 2, "Verstand": 1, "Herz": 1},
                    {"Kampf": 2, "Zähmen": 1}, ["Seil (15 m)", "Fischkorb"], "Axt", "Lederwams"),
        dragon=Dragon("Sturmspitz", "Tödlicher Nadder", {"Wucht": 1, "Tempo": 2, "Sinne": 2, "Wildheit": 1},
                      quirk="Eitel, putzt sich ständig",
                      behavior="Neugierig und stolz. Misstraut Fremden, folgt Sigrun aber überallhin.",
                      saddle="Einfacher Sattel"),
    )


def set_value(path, key, raw):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    *parents, last = key.split(".")
    target = data
    for k in parents:
        target = target[k]
    try:
        target[last] = json.loads(raw)  # numbers, lists, ...
    except json.JSONDecodeError:
        target[last] = raw  # plain text
    sheet = Sheet.from_dict(data)  # validates structure
    save(sheet, path)
    return sheet


def main(args):
    sys.stdout.reconfigure(encoding="utf-8")
    match args:
        case ["new", path]:
            save(example(), path)
            show(load(path))
        case ["show", path]:
            show(load(path))
        case ["set", path, key, value]:
            show(set_value(path, key, value))
        case _:
            print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
