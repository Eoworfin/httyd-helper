"""Minimal PDF export of a tkinter Canvas (no extra packages needed).

The character sheet is drawn on a Canvas anyway, so the export walks its items (rectangles, ovals, lines,
text) and writes them as vector graphics with the standard PDF fonts Helvetica, Times and Courier.
"""
import tkinter.font as tkfont
import zlib

# glyph widths (1/1000 em) of the standard fonts for cp1252 codes 32..255 (Courier is fixed at 600)
_WIDTHS = {
    "Helvetica": "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 556 556 278 278 584 584 584 556 1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 556 500 556 556 278 556 556 222 222 500 222 833 556 556 556 556 333 500 278 556 500 722 500 500 500 334 260 334 584 761 556 0 222 556 333 1000 556 556 333 1000 667 333 1000 0 611 0 0 222 222 333 333 350 556 1000 333 1000 500 333 944 0 500 667 278 333 556 556 556 556 260 556 333 737 370 556 584 333 737 333 400 584 333 333 333 556 537 278 333 333 365 556 834 834 834 611 667 667 667 667 667 667 1000 722 667 667 667 667 278 278 278 278 722 722 778 778 778 778 778 584 778 722 722 722 722 667 667 611 556 556 556 556 556 556 889 500 556 556 556 556 278 278 278 278 556 556 556 556 556 556 556 584 611 556 556 556 556 500 556 500",
    "Helvetica-Bold": "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 556 556 333 333 584 584 584 611 975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 333 556 611 556 611 556 333 611 611 278 278 556 278 889 611 611 611 611 389 556 333 611 556 778 556 556 500 389 280 389 584 761 556 0 278 556 500 1000 556 556 333 1000 667 333 1000 0 611 0 0 278 278 500 500 350 556 1000 333 1000 556 333 944 0 500 667 278 333 556 556 556 556 280 556 333 737 370 556 584 333 737 333 400 584 333 333 333 611 556 278 333 333 365 556 834 834 834 611 722 722 722 722 722 722 1000 722 667 667 667 667 278 278 278 278 722 722 778 778 778 778 778 584 778 722 722 722 722 667 667 611 556 556 556 556 556 556 889 556 556 556 556 556 278 278 278 278 611 611 611 611 611 611 611 584 611 611 611 611 611 556 611 556",
    "Times-Roman": "250 333 408 500 500 833 778 180 333 333 500 564 250 333 250 278 500 500 500 500 500 500 500 500 500 500 278 278 564 564 564 444 921 722 667 667 722 611 556 722 722 333 389 722 611 889 722 722 556 722 667 556 611 722 722 944 722 722 611 333 278 333 469 500 333 444 500 444 500 444 333 500 500 278 278 500 278 778 500 500 500 500 333 389 278 500 500 722 500 500 444 480 200 480 541 761 500 0 333 500 444 1000 500 500 333 1000 556 333 889 0 611 0 0 333 333 444 444 350 500 1000 333 980 389 333 722 0 444 722 250 333 500 500 500 500 200 500 333 760 276 500 564 333 760 333 400 564 300 300 333 500 453 250 333 300 310 500 750 750 750 444 722 722 722 722 722 722 889 667 611 611 611 611 333 333 333 333 722 722 722 722 722 722 722 564 722 722 722 722 722 722 556 500 444 444 444 444 444 444 667 444 444 444 444 444 278 278 278 278 500 500 500 500 500 500 500 564 500 500 500 500 500 500 500 500",
    "Times-Bold": "250 333 555 500 500 1000 833 278 333 333 500 570 250 333 250 278 500 500 500 500 500 500 500 500 500 500 333 333 570 570 570 500 930 722 667 722 722 667 611 778 778 389 500 778 667 944 722 778 611 778 722 556 667 722 722 1000 722 722 667 333 278 333 581 500 333 500 556 444 556 444 333 500 556 278 333 556 278 833 556 500 556 556 444 389 333 556 500 722 500 500 444 394 220 394 520 761 500 0 333 500 500 1000 500 500 333 1000 556 333 1000 0 667 0 0 333 333 500 500 350 500 1000 333 1000 389 333 722 0 444 722 250 333 500 500 500 500 220 500 333 747 300 500 570 333 747 333 400 570 300 300 333 556 540 250 333 300 330 500 750 750 750 500 722 722 722 722 722 722 1000 722 667 667 667 667 389 389 389 389 722 722 778 778 778 778 778 570 778 722 722 722 722 722 611 556 500 500 500 500 500 500 722 444 444 444 444 444 278 278 278 278 500 556 500 500 500 500 500 570 500 556 556 556 556 500 556 500",}
WIDTHS = {name: [int(w) for w in table.split()] for name, table in _WIDTHS.items()}
PDF_FONTS = ["Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold", "Courier", "Courier-Bold"]
# characters the standard fonts (WinAnsi encoding) do not have
REPLACE = {"●": "•", "○": "o", "→": "->", "−": "-", "☐": "[ ]", "☑": "[x]", "✓": "x", "≥": ">=", "≤": "<="}
A4_LANDSCAPE = (842, 595)


def _encode(text):
    for a, b in REPLACE.items():
        text = text.replace(a, b)
    return text.encode("cp1252", "replace")


def _escape(raw):
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _pdf_font(tk_font, requested=""):
    """Map a Tk font to one of the standard PDF fonts."""
    # the requested family decides (the installed fallback may differ, e.g. Georgia on Linux)
    family = f'{requested} {tk_font.actual("family")}'.lower()
    bold = tk_font.actual("weight") == "bold"
    if any(name in family for name in ("georgia", "times", "garamond")) or family.startswith("serif"):
        base = "Times-Bold" if bold else "Times-Roman"
    elif any(name in family for name in ("mono", "courier", "consolas", "cascadia")):
        base = "Courier-Bold" if bold else "Courier"
    else:
        base = "Helvetica-Bold" if bold else "Helvetica"
    return base


def text_width(raw, font, size):
    if font.startswith("Courier"):
        return len(raw) * 0.6 * size
    table = WIDTHS[font]
    return sum(table[c - 32] if c >= 32 else 0 for c in raw) * size / 1000


def _wrap(text, tk_font, width):
    """Reproduce Tk's word wrap of a canvas text item with a width option."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if line and tk_font.measure(candidate) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def _rgb(color, colormap):
    """'#rrggbb' -> (r, g, b) floats after the print colour mapping; None = do not paint."""
    if not color:
        return None
    color = colormap.get(color.lower(), color)
    if color is None:
        return None
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def canvas_to_pdf(canvas, path, colormap=None, page=A4_LANDSCAPE, margin=22):
    """Write all items of canvas to a one-page PDF, scaled to fit the page.
    colormap maps lower-case '#rrggbb' screen colours to print colours (None = leave white)."""
    colormap = {k.lower(): v for k, v in (colormap or {}).items()}
    canvas.update_idletasks()
    x0, y0, x1, y1 = canvas.bbox("all")
    pw, ph = page
    scale = min((pw - 2 * margin) / (x1 - x0), (ph - 2 * margin) / (y1 - y0))
    ox = (pw - (x1 - x0) * scale) / 2
    px_per_pt = float(canvas.tk.call("tk", "scaling"))
    fonts_used, ops = {}, []
    # flip the y axis once: from here on, coordinates are canvas pixels
    ops.append(f"{scale:.5f} 0 0 {-scale:.5f} {ox - x0 * scale:.2f} {ph - margin + y0 * scale:.2f} cm")

    def stroke_fill(fill, outline, width, dash=None):
        f, o = _rgb(fill, colormap), _rgb(outline, colormap)
        if o:
            ops.append(f"{o[0]:.3f} {o[1]:.3f} {o[2]:.3f} RG {max(width, 0.5):.2f} w")
            ops.append(f"[{' '.join(str(d) for d in dash)}] 0 d" if dash else "[] 0 d")
        if f:
            ops.append(f"{f[0]:.3f} {f[1]:.3f} {f[2]:.3f} rg")
        return "B" if f and o else "f" if f else "S" if o else None

    for item in canvas.find_all():
        kind, c = canvas.type(item), canvas.coords(item)
        opt = lambda name: canvas.itemcget(item, name)
        if kind in ("rectangle", "oval"):
            paint = stroke_fill(opt("fill"), opt("outline"), float(opt("width") or 1))
            if not paint:
                continue
            ax, ay, bx, by = c
            if kind == "rectangle":
                ops.append(f"{ax:.2f} {ay:.2f} {bx - ax:.2f} {by - ay:.2f} re {paint}")
            else:  # ellipse from four Bezier curves
                cx, cy, rx, ry = (ax + bx) / 2, (ay + by) / 2, (bx - ax) / 2, (by - ay) / 2
                k = 0.5523
                ops.append(f"{cx + rx:.2f} {cy:.2f} m "
                           f"{cx + rx:.2f} {cy + k * ry:.2f} {cx + k * rx:.2f} {cy + ry:.2f} {cx:.2f} {cy + ry:.2f} c "
                           f"{cx - k * rx:.2f} {cy + ry:.2f} {cx - rx:.2f} {cy + k * ry:.2f} {cx - rx:.2f} {cy:.2f} c "
                           f"{cx - rx:.2f} {cy - k * ry:.2f} {cx - k * rx:.2f} {cy - ry:.2f} {cx:.2f} {cy - ry:.2f} c "
                           f"{cx + k * rx:.2f} {cy - ry:.2f} {cx + rx:.2f} {cy - k * ry:.2f} {cx + rx:.2f} {cy:.2f} c "
                           f"h {paint}")
        elif kind == "line":
            dash = [int(d) for d in canvas.tk.splitlist(opt("dash"))] if opt("dash") else None
            if stroke_fill(None, opt("fill"), float(opt("width") or 1), dash):
                points = " ".join(f"{c[i]:.2f} {c[i + 1]:.2f} {'m' if i == 0 else 'l'}" for i in range(0, len(c), 2))
                ops.append(f"{points} S")
        elif kind == "text" and opt("text").strip():
            color = _rgb(opt("fill"), colormap)
            if not color:
                continue
            tk_font = tkfont.Font(font=opt("font"))
            name = _pdf_font(tk_font, canvas.tk.splitlist(opt("font"))[0])
            ref = fonts_used.setdefault(name, f"F{len(fonts_used) + 1}")
            size = abs(tk_font.actual("size")) * (px_per_pt if tk_font.actual("size") > 0 else 1)
            width = float(opt("width") or 0)
            lines = _wrap(opt("text"), tk_font, width) if width else opt("text").split("\n")
            ascent, linespace = tk_font.metrics("ascent"), tk_font.metrics("linespace")
            raws = [_encode(line) for line in lines]
            block_w = max(text_width(raw, name, size) for raw in raws)
            anchor = opt("anchor")
            x, y = c
            if anchor == "center":
                left = x - block_w / 2
            else:
                left = x - block_w if "e" in anchor else x if "w" in anchor else x - block_w / 2
            height = linespace * len(lines)
            top = y if anchor.startswith("n") else y - height if anchor.startswith("s") else y - height / 2
            ops.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg BT /{ref} 1 Tf")
            for i, raw in enumerate(raws):
                baseline = top + ascent + i * linespace
                ops.append(f"{size:.2f} 0 0 {-size:.2f} {left:.2f} {baseline:.2f} Tm ({_escape(raw).decode('latin-1')}) Tj")
            ops.append("ET")

    content = zlib.compress("\n".join(ops).encode("latin-1"))
    objects = ["<< /Type /Catalog /Pages 2 0 R >>",
               "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               None,  # page, filled in below once the font objects are numbered
               f"<< /Length {len(content)} /Filter /FlateDecode >>"]
    font_refs = []
    for name, ref in fonts_used.items():
        objects.append(f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>")
        font_refs.append(f"/{ref} {len(objects)} 0 R")
    objects[2] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw} {ph}] /Contents 4 0 R "
                  f"/Resources << /Font << {' '.join(font_refs)} >> >> >>")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode()
        if n == 4:
            out += obj.encode() + b"\nstream\n" + content + b"\nendstream"
        else:
            out += obj.encode()
        out += b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as fh:
        fh.write(out)
