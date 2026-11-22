"""HTTYD PnP - overlay UI: edit/view character sheets, save/load JSON, browse the dragon list.

Run:   python httyd_overlay.py [sheet.json]
Needs httyd_sheet.py and Drachenliste.md in the same folder (tkinter ships with Python).
"""
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import json
import threading

import httyd_update as updater
from httyd_pdf import canvas_to_pdf

from httyd_sheet import (BOND_TIERS, COSTS, DRAGON_ATTRS, ITEM_TYPES, ORIGIN_BONUS, SKILLS, Dragon, Rider, Sheet,
                         ROLE_LEVEL, add_item, add_species, attr_limit, check, derive, has_dragon, role_attrs, skill_limit, example, fmt_mods, load, load_items, load_species,
                         parse_mods, save, upgrade_cost, TOUGH_LP, rest, tough_limit, WOUNDS, BOND_SAVE_COST,
                         APP_DIR, DATA_DIR)

RIDER_ATTRS = ["Kraft", "Geschick", "Verstand", "Herz"]
ORIGINS = ["Berker Wikinger", "Schmiedelehrling", "Drachenjäger-Überläufer", "Ausgestossener (Outcast)", "Handelsfahrer"]
ROLES = ["Tüftler", "Kriegerin", "Flüsterer", "Späher", "Herz der Gruppe", "Tank"]
COLUMNS = ["Art", "Original", "Klasse", "W", "T", "S", "Wi", "KB", "Sch", "ZW", "Fliegt", "Schwimmt", "Reitbar",
           "Grundschuss", "Spezialfähigkeit", "Schwäche", "Lieblingsfutter"]
WIDTHS = [150, 130, 65, 28, 28, 28, 28, 32, 34, 32, 52, 74, 66, 110, 200, 260, 170]
# equipment slots: form key -> (item type, owner)
SLOTS = {"rider.weapon": ("Waffe", "Reiter"), "rider.armor": ("Rüstung", "Reiter"),
         "dragon.armor": ("Rüstung", "Drache"), "dragon.saddle": ("Sattel", "Drache")}

# Berk palette: smoked wood, leather and parchment, forge fire as accent, shield red, North Sea green
BG, PANEL, FIELD, BORDER = "#1a1511", "#272019", "#352a20", "#4b3b2c"
TEXT, MUTED, ACCENT, WARN = "#efe3cb", "#a8957a", "#e07b2e", "#c8473a"
SEA, ROW_ALT = "#6f9a92", "#2e251d"
ACCENT_DARK, ACCENT_LIGHT = "#b8611f", "#f0943f"
# print colours for the PDF: white paper, dark ink, backgrounds left blank (None)
PRINT_COLORS = {BG: "#ffffff", PANEL: "#ffffff", ROW_ALT: None, FIELD: "#f1ece3", BORDER: "#8f8578", TEXT: "#1b1b1b",
                MUTED: "#5f574e", ACCENT: "#9c4f16", WARN: "#a3352a", SEA: "#3b6b64"}
FONT = ("Segoe UI", 10)
MONO = ("Consolas", 11)


def apply_dark_theme(root):
    """Flat dark look on top of the built-in 'clam' theme (no extra packages)."""
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(bg=BG)
    root.option_add("*Font", FONT)
    # dropdown list of comboboxes is a plain Tk listbox
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", BG)

    style.configure(".", background=BG, foreground=TEXT, fieldbackground=FIELD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, troughcolor=PANEL, insertcolor=TEXT,
                    selectbackground=ACCENT, selectforeground=BG, arrowcolor=MUTED, font=FONT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=PANEL)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Title.TLabel", background=PANEL, foreground=ACCENT, font=(FONT[0], 11, "bold"))
    style.configure("TButton", background=FIELD, foreground=TEXT, borderwidth=0, padding=(12, 6), focusthickness=0)
    style.map("TButton", background=[("pressed", BORDER), ("active", BORDER)])
    style.configure("TMenubutton", background=FIELD, foreground=TEXT, borderwidth=0, padding=(12, 6),
                    arrowcolor=ACCENT, relief="flat")
    style.map("TMenubutton", background=[("pressed", BORDER), ("active", BORDER)])
    style.configure("Accent.TButton", background=ACCENT, foreground=BG, font=(FONT[0], 10, "bold"))
    style.map("Accent.TButton", background=[("pressed", ACCENT_DARK), ("active", ACCENT_LIGHT)])
    style.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorbackground=FIELD,
                    indicatorforeground=BG, upperbordercolor=BORDER, lowerbordercolor=BORDER)
    style.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("selected", ACCENT)])
    style.configure("Card.TCheckbutton", background=PANEL)
    style.map("Card.TCheckbutton", background=[("active", PANEL)])
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(widget, fieldbackground=FIELD, foreground=TEXT, background=FIELD,
                        bordercolor=BORDER, padding=3, arrowsize=12)
        style.map(widget, bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
                  fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)])
    flat = dict(bordercolor=BG, lightcolor=BG, darkcolor=BG)
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0), **flat)
    style.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(16, 8), borderwidth=0, **flat)
    style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", ACCENT)],
              bordercolor=[("selected", PANEL)], lightcolor=[("selected", PANEL)])
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=26, borderwidth=0, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", BG)])
    style.configure("Treeview.Heading", background=FIELD, foreground=MUTED, borderwidth=0,
                    padding=6, font=(FONT[0], 10, "bold"))
    style.map("Treeview.Heading", background=[("active", BORDER)])
    for bar in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(bar, background=BORDER, troughcolor=PANEL, borderwidth=0, arrowsize=0)
        style.map(bar, background=[("active", MUTED)])


RULES_NAME = "HTTYD_Regelwerk_Konzept.md"
SETTINGS_FILE = DATA_DIR / "settings.json"
DEFAULT_SETTINGS = {"free_edit": False, "topmost": False, "start_xp": 24, "update_check": True}


def load_settings():
    try:
        return {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)


def cost_kind(key):
    """Which cost row a form field belongs to (None = no EP cost)."""
    if key.startswith("skill."):
        return "skill"
    if key.startswith("rider.attr."):
        return "rider_attr"
    if key.startswith("dragon.attr."):
        return "dragon_attr"
    return {"dragon.training": "training", "rider.toughness": "rider_tough",
            "dragon.toughness": "dragon_tough"}.get(key)


def find_rules():
    """Rulebook lives in the data folder (or one folder above the program, as in older layouts)."""
    return next((p for p in (DATA_DIR / RULES_NAME, APP_DIR.parent / RULES_NAME) if p.exists()), None)


# --- small converters ---------------------------------------------------------

def to_int(text, default=0):
    try:
        return int(text)
    except ValueError:
        return default


def species_row(s):
    return [s["name"], s["original"], s["cls"], *s["potential"].values(), s["combat"], s["shots"], s["zw"],
            "ja" if s["flies"] else "nein", "ja" if s["swims"] else "nein",
            "ja" if s.get("rideable") else "nein", s["shot"], s["special"], s["weakness"], s["food"]]


# --- read-only character sheet (DnD/DSA style) ---------------------------------

SERIF = ("Georgia", 11)


class SheetView(tk.Canvas):
    """Draws a printable-looking character sheet for rider + dragon on a canvas."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG, highlightthickness=0)
        self.sheet = self.values = None
        self.printing = False   # print version: all trackers (LP, wounds, bond, flags) blank for pencil marks
        self.fixed_width = None  # draw at this width instead of the window width (PDF export)
        self.dirty = False      # sheet changed while the tab was hidden: draw when it becomes visible
        self._resize_job = None
        self._width = 0
        self.on_track = None  # callback(key, value) when a pip or ability flag is clicked
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        # a window drag fires many events: redraw once it settles, and only if the width changed
        if event.width == self._width:
            return
        self._width = event.width
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self._resized)

    def _resized(self):
        self._resize_job = None
        self.draw()

    def show(self, sheet, values=None):
        """New data; drawing is skipped while the tab is hidden (see draw_if_dirty)."""
        self.sheet, self.values = sheet, values
        if self.winfo_ismapped():
            self.draw()
        else:
            self.dirty = True

    def draw_if_dirty(self):
        if self.dirty:
            self.draw()

    # --- drawing primitives
    def text(self, x, y, value, size=10, color=TEXT, font=None, anchor="nw", bold=False):
        family = (font or FONT)[0]
        return self.create_text(x, y, text=value, fill=color, anchor=anchor,
                                font=(family, size, "bold" if bold else "normal"))

    def title(self, x, y, w, label):
        """Section heading with a rule, like the banners on DnD sheets."""
        self.text(x, y, label.upper(), 11, ACCENT, SERIF, bold=True)
        self.create_line(x, y + 22, x + w, y + 22, fill=ACCENT)
        return y + 32

    def field(self, x, y, w, label, value):
        """Underlined value with a small caption below (header fields)."""
        item = self.text(x + 2, y, value or "–", 12, TEXT, SERIF)
        while self.bbox(item)[2] > x + w - 12 and len(self.itemcget(item, "text")) > 4:
            self.itemconfigure(item, text=self.itemcget(item, "text")[:-2] + "…")  # shorten to fit
        self.create_line(x, y + 22, x + w - 10, y + 22, fill=BORDER)
        self.text(x + 2, y + 25, label.upper(), 7, MUTED)

    def stat(self, x, y, label, value, sub, w=78, h=86):
        """Attribute box: caption, big number, small note (DnD ability score style)."""
        self.create_rectangle(x, y, x + w, y + h, outline=BORDER, fill=PANEL, width=2)
        self.text(x + w / 2, y + 8, label.upper(), 8, MUTED, anchor="n")
        self.text(x + w / 2, y + 42, str(value), 24, TEXT, SERIF, anchor="center", bold=True)
        self.create_oval(x + w / 2 - 22, y + h - 14, x + w / 2 + 22, y + h + 8, outline=BORDER, fill=BG)
        self.text(x + w / 2, y + h - 3, sub, 8, ACCENT, anchor="center")

    def combat(self, x, y, w, label, value, formula, dmg=None):
        """Combat value box with its breakdown below (base + skill + items)."""
        self.create_rectangle(x, y, x + w, y + 54, outline=ACCENT, fill=PANEL, width=2)
        self.text(x + 10, y + 8, label.upper(), 8, ACCENT, bold=True)
        self.text(x + w - 12, y + 28, str(value), 22, TEXT, SERIF, anchor="e", bold=True)
        if label != "Verteidigung":  # defence is a fixed target value like DnD AC, not a dice pool
            self.text(x + 10, y + 28, "W6" + (" · keine Fernwaffe" if dmg == "–" else
                                              f" · Schaden {dmg}" if dmg is not None else ""), 9, MUTED)
        note = self.text(x + 2, y + 60, formula, 8, MUTED)
        self.itemconfigure(note, width=w - 4)
        return self.bbox(note)[3]

    def pips(self, x, y, label, count, width, color=ACCENT, key=None, taken=False):
        """Row(s) of clickable circles (DSA style): filled = still available, empty = lost.
        Clicking a filled circle drops the value to there, clicking an empty one restores up to it."""
        lost = min(self.sheet.track.get(key, 0), count) if key else 0
        left = lost if taken else count - lost  # taken: filled circles are the ones used up (wounds)
        self.text(x, y, label.upper(), 8, MUTED)
        value = ("TOT" if lost >= count else f"{lost}/{count}") if taken else (f"{left}/{count}" if key else str(count))
        if self.printing and key:  # blank circles to tick off on paper
            left, lost, value = 0, 0, f"max {count}"
        self.text(x + width, y, value, 10, WARN if taken and lost >= count else TEXT, anchor="ne", bold=True)
        per_row = max(1, int(width // 16))
        for i in range(count):
            cx, cy = x + 7 + (i % per_row) * 16, y + 24 + (i // per_row) * 16
            pip = self.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline=color, width=2,
                                   fill=color if i < left else BG)
            if key:
                new_left = i if i < left else i + 1
                new_value = new_left if taken else count - new_left
                self.tag_bind(pip, "<Button-1>", lambda _, k=key, n=new_value: self.track(k, n))
                self.tag_bind(pip, "<Enter>", lambda _: self.configure(cursor="hand2"))
                self.tag_bind(pip, "<Leave>", lambda _: self.configure(cursor=""))
        return y + 24 + ((count - 1) // per_row + 1) * 16 if count else y + 30

    def track(self, key, value):
        if self.on_track:
            self.on_track(key, value)

    def flag(self, x, y, key):
        """Clickable ability flag: filled = available, empty = used."""
        used = self.printing or key in self.sheet.track.get("used", [])
        item = self.create_oval(x - 6, y - 6, x + 6, y + 6, outline=ACCENT, width=2, fill=BG if used else ACCENT)
        self.tag_bind(item, "<Button-1>", lambda _: self.track("used", key))
        self.tag_bind(item, "<Enter>", lambda _: self.configure(cursor="hand2"))
        self.tag_bind(item, "<Leave>", lambda _: self.configure(cursor=""))

    def table(self, x, y, w, label, rows, flags=()):
        """DSA-like list: name ..... value. flags: optional ability key per row for a clickable flag."""
        self.text(x, y, label.upper(), 8, MUTED)
        y += 18
        for i, (name, value) in enumerate(rows or [("–", "")]):
            item = self.text(x, y, name, 10)
            self.itemconfigure(item, width=w - 30)  # wrap long entries
            if i < len(flags) and flags[i]:
                self.flag(x + w - 7, y + 9, flags[i])
            self.text(x + w, y, str(value), 10, TEXT, anchor="ne", bold=True)
            y = self.bbox(item)[3] + 3
            self.create_line(x, y, x + w, y, fill=BORDER, dash=(1, 3))
            y += 4
        return y

    # --- layout
    def draw(self):
        self.dirty = False
        self.delete("all")
        if not self.sheet:
            return
        sheet, r, d = self.sheet, self.sheet.rider, self.sheet.dragon
        v = self.values or derive(sheet)
        spec = v["spec"] or {}
        pot = spec.get("potential", {})
        attr_cap, skill_cap = v["caps"]
        m = 24
        W = self.fixed_width or max(self.winfo_width(), 900)
        col = (W - 3 * m) / 2

        # title and level / XP box only on paper; on screen they sit in the fixed bar above the sheet
        top = 75 if self.printing else 14
        if self.printing:
            self.text(W / 2, 14, "DRACHENREITER VON BERK", 18, ACCENT, SERIF, "n", bold=True)
            self.text(W / 2, 44, "Charakterbogen", 9, MUTED, anchor="n")
            bw, bx = 170, W - m - 170  # like the DnD class & level box
            self.create_rectangle(bx, 8, bx + bw, 58, outline=ACCENT, fill=PANEL, width=2)
            for i, (label, value) in enumerate([("Stufe", sheet.level), ("EP", sheet.xp)]):
                cx = bx + bw / 4 + i * bw / 2
                self.text(cx, 30, str(value), 18, TEXT, SERIF, "center", bold=True)
                self.text(cx, 48, label.upper(), 7, MUTED, anchor="center")
            self.create_line(bx + bw / 2, 16, bx + bw / 2, 50, fill=BORDER)


        # rider column
        x, y = m, self.title(m, top, col, "Reiter")
        third = col / 3
        for i, (label, value) in enumerate([("Name", r.name), ("Herkunft", r.origin), ("Rolle", r.role)]):
            self.field(x + i * third, y, third, label, value)
        y += 50
        for i, attr in enumerate(RIDER_ATTRS):
            self.stat(x + i * (col / 4), y, attr, r.attributes.get(attr, 0),
                      f"max {attr_limit(sheet, attr, v['caps'])}", w=col / 4 - 10)
        y += 108
        third = col / 3
        y = max(self.combat(x + i * third, y, third - 10, label, *v[key], dmg=v.get(f"{key}_dmg"))
                for i, (label, key) in enumerate([("Nahkampf", "rider_melee"), ("Fernkampf", "rider_ranged"),
                                                  ("Verteidigung", "rider_defense")])) + 14
        half = col / 2 - 10
        y_lp = self.pips(x, y, "Lebenspunkte" + (f" · Zähigkeit {r.toughness}" if r.toughness else ""),
                         v["rider_lp"], half, key="rider_lp")
        y_mut = self.pips(x + col / 2, y, "Mut", v["courage"], half, key="courage")
        y_lp = self.pips(x, y_lp + 6, "Wunden (bei 0 LP)", WOUNDS, half, color=WARN, key="rider_wounds", taken=True)
        y = max(y_lp, y_mut) + 8
        mods = v["skill_mods"]
        skills = [(k, f"{x_} ({mods[k]:+d})" if mods.get(k) else x_) for k, x_ in r.skills.items()]
        y_s = self.table(x, y, half, "Fertigkeiten", skills)
        items = load_items()
        slot = lambda kind, name: (f"{kind}: {name or '–'}" +
                                   (f"  ({fmt_mods(items[name]['mods'])})" if name in items else ""), "")
        gear = [slot("Waffe", r.weapon), slot("Rüstung", r.armor)] + [(f"• {g}", "") for g in r.gear]
        y_g = self.table(x + col / 2, y, half, "Ausrüstung & Inventar", gear)
        bottom_left = max(y_s, y_g)

        # dragon column
        x = 2 * m + col
        y = self.title(x, top, col, "Drache")
        blank = self.printing and not has_dragon(sheet)  # print version without dragon: empty form to fill in
        if not has_dragon(sheet) and not blank:  # campaign start: no dragon yet
            self.create_rectangle(x, y + 4, x + col, y + 124, outline=BORDER, dash=(4, 4))
            self.text(x + col / 2, y + 44, "Noch kein Drache", 16, MUTED, SERIF, "center", bold=True)
            self.text(x + col / 2, y + 76, "Wähle im Editor eine Art, sobald ein Drache gezähmt ist.",
                      9, MUTED, anchor="center")
            y = max(bottom_left, y + 140) + 12
            return self._draw_bond(sheet, v, m, W, y)
        fx = x
        header = [("Name", d.name, .22), ("Art", spec.get("name", d.species), .33),
                  ("Klasse", spec.get("cls", "?"), .15), ("Phase", v["phase"], .30)]
        for label, value, share in header:
            self.field(fx, y, col * share, label, " " if blank else value)
            fx += col * share
        y += 50
        for i, attr in enumerate(DRAGON_ATTRS):
            limit = min(attr_cap, pot.get(attr, attr_cap))
            sub = "Pot. ___" if blank else f"Pot. {pot.get(attr, '?')}" if pot else f"max {limit}"
            self.stat(x + i * (col / 4), y, attr, "" if blank else d.attributes.get(attr, 0), sub, w=col / 4 - 10)
        y += 108
        if blank:
            combat = [("Kampf", ("", "Kampfbasis + Training + Rüstung/Sattel"), "__"),
                      ("Schuss", ("", "Sinne + Training"), "__"),
                      ("Verteidigung", ("", "Tempo ÷ 2 (aufgerundet) + Rüstung"), None)]
        else:
            shot = (d.attributes.get("Sinne", 0) + d.training,
                    f"Sinne {d.attributes.get('Sinne', 0)} + Training {d.training}")
            combat = [("Kampf", v["dragon_attack"], v["dragon_melee_dmg"]), ("Schuss", shot, v["dragon_shot_dmg"]),
                      ("Verteidigung", v["dragon_defense"], None)]
        third = col / 3
        y = max(self.combat(x + i * third, y, third - 10, label, *value, dmg=dmg)
                for i, (label, value, dmg) in enumerate(combat)) + 14
        quarter = col / 4 - 10
        if blank:  # LP depend on the dragon: write them in; at most 6 shots for any species
            y_lp = self.write_in(x, y, "Lebenspunkte", half)
            y_sh = self.pips(x + col / 2, y, "Schüsse", 6, quarter, color=SEA, key="shots")
        else:
            y_lp = self.pips(x, y, "Lebenspunkte" + (f" · Zähigkeit {d.toughness}" if d.toughness else ""),
                             v["dragon_lp"], half, key="dragon_lp")
            y_sh = self.pips(x + col / 2, y, "Schüsse", v["shots"], quarter, color=SEA, key="shots")
        self.text(x + col * 3 / 4, y, "TRAINING / ZW", 8, MUTED)
        self.text(x + col * 3 / 4, y + 16, "     /" if blank else f"{d.training}  /  {spec.get('zw', '?')}",
                  16, TEXT, SERIF, bold=True)
        y_lp = self.pips(x, y_lp + 6, "Wunden (bei 0 LP)", WOUNDS, half, color=WARN, key="dragon_wounds", taken=True)
        y = max(y_lp, y_sh, y + 44) + 8
        get = lambda key: "" if blank else spec.get(key, "–")
        abilities = [(f"Grundschuss: {get('shot')}", ""), (f"Art: {get('special')}", ""),
                     (f"Klasse: {get('class_ability')}", "")]
        y_a = self.table(x, y, half, "Fähigkeiten  (gebraucht: Kreis ausmalen)" if self.printing
                         else "Fähigkeiten  (● bereit  ○ gebraucht)", abilities,
                         flags=(None, "special", "class"))
        armor = [("Rüstung:", ""), ("Sattel:", "")] if blank else [slot("Rüstung", d.armor), slot("Sattel", d.saddle)]
        y_a = self.table(x, y_a + 10, half, "Ausrüstung", armor)
        yes = lambda flag: "ja" if flag else "nein"
        moves = ("Fliegt ja / nein · Schwimmt ja / nein · Reitbar ja / nein" if blank else
                 f"Fliegt {yes(spec.get('flies'))} · Schwimmt {yes(spec.get('swims'))} · "
                 f"Reitbar {yes(spec.get('rideable'))}")
        traits = [(moves, ""), (f"Macke: {'' if blank else d.quirk or '–'}", ""),
                  (f"Schwäche: {get('weakness')}", ""), (f"Lieblingsfutter: {get('food')}", "")]
        y_q = self.table(x + col / 2, y, half, "Eigenheiten", traits)
        behavior = [(" ", "")] * 3 if blank else [(d.behavior or "–", "")]
        y_q = self.table(x + col / 2, y_q + 10, half, "Verhalten", behavior)
        y = max(bottom_left, y_a, y_q) + 12
        self._draw_bond(sheet, v, m, W, y)

    def write_in(self, x, y, label, width):
        """Empty box to write a value in by hand: current | max (print version)."""
        self.text(x, y, label.upper(), 8, MUTED)
        self.create_rectangle(x, y + 16, x + width, y + 46, outline=BORDER, fill=PANEL)
        self.create_line(x + width * .62, y + 16, x + width * .62, y + 46, fill=BORDER)
        self.text(x + 6, y + 19, "aktuell", 7, MUTED)
        self.text(x + width * .62 + 6, y + 19, "max", 7, MUTED)
        return y + 50

    def _draw_bond(self, sheet, v, m, W, y):
        """Bond track across the full width (only with a dragon), then rule warnings."""
        if has_dragon(sheet) or self.printing:  # the print version always has the track to fill in
            y = self._bond_track(sheet, v, m, W, y)
        for warning in [] if self.printing else check(sheet, v):
            self.text(m, y, f"! {warning}", 9, WARN)
            y += 18
        self.configure(scrollregion=(0, 0, W, y + m))

    def _bond_track(self, sheet, v, m, W, y):
        y = self.title(m, y, W - 2 * m, "Bindung")
        box = (W - 2 * m - 160) / 20
        for i in range(20):
            bx = m + i * box
            self.create_rectangle(bx + 2, y, bx + box - 2, y + 22, outline=BORDER,
                                  fill=ACCENT if i < sheet.bond and not self.printing else PANEL,
                                  width=2 if i % 5 == 4 else 1)
        for i, name in enumerate(BOND_TIERS[:4]):
            self.text(m + (i * 5 + 2.5) * box, y + 28, f"{name} +{i} W6" if self.printing else name, 8,
                      ACCENT if v["tier"] == i and not self.printing else MUTED, anchor="n")
        self.text(W - m, y - 4, "     /20" if self.printing else f"{sheet.bond}/20", 18, TEXT, SERIF, "ne", bold=True)
        self.text(W - m, y + 26, "Teamwork je Stufe" if self.printing else f"Teamwork +{v['teamwork']} W6",
                  9, SEA, anchor="ne", bold=True)
        self.text(W - m - 20, y + 44, f"Rettung (−{BOND_SAVE_COST} Bindung, 1× pro Tag)", 9, MUTED, anchor="ne")
        self.flag(W - m - 7, y + 52, "bond_save")
        return y + 70


# --- main window --------------------------------------------------------------

class Overlay(tk.Tk):
    def __init__(self, path=None):
        super().__init__()
        self.title("HTTYD - Drachenreiter von Berk")
        self.geometry("1280x780")
        apply_dark_theme(self)
        self.species = load_species()
        self.items = load_items()
        self.slot_boxes = {}    # slot key -> combobox, refilled when items.json is reloaded
        self.hints = {}         # spin field key -> hint label (max value)
        self.locked = {}        # key -> combobox that locks once chosen (origin, role)
        self.chosen = {}        # key -> confirmed value of a locked combobox
        self.vars = {}          # field key -> StringVar
        self.loading = False    # suppresses refresh while filling the form
        self.adjusting = False  # suppresses EP logic while the program itself changes values
        self.committed = {}     # last accepted numeric values, used to price changes
        self.track = {}         # in-play tracking from the character sheet (lost LP, used abilities)
        self._refresh_job = None  # pending idle refresh (several field changes are merged into one)
        self._shown = {}          # label -> last text, avoids needless widget reconfiguration
        self.path = None
        self.settings = load_settings()
        self.free_edit = tk.BooleanVar(value=self.settings["free_edit"])
        self.topmost = tk.BooleanVar(value=self.settings["topmost"])
        self.attributes("-topmost", self.topmost.get())
        self.start_xp = tk.StringVar(value=str(self.settings["start_xp"]))
        self.start_xp.trace_add("write", lambda *_: self.update_mode())

        self._build_toolbar()
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tabs.add(self._build_sheet_tab(), text="Bearbeiten")
        self.tabs.add(self._build_view_tab(), text="Charakterbogen")
        self.tabs.add(self._build_notes_tab(), text="Notizen")
        self.tabs.add(self._build_list_tab(), text="Drachenliste")
        self.tabs.add(self._build_items_tab(), text="Items")
        self.tabs.add(self._build_rules_tab(), text="Regeln")
        self.update_mode()
        self.set_sheet(load(path) if path else example(), path)
        if updater.can_self_update() and self.settings.get("update_check", True):
            self.after(1500, self.check_updates)  # quietly, once the window is up

    # --- toolbar / file handling
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(10, 10, 10, 6))
        bar.pack(fill="x")
        ttk.Label(bar, text="Drachenreiter von Berk", font=(SERIF[0], 14, "bold"),
                  foreground=ACCENT).pack(side="left", padx=(0, 16))
        menu_button = ttk.Menubutton(bar, text="☰  Menü")
        menu = tk.Menu(menu_button, tearoff=False, bg=PANEL, fg=TEXT, activebackground=ACCENT,
                       activeforeground=BG, bd=0, relief="flat", font=FONT)
        for entry in [("Neu", self.new, "Strg+N"), ("Laden …", self.open, "Strg+O"),
                                     ("Speichern", self.save, "Strg+S"),
                                     ("Speichern unter …", self.save_as, "Strg+Shift+S"), None,
                                     ("Einstellungen …", self.open_settings, ""),
                                     ("Nach Updates suchen …", lambda: self.check_updates(quiet=False), ""),
                                     ("Über …", self.about, ""), None,
                                     ("Beenden", self.destroy, "")]:
            if entry is None:
                menu.add_separator()
            else:
                label, command, keys = entry
                menu.add_command(label=label, command=command, accelerator=keys)
        menu_button["menu"] = menu
        menu_button.pack(side="left", padx=3)
        for keys, command in [("<Control-n>", self.new), ("<Control-o>", self.open), ("<Control-s>", self.save),
                              ("<Control-Shift-S>", self.save_as)]:
            self.bind_all(keys, lambda _, c=command: c())
        self.mode = ttk.Label(bar, style="Muted.TLabel")
        self.mode.pack(side="left", padx=12)
        self.status = ttk.Label(bar, style="Muted.TLabel")
        self.status.pack(side="right")

    def rest(self, fed=True):
        """Rest (once per day). Fed: eats 1 Proviant from the inventory and heals.
        Brotlose Nacht: abilities still reset, but no healing and -1 LP each (not below 1)."""
        note = ""
        if fed:
            gear = list(self.gear.get(0, "end"))
            food = next((i for i, g in enumerate(gear) if g.startswith(("Proviant", "Fischkorb"))), None)
            if food is None:
                note = "  Achtung: kein Proviant im Inventar, eigentlich wäre das eine brotlose Nacht."
            else:
                note = f"  {gear[food]} gegessen."
                self.gear.delete(food)
        sheet = self.collect()
        self.track = rest(sheet, fed)
        self.refresh()
        if fed:
            self.info.config(text=f"Rast: Fähigkeiten bereit, Schüsse und Mut voll, Reiter +{sheet.rider.toughness + 2} LP, "
                                  f"Drache +{sheet.dragon.toughness + 2} LP.{note}")
        else:
            self.info.config(text="Brotlose Nacht: Fähigkeiten bereit, Schüsse und Mut voll, keine Heilung, "
                                  "Reiter und Drache −1 LP (nicht unter 1).")

    def new(self):
        self.set_sheet(Sheet(xp=self.settings["start_xp"]), None)  # new riders spend start EP in EP mode
        self.info.config(text=f"Neuer Reiter mit {self.settings['start_xp']} Start-EP. Werte im EP-Modus kaufen.")

    def open(self):
        path = filedialog.askopenfilename(filetypes=[("Charakterbogen", "*.json")])
        if path:
            try:
                self.set_sheet(load(path), path)
            except (ValueError, KeyError, TypeError) as err:
                messagebox.showerror("Fehler", f"Datei ungültig:\n{err}")

    def save(self):
        if not self.path:
            return self.save_as()
        save(self.collect(), self.path)
        self.status.config(text=f"Gespeichert: {Path(self.path).name}")

    def save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Charakterbogen", "*.json")])
        if path:
            self.path = path
            self.save()

    # --- character sheet tab
    def _field(self, parent, row, label, key, kind="entry", values=(), maxv=20):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=1)
        var = self.vars[key] = tk.StringVar()
        var.trace_add("write", lambda *_, k=key: self.on_change(k))
        if kind == "spin":  # spinbox plus a hint label to its right (e.g. "max: 2")
            cell = ttk.Frame(parent, style="Card.TFrame")
            cell.grid(row=row, column=1, sticky="w", pady=1)
            widget = ttk.Spinbox(cell, from_=0, to=maxv, width=5, textvariable=var)
            widget.pack(side="left")
            self.hints[key] = ttk.Label(cell, style="Card.TLabel", foreground=MUTED)
            self.hints[key].pack(side="left", padx=(12, 0))
        else:
            widget = ttk.Combobox(parent, values=values, textvariable=var) if kind == "combo" \
                else ttk.Entry(parent, textvariable=var)
            widget.grid(row=row, column=1, sticky="ew", pady=1)
        return widget

    def _attr_row(self, parent, row, prefix, attrs, maxv=6, label="Attribute"):
        """Several small number fields side by side in a single row."""
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=1)
        line = ttk.Frame(parent, style="Card.TFrame")
        line.grid(row=row, column=1, sticky="w", pady=1)
        for attr in attrs:
            key = f"{prefix}.{attr}" if prefix else attr
            var = self.vars[key] = tk.StringVar()
            var.trace_add("write", lambda *_, k=key: self.on_change(k))
            ttk.Label(line, text=attr, style="Card.TLabel", foreground=MUTED).pack(side="left", padx=(0, 3))
            ttk.Spinbox(line, from_=0, to=maxv, width=2, textvariable=var).pack(side="left", padx=(0, 6))

    def _group(self, parent, title, **pack):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 6, 12, 8))
        card.pack(**({"fill": "x", "pady": (0, 6)} | pack))
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text=title.upper(), style="Title.TLabel").grid(row=0, column=0, columnspan=2,
                                                                      sticky="w", pady=(0, 2))
        box = ttk.Frame(card, style="Card.TFrame")
        box.grid(row=1, column=0, columnspan=2, sticky="ew")
        box.columnconfigure(1, weight=1)
        return box

    def _column(self, parent, title, expand=False):
        """A full-height card used as one column of the editor."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 6, 12, 10))
        card.pack(side="left", fill="both", expand=expand, padx=(0, 8))
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text=title.upper(), style="Title.TLabel").grid(row=0, column=0, columnspan=2,
                                                                      sticky="w", pady=(0, 4))
        return card

    def _build_sheet_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 6))
        g = self._group(top, "Allgemein", side="left", fill="y", pady=0, padx=(0, 8))
        self._field(g, 0, "Stufe", "Stufe", "spin", maxv=12)
        self._field(g, 1, "Bindung", "Bindung", "spin", maxv=20)
        self._field(g, 2, "EP", "EP", "spin", maxv=999)
        self.bond_row = [w for w in g.grid_slaves() if int(w.grid_info()["row"]) == 1]  # hidden without dragon
        self._cost_table(self._group(top, "Kostentabelle (EP)", side="left", fill="both", expand=True, pady=0))
        self.warnings = ttk.Label(tab, foreground=WARN)  # rule warnings below the columns
        self.warnings.pack(side="bottom", anchor="w")
        self.info = ttk.Label(tab, foreground=ACCENT)    # EP purchases and blocked changes
        self.info.pack(side="bottom", anchor="w", pady=(6, 0))
        cols = ttk.Frame(tab)
        cols.pack(fill="both", expand=True)

        # rider: identity, attributes, expandable gear list
        r = self._column(cols, "Reiter")
        self._field(r, 1, "Name", "rider.name")
        # origin (chosen once at the start) and role (from level 3) are fixed once chosen, except in free edit
        self._locked_combo(r, 2, "Herkunft", "rider.origin", ORIGINS)
        self._locked_combo(r, 3, "Rolle", "rider.role", ROLES)
        for i, attr in enumerate(RIDER_ATTRS, start=4):
            self._field(r, i, attr, f"rider.attr.{attr}", "spin", maxv=6)
        self._field(r, 8, "Zähigkeit", "rider.toughness", "spin", maxv=4)
        self._slot(r, 9, "Waffe", "rider.weapon")
        self._slot(r, 10, "Rüstung", "rider.armor")
        ttk.Label(r, text="INVENTAR", style="Title.TLabel").grid(row=11, column=0, columnspan=2,
                                                               sticky="w", pady=(12, 4))
        self.gear = tk.Listbox(r, height=4, bg=FIELD, fg=TEXT, selectbackground=ACCENT, selectforeground=BG,
                               relief="flat", highlightthickness=0, activestyle="none", font=FONT)
        self.gear.grid(row=12, column=0, columnspan=2, sticky="nsew")
        r.rowconfigure(12, weight=1)
        add = ttk.Frame(r, style="Card.TFrame")
        add.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.gear_entry = ttk.Combobox(add, values=self.item_names("Sonstiges", "Reiter"))
        self.gear_entry.pack(side="left", fill="x", expand=True)
        self.gear_entry.bind("<Return>", lambda _: self.add_gear())
        ttk.Button(add, text="+", width=3, command=self.add_gear, style="Accent.TButton").pack(side="left", padx=4)
        ttk.Button(add, text="–", width=3, command=self.remove_gear).pack(side="left")

        # skills: every skill of the rulebook, grouped by attribute, 0 = not learned
        k = self._column(cols, "Fertigkeiten", expand=True)
        row = 1
        for attr, skills in SKILLS.items():
            self.hints[f"group.{attr}"] = ttk.Label(k, text=attr, style="Card.TLabel", foreground=ACCENT)
            self.hints[f"group.{attr}"].grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 1))
            row += 1
            for i, skill in enumerate(skills):
                cell = ttk.Frame(k, style="Card.TFrame")
                cell.grid(row=row + i // 3, column=i % 3, sticky="ew", padx=(0, 16))
                var = self.vars[f"skill.{skill}"] = tk.StringVar(value="0")
                var.trace_add("write", lambda *_, k=f"skill.{skill}": self.on_change(k))
                ttk.Spinbox(cell, from_=0, to=5, width=2, textvariable=var).pack(side="right")
                ttk.Label(cell, text=skill, style="Card.TLabel").pack(side="left")
            row += (len(skills) + 2) // 3
        for c in range(3):
            k.columnconfigure(c, weight=1)

        # dragon
        d = self._column(cols, "Drache")
        d.columnconfigure(1, weight=1, minsize=230)
        self._field(d, 1, "Name", "dragon.name")
        self.species_box = self._field(d, 2, "Art", "dragon.species", "combo", sorted(self.species))
        for i, attr in enumerate(DRAGON_ATTRS, start=3):
            self._field(d, i, attr, f"dragon.attr.{attr}", "spin", maxv=6)
        self._field(d, 7, "Training", "dragon.training", "spin", maxv=4)
        self._field(d, 8, "Zähigkeit", "dragon.toughness", "spin", maxv=4)
        # fixed by species/class, shown read-only
        ttk.Label(d, text="Art-Werte", style="Card.TLabel").grid(row=9, column=0, sticky="nw", pady=(4, 1))
        self.species_info = ttk.Label(d, style="Card.TLabel", foreground=MUTED, justify="left", wraplength=230)
        self.species_info.grid(row=9, column=1, sticky="w", pady=(4, 1))
        # individual per dragon
        self._field(d, 10, "Macke", "dragon.quirk")
        ttk.Label(d, text="Verhalten", style="Card.TLabel").grid(row=11, column=0, sticky="nw", pady=1)
        self.behavior = tk.Text(d, height=2, width=28, wrap="word", font=FONT, bg=FIELD, fg=TEXT,
                                insertbackground=ACCENT, relief="flat", highlightthickness=1,
                                highlightbackground=BORDER, highlightcolor=ACCENT, padx=4, pady=3)
        self.behavior.grid(row=11, column=1, sticky="ew", pady=1)
        self.behavior.bind("<KeyRelease>", lambda _: self.schedule_refresh())
        self._slot(d, 12, "Rüstung", "dragon.armor")
        self._slot(d, 13, "Sattel", "dragon.saddle")
        # everything below "Art" is hidden until a dragon is chosen
        self.dragon_rows = [w for w in d.grid_slaves() if int(w.grid_info()["row"]) >= 3]
        self.no_dragon = ttk.Label(d, text="Noch kein Drache.\nSobald einer gezähmt ist, oben die Art wählen –\n"
                                           "dann erscheinen hier seine Werte.", style="Card.TLabel",
                                   foreground=MUTED, justify="left")
        self.no_dragon.grid(row=3, column=0, columnspan=2, sticky="w", pady=(16, 0))

        return tab

    def _locked_combo(self, parent, row, label, key, values):
        """Dropdown that becomes read-only once a value is chosen (see refresh)."""
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=1)
        cell = ttk.Frame(parent, style="Card.TFrame")
        cell.grid(row=row, column=1, sticky="ew", pady=1)
        self.vars[key] = tk.StringVar()
        self.vars[key].trace_add("write", lambda *_: self.schedule_refresh())
        self.locked[key] = box = ttk.Combobox(cell, values=values, textvariable=self.vars[key], width=16)
        box.pack(side="left", fill="x", expand=True)
        box.bind("<<ComboboxSelected>>", lambda _: self.confirm_choice(key, label))
        self.hints[key] = ttk.Label(cell, style="Card.TLabel", foreground=MUTED)
        self.hints[key].pack(side="left", padx=(8, 0))

    def confirm_choice(self, key, label):
        """Origin and role are permanent in EP mode, so ask once before fixing them."""
        value = self.vars[key].get()
        if self.free_edit.get() or value == self.chosen[key]:
            self.chosen[key] = value
            return
        if messagebox.askyesno(f"{label} festlegen", f"{label} «{value}» wählen?\n\nSie kann danach nur noch "
                                                    "mit «Freies Editieren» geändert werden."):
            self.chosen[key] = value
            self.info.config(text=f"{label} «{value}» festgelegt.")
        else:
            self.vars[key].set(self.chosen[key])

    def item_names(self, kind, owner):
        return [""] + sorted(n for n, i in self.items.items() if i["type"] == kind and i["for"] == owner)

    def _slot(self, parent, row, label, key):
        """Equipment slot: dropdown of matching items from items.json (empty = nothing equipped)."""
        box = self._field(parent, row, label, key, "combo", self.item_names(*SLOTS[key]))
        box.configure(state="readonly")
        self.slot_boxes[key] = box

    def add_gear(self):
        item = self.gear_entry.get().strip()
        if item:
            self.gear.insert("end", item)
            self.gear_entry.delete(0, "end")
            self.refresh()

    def remove_gear(self):
        for index in reversed(self.gear.curselection()):
            self.gear.delete(index)
        self.refresh()

    def set_sheet(self, sheet, path):
        """Fill the form from a Sheet."""
        self.loading, self.path = True, path
        r, d, v = sheet.rider, sheet.dragon, self.vars
        known = {skill for skills in SKILLS.values() for skill in skills}
        self.extra_skills = {k: x for k, x in r.skills.items() if k not in known}  # keep custom skills
        values = {
            "Stufe": sheet.level, "Bindung": sheet.bond, "EP": sheet.xp,
            "rider.name": r.name, "rider.origin": r.origin, "rider.role": r.role,
            "dragon.name": d.name, "dragon.species": d.species, "dragon.training": d.training,
            "dragon.quirk": d.quirk, "rider.toughness": r.toughness, "dragon.toughness": d.toughness,
            "rider.weapon": r.weapon, "rider.armor": r.armor, "dragon.armor": d.armor, "dragon.saddle": d.saddle,
            **{f"rider.attr.{k}": x for k, x in r.attributes.items()},
            **{f"dragon.attr.{k}": x for k, x in d.attributes.items()},
            **{f"skill.{k}": r.skills.get(k, 0) for k in known},
        }
        for key, value in values.items():
            v[key].set(value)
        self.chosen = {"rider.origin": r.origin, "rider.role": r.role}
        self.prev_species = d.species
        self.gear.delete(0, "end")
        self.gear.insert("end", *r.gear)
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", sheet.notes)
        self.behavior.delete("1.0", "end")
        self.behavior.insert("1.0", d.behavior)
        self.track = dict(sheet.track)
        self.loading = False
        self.snapshot()
        self.info.config(text="")
        self.status.config(text=Path(path).name if path else "Neuer Bogen (nicht gespeichert)")
        self.refresh()

    def collect(self):
        """Build a Sheet from the form."""
        v = {key: var.get() for key, var in self.vars.items()}
        skills = {k[6:]: to_int(x) for k, x in v.items() if k.startswith("skill.") and to_int(x) > 0}
        rider = Rider(v["rider.name"], v["rider.origin"], v["rider.role"],
                      {a: to_int(v[f"rider.attr.{a}"], 1) for a in RIDER_ATTRS},
                      {**skills, **self.extra_skills}, list(self.gear.get(0, "end")),
                      v["rider.weapon"], v["rider.armor"], to_int(v["rider.toughness"]))
        dragon = Dragon(v["dragon.name"], v["dragon.species"],
                        {a: to_int(v[f"dragon.attr.{a}"], 0) for a in DRAGON_ATTRS},
                        to_int(v["dragon.training"]), v["dragon.quirk"], self.behavior.get("1.0", "end-1c").strip(),
                        v["dragon.armor"], v["dragon.saddle"], to_int(v["dragon.toughness"]))
        level = min(max(to_int(v["Stufe"], 1), 1), 12)
        bond = min(max(to_int(v["Bindung"]), 0), 20)
        return Sheet(level, bond, to_int(v["EP"]), self.notes.get("1.0", "end-1c"), rider, dragon, dict(self.track))

    # --- EP economy: every raise costs EP unless free editing is on
    def snapshot(self):
        self.committed = {k: to_int(v.get()) for k, v in self.vars.items()
                          if cost_kind(k) or k in ("EP", "Stufe")}

    def on_species_change(self):
        """A rider without a dragon who picks a species has tamed one: free start values (all 1, bond 1)."""
        species = self.vars["dragon.species"].get()
        tamed = not self.loading and self.prev_species in ("", "-") and species in self.species
        if tamed:
            for attr in DRAGON_ATTRS:
                if to_int(self.vars[f"dragon.attr.{attr}"].get()) == 0:
                    self._set(f"dragon.attr.{attr}", 1)
            if to_int(self.vars["Bindung"].get()) == 0:
                self._set("Bindung", 1)
            if self.vars["dragon.name"].get() in ("", "-"):
                self._set("dragon.name", species)
            for key in ("dragon_lp", "shots", "used"):  # a new dragon starts fresh
                self.track.pop(key, None)
            self.snapshot()
            self.info.config(text=f"{species} gezähmt: Attribute auf 1, Bindung 1. Die 2 Startpunkte mit "
                                  "«Freies Editieren» verteilen.")
        if species in self.species or species in ("", "-"):
            self.prev_species = species
        self.schedule_refresh()

    def _set(self, key, value):
        self.adjusting = True
        self.vars[key].set(value)
        self.adjusting = False

    def _revert(self, key, value):
        """Undo a blocked change. Tk ignores a set inside the variable's own write trace for the widget,
        so the value is set again once the trace has finished."""
        self._set(key, value)
        self.after_idle(lambda: self._set(key, value))

    def _limit(self, key, sheet):
        """Highest allowed value for a field at the current level (and species potential)."""
        v = derive(sheet)
        attr_cap, skill_cap = v["caps"]
        if key.startswith("skill."):
            return skill_limit(sheet, key[6:], v["caps"])
        if key.startswith("rider.attr."):
            return attr_limit(sheet, key[11:], v["caps"])
        if key.startswith("dragon.attr.") and v["spec"]:
            return min(attr_cap, v["spec"]["potential"][key[12:]])
        if key in ("rider.toughness", "dragon.toughness"):
            return tough_limit(sheet, key.startswith("rider"), v["caps"])
        return skill_cap if key == "dragon.training" else attr_cap

    def on_change(self, key):
        if key == "dragon.species":
            return self.on_species_change()
        raw = self.vars[key].get()
        if self.loading or self.adjusting or key not in self.committed or not raw.isdigit():
            return self.schedule_refresh()
        old, new = self.committed[key], int(raw)
        if self.free_edit.get() or new == old:
            self.committed[key] = new
            self.info.config(text="")
            return self.schedule_refresh()
        label = {"dragon.training": "Training", "rider.toughness": "Zähigkeit Reiter",
                 "dragon.toughness": "Zähigkeit Drache"}.get(key, key.split(".")[-1])
        if new < old:  # lowering is only allowed in free edit mode
            self._revert(key, old)
            self.info.config(text=f"{label} kann nur mit «Freies Editieren» verringert werden.")
            return self.schedule_refresh()
        kind = cost_kind(key)
        if not kind:  # EP awards and level-ups cost nothing
            self.committed[key] = new
            self.info.config(text="")
            return self.schedule_refresh()
        limit = self._limit(key, self.collect())
        price, ep = upgrade_cost(kind, old, new), self.committed["EP"]
        if new > limit:
            self._revert(key, old)
            self.info.config(text=f"{label}: Maximum auf dieser Stufe ist {limit}.")
        elif price > ep:
            self._revert(key, old)
            self.info.config(text=f"{label} {old} → {new} kostet {price} EP, vorhanden sind {ep} EP.")
        else:
            self.committed[key], self.committed["EP"] = new, ep - price
            self._set("EP", ep - price)
            self.info.config(text=f"{label} {old} → {new}: −{price} EP (Rest {ep - price} EP)")
        self.schedule_refresh()

    # --- settings tab
    def open_settings(self):
        """Settings dialog (opened from the menu); changes apply and are saved at once."""
        if getattr(self, "settings_win", None) and self.settings_win.winfo_exists():
            return self.settings_win.lift()
        win = self.settings_win = tk.Toplevel(self, bg=BG, padx=12, pady=12)
        win.title("Einstellungen")
        win.transient(self)
        win.resizable(False, False)
        card = self._group(win, "Bearbeitung")
        ttk.Checkbutton(card, text="Freies Editieren", variable=self.free_edit, style="Card.TCheckbutton",
                        command=self.update_mode).grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Werte ohne EP-Kosten setzen und auch verringern – für die Charaktererschaffung "
                             "oder Korrekturen durch die Spielleitung.", style="Card.TLabel",
                  foreground=MUTED, wraplength=380, justify="left").grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Checkbutton(card, text="Fenster immer im Vordergrund", variable=self.topmost, style="Card.TCheckbutton",
                        command=self.update_mode).grid(row=2, column=0, sticky="w")
        start = ttk.Frame(card, style="Card.TFrame")
        start.grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(start, text="Start-EP für neue Reiter", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(start, from_=0, to=200, width=5, textvariable=self.start_xp).pack(side="left", padx=8)
        ttk.Label(card, text="Standard 24 (entspricht 2 Attributen auf 2 + 4 Fertigkeiten auf 1)",
                  style="Card.TLabel", foreground=MUTED, wraplength=380, justify="left").grid(row=4, column=0, sticky="w")

        card = self._group(win, "Updates")
        self.update_check = tk.BooleanVar(value=self.settings.get("update_check", True))
        ttk.Checkbutton(card, text="Beim Start nach neuer Version suchen", variable=self.update_check,
                        style="Card.TCheckbutton", command=self.update_mode).grid(row=0, column=0, sticky="w")
        ttk.Label(card, text=f"Installiert: {updater.current_version()}", style="Card.TLabel",
                  foreground=MUTED).grid(row=1, column=0, sticky="w")
        ttk.Button(win, text="Schliessen", command=win.destroy, style="Accent.TButton").pack(anchor="e", pady=(10, 0))
        win.bind("<Escape>", lambda _: win.destroy())

    # --- updates from GitHub releases
    def check_updates(self, quiet=True):
        """Look for a newer release in the background; quiet: only speak up when there is one."""
        if not updater.can_self_update():
            if not quiet:
                messagebox.showinfo("Updates", "Updates gibt es nur in der installierten Drachenreiter.exe.\n"
                                               "Im Code-Ordner einfach «git pull» verwenden.", parent=self)
            return
        result = {}

        def work():  # network in a thread, the window keeps responding
            try:
                result["release"] = updater.latest_release()
            except Exception as error:  # offline, rate limit, ...
                result["error"] = error

        thread = threading.Thread(target=work, daemon=True)
        thread.start()

        def done():
            if thread.is_alive():
                return self.after(200, done)
            release = result.get("release")
            if result.get("error") or not release:
                if not quiet:
                    messagebox.showwarning("Updates", f"Keine Verbindung zu GitHub.\n{result.get('error', '')}",
                                           parent=self)
            elif updater.is_newer(release["tag"]):
                self.offer_update(release)
            elif not quiet:
                messagebox.showinfo("Updates", f"Du hast die neueste Version ({updater.current_version()}).",
                                    parent=self)
        done()

    def offer_update(self, release):
        notes = release["notes"][:600] + ("…" if len(release["notes"]) > 600 else "")
        if not messagebox.askyesno("Update verfügbar",
                                   f"Version {release['tag']} ist da (installiert: {updater.current_version()}).\n\n"
                                   f"{notes}\n\nJetzt aktualisieren? Das Programm startet danach neu. "
                                   "Eigene Arten, Items, Einstellungen und Charakterbögen bleiben erhalten.",
                                   parent=self):
            return
        self.info.config(text=f"Lade Version {release['tag']} …")
        self.update_idletasks()
        try:
            work, program, notes = updater.download_and_prepare(release["url"])
            updater.launch_swap_and_restart(work, program)
        except Exception as error:
            messagebox.showerror("Update", f"Update fehlgeschlagen:\n{error}", parent=self)
            return
        self.destroy()  # the update script waits for this, swaps the files and restarts

    def about(self):
        messagebox.showinfo("Über", f"Drachenreiter von Berk  ·  Version {updater.current_version()}\n"
                                    "Charakterbogen-Werkzeug für das HTTYD-Pen-&-Paper\n\n"
                                    "Reiter und Drache bearbeiten, Charakterbogen mit Kampf-Tracking, Drachenliste, "
                                    "Items, Regelwerk und PDF-Druckversion.\n\n"
                                    f"Daten: {DATA_DIR}\n"
                                    f"github.com/{updater.REPO}", parent=self)

    def _cost_table(self, box):
        """Compact EP cost grid: factor x new value, summed over several steps."""
        heads = ["", "Faktor", "→1", "→2", "→3", "→4", "→5"]
        box.columnconfigure(1, weight=0)
        for c, head in enumerate(heads):
            ttk.Label(box, text=head, style="Card.TLabel", foreground=MUTED,
                      font=(FONT[0], 9, "bold")).grid(row=0, column=c, sticky="w" if c == 0 else "e", padx=(0, 14))
        shown = {"Reiter-Attribut": "Reiter-Attribut / Zähigkeit", "Drachen-Attribut": "Drachen-Attribut / Zähigkeit"}
        rows = [(shown.get(name, name), f) for name, f in COSTS.values() if "Zähigkeit" not in name]
        for r, (name, factor) in enumerate(rows, start=1):
            row = [name, f"× {factor}", *(factor * n for n in range(1, 6))]
            for c, value in enumerate(row):
                ttk.Label(box, text=value, style="Card.TLabel", font=(FONT[0], 9),
                          foreground=TEXT if c else MUTED).grid(row=r, column=c, sticky="w" if c == 0 else "e",
                                                               padx=(0, 14))
        ttk.Label(box, text="Mehrere Stufen = Summe, z. B. Fertigkeit 1→3 = 4 + 6 = 10 EP",
                  style="Card.TLabel", foreground=MUTED, font=(FONT[0], 9)).grid(row=0, column=len(heads),
                                                                               rowspan=5, sticky="nw", padx=(10, 0))

    def update_mode(self):
        """Apply and persist settings, show the edit mode in the toolbar."""
        self.settings.update(free_edit=self.free_edit.get(), topmost=self.topmost.get())
        if hasattr(self, "update_check"):
            self.settings["update_check"] = self.update_check.get()
        if hasattr(self, "start_xp") and self.start_xp.get().isdigit():
            self.settings["start_xp"] = int(self.start_xp.get())
        try:
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.attributes("-topmost", self.topmost.get())
        free = self.free_edit.get()
        self.mode.config(text="● Freies Editieren" if free else "● EP-Modus",
                         foreground=WARN if free else MUTED)
        self.snapshot()
        if self.chosen:  # re-evaluate locked fields (origin, role) for the new mode
            self.refresh()

    def debounce(self, name, func, ms=120):
        """Run func once typing pauses (search fields refill a whole table)."""
        jobs = self.__dict__.setdefault("_jobs", {})
        if jobs.get(name):
            self.after_cancel(jobs[name])
        jobs[name] = self.after(ms, lambda: (jobs.pop(name, None), func()))

    def schedule_refresh(self):
        """Refresh once the current event is handled (typing or a spinbox click can write several fields)."""
        if not self._refresh_job:
            self._refresh_job = self.after_idle(self.refresh)

    def _text(self, widget, text):
        """Set a label text only when it changed (each change costs a relayout)."""
        if self._shown.get(widget) != text:
            self._shown[widget] = text
            widget.config(text=text)

    def refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        if self.loading or not hasattr(self, "notes"):
            return
        sheet = self.collect()
        v = derive(sheet)  # computed once per refresh and shared with the sheet view and the checks
        self.view.show(sheet, v)
        self._text(self.view_level, f"Stufe {sheet.level}  ·  {sheet.xp} EP")
        dragon = has_dragon(sheet)
        spec = v["spec"]
        if spec:
            yes = lambda flag: "ja" if flag else "nein"
            # compact: full abilities are on the character sheet
            self._text(self.species_info, f"{spec['cls']} · fliegt {yes(spec['flies'])} · schwimmt "
                                          f"{yes(spec['swims'])} · reitbar {yes(spec['rideable'])}")
        if self._shown.get("dragon") != dragon:  # show dragon values only when there is a dragon
            self._shown["dragon"] = dragon
            for widget in (*self.dragon_rows, *self.bond_row):
                widget.grid() if dragon else widget.grid_remove()
            self.no_dragon.grid_remove() if dragon else self.no_dragon.grid()
        attr_cap, skill_cap = v["caps"]
        pot = v["spec"]["potential"] if v["spec"] else {}
        role = role_attrs(sheet)
        free, chosen = self.free_edit.get(), bool(sheet.rider.role)
        unlocked = sheet.level >= ROLE_LEVEL
        self.locked["rider.role"].configure(state="readonly" if free or (unlocked and not chosen) else "disabled")
        self._text(self.hints["rider.role"], ("" if free else "fest" if chosen and unlocked
                                              else f"ab Stufe {ROLE_LEVEL}" if not unlocked else "wählbar"))
        has_origin = bool(sheet.rider.origin)
        self.locked["rider.origin"].configure(state="readonly" if free or not has_origin else "disabled")
        self._text(self.hints["rider.origin"], "" if free else "fest" if has_origin else "wählbar")
        for attr in RIDER_ATTRS:
            bonus = "  (+1 Rolle)" if attr in role else ""
            self._text(self.hints[f"rider.attr.{attr}"], f"max: {attr_limit(sheet, attr, v['caps'])}{bonus}")
            origin = ORIGIN_BONUS.get(sheet.rider.origin)
            extra = f", {origin} max {skill_cap + 1 + (attr in role)} (Herkunft)" if SKILLS[attr].count(origin) else ""
            self._text(self.hints[f"group.{attr}"],
                f"{attr}   ·   max {skill_cap + (attr in role)}{' (+1 Rolle)' if attr in role else ''}{extra}")
        for attr in DRAGON_ATTRS:
            limit = min(attr_cap, pot.get(attr, attr_cap))
            self._text(self.hints[f"dragon.attr.{attr}"], f"max: {limit}" + (f"  (Pot. {pot[attr]})" if pot else ""))
        self._text(self.hints["dragon.training"], f"max: {skill_cap}")
        for key in ("rider.toughness", "dragon.toughness"):
            limit = tough_limit(sheet, key.startswith("rider"), v["caps"])
            tank = "  Tank" if limit > skill_cap else ""
            self._text(self.hints[key], f"max: {limit}{tank}  (+{TOUGH_LP} LP/Pkt.)")
        self._text(self.warnings, "   ".join(f"! {w}" for w in check(sheet, v)))

    def on_track(self, key, value):
        """Click on the character sheet: set lost points of a resource or toggle an ability flag."""
        if key == "used":
            used = set(self.track.get("used", []))
            used ^= {value}
            self.track["used"] = sorted(used)
            if value == "bond_save":  # spending the save costs bond, undoing it gives it back
                bond = to_int(self.vars["Bindung"].get())
                bond = max(0, bond - BOND_SAVE_COST) if value in used else min(20, bond + BOND_SAVE_COST)
                self._set("Bindung", bond)
                self.committed["Bindung"] = bond
        else:
            self.track[key] = value
        # back above 0 LP (death save 6, healing, bond save): wounds reset at once, unless dead
        v = derive(self.collect())
        for who in ("rider", "dragon"):
            alive = self.track.get(f"{who}_wounds", 0) < WOUNDS
            if alive and v[f"{who}_lp"] - self.track.get(f"{who}_lp", 0) > 0:
                self.track.pop(f"{who}_wounds", None)
        self.refresh()

    # --- read-only sheet and notes tabs
    def _build_view_tab(self):
        tab = ttk.Frame(self.tabs)
        bar = ttk.Frame(tab, padding=(0, 0, 0, 6))
        bar.pack(fill="x")
        self.view_level = ttk.Label(bar, font=(SERIF[0], 14, "bold"), foreground=ACCENT)
        self.view_level.pack(side="left", padx=(4, 18))
        ttk.Button(bar, text="Rasten", command=self.rest).pack(side="left")
        ttk.Button(bar, text="Brotlose Nacht", command=lambda: self.rest(fed=False)).pack(side="left", padx=6)
        ttk.Button(bar, text="Als PDF exportieren", command=self.export_pdf, style="Accent.TButton").pack(side="right")
        ttk.Label(bar, text="Druck: Kreise, Bindung und Flags leer zum Ankreuzen", style="Muted.TLabel").pack(side="right", padx=8)
        self.view = SheetView(tab)
        tab.bind("<Map>", lambda _: self.view.draw_if_dirty())
        self.view.on_track = self.on_track
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.view.yview)
        self.view.configure(yscrollcommand=scroll.set)
        self.view.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.view.bind("<MouseWheel>", lambda e: self.view.yview_scroll(-e.delta // 120, "units"))
        return tab

    def export_pdf(self, path=None):
        """Print version of the character sheet as PDF (A4 landscape, light colours, blank trackers)."""
        sheet = self.collect()
        if not path:
            name = "_".join(filter(None, [sheet.rider.name, sheet.dragon.name if has_dragon(sheet) else ""]))
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                                initialfile=f"{name or 'Charakterbogen'}_Charakterbogen.pdf")
        if not path:
            return
        page = SheetView(self)  # never shown: drawn offscreen at a fixed width
        page.printing, page.fixed_width = True, 1180
        page.sheet, page.values = sheet, derive(sheet)
        page.draw()
        try:
            canvas_to_pdf(page, path, PRINT_COLORS)
            self.info.config(text=f"PDF gespeichert: {Path(path).name}")
        except OSError as error:
            messagebox.showerror("PDF", f"Konnte nicht speichern:\n{error}")
        finally:
            page.destroy()

    def _build_notes_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        ttk.Label(tab, text="Notizen zur Kampagne, zum Charakter und zum Drachen (werden im JSON gespeichert)",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.notes = tk.Text(tab, font=FONT, wrap="word", undo=True, padx=14, pady=12, bg=PANEL, fg=TEXT,
                             insertbackground=ACCENT, selectbackground=ACCENT, selectforeground=BG,
                             relief="flat", highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=ACCENT)
        self.notes.pack(fill="both", expand=True)
        return tab

    # --- rules tab (renders the rulebook markdown)
    def _build_rules_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Springe zu", style="Muted.TLabel").pack(side="left")
        self.chapter = ttk.Combobox(bar, state="readonly", width=40)
        self.chapter.pack(side="left", padx=6)
        self.chapter.bind("<<ComboboxSelected>>", lambda _: self.rules.see(self.chapters[self.chapter.get()]))
        ttk.Button(bar, text="Neu laden", command=self.load_rules).pack(side="right")

        self.rules = tk.Text(tab, wrap="word", padx=24, pady=16, bg=PANEL, fg=TEXT, relief="flat",
                             highlightthickness=0, font=FONT, spacing1=2, spacing3=2)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.rules.yview)
        self.rules.configure(yscrollcommand=scroll.set)
        self.rules.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tags = {"h1": dict(font=(SERIF[0], 20, "bold"), foreground=ACCENT, spacing3=8),
                "h2": dict(font=(SERIF[0], 15, "bold"), foreground=ACCENT, spacing1=16, spacing3=6),
                "bold": dict(font=(FONT[0], 10, "bold")),
                "table": dict(font=MONO, lmargin1=8, wrap="none"),
                "thead": dict(font=(MONO[0], 11, "bold"), foreground=ACCENT, lmargin1=8, wrap="none"),
                "bullet": dict(lmargin1=12, lmargin2=28),
                "muted": dict(foreground=MUTED)}
        for name, options in tags.items():
            self.rules.tag_configure(name, **options)
        self.chapters, self.rules_loaded = {}, False
        tab.bind("<Map>", lambda _: self.rules_loaded or self.load_rules())
        return tab

    def load_rules(self):
        self.rules_loaded = True
        path = find_rules()
        self.rules.config(state="normal")
        self.rules.delete("1.0", "end")
        self.chapters = {}
        if not path:
            self.rules.insert("end", f"{RULES_NAME} nicht gefunden (gleicher Ordner oder ein Ordner höher).", "muted")
        else:
            self._render_markdown(path.read_text(encoding="utf-8").splitlines())
        self.chapter.configure(values=list(self.chapters))
        self.rules.config(state="disabled")

    def _inline(self, text, base=()):
        """Insert a line with **bold** parts; strips `code` and *italic* markers."""
        text = text.replace("`", "")
        for i, part in enumerate(text.split("**")):
            part = part.replace("*", "")
            self.rules.insert("end", part, (*base, "bold") if i % 2 else base)

    def _render_markdown(self, lines):
        table = []
        for line in lines + [""]:
            if line.startswith("|"):
                table.append([c.strip().replace("**", "") for c in line.strip("|").split("|")])
                continue
            if table:  # flush a finished table as aligned monospace columns
                rows = [r for r in table if not set("".join(r)) <= set("-: ")]
                widths = [max(len(r[i]) for r in rows if i < len(r)) for i in range(len(rows[0]))]
                for n, row in enumerate(rows):
                    cells = "  ".join(c.ljust(w) for c, w in zip(row, widths))
                    self.rules.insert("end", cells.rstrip() + "\n", "thead" if n == 0 else "table")
                self.rules.insert("end", "\n")
                table = []
            if line.startswith("# "):
                self.rules.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                self.chapters[line[3:]] = self.rules.index("end-1c")
                self.rules.insert("end", line[3:] + "\n", "h2")
            elif line.startswith(("- [ ] ", "- [x] ")):
                self._inline(("☑ " if line[3] == "x" else "☐ ") + line[6:] + "\n", ("bullet",))
            elif line.startswith("- "):
                self._inline("•  " + line[2:] + "\n", ("bullet",))
            elif line.split(". ")[0].isdigit():
                self._inline(line + "\n", ("bullet",))
            else:
                self._inline(line + "\n")

    # --- items tab (catalogue from items.json)
    def _build_items_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Suche", style="Muted.TLabel").pack(side="left")
        self.item_search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.item_search, width=22).pack(side="left", padx=4)
        self.item_type = tk.StringVar(value="Alle")
        self.item_owner = tk.StringVar(value="Alle")
        for label, var, values in [("Typ", self.item_type, ["Alle", *ITEM_TYPES]),
                                   ("Für", self.item_owner, ["Alle", "Reiter", "Drache"])]:
            ttk.Label(bar, text=label, style="Muted.TLabel").pack(side="left", padx=(16, 0))
            ttk.Combobox(bar, values=values, textvariable=var, width=10, state="readonly").pack(side="left", padx=4)
        for var in (self.item_search, self.item_type, self.item_owner):
            var.trace_add("write", lambda *_: self.debounce("items", self.fill_items))
        ttk.Button(bar, text="Ausrüsten / ins Inventar", command=self.equip_item,
                   style="Accent.TButton").pack(side="right")
        ttk.Button(bar, text="items.json neu laden", command=self.reload_items).pack(side="right", padx=6)
        ttk.Button(bar, text="+ Neues Item", command=self.new_item).pack(side="right")

        cols = ["Name", "Typ", "Für", "Modifikator", "Beschreibung"]
        self.item_tree = ttk.Treeview(tab, columns=cols, show="headings")
        for col, width in zip(cols, [190, 80, 70, 300, 380]):
            self.item_tree.heading(col, text=col)
            self.item_tree.column(col, width=width, anchor="w", stretch=col == "Beschreibung")
        self.item_tree.tag_configure("odd", background=ROW_ALT)
        self.item_tree.bind("<Double-1>", lambda _: self.equip_item())
        self.item_tree.pack(fill="both", expand=True)
        ttk.Label(tab, text="Neue Items in items.json eintragen (Name, type, for, mods, text) und neu laden. "
                            "Modifikatoren wirken nur in einem Slot, nicht im Inventar.",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        self.fill_items()
        return tab

    def fill_items(self):
        query, kind, owner = self.item_search.get().lower(), self.item_type.get(), self.item_owner.get()
        rows = [i for i in self.items.values()
                if (kind == "Alle" or i["type"] == kind) and (owner == "Alle" or i["for"] == owner)
                and query in (i["name"] + " " + i.get("text", "")).lower()]
        rows.sort(key=lambda i: (ITEM_TYPES.index(i["type"]) if i["type"] in ITEM_TYPES else 9, i["for"], i["name"]))
        self.item_tree.delete(*self.item_tree.get_children())
        for n, i in enumerate(rows):
            self.item_tree.insert("", "end", values=[i["name"], i["type"], i["for"], fmt_mods(i.get("mods", {})),
                                                     i.get("text", "")], tags=("odd",) if n % 2 else ())

    def reload_items(self):
        self.items = load_items()
        for key, box in self.slot_boxes.items():
            box.configure(values=self.item_names(*SLOTS[key]))
        self.gear_entry.configure(values=self.item_names("Sonstiges", "Reiter"))
        self.fill_items()
        self.refresh()

    def equip_item(self):
        """Put the selected item into its slot (weapon, armor, saddle) or the rider's inventory."""
        selected = self.item_tree.selection()
        if not selected:
            return
        item = self.items[self.item_tree.item(selected[0], "values")[0]]
        slot = next((k for k, (kind, owner) in SLOTS.items() if (kind, owner) == (item["type"], item["for"])), None)
        if slot:
            self.vars[slot].set(item["name"])
            self.info.config(text=f"{item['name']} ausgerüstet.")
        else:
            self.gear.insert("end", item["name"])
            self.info.config(text=f"{item['name']} ins Inventar gelegt.")
            self.refresh()
        self.tabs.select(0)

    # --- creating new entries (saved straight into items.json / Drachenliste.md)
    def ask(self, title, fields):
        """Small modal form. fields: (key, label, kind, options/default). Returns dict or None."""
        win = tk.Toplevel(self, bg=BG, padx=16, pady=14)
        win.title(title)
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text=title.upper(), style="Title.TLabel", background=BG).grid(row=0, column=0, columnspan=2,
                                                                                    sticky="w", pady=(0, 8))
        values, result = {}, {}
        for row, (key, label, kind, option) in enumerate(fields, start=1):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            var = values[key] = tk.StringVar(value=option if kind != "combo" else option[0])
            widget = (ttk.Combobox(win, values=option, textvariable=var, state="readonly") if kind == "combo"
                      else ttk.Spinbox(win, from_=0, to=6, width=4, textvariable=var) if kind == "spin"
                      else ttk.Entry(win, textvariable=var, width=42))
            widget.grid(row=row, column=1, sticky="w", pady=2)
        error = ttk.Label(win, foreground=WARN)
        error.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def submit():
            result.update({k: v.get().strip() for k, v in values.items()})
            if not result[fields[0][0]]:
                result.clear()
                error.config(text=f"{fields[0][1]} fehlt.")
            else:
                win.destroy()

        buttons = ttk.Frame(win)
        buttons.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Abbrechen", command=win.destroy).pack(side="right")
        ttk.Button(buttons, text="Speichern", command=submit, style="Accent.TButton").pack(side="right", padx=6)
        win.bind("<Return>", lambda _: submit())
        self.wait_window(win)
        return result or None

    def new_item(self):
        data = self.ask("Neues Item", [
            ("name", "Name", "entry", ""), ("type", "Typ", "combo", ITEM_TYPES),
            ("for", "Für", "combo", ["Reiter", "Drache"]),
            ("mods", "Modifikatoren (z. B. Kampf +1, Schaden 2, Reiten -1)", "entry", ""),
            ("text", "Beschreibung", "entry", "")])
        if not data:
            return
        try:
            mods = parse_mods(data["mods"])
            add_item({"name": data["name"], "type": data["type"], "for": data["for"], "mods": mods,
                      "text": data["text"]})
        except ValueError as err:
            return messagebox.showerror("Item nicht gespeichert", str(err))
        self.reload_items()
        self.info.config(text=f"Item «{data['name']}» in items.json gespeichert.")

    def new_species(self):
        classes = list(dict.fromkeys(s["cls"] for s in self.species.values()))
        data = self.ask("Neue Drachenart", [
            ("name", "Deutscher Name", "entry", ""), ("original", "Originalname", "entry", ""),
            ("cls", "Klasse", "combo", classes),
            *[(a, f"Potenzial {a}", "spin", "3") for a in DRAGON_ATTRS],
            ("kb", "Kampfbasis", "spin", "3"), ("shots", "Max. Schüsse", "spin", "4"),
            ("zw", "Zähmungswert (– = nicht zähmbar)", "entry", "4"),
            ("flies", "Fliegt", "combo", ["ja", "nein"]), ("swims", "Schwimmt", "combo", ["nein", "ja"]),
            ("ride", "Reitbar", "combo", ["ja", "nein"]),
            ("shot", "Grundschuss", "entry", ""), ("special", "Spezialfähigkeit (Art)", "entry", ""),
            ("weakness", "Schwäche (fix für die Art)", "entry", ""),
            ("food", "Lieblingsfutter", "entry", "")])
        if not data:
            return
        row = [data["name"], data["original"] or data["name"], data["cls"],
               *(to_int(data[a], 1) for a in DRAGON_ATTRS), to_int(data["kb"], 1), to_int(data["shots"]),
               data["zw"] or "–", data["flies"], data["swims"], data["ride"], data["shot"] or "–", data["special"] or "–",
               data["weakness"] or "–", data["food"] or "–"]
        try:
            add_species(row)
        except (ValueError, OSError) as err:
            return messagebox.showerror("Art nicht gespeichert", str(err))
        self.species = load_species()
        self.species_box.configure(values=sorted(self.species))
        self.fill_list()
        self.info.config(text=f"Art «{data['name']}» in Drachenliste.md gespeichert.")

    # --- dragon list tab
    def _build_list_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Suche", style="Muted.TLabel").pack(side="left")
        self.search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search, width=24).pack(side="left", padx=4)
        ttk.Label(bar, text="Klasse", style="Muted.TLabel").pack(side="left", padx=(16, 0))
        classes = ["Alle", *dict.fromkeys(s["cls"] for s in self.species.values())]
        self.cls_filter = tk.StringVar(value="Alle")
        ttk.Combobox(bar, values=classes, textvariable=self.cls_filter, width=10, state="readonly").pack(side="left", padx=4)
        ttk.Button(bar, text="+ Neue Art", command=self.new_species).pack(side="right", padx=6)
        ttk.Button(bar, text="Als Drache übernehmen", command=self.take_species,
                   style="Accent.TButton").pack(side="right")
        for var in (self.search, self.cls_filter):
            var.trace_add("write", lambda *_: self.debounce("list", self.fill_list))

        box = ttk.Frame(tab)
        box.pack(fill="both", expand=True)
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(box, columns=COLUMNS, show="headings")
        for col, width in zip(COLUMNS, WIDTHS):
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_list(c))
            self.tree.column(col, width=width, minwidth=width, anchor="w" if width > 40 else "center",
                             stretch=col == COLUMNS[-1])
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)  # table is wider than the window
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", lambda _: self.take_species())
        self.tree.tag_configure("odd", background=ROW_ALT)
        self.sort_key, self.sort_desc = None, False
        self.fill_list()
        return tab

    def fill_list(self):
        query, cls = self.search.get().lower(), self.cls_filter.get()
        rows = [species_row(s) for s in self.species.values()
                if (cls == "Alle" or s["cls"] == cls)
                and (query in s["name"].lower() or query in s["original"].lower())]
        if self.sort_key:
            i = COLUMNS.index(self.sort_key)
            rows.sort(key=lambda row: (str(row[i]).isdigit(), to_int(str(row[i]), -1), str(row[i])),
                      reverse=self.sort_desc)
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            self.tree.insert("", "end", values=row, tags=("odd",) if i % 2 else ())

    def sort_list(self, col):
        self.sort_desc = not self.sort_desc if self.sort_key == col else col in {"W", "T", "S", "Wi", "Sch", "ZW"}
        self.sort_key = col
        self.fill_list()

    def take_species(self):
        selected = self.tree.selection()
        if selected:
            self.vars["dragon.species"].set(self.tree.item(selected[0], "values")[0])
            self.tabs.select(0)


if __name__ == "__main__":
    Overlay(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
