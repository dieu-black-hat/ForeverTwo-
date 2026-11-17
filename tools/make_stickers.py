"""
Draws the ForeverTwo sticker pack as SVG files (pure code, no images needed).

Run it from the project folder whenever you change or add a sticker:
    python tools/make_stickers.py

Each sticker is a small vector drawing: shapes like <circle> and <path>.
To add your own: write a function that returns SVG shapes, add it to FACES or
TEXTS at the bottom, run this script, then add its code to chat/stickers.py.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "chat" / "stickers"
INK = "#3b2a1a"  # colour of eyes and mouths

DEFS = """<defs>
  <radialGradient id="g" cx="38%" cy="32%" r="75%"><stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/></radialGradient>
  <filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#000" flood-opacity=".25"/></filter>
</defs>"""


def svg(body, light="#ffe27a", dark="#f5b51b"):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
        + DEFS.format(light=light, dark=dark) + body + "</svg>"
    )


def face_base():
    # white outline (like a die-cut sticker) + coloured face
    return '<g filter="url(#s)"><circle cx="100" cy="104" r="86" fill="#fff"/><circle cx="100" cy="104" r="77" fill="url(#g)"/></g>'


def dot_eyes(y=92):
    return "".join(
        f'<ellipse cx="{x}" cy="{y}" rx="9" ry="12" fill="{INK}"/><circle cx="{x + 3}" cy="{y - 4}" r="3.2" fill="#fff"/>'
        for x in (72, 128)
    )


def blush():
    return '<ellipse cx="54" cy="118" rx="12" ry="7" fill="#ff6b8a" opacity=".45"/><ellipse cx="146" cy="118" rx="12" ry="7" fill="#ff6b8a" opacity=".45"/>'


def line(d, w=7, color=INK):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'


def heart(cx, cy, s, color="#ff3b5c"):
    # a heart drawn with two curves; s = size
    return (
        f'<path transform="translate({cx} {cy}) scale({s})" fill="{color}" '
        'd="M0 6 C-10 -6 -26 2 -18 14 C-12 22 0 30 0 30 C0 30 12 22 18 14 C26 2 10 -6 0 6Z"/>'
    )


# ------------------------------------------------------------------ faces --
def happy():
    return face_base() + dot_eyes() + blush() + line("M66 120 Q100 152 134 120")


def laugh():
    return (face_base() + line("M58 94 L72 80 L86 94") + line("M114 94 L128 80 L142 94") + blush()
            + '<path d="M60 114 Q100 172 140 114 Z" fill="#5b1a1a"/><path d="M80 140 Q100 158 120 140 Q100 132 80 140Z" fill="#ff7a8a"/>')


def love():
    return face_base() + heart(72, 76, 1.1) + heart(128, 76, 1.1) + blush() + line("M70 124 Q100 150 130 124")


def wink():
    return (face_base() + '<ellipse cx="72" cy="92" rx="9" ry="12" fill="#3b2a1a"/><circle cx="75" cy="88" r="3.2" fill="#fff"/>'
            + line("M116 94 Q128 84 140 94") + blush() + line("M70 122 Q104 146 134 116")
            + '<path d="M108 132 Q118 150 126 132" fill="#ff7a8a"/>')


def sad():
    return (face_base() + dot_eyes(96) + line("M56 76 L84 82", 6) + line("M144 76 L116 82", 6)
            + line("M72 140 Q100 118 128 140"))


def cry():
    return face_base() + (
        line("M58 92 Q72 84 86 92") + line("M114 92 Q128 84 142 92")
        + '<path d="M66 96 Q60 130 70 160 L80 160 Q76 130 78 96Z" fill="#5ab4ff" opacity=".9"/>'
        + '<path d="M122 96 Q120 130 124 160 L134 160 Q140 130 134 96Z" fill="#5ab4ff" opacity=".9"/>'
        + '<path d="M78 138 Q100 118 122 138 Q100 132 78 138Z" fill="#5b1a1a" stroke="#5b1a1a" stroke-width="6" stroke-linejoin="round"/>'
    )


def angry():
    return (dot_eyes(98) + line("M54 74 L88 88", 8) + line("M146 74 L112 88", 8)
            + line("M74 140 Q100 124 126 140") + '<path d="M150 56 l10 -10 M156 64 l14 -4 M146 48 l2 -14" stroke="#c21a1a" stroke-width="5" stroke-linecap="round"/>')


def wow():
    return (face_base()
            + "".join(f'<circle cx="{x}" cy="88" r="17" fill="#fff" stroke="{INK}" stroke-width="4"/><circle cx="{x}" cy="90" r="8" fill="{INK}"/>' for x in (70, 130))
            + line("M56 62 Q70 54 84 60", 5) + line("M116 60 Q130 54 144 62", 5)
            + f'<ellipse cx="100" cy="138" rx="14" ry="18" fill="#5b1a1a"/>')


def cool():
    return (face_base()
            + '<path d="M44 80 H156 V88 Q154 112 128 112 Q106 112 104 90 H96 Q94 112 72 112 Q46 112 44 88Z" fill="#1f1f2e"/>'
            + '<path d="M56 86 L74 86" stroke="#fff" stroke-width="4" stroke-linecap="round" opacity=".6"/>'
            + '<path d="M112 86 L130 86" stroke="#fff" stroke-width="4" stroke-linecap="round" opacity=".6"/>'
            + line("M74 134 Q104 150 132 126"))


def sleepy():
    return (face_base() + line("M58 96 Q72 104 86 96") + line("M114 96 Q128 104 142 96") + blush()
            + '<ellipse cx="100" cy="136" rx="8" ry="6" fill="#5b1a1a"/>'
            + '<text x="146" y="58" font-family="Arial, sans-serif" font-weight="900" font-size="34" fill="#4f46e5" stroke="#fff" stroke-width="5" paint-order="stroke">Z</text>'
            + '<text x="172" y="34" font-family="Arial, sans-serif" font-weight="900" font-size="22" fill="#4f46e5" stroke="#fff" stroke-width="4" paint-order="stroke">z</text>')


def party():
    confetti = "".join(
        f'<rect x="{x}" y="{y}" width="9" height="5" rx="2" fill="{c}" transform="rotate({r} {x} {y})"/>'
        for x, y, c, r in [(24, 60, "#ff3b5c", 30), (176, 70, "#22c55e", -20), (30, 150, "#3b82f6", 60),
                           (170, 150, "#a855f7", 15), (150, 30, "#f97316", 45), (40, 30, "#06b6d4", -30)]
    )
    hat = ('<path d="M100 2 L132 52 Q100 62 68 52Z" fill="#a855f7" stroke="#fff" stroke-width="5" stroke-linejoin="round"/>'
           '<path d="M86 30 L114 30 M78 42 L122 42" stroke="#fde047" stroke-width="5"/><circle cx="100" cy="4" r="8" fill="#fde047" stroke="#fff" stroke-width="3"/>')
    return confetti + laugh() + hat


def love_heart():
    return ('<g filter="url(#s)">' + heart(100, 34, 4.7, "#fff") + heart(100, 44, 4.1, "url(#g)") + "</g>"
            + dot_eyes(98) + line("M76 124 Q100 146 124 124"))


# ------------------------------------------------------------------- hugs --
def face_at(cx, cy, r, fill="url(#g)"):
    """A round face anywhere (white sticker outline + colour)."""
    return f'<circle cx="{cx}" cy="{cy}" r="{r + 8}" fill="#fff"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>'


def arm(d, color, width=20):
    """A chubby arm: a thick rounded line with a white outline."""
    return (f'<path d="{d}" fill="none" stroke="#fff" stroke-width="{width + 9}" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')


def happy_closed_eyes(cx, cy, gap=20):
    return line(f"M{cx - gap - 9} {cy} Q{cx - gap} {cy - 9} {cx - gap + 9} {cy}", 5) + \
        line(f"M{cx + gap - 9} {cy} Q{cx + gap} {cy - 9} {cx + gap + 9} {cy}", 5)


PINK_DEFS = ('<defs><radialGradient id="p" cx="38%" cy="32%" r="75%">'
             '<stop offset="0" stop-color="#ffd6e0"/><stop offset="1" stop-color="#ff8fab"/></radialGradient></defs>')


def hug():
    """Two friends cheek to cheek, one arm around the other."""
    return (PINK_DEFS + '<g filter="url(#s)">' + face_at(62, 112, 50) + face_at(138, 104, 48, "url(#p)") + "</g>"
            + happy_closed_eyes(56, 106, 16) + line("M46 128 Q58 138 70 128", 5)
            + happy_closed_eyes(144, 98, 15) + line("M132 120 Q144 130 156 120", 5)
            + '<ellipse cx="30" cy="124" rx="8" ry="5" fill="#ff6b8a" opacity=".45"/>'
            + '<ellipse cx="172" cy="116" rx="8" ry="5" fill="#ff6b8a" opacity=".45"/>'
            + arm("M156 140 Q110 186 44 152", "#ff8fab")
            + '<circle cx="42" cy="151" r="12" fill="#ff8fab" stroke="#fff" stroke-width="4"/>'
            + arm("M50 146 Q86 172 136 150", "#f5b51b", 16)
            + '<circle cx="138" cy="149" r="10" fill="#f5b51b" stroke="#fff" stroke-width="4"/>'
            + heart(100, 40, 1.0) + heart(100, 14, 0.55) + heart(170, 36, 0.55))


def self_hug():
    """Wrapping your own arms around yourself, eyes closed, happy."""
    return (face_base() + happy_closed_eyes(100, 92, 26) + blush() + line("M84 118 Q100 130 116 118", 6)
            + arm("M34 132 Q76 176 142 132", "#f5b51b") + arm("M166 132 Q124 176 58 132", "#e9a40f")
            + '<circle cx="142" cy="132" r="12" fill="#f5b51b" stroke="#fff" stroke-width="4"/>'
            + '<circle cx="58" cy="132" r="12" fill="#e9a40f" stroke="#fff" stroke-width="4"/>'
            + heart(168, 30, 0.75) + heart(186, 56, 0.5))


def hug_me():
    """Arms wide open, asking for a hug."""
    return ('<g filter="url(#s)">' + face_at(100, 118, 60) + "</g>"
            + arm("M50 130 Q26 108 22 74", "#f5b51b") + arm("M150 130 Q174 108 178 74", "#f5b51b")
            + '<circle cx="22" cy="70" r="13" fill="#f5b51b" stroke="#fff" stroke-width="4"/>'
            + '<circle cx="178" cy="70" r="13" fill="#f5b51b" stroke="#fff" stroke-width="4"/>'
            + '<ellipse cx="82" cy="108" rx="7" ry="10" fill="#3b2a1a"/><ellipse cx="118" cy="108" rx="7" ry="10" fill="#3b2a1a"/>'
            + '<circle cx="84" cy="104" r="2.5" fill="#fff"/><circle cx="120" cy="104" r="2.5" fill="#fff"/>'
            + '<ellipse cx="66" cy="130" rx="9" ry="5" fill="#ff6b8a" opacity=".5"/><ellipse cx="134" cy="130" rx="9" ry="5" fill="#ff6b8a" opacity=".5"/>'
            + '<path d="M84 132 Q100 156 116 132 Z" fill="#5b1a1a"/>'
            + heart(100, 24, 1.0))


# ----------------------------------------------------------- word stickers --
def sparkle(x, y, s=1, color="#fde047"):
    return (f'<path transform="translate({x} {y}) scale({s})" fill="{color}" stroke="#fff" stroke-width="2" '
            'd="M0 -14 L4 -4 L14 0 L4 4 L0 14 L-4 4 L-14 0 L-4 -4Z"/>')


def word(text, size=38, extra=""):
    # Long words are squeezed so they always fit inside the badge (max 146px wide).
    estimated = len(text) * size * 0.62
    fit = f' textLength="146" lengthAdjust="spacingAndGlyphs"' if estimated > 146 else ""
    return ('<g filter="url(#s)" transform="rotate(-6 100 100)">'
            '<rect x="10" y="56" width="180" height="92" rx="30" fill="#fff"/>'
            '<rect x="18" y="64" width="164" height="76" rx="24" fill="url(#g)"/>'
            f'<text x="100" y="{102 + size * 0.36:.0f}" text-anchor="middle" font-family="Arial Rounded MT Bold, Arial, Helvetica, sans-serif" '
            f'font-weight="900" font-size="{size}" fill="#fff" stroke="rgba(0,0,0,.18)" stroke-width="3" paint-order="stroke"'
            f'{fit}>{text}</text>'
            "</g>" + sparkle(28, 50, 1.1) + sparkle(176, 156, 0.9, "#fff") + extra)


# code -> (drawing, light colour, dark colour)
FACES = {
    "happy": (happy, "#ffe27a", "#f5b51b"),
    "laugh": (laugh, "#ffe27a", "#f5b51b"),
    "love": (love, "#ffd6e0", "#ff8fab"),
    "wink": (wink, "#ffe27a", "#f5b51b"),
    "sad": (sad, "#cfe3ff", "#7fb0f5"),
    "cry": (cry, "#cfe3ff", "#7fb0f5"),
    "angry": (lambda: face_base() + angry(), "#ff9a8a", "#e8412c"),
    "wow": (wow, "#ffe27a", "#f5b51b"),
    "cool": (cool, "#ffe27a", "#f5b51b"),
    "sleepy": (sleepy, "#e6e0ff", "#a99cf5"),
    "party": (party, "#ffe27a", "#f5b51b"),
    "heart": (love_heart, "#ff8fa3", "#e11d48"),
    "hug": (hug, "#ffe27a", "#f5b51b"),
    "selfhug": (self_hug, "#ffe27a", "#f5b51b"),
    "hugme": (hug_me, "#ffe27a", "#f5b51b"),
}
TEXTS = {
    "muraho": ("Muraho!", 40, "#7dd3fc", "#2563eb", ""),
    "murakoze": ("Murakoze!", 36, "#86efac", "#16a34a", ""),
    "ndagukunda": ("Ndagukunda", 30, "#fda4af", "#e11d48", heart(160, 30, 1.5)),
    "amahoro": ("Amahoro", 38, "#c4b5fd", "#7c3aed", ""),
    "hello": ("Hello!", 44, "#fdba74", "#ea580c", ""),
    "thanks": ("Thank you!", 32, "#5eead4", "#0d9488", ""),
    "ok": ("OK!", 54, "#bef264", "#65a30d", ""),
    "lol": ("LOL", 54, "#fde047", "#f59e0b", ""),
    "bye": ("Bye bye!", 36, "#f9a8d4", "#db2777", ""),
    "omw": ("On my way!", 30, "#93c5fd", "#4f46e5", ""),
    "bighug": ("Big hug!", 38, "#fbcfe8", "#ec4899", heart(30, 160, 1.3) + heart(172, 36, 1.0)),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, (draw, light, dark) in FACES.items():
        (OUT / f"{code}.svg").write_text(svg(draw(), light, dark), encoding="utf-8")
    for code, (text, size, light, dark, extra) in TEXTS.items():
        (OUT / f"{code}.svg").write_text(svg(word(text, size, extra), light, dark), encoding="utf-8")
    print(f"Wrote {len(FACES) + len(TEXTS)} stickers to {OUT}")


if __name__ == "__main__":
    main()
