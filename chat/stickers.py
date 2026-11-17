"""
The sticker pack. The pictures are SVG files in static/chat/stickers/,
drawn by tools/make_stickers.py.  To add a sticker: draw it in that script,
run it, then add its code and label here.
"""
from django.templatetags.static import static

STICKERS = [
    # faces
    ("happy", "Happy"), ("laugh", "Laughing"), ("love", "In love"), ("wink", "Wink"),
    ("heart", "Heart"), ("hug", "Hug"), ("selfhug", "Warm hug"), ("hugme", "Hug me!"),
    ("cool", "Cool"), ("wow", "Wow"), ("party", "Party"),
    ("sad", "Sad"), ("cry", "Crying"), ("angry", "Angry"), ("sleepy", "Sleepy"),
    # words (Kinyarwanda + English)
    ("muraho", "Muraho! (Hello)"), ("murakoze", "Murakoze! (Thank you)"),
    ("ndagukunda", "Ndagukunda (I love you)"), ("amahoro", "Amahoro (Peace)"),
    ("hello", "Hello!"), ("thanks", "Thank you!"), ("ok", "OK!"), ("lol", "LOL"),
    ("bighug", "Big hug!"), ("bye", "Bye bye!"), ("omw", "On my way!"),
]
STICKER_CODES = {code for code, _ in STICKERS}


def sticker_list():
    """For the browser: code, label and picture address of every sticker."""
    return [{"code": c, "label": label, "url": static(f"chat/stickers/{c}.svg")} for c, label in STICKERS]
