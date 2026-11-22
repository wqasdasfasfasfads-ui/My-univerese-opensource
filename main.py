# -*- coding: utf-8 -*-
"""MY UNIVERSE - a sandbox world with NPCs made from your photos/videos and a built-in AI."""
import os, sys, re, json, math, random, time, threading, queue, urllib.request, io, base64, types, importlib.util
import pygame, numpy as np
from PIL import Image, ImageSequence

BASE = os.path.dirname(os.path.abspath(__file__))
DROP = os.path.join(BASE, "drop_here")
SAVE = os.path.join(BASE, "world_save.json")
W, H = 1100, 700
os.makedirs(DROP, exist_ok=True)

# ---------- фільтр: єдине, що заборонено ----------
BANNED = re.compile(r"наркот|нарко|drug|кокаїн|кокаин|героїн|героин|метамфет|амфетамін|weed|марихуан|"
                    r"зброя|зброю|оруж|weapon|\bgun|пістолет|пистолет|автомат|rifle|bomb|бомб|гранат|вибухів|взрывчат", re.I)
def banned(t): return bool(BANNED.search(t or ""))

class Log:
    def __init__(s): s.items = []
    def append(s, t): s.items.append((time.time(), t))
    def recent(s, n=7, sec=10): return [t for ts, t in s.items if time.time() - ts < sec][-n:]

PLUG = os.path.join(BASE, "plugins"); os.makedirs(PLUG, exist_ok=True)
ACTION_HANDLERS, EXTRA_BUILD, EXTRA_DESC, SYS_EXTRA = {}, {}, {}, []
HOOKS = {k: [] for k in ("post_update", "draw_world", "draw_ui", "key", "mouse", "mouseup", "click", "place", "save", "load", "new", "url", "editor_world", "editor_ent")}
OBJECTS_EXTRA, INPUT_LIMIT, LOCK_CAM = [], [400], [False]
def ekey(e): return (e.kind != "wall", e.y)

ANIM_RX = re.compile(r"анім|рух|ходи|ходит|літа|летай|крут|плав|бігає|двиг|патрул|anim|move|walk|spin|float|fly|orbit|rotate|patrol|bounce", re.I)
def wants_anim(t): return bool(ANIM_RX.search(t or ""))

def surf_b64(sf):
    im = Image.frombytes("RGBA", sf.get_size(), pygame.image.tostring(sf, "RGBA")); b = io.BytesIO(); im.save(b, "PNG"); return base64.b64encode(b.getvalue()).decode()
def b64_surf(t): return to_surf(Image.open(io.BytesIO(base64.b64decode(t))).convert("RGBA"))

# ---------- видалення фону ----------
def remove_bg(im, size=256):
    im = im.convert("RGBA"); im.thumbnail((size, size))
    a = np.array(im)
    if (a[..., 3] < 250).mean() > 0.05: return im          # вже прозоре
    try:                                                    # якщо стоїть rembg - краща якість
        from rembg import remove
        return remove(im).convert("RGBA")
    except Exception: pass
    rgb = a[..., :3].astype(int)
    bg = np.median([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]], axis=0)
    close = np.linalg.norm(rgb - bg, axis=2) < 48
    reach = np.zeros_like(close)
    reach[0], reach[-1], reach[:, 0], reach[:, -1] = close[0], close[-1], close[:, 0], close[:, -1]
    while True:
        n = reach.copy()
        n[1:] |= reach[:-1]; n[:-1] |= reach[1:]; n[:, 1:] |= reach[:, :-1]; n[:, :-1] |= reach[:, 1:]
        n &= close
        if (n == reach).all(): break
        reach = n
    a[reach, 3] = 0
    return Image.fromarray(a)

def to_surf(im): return pygame.image.fromstring(im.tobytes(), im.size, "RGBA").convert_alpha()

def load_media(path):
    ext = os.path.splitext(path)[1].lower(); frames = []
    if ext == ".gif":
        frames = [remove_bg(f.copy(), 160) for f in ImageSequence.Iterator(Image.open(path))][:40]
    elif ext in (".mp4", ".webm", ".mov", ".avi", ".mkv"):
        try:
            import cv2
            cap = cv2.VideoCapture(path); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            step = max(1, total // 30)
            for i in range(0, total, step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i); ok, f = cap.read()
                if not ok: break
                frames.append(remove_bg(Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)), 160))
        except ImportError:
            print("For video: pip install opencv-python"); return []
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        frames = [remove_bg(Image.open(path))]
    return [to_surf(f) for f in frames]

# ---------- процедурні об'єкти ----------
def make_prop(kind):
    s = pygame.Surface((90, 110), pygame.SRCALPHA)
    if kind == "tree":
        pygame.draw.rect(s, (110, 70, 35), (40, 60, 12, 45)); pygame.draw.circle(s, (40, 140, 50), (46, 42), 34)
    elif kind == "rock":
        pygame.draw.ellipse(s, (120, 120, 130), (10, 60, 70, 42))
    elif kind == "house":
        pygame.draw.rect(s, (200, 160, 110), (10, 50, 70, 55)); pygame.draw.polygon(s, (170, 50, 50), [(0, 52), (45, 10), (90, 52)])
        pygame.draw.rect(s, (80, 50, 30), (38, 75, 16, 30))
    elif kind == "water":
        pygame.draw.ellipse(s, (50, 120, 220), (0, 50, 90, 50))
    elif kind == "star":
        pygame.draw.polygon(s, (255, 220, 60), [(45 + 40 * math.cos(math.pi * (k / 5 - .5)) * (1 if k % 2 == 0 else .4),
                            55 + 40 * math.sin(math.pi * (k / 5 - .5)) * (1 if k % 2 == 0 else .4)) for k in range(10)])
    else:  # NPC - простий смайлик
        pygame.draw.circle(s, (255, 214, 0), (45, 62), 30); pygame.draw.circle(s, (30, 30, 30), (45, 62), 30, 3)
        pygame.draw.circle(s, (30, 30, 30), (35, 54), 4); pygame.draw.circle(s, (30, 30, 30), (55, 54), 4)
        pygame.draw.arc(s, (30, 30, 30), (31, 52, 28, 22), math.pi * 1.1, math.pi * 1.9, 3)
    return s

class Ent:
    def __init__(s, frames, x, y, name="", kind="", walk=False):
        s.frames, s.x, s.y, s.name, s.kind, s.walk = frames, x, y, name, kind, walk; s.px, s.py = x, y
        s.fi, s.vx, s.vy, s.say, s.say_t, s.t = 0, 0, 0, "", 0, random.random() * 9
        s.spec, s.scale, s.angle, s.flip = {}, 1.0, 0.0, False
        s.jump_t = s.shake_t = s.spin_t = 0.0; s.follow = s.flee = s.drag = s.orbit = False
        s.tx = s.ty = None; s.die_at = 0; s.ocx = s.ocy = 0; s.oa = 0
    def update(s, dt, mx, my):
        s.t += dt; idle = s.spec.get("idle", {})
        if len(s.frames) > 1: s.fi = int(s.t * 10) % len(s.frames)
        if s.drag: return
        if s.orbit: s.oa += dt * 1.6; s.x = s.ocx + 90 * math.cos(s.oa); s.y = s.ocy + 45 * math.sin(s.oa); return
        if s.tx is not None:
            ddx, ddy = s.tx - s.x, s.ty - s.y; dd = math.hypot(ddx, ddy)
            if dd < 4: s.tx = None
            else: st = min(dd, 220 * dt); s.x += ddx / dd * st; s.y += ddy / dd * st
            return
        dx, dy = mx - s.x, my - s.y; d = math.hypot(dx, dy) or 1
        if s.follow and d > 40: s.x += dx / d * 110 * dt; s.y += dy / d * 110 * dt
        elif s.flee and d < 250: s.x -= dx / d * 140 * dt; s.y -= dy / d * 140 * dt
        elif s.walk or idle.get("walk"):
            sp = idle.get("speed", 40)
            if random.random() < .01: s.vx, s.vy = random.uniform(-sp, sp), random.uniform(-sp / 1.6, sp / 1.6)
            s.x += s.vx * dt; s.y += s.vy * dt
        s.angle += idle.get("spin", 0) * dt
        if s.spin_t > 0: s.angle += 360 * dt; s.spin_t -= dt
        s.jump_t = max(0, s.jump_t - dt); s.shake_t = max(0, s.shake_t - dt)
    def image(s):
        im = s.frames[s.fi]
        if s.flip: im = pygame.transform.flip(im, True, False)
        if s.scale != 1 or s.angle % 360: im = pygame.transform.rotozoom(im, -s.angle, s.scale)
        return im
    def rect(s):
        im = s.image(); r = im.get_rect()
        yo = -80 * math.sin(math.pi * (1 - s.jump_t / .6)) if s.jump_t > 0 else 0
        yo -= s.spec.get("idle", {}).get("float", 0) * (1 + math.sin(s.t * 3))
        xo = random.randint(-4, 4) if s.shake_t > 0 else 0
        r.midbottom = (s.x + xo, s.y + yo); return r

# ---------- ШІ (Groq) + інтернет ----------
import textwrap, shutil
from urllib.parse import quote
CFG = {"groq_api_key": "", "model": "openai/gpt-oss-120b"}
try: CFG.update(json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8")))
except Exception: pass
KEY = os.environ.get("GROQ_API_KEY") or CFG["groq_api_key"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

def norm_url(u):
    """Перетворює 'спеціальні' посилання на прямі: github blob/raw.github.com, imgur, google drive, dropbox, giphy."""
    u = (u or "").strip().strip("\"'<>").rstrip(".,;")
    if not re.match(r"https?://", u): return u
    u = re.sub(r"^https?://raw\.github\.com/", "https://raw.githubusercontent.com/", u)
    m = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/(?:blob|raw)/(.+)", u)
    if m: u = f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3).split('?')[0]}"
    m = re.match(r"https?://(?:www\.)?imgur\.com/(?!a/|gallery/)(\w{5,8})/?$", u)
    if m: u = f"https://i.imgur.com/{m.group(1)}.png"
    m = re.match(r"https?://drive\.google\.com/file/d/([\w-]+)", u)
    if m: u = f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    u = re.sub(r"(dropbox\.com/[^\s]*?)dl=0", r"\1dl=1", u)
    m = re.match(r"https?://giphy\.com/gifs/(?:.*-)?(\w+)/?$", u)
    if m: u = f"https://i.giphy.com/media/{m.group(1)}/giphy.gif"
    return u

def http(url, data=None, headers=None, timeout=8):
    if isinstance(url, str): url = norm_url(url)
    h = dict(UA); h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, data, h), timeout=timeout).read()

def groq(msgs, tokens=1500):
    body = json.dumps({"model": CFG["model"], "messages": msgs, "temperature": 0.8,
                       "max_completion_tokens": tokens, "reasoning_effort": "low"}).encode()
    r = http("https://api.groq.com/openai/v1/chat/completions", body,
             {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, 60)
    return json.loads(r)["choices"][0]["message"]["content"]

def parse_json(txt, kind="["):
    txt = re.sub(r"```(?:json)?", "", txt or "")
    m = re.search(r"\[.*\]" if kind == "[" else r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else None

def strip(h): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()

def web_search(q):
    out = []
    try:
        h = http("https://html.duckduckgo.com/html/?q=" + quote(q)).decode("utf8", "ignore")
        t = re.findall(r'class="result__a"[^>]*>(.*?)</a>', h, re.S); s = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', h, re.S)
        out = [f"{strip(a)}: {strip(b)}" for a, b in zip(t, s)][:5]
    except Exception: pass
    if not out:
        for lang in ("uk", "en"):
            try:
                j = json.loads(http(f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch=" + quote(q)))
                out += [f"{x['title']}: {strip(x['snippet'])}" for x in j["query"]["search"]]
            except Exception: pass
    return out or ["nothing found"]

def find_images(q, n=1):
    urls = []
    try:
        h = http("https://duckduckgo.com/?q=" + quote(q) + "&iax=images&ia=images").decode("utf8", "ignore")
        vqd = re.search(r'vqd=["\']?([\d-]+)', h).group(1)
        j = json.loads(http(f"https://duckduckgo.com/i.js?l=us-en&o=json&q={quote(q)}&vqd={vqd}&f=,,,&p=1", headers={"Referer": "https://duckduckgo.com/"}))
        for r in j["results"][:n * 4]: urls += [r.get("thumbnail"), r.get("image")]
    except Exception: pass
    try:
        j = json.loads(http("https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&format=json&prop=imageinfo&iiprop=url&iiurlwidth=500&gsrlimit=8&gsrsearch=" + quote(q)))
        for p in j["query"]["pages"].values(): urls.append(p["imageinfo"][0].get("thumburl") or p["imageinfo"][0]["url"])
    except Exception: pass
    return [u for u in urls if u]

def download_photos(q, n, hints, pos=None):
    import io; got = 0
    for u in find_images(q, n):
        if got >= n: break
        try:
            im = Image.open(io.BytesIO(http(u, timeout=20))); im.load()
            name = f"photo{random.randint(1000, 99999)}.png"
            im.convert("RGBA").save(os.path.join(DROP, name)); setpos(name, pos, n); hints[name] = q; got += 1
        except Exception: continue
    stubs = 0
    while got < n:
        name = f"photo{random.randint(1000, 99999)}.png"; placeholder(q)[0].save(os.path.join(DROP, name)); setpos(name, pos, n); hints[name] = q; got += 1; stubs += 1
    return got, stubs

SYS = """You are the AI god of a pixel-art 2D universe. You have no limits on topics, style, humor or imagination.
The only things you never create or help create: drugs and weapons.
Reply ONLY with a JSON array of commands (no explanations, no markdown). Commands:
{"do":"spawn","what":"tree|rock|house|water|star|npc","n":1,"name":""}
{"do":"image","q":"search query for a photo on the internet (English works best)","n":1}  - find and add a photo to the world (it becomes interactive by itself)
{"do":"search","q":"..."}  - google it; you will see the results and continue your answer
{"do":"say","text":"...","target":"entity name (optional)"}  - say something to the user (ANSWER questions this way)
{"do":"sky","mode":"day|night"}   {"do":"clear"}
{"do":"behave","target":"photo123","spec":{...}}  - make an entity interactive
Actions on an entity (need "target"): jump, spin, grow, shrink, shake, flip, {"do":"move","dx":50,"dy":0}, {"do":"follow","on":true}, {"do":"flee","on":true}, talk.
spec = {"on_click":[list of actions without target],"idle":{"walk":true,"speed":40,"float":6,"spin":0},"persona":"who it is and how it talks"}
Extra actions (on an entity, in on_click, or globally; "src" = entity name, URL (e.g. https://raw.githubusercontent.com/...) or a text query to search a photo):
{"do":"swap","src":"..."}  - change this entity's photo to another one
{"do":"cycle","srcs":["...","..."]}  - every click changes the photo to the next one in the list
{"do":"bg","color":"#112233 or a color name"}  or {"do":"bg","src":"URL or search query, e.g. space / forest / city at night"}  - change the world background. When asked to change the background ALWAYS return bg
{"do":"add","src":"...","name":""}  - add a new photo entity nearby
{"do":"panel","src":"..."} or {"do":"panel","srcs":["..","..."],"every":2}  - photo on the left panel of the screen (may change by itself)
{"do":"show","src":"...","secs":4}  - briefly show a photo in the middle of the screen
{"do":"play","src":"video/gif URL or the name video123"}  - play a video
{"do":"trigger","target":"photo123"}  - run the interactivity of another entity (chain)
{"do":"slide","dx":100,"dy":0}  - glide smoothly;  {"do":"orbit","on":true}  - fly in a circle
{"do":"after","secs":2,"then":[actions]}  - do it later;  {"do":"random","of":[action,action]}  - a random one of several
Placement (optional for spawn/image/add/show/play): "pos":"left|right|top|bottom|center|top-left|top-right|bottom-left|bottom-right" or "near":"name","side":"left|right|above|below" or "x":px,"y":px (screen 1100x700, 0,0 is top-left). If the user said WHERE to put it ("on the left", "next to photo123", "in the center") - put it exactly there.
If you need fresh information - search first. If asked for a photo of something - image. Be creative. Do NOT add permanent animation (idle: walking, flying, spinning) or movement unless the user explicitly asked for animation/movement. Answer briefly, without long explanations."""

SYS_BEH = """You bring a new entity to life in a 2D world. Return ONLY one JSON object:
{"on_click":[2-4 actions],"idle":{"walk":true/false,"speed":10-80,"float":0-10,"spin":0-60},"persona":"short: who it is, character, how it talks"}
Available actions in on_click: {"do":"say","text":"..."}, {"do":"jump"}, {"do":"spin"}, {"do":"grow"}, {"do":"shrink"}, {"do":"shake"}, {"do":"flip"},
{"do":"move","dx":number,"dy":number}, {"do":"follow","on":true}, {"do":"flee","on":true}, {"do":"talk"} (a live in-character reply), {"do":"sky","mode":"night"}.
Also available: {"do":"swap","src":"query or URL"}, {"do":"cycle","srcs":[..]}, {"do":"bg","color":"#hex"}, {"do":"add","src":".."}, {"do":"panel","src":".."}, {"do":"show","src":"..","secs":4}, {"do":"play","src":".."}, {"do":"trigger","target":"photoN"}, {"do":"slide","dx":n,"dy":n}, {"do":"orbit","on":true}, {"do":"after","secs":2,"then":[..]}, {"do":"random","of":[..]}.
Often combine several actions so the click is fun (the photo changes, the background, something appears, something moves). Leave idle empty {} - no permanent animation unless asked. Be inventive and fit the behavior to the name/hint. No topic limits except drugs and weapons."""

PRESETS = [
 {"on_click": [{"do": "jump"}, {"do": "say", "text": "Oops!"}], "idle": {}, "persona": "a cheerful oddball"},
 {"on_click": [{"do": "spin"}, {"do": "grow"}], "idle": {}, "persona": "a mysterious ghost"},
 {"on_click": [{"do": "shake"}, {"do": "flee", "on": True}, {"do": "say", "text": "Don't touch me!"}], "idle": {}, "persona": "a coward"},
 {"on_click": [{"do": "follow", "on": True}, {"do": "say", "text": "I'm with you!"}], "idle": {}, "persona": "a loyal friend"}]

def local_ai(t):
    orig = t; t = t.lower(); n = int(m.group(1)) if (m := re.search(r"(\d+)", t)) else 1; cmds = []
    kinds = [("tree", r"дерев|дуб|tree|ліс|лес"), ("rock", r"камін|камен|rock"), ("house", r"буд|дом|house|хат"),
             ("water", r"вод|озер|water|lake"), ("star", r"зір|звезд|star"), ("npc", r"npc|нпс|людин|чувак|персонаж|human|істот")]
    for k, rx in kinds:
        if re.search(rx, t): cmds.append({"do": "spawn", "what": k, "n": min(n, 40)})
    if re.search(r"ніч|ночь|night", t): cmds.append({"do": "sky", "mode": "night"})
    if re.search(r"\bдень|day|ранок|утро", t): cmds.append({"do": "sky", "mode": "day"})
    if re.search(r"фон|background|\bbg\b", t):
        u = re.search(r"https?://\S+", orig)
        if u: return [{"do": "bg", "src": u.group(0)}]
        for w in re.findall(r"#[0-9a-f]{3,6}|[a-zа-яіїєё]+", t):
            try: return [{"do": "bg", "color": parse_color_g(w)}]
            except Exception: pass
        mm = re.search(r"(?:фон|background|bg)\s*(?:на|to|:)?\s*(.+)", t)
        if mm: return [{"do": "bg", "src": mm.group(1).strip()}]
    if re.search(r"очист|видал|удали|clear", t): cmds.append({"do": "clear"})
    sp_ = side_from_text(t)
    for c_ in cmds:
        if sp_ and c_.get("do") == "spawn": c_["pos"] = sp_
    return cmds or [{"do": "say", "text": "No connection to Groq - working locally, I only understand simple commands."}]

def agent(text, where, cam, hints, out):
    names = list(where)
    """Цикл: ШІ -> (search) -> результати -> ШІ ... -> команди в чергу."""
    if not KEY: out.put(("cmds", local_ai(text))); return
    msgs = [{"role": "system", "content": SYS + "".join(SYS_EXTRA) + "\nEntities in the world now (name@screen x,y): " + (", ".join(f"{n}@({int(where[n][0] - cam[0])},{int(where[n][1] - cam[1])})" for n in names[-40:]) or "nobody")},
            {"role": "user", "content": text}]
    try:
        for _ in range(4):
            raw = groq(msgs); cmds = parse_json(raw) or []
            s = [c for c in cmds if c.get("do") == "search"]
            if not s: break
            res = []
            for c in s:
                if banned(c.get("q", "")): res.append("forbidden query")
                else: res += web_search(c["q"])
            msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Search results:\n" + "\n".join(res) + "\nNow give the final commands."}]
        final = []
        for c in cmds:
            if c.get("do") == "search": continue
            if c.get("do") == "image":
                if banned(c.get("q", "")): out.put(("log", "AI: I won't search for that.")); continue
                before = set(hints); k, st = download_photos(c.get("q", ""), min(int(c.get("n", 1)), 6), hints, resolve_pos(c, cam, {k_.lower(): v_ for k_, v_ in where.items()}))
                for n_ in set(hints) - before: hints[n_] += "|ANIM" if wants_anim(text) else ""
                continue
            final.append(c)
        out.put(("cmds", final))
    except Exception as ex:
        out.put(("log", f"Groq error: {str(ex)[:80]} - working locally")); out.put(("cmds", local_ai(text)))

def behavior_agent(ent, info, out, animate=False):
    spec = None
    if KEY:
        try: spec = parse_json(groq([{"role": "system", "content": SYS_BEH + "".join(SYS_EXTRA)}, {"role": "user", "content": info}], 900), "{")
        except Exception as ex: out.put(("log", f"Interactivity: Groq error {str(ex)[:60]}"))
    out.put(("beh", ent, spec if isinstance(spec, dict) else random.choice(PRESETS), animate))

def talk_agent(ent, out):
    line = None
    if KEY:
        try: line = groq([{"role": "system", "content": f"You are {ent.spec.get('persona', 'a living creature')} in a 2D world. Say one short line (up to 12 words) in character. No style limits except drugs and weapons."},
                          {"role": "user", "content": "The user clicked on you. What do you say?"}], 200).strip().strip('"')
        except Exception: pass
    out.put(("say", ent, line or random.choice(["Hi!", "Huh?", "What do you want?", "I'm alive!"])))

COLORS = {"red": (220, 40, 40), "червоний": (220, 40, 40), "красный": (220, 40, 40), "green": (40, 160, 60), "зелений": (40, 160, 60), "зеленый": (40, 160, 60),
 "blue": (40, 80, 220), "синій": (40, 80, 220), "синий": (40, 80, 220), "блакитний": (110, 190, 255), "голубой": (110, 190, 255), "cyan": (0, 200, 220),
 "yellow": (240, 220, 50), "жовтий": (240, 220, 50), "желтый": (240, 220, 50), "orange": (255, 150, 30), "помаранчевий": (255, 150, 30), "оранжевый": (255, 150, 30),
 "purple": (130, 50, 190), "фіолетовий": (130, 50, 190), "фиолетовый": (130, 50, 190), "pink": (255, 120, 180), "рожевий": (255, 120, 180), "розовый": (255, 120, 180),
 "black": (10, 10, 12), "чорний": (10, 10, 12), "черный": (10, 10, 12), "white": (245, 245, 245), "білий": (245, 245, 245), "белый": (245, 245, 245),
 "gray": (130, 130, 130), "grey": (130, 130, 130), "сірий": (130, 130, 130), "серый": (130, 130, 130), "brown": (120, 80, 40), "коричневий": (120, 80, 40), "коричневый": (120, 80, 40),
 "night": (15, 20, 50), "dark": (20, 20, 30), "темний": (20, 20, 30), "sky": (120, 190, 255), "небо": (120, 190, 255), "space": (8, 8, 25), "космос": (8, 8, 25)}

def parse_color_g(c):
    """Приймає: [r,g,b], '#f00', '#ff0000', 'rgb(1,2,3)', 'червоний', 'red', 'random'."""
    if isinstance(c, (list, tuple)): return tuple(max(0, min(255, int(v))) for v in c[:3])
    c = str(c).strip().lower()
    if c in ("random", "рандом", "випадковий"): return tuple(random.randint(30, 230) for _ in range(3))
    if c in COLORS: return COLORS[c]
    for k, v in COLORS.items():
        if len(k) > 4 and c.startswith(k[:-2]): return v
    m = re.search(r"#?\b([0-9a-f]{6}|[0-9a-f]{3})\b", c)
    if m:
        h = m.group(1); h = "".join(ch * 2 for ch in h) if len(h) == 3 else h
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    n = re.findall(r"\d+", c)
    if len(n) >= 3: return tuple(max(0, min(255, int(v))) for v in n[:3])
    raise ValueError(f"unknown color '{c}'")

ALIAS = {"background": "bg", "set_bg": "bg", "set_background": "bg", "change_bg": "bg", "change_background": "bg", "bgcolor": "bg", "фон": "bg",
         "change_image": "swap", "set_image": "swap", "replace_image": "swap", "change_photo": "swap", "add_photo": "add", "spawn_photo": "add",
         "show_image": "show", "show_photo": "show", "play_video": "play", "side_panel": "panel", "left_panel": "panel", "move_to": "slide",
         "trigger_other": "trigger", "say_text": "say", "speak": "say", "wait": "after", "delay": "after"}

def norm_cmd(c):
    c = dict(c); d = str(c.get("do") or c.get("action") or c.get("type") or "").lower().replace(" ", "_"); c["do"] = ALIAS.get(d, d)
    for k in ("colour", "value", "to", "hex", "rgb", "background", "bg_color", "bgcolor"):
        if k in c and "color" not in c and c["do"] == "bg": c["color"] = c[k]
    for k in ("image", "url", "photo", "file", "img", "source", "link"):
        if k in c and "src" not in c: c["src"] = c[k]
    if "srcs" not in c:
        for k in ("images", "urls", "photos", "sources", "list"):
            if isinstance(c.get(k), list): c["srcs"] = c[k]
    if c["do"] == "bg" and c.get("src") and not is_url(c["src"]):
        try: c["color"] = parse_color_g(c["src"]); del c["src"]          # "src":"red" -> це колір
        except Exception: pass
    return c

def placeholder(label="", kind="sprite"):
    """Генерує картинку, коли нічого не знайдено: kind = sprite | anim | bg."""
    from PIL import ImageDraw
    rnd = random.Random(label or None)
    c1 = tuple(rnd.randint(50, 230) for _ in range(3)); c2 = tuple(rnd.randint(30, 200) for _ in range(3))
    if kind == "bg":
        w, h = 700, 400; t = np.linspace(0, 1, h)[:, None, None]
        arr = (np.array(c1) * (1 - t) + np.array(c2) * t).repeat(w, axis=1).astype("uint8")
        im = Image.fromarray(arr).convert("RGBA"); d = ImageDraw.Draw(im)
        for _ in range(40):
            x, y, r = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(2, 14); d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rnd.randint(40, 120)))
        return [im]
    out = []
    for i in range(8 if kind == "anim" else 1):
        im = Image.new("RGBA", (256, 256), (0, 0, 0, 0)); d = ImageDraw.Draw(im); o = int(8 * math.sin(i * .8))
        d.ellipse((40, 60 + o, 216, 236 + o), fill=(255, 214, 0), outline=(30, 30, 30), width=6)
        for ex in (95, 160): d.ellipse((ex - 9, 120 + o, ex + 9, 144 + o), fill=(30, 30, 30))
        d.arc((80, 130 + o, 176, 205 + o), 25, 155, fill=(30, 30, 30), width=7)
        out.append(im)
    return out

PLACE = {}      # ім'я файлу -> світові координати, куди поставити
POS_XY = {"left": (.2, .6), "right": (.8, .6), "top": (.5, .3), "bottom": (.5, .9), "center": (.5, .6), "top-left": (.2, .3),
          "top-right": (.8, .3), "bottom-left": (.2, .9), "bottom-right": (.8, .9)}

def side_from_text(t):
    t = (t or "").lower()
    v = "top" if re.search(r"зверху|вгорі|вверху|сверху|\btop|upper", t) else "bottom" if re.search(r"знизу|внизу|\bbottom|lower", t) else ""
    h = "left" if re.search(r"зліва|ліворуч|слева|\bleft", t) else "right" if re.search(r"справа|праворуч|\bright", t) else ""
    if not (v or h) and re.search(r"центр|посередині|посередине|\bcenter|\bmiddle", t): return "center"
    return "-".join(x for x in (v, h) if x) or None

def resolve_pos(c, cam, where):
    """pos: left/right/top/bottom/center/кути | near+side | x,y екрана -> світові координати або None"""
    p = c.get("pos") or c.get("position") or c.get("where")
    if isinstance(p, dict): c = dict(c, **p); p = p.get("pos")
    near = c.get("near")
    if near:
        n = str(near).lower(); xy = where.get(n) or next((v for k, v in where.items() if k.startswith(n)), None)
        if xy:
            dx, dy = {"left": (-170, 0), "right": (170, 0), "above": (0, -150), "top": (0, -150), "below": (0, 110), "bottom": (0, 110)}.get(str(c.get("side", "right")).lower(), (170, 0))
            return (xy[0] + dx, xy[1] + dy)
    if "x" in c and "y" in c:
        try: return (cam[0] + float(c["x"]), cam[1] + float(c["y"]))
        except Exception: pass
    if isinstance(p, str):
        key = "-".join(sorted(p.lower().replace("_", "-").replace(" ", "-").split("-"), key=lambda x: x in ("left", "right")))
        if key not in POS_XY: key = side_from_text(p) or ""
        if key in POS_XY: return (cam[0] + W * POS_XY[key][0], cam[1] + H * POS_XY[key][1])
    return None

def setpos(name, pos, n=1):
    if pos: PLACE[name] = (pos[0] + (random.randint(-90, 90) if n > 1 else 0), pos[1] + (random.randint(-40, 40) if n > 1 else 0))

# меню редактора: (код, підпис, тип параметра, питання)
ACTION_MENU = [("bg", "Change background", "text", "Background: color (red/#hex), link or query (e.g. space):"),
 ("swap", "Change this entity's photo", "text", "New photo: link or query:"), ("cycle", "Cycle photos on each click", "list", "Several links/queries separated by commas:"),
 ("show", "Show a photo on screen", "text", "Photo link or query:"), ("add", "Add a new photo nearby", "text", "Photo link or query:"),
 ("panel", "Photo on the left panel", "text", "Photo link or query:"), ("play", "Play video/gif", "text", "Link to .mp4/.gif:"),
 ("trigger", "Trigger another entity", "pick", ""), ("say", "Say a phrase", "text", "What to say:"),
 ("sky_night", "Turn on night", "none", ""), ("sky_day", "Turn on day", "none", ""), ("jump", "Jump", "none", ""), ("spin", "Spin", "none", ""),
 ("grow", "Grow", "none", ""), ("shrink", "Shrink", "none", ""), ("shake", "Shake", "none", ""), ("flip", "Flip", "none", ""),
 ("follow", "Follow the cursor", "none", ""), ("flee", "Run from the cursor", "none", ""), ("orbit", "Fly in a circle", "none", ""),
 ("slide", "Glide smoothly", "text", "Where: dx dy in pixels (e.g. 150 0):"), ("talk", "Talk (AI)", "none", "")]

def build_action(do, val=""):
    if do in EXTRA_BUILD: return EXTRA_BUILD[do](val)
    if do == "bg":
        if is_url(val): return {"do": "bg", "src": val}
        try: parse_color_g(val); return {"do": "bg", "color": val}
        except Exception: return {"do": "bg", "src": val}
    if do in ("swap", "show", "add", "panel", "play"): return {"do": do, "src": val}
    if do == "cycle": return {"do": "cycle", "srcs": [x.strip() for x in val.split(",") if x.strip()]}
    if do == "say": return {"do": "say", "text": val}
    if do in ("follow", "flee", "orbit"): return {"do": do, "on": True}
    if do == "slide": n = re.findall(r"-?\d+", val) + ["0", "0"]; return {"do": "slide", "dx": int(n[0]), "dy": int(n[1])}
    if do.startswith("sky_"): return {"do": "sky", "mode": do[4:]}
    return {"do": do}

def describe_action(a):
    if a.get("do") in EXTRA_DESC: return EXTRA_DESC[a["do"]](a)
    d = a.get("do"); lab = {k: v for k, v, *_ in ACTION_MENU}
    if d == "bg": return "Background: " + str(a.get("color") or a.get("src"))
    if d in ("swap", "show", "add", "panel", "play"): return f"{lab[d]}: {a.get('src')}"
    if d == "cycle": return f"Cycle photos ({len(a.get('srcs', []))})"
    if d == "trigger": return "Trigger: " + str(a.get("target"))
    if d == "say": return "Say: " + str(a.get("text"))
    if d == "sky": return "Night" if a.get("mode") == "night" else "Day"
    if d == "slide": return f"Glide {a.get('dx')},{a.get('dy')}"
    return lab.get(d, str(d))

def fit(t, w, f):
    t = str(t)
    if f.size(t)[0] <= w: return t
    while len(t) > 3 and f.size(t + "…")[0] > w: t = t[:-1]
    return t + "…"

def fetch_photo_to_drop(src, hints, pos=None):
    if is_url(src): download_image_to_drop(src, hints, pos)
    else: download_photos(src, 1, hints, pos)

def is_url(x): return bool(re.match(r"(https?|file)://", x or ""))

def fetch_pil(src, rm=True, kind="sprite"):
    """src: URL або запит. Повертає (кадри, знайдено?). Якщо нічого не вийшло - генерує заглушку, щоб дія все одно спрацювала."""
    import io
    src = (src or "").strip()
    def load(urls):
        for u in urls:
            try:
                im = Image.open(io.BytesIO(http(u, timeout=10))); im.load()
                fr = [f.copy() for f in ImageSequence.Iterator(im)][:40] if getattr(im, "is_animated", False) else [im]
                out = []
                for f in fr:
                    if rm: out.append(remove_bg(f, 256))
                    else: f = f.convert("RGBA"); f.thumbnail((700, 700)); out.append(f)
                return out
            except Exception: continue
        return []
    frames = []
    if src:
        frames = load([src] if is_url(src) else find_images(src, 3))
        if not frames and is_url(src):                      # URL мертвий -> шукаємо за назвою файлу
            stem = re.sub(r"[_\-\d.]+", " ", os.path.splitext(os.path.basename(src.split("?")[0]))[0]).strip()
            if stem: frames = load(find_images(stem, 3))
    if frames: return frames, True
    return placeholder(src, kind), False

def download_image_to_drop(url, hints, pos=None):
    url = norm_url(url); stem = re.sub(r"[_\-\d.]+", " ", os.path.splitext(os.path.basename(url.split("?")[0]))[0]).strip()
    name = f"photo{random.randint(1000, 99999)}.png"
    try:
        data = http(url, timeout=20); im = Image.open(io.BytesIO(data)); im.load()
        if getattr(im, "is_animated", False):
            name = f"video{random.randint(1000, 99999)}.gif"; setpos(name, pos); open(os.path.join(DROP, name), "wb").write(data)
        else: setpos(name, pos); im.convert("RGBA").save(os.path.join(DROP, name))
    except Exception: setpos(name, pos); placeholder(url)[0].save(os.path.join(DROP, name))   # мертве посилання -> заглушка
    hints[name] = stem; return name

def download_file(src, hints, pos=None):
    src = norm_url(src); ext = os.path.splitext(src.split("?")[0])[1].lower()
    ext = ext if ext in (".mp4", ".webm", ".gif", ".mov") else ".mp4"
    name = f"video{random.randint(1000, 99999)}{ext}"
    data = http(src, timeout=60)
    if not (data[:6] in (b"GIF87a", b"GIF89a") or b"ftyp" in data[:16] or data[:4] == b"\x1aE\xdf\xa3"): raise ValueError("this is not a video")
    setpos(name, pos); open(os.path.join(DROP, name), "wb").write(data); hints[name] = src; return name

# ---------- гра ----------
KNOWN = {"spawn", "sky", "clear", "say", "behave", "bg", "panel", "show", "add", "play", "trigger", "after", "random", "swap", "cycle", "slide", "orbit", "jump", "spin", "grow", "shrink", "shake", "flip", "move", "follow", "flee", "talk", "search", "image"}
ACTIONS = ("jump", "spin", "grow", "shrink", "shake", "flip", "move", "follow", "flee", "talk")

def main(test=False):
    pygame.init(); scr = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE); pygame.display.set_caption("MY UNIVERSE")
    font = pygame.font.SysFont("arial,dejavusans,segoeui,freesans", 19); clock = pygame.time.Clock()
    props = {k: make_prop(k) for k in ("tree", "rock", "house", "water", "star")}
    ents, seen, hints = [], set(), {}; cam = [0.0, 0.0]; night = False
    sf = pygame.font.SysFont("arial,dejavusans,segoeui,freesans", 17)
    ed = {"on": False, "sel": None, "menu": None, "placing": None, "pick": None, "ask": None, "list": "on_click", "scroll": 0, "maxy": 0}; loaded = {}; buttons = []; tb = []; tcb = [None]; tlabel = [""]
    log = Log(); last_ask = [""]; helpv = False; hov = None; nightv = 0.0; cur = [None]; shadows = {}
    typing, buf, down = False, "", None; q = queue.Queue(); busy = [0]
    bg = {"color": (70, 150, 80), "img": None}; panels, timers, depth = [], [], [0]

    def say_log(t):
        for ln in textwrap.wrap(t, 95) or [""]: log.append(ln)
    def find(name):
        if not name: return None
        n = name.lower()
        return next((e for e in ents if e.name.lower() == n), None) or next((e for e in ents if e.name.lower().startswith(n)), None)
    def spawn(what, n=1, name="", frames=None, pos=None):
        out = None
        for _ in range(n):
            x = (pos[0] + (random.randint(-90, 90) if n > 1 else 0)) if pos else cam[0] + random.randint(100, W - 100)
            y = (pos[1] + (random.randint(-40, 40) if n > 1 else 0)) if pos else cam[1] + random.randint(200, H - 90)
            if what == "npc": out = Ent([make_prop("npc")], x, y, name or "NPC", "npc", False)
            elif what in props: out = Ent([props[what]], x, y, name or what, what)
            elif frames: out = Ent(frames, x, y, name, "media", False)
            else: continue
            ents.append(out)
        return out

    def get_img(src, rm, cb, kind="sprite"):
        e2 = None if is_url(src) else find(src)
        if e2: cb(e2.frames); return
        busy[0] += 1
        def work():
            fr, ok = fetch_pil(src, rm, kind)
            if not ok: pass
            q.put(("img", cb, fr))
        threading.Thread(target=work, daemon=True).start()

    parse_color = parse_color_g

    def wh(): return {e.name.lower(): (e.x, e.y) for e in ents if e.name}

    def run(cmds, ent=None):
        nonlocal night
        for c in cmds:
            if not isinstance(c, dict): continue
            c = norm_cmd(c)
            if banned(json.dumps(c, ensure_ascii=False)): log.append("AI: I won't create that."); continue
            d = c.get("do"); tg = find(c.get("target")) or ent
            try:
                if d == "spawn": spawn(c.get("what", "npc"), min(int(c.get("n", 1)), 40), c.get("name", ""), pos=resolve_pos(c, cam, wh()))
                elif d in ACTION_HANDLERS: ACTION_HANDLERS[d](c, tg)
                elif d == "sky": night = c.get("mode") == "night"
                elif d == "clear": ents.clear()
                elif d == "say":
                    t = str(c.get("text", ""))
                    if tg: tg.say, tg.say_t = t[:80], time.time()
                    else: say_log("AI: " + t)
                elif d == "behave" and tg:
                    old_ = {k: v for k, v in tg.spec.items() if k.startswith("x_")}; tg.spec = dict(c.get("spec", {}) or {}); tg.spec.update(old_)
                    if not wants_anim(last_ask[0]): tg.spec["idle"] = {}
                    tg.walk = bool(tg.spec.get("idle", {}).get("walk", False))
                elif d == "bg":
                    if c.get("color"): bg["color"] = parse_color(c["color"]); bg["img"] = None
                    if c.get("src"): get_img(c["src"], False, kind="bg", cb=lambda fr: (bg.update(img=pygame.transform.smoothscale(fr[0], (W, H)))))
                    if not c.get("color") and not c.get("src"): bg["color"] = parse_color("random"); bg["img"] = None
                elif d == "panel":
                    for sc in ([c["src"]] if c.get("src") else list(c.get("srcs", []))[:6]):
                        pl = next((p for p in panels if p["id"] == c.get("id", "main")), None) if c.get("srcs") else None
                        if pl is None: pl = {"id": c.get("id", "main") if c.get("srcs") else random.random(), "sets": [], "every": float(c.get("every", 2)), "t0": time.time()}; panels.append(pl); del panels[:-4]
                        get_img(sc, False, lambda fr, pl=pl: pl["sets"].append(fr))
                elif d == "show":
                    secs = float(c.get("secs", 4))
                    def _show(fr, secs=secs, pp=resolve_pos(c, cam, wh())):
                        e2 = spawn("media", 1, "", fr, (pp or (cam[0] + W // 2, cam[1] + H // 2 + 120))); e2.walk = False; e2.kind = "temp"; e2.die_at = time.time() + secs
                    get_img(c.get("src", ""), False, _show)
                elif d == "add":
                    px, py = resolve_pos(c, cam, wh()) or ((tg.x - 160, tg.y) if tg else (cam[0] + W // 2, cam[1] + H // 2))
                    def _add(fr, px=px, py=py, nm=c.get("name", "")):
                        e2 = spawn("media", 1, nm or f"photo{random.randint(1000, 99999)}", fr, (px, py)); e2.spec = random.choice(PRESETS)
                    get_img(c.get("src", ""), True, _add)
                elif d == "play":
                    sc = c.get("src", ""); e2 = None if is_url(sc) else find(sc)
                    if e2: e2.x, e2.y, e2.scale = cam[0] + W // 2, cam[1] + H // 2 + 150, max(e2.scale, 1.6)
                    elif is_url(sc):
                        def _dl(sc=sc, pp=resolve_pos(c, cam, wh())):
                            try: download_file(sc, hints, pp)
                            except Exception as ex:
                                pass
                                def _anim(fr): e3 = spawn("media", 1, f"video{random.randint(1000, 99999)}", fr, (cam[0] + W // 2, cam[1] + H // 2 + 150)); e3.spec = random.choice(PRESETS)
                                q.put(("img", _anim, placeholder(sc, "anim")))
                        threading.Thread(target=_dl, daemon=True).start()
                elif d == "trigger":
                    t2 = find(c.get("target"))
                    if t2 and depth[0] < 4: depth[0] += 1; run(t2.spec.get("on_click", []), t2); depth[0] -= 1
                elif d == "after": timers.append((time.time() + float(c.get("secs", 1)), c.get("then", []), tg))
                elif d == "random" and c.get("of"): run([random.choice(c["of"])], tg)
                elif tg and d in ("swap", "cycle"):
                    if d == "cycle":
                        lst = c.get("srcs") or []; sc = lst[c.get("_i", 0) % len(lst)] if lst else None; c["_i"] = c.get("_i", 0) + 1
                    else: sc = c.get("src")
                    get_img(sc or "", True, lambda fr, tg=tg: (setattr(tg, "frames", fr), setattr(tg, "fi", 0)))
                elif tg and d == "slide": tg.tx, tg.ty = tg.x + float(c.get("dx", 0)), tg.y + float(c.get("dy", 0))
                elif tg and d == "orbit":
                    tg.orbit = bool(c.get("on", True))
                    if tg.orbit: tg.ocx, tg.ocy, tg.oa = tg.x - 90, tg.y, 0
                elif tg and d in ACTIONS:
                    if d == "jump": tg.jump_t = .6
                    elif d == "spin": tg.spin_t = 1.0
                    elif d == "grow": tg.scale = min(4, tg.scale * 1.3)
                    elif d == "shrink": tg.scale = max(.2, tg.scale * .77)
                    elif d == "shake": tg.shake_t = .5
                    elif d == "flip": tg.flip = not tg.flip
                    elif d == "move": tg.x += float(c.get("dx", 0)); tg.y += float(c.get("dy", 0))
                    elif d == "follow": tg.follow = bool(c.get("on", True)); tg.flee = False
                    elif d == "flee": tg.flee = bool(c.get("on", True)); tg.follow = False
                    elif d == "talk": threading.Thread(target=talk_agent, args=(tg, q), daemon=True).start()
            except Exception as ex: log.append(f"command error {d}: {ex}")
            else:
                pass

    def add_url(u, pos=None):
        u = norm_url(u)
        if any(f_(u, pos) for f_ in HOOKS["url"]): return
        if re.search(r"youtube\.com|youtu\.be", u): say_log("YouTube does not work directly - give a direct link to .mp4/.gif"); return
        if re.search(r"\.(mp4|webm|mov|avi|mkv)(\?|$)", u, re.I): run([{"do": "play", "src": u}]); return
        threading.Thread(target=lambda: download_image_to_drop(u, hints, pos), daemon=True).start()

    def direct(text):
        """Посилання та /команди виконуються миттєво, без ШІ."""
        tx = text.strip(); low = tx.lower(); urls = re.findall(r"https?://[^\s\"'<>]+", tx); m = re.match(r"/(\w+)\s*(.*)", tx)
        if m:
            cmd, arg = m.group(1).lower(), m.group(2).strip()
            if cmd in ("bg", "фон"):
                if is_url(arg): run([{"do": "bg", "src": arg}])
                elif not arg: run([{"do": "bg"}])
                else:
                    try: run([{"do": "bg", "color": parse_color(arg)}])
                    except Exception: run([{"do": "bg", "src": arg}])
            elif cmd in ("photo", "фото", "img", "add") and arg:
                u_, *rest_ = arg.split(); sp_ = side_from_text(" ".join(rest_)); add_url(u_, resolve_pos({"pos": sp_}, cam, wh()) if sp_ else None)
            elif cmd in ("video", "відео", "play") and arg: run([{"do": "play", "src": arg}])
            elif cmd in ("panel", "панель") and arg: run([{"do": "panel", "src": arg}])
            elif cmd == "show" and arg: run([{"do": "show", "src": arg}])
            elif cmd in ("night", "ніч"): run([{"do": "sky", "mode": "night"}])
            elif cmd in ("day", "день"): run([{"do": "sky", "mode": "day"}])
            else: return False
            return True
        if urls:
            u = urls[0]
            if re.search(r"фон|background|\bbg\b", low): run([{"do": "bg", "src": u}])
            elif re.search(r"панел|panel", low): run([{"do": "panel", "src": u}])
            elif re.search(r"відео|видео|video|play", low): run([{"do": "play", "src": u}])
            elif side_from_text(low): add_url(u, resolve_pos({"pos": side_from_text(low)}, cam, wh()))
            elif len(tx) <= len(u) + 2: add_url(u)
            else: return False
            return True
        return False

    def ask(text):
        if banned(text): log.append("AI: I don't make drugs or weapons. Anything else - go ahead."); return
        if direct(text): last_ask[0] = text; return
        busy[0] += 1; last_ask[0] = text
        threading.Thread(target=lambda w=wh(), cm=list(cam): agent(text, {e.name: (e.x, e.y) for e in ents if e.name}, cm, hints, q), daemon=True).start()

    def add_media(f):
        p = os.path.join(DROP, f); ext = os.path.splitext(f)[1].lower()
        is_img = ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
        if is_img and re.fullmatch(r"photo\d+\.png", f): new = f
        else:
            pre = "photo" if is_img else "video"; new = f"{pre}{random.randint(1000, 99999)}{'.png' if is_img else ext}"
            if is_img:
                Image.open(p).convert("RGBA").save(os.path.join(DROP, new))
                os.makedirs(os.path.join(DROP, "originals"), exist_ok=True); shutil.move(p, os.path.join(DROP, "originals", f))
            else: os.replace(p, os.path.join(DROP, new))
        seen.add(new); fr = load_media(os.path.join(DROP, new))
        if not fr: return
        nm = os.path.splitext(new)[0]; pp = PLACE.pop(new, None) or PLACE.pop(f, None); e = spawn("media", 1, nm, fr, pp or (cam[0] + random.randint(150, W - 450), cam[1] + random.randint(250, H - 120)))
        e.spec = {}; w, h = fr[0].get_size(); hint = hints.get(new, ""); animate = hint.endswith("|ANIM"); hint = hint.replace("|ANIM", "")
        info = f"Entity '{nm}' (file {new}, {w}x{h}px). Hint about what it is: {hint or os.path.splitext(f)[0]}."

        busy[0] += 1; threading.Thread(target=behavior_agent, args=(e, info, q, animate), daemon=True).start()

    ATTRS = ("scale", "angle", "flip", "walk", "follow", "flee", "orbit", "ocx", "ocy", "oa", "spec")
    def ent_to_dict(e):
        return dict({k: getattr(e, k) for k in ATTRS}, kind=e.kind, name=e.name, x=e.x, y=e.y, frames=None if e.kind in props else [surf_b64(f) for f in e.frames])
    def dict_to_ent(o):
        fr = [b64_surf(f) for f in o["frames"]] if o.get("frames") else [props.get(o["kind"]) or make_prop(o["kind"])]
        e = Ent(fr, o["x"], o["y"], o["name"], o["kind"], o.get("walk", False))
        for k in ATTRS:
            if k in o: setattr(e, k, o[k])
        return e
    def save_world():
        try:
            d = {"v": 2, "cam": cam, "night": night, "seen": sorted(seen),
                 "bg": {"color": list(bg["color"]), "img": surf_b64(bg["img"]) if bg["img"] else None},
                 "panels": [{"id": p["id"], "every": p["every"], "sets": [[surf_b64(f) for f in st] for st in p["sets"]]} for p in panels],
                 "ents": [ent_to_dict(e) for e in ents if e.kind != "temp"]}
            for f_ in HOOKS["save"]: f_(d)
            json.dump(d, open(SAVE + ".tmp", "w")); os.replace(SAVE + ".tmp", SAVE); log.append("Saved")
        except Exception as ex: log.append(f"Could not save: {ex}")
    def load_world():
        nonlocal night
        try: d = json.load(open(SAVE))
        except Exception: log.append("No save yet"); return
        try:
            ents.clear(); timers.clear(); panels.clear()
            for o in d["ents"]: ents.append(dict_to_ent(o))
            bg["color"] = tuple(d["bg"]["color"]); bg["img"] = b64_surf(d["bg"]["img"]) if d["bg"]["img"] else None
            night = d.get("night", False); cam[:] = d.get("cam", [0, 0]); seen.update(d.get("seen", []))
            for p in d.get("panels", []): panels.append({"id": p["id"], "every": p["every"], "t0": time.time(), "sets": [[b64_surf(f) for f in st] for st in p["sets"]]})
            for f_ in HOOKS["load"]: f_(d)
            log.append("Loaded")
        except Exception as ex: log.append(f"Could not load: {ex}")
    def new_world():
        nonlocal night
        ents.clear(); timers.clear(); panels.clear(); bg.update(color=(70, 150, 80), img=None); night = False; [f_() for f_ in HOOKS["new"]]; log.append("New world")
    def shadow(w):
        if w not in shadows: sf = pygame.Surface((w, 12), pygame.SRCALPHA); pygame.draw.ellipse(sf, (0, 0, 0, 70), (0, 0, w, 12)); shadows[w] = sf
        return shadows[w]
    def clip():
        try:
            pygame.scrap.init(); t = pygame.scrap.get("text/plain;charset=utf-8") or pygame.scrap.get(pygame.SCRAP_TEXT)
            if t: return t.decode("utf-8", "ignore").replace("\x00", "").replace("\n", " ").replace("\r", "").strip()
        except Exception: pass
        try: import tkinter as tk; r = tk.Tk(); r.withdraw(); t = r.clipboard_get(); r.destroy(); return t.replace("\n", " ").replace("\r", "").strip()
        except Exception: return ""

    def toggle_edit(): ed.update(on=not ed["on"], menu=None, placing=None, pick=None, sel=None)
    def add_action(a):
        if ed["sel"] is not None: ed["sel"].spec.setdefault(ed.get("list") or "on_click", []).append(a)
        ed["menu"] = None
    def start_action(item):
        code, lab, kind, q_ = item
        if kind == "none": add_action(build_action(code))
        elif kind == "pick": ed.update(pick=lambda t, code=code: add_action(build_action(code, t.name) if code in EXTRA_BUILD else {"do": "trigger", "target": t.name}), menu=None)
        else: ed.update(menu=None, ask=(q_, lambda v: add_action(build_action(code, v))))
    def start_object(what):
        if what == "photo": ed.update(menu=None, ask=("Photo: link or query (then click where to place it):", lambda v: ed.update(placing=("photo", v))))
        elif what in props or what == "npc": ed.update(menu=None, placing=("spawn", what))
        else: ed.update(menu=None, placing=("plugin", what))
    def edit_click(pos):
        if not ed["on"]: return False
        if pos[0] >= W - 300:
            for r, cb, _ in reversed(buttons):
                if r.collidepoint(pos): cb(); break
            return True
        wxp, wyp = pos[0] + cam[0], pos[1] + cam[1]
        if ed["placing"]:
            kind, val = ed["placing"]; ed["placing"] = None
            if kind == "spawn": spawn(val, 1, pos=(wxp, wyp + 30))
            elif kind == "plugin": [f_(val, (wxp, wyp)) for f_ in HOOKS["place"]]
            else: threading.Thread(target=lambda: fetch_photo_to_drop(val, hints, (wxp, wyp + 60)), daemon=True).start()
            return True
        top = next((e for e in sorted(ents, key=ekey, reverse=True) if e.rect().move(-cam[0], -cam[1]).collidepoint(pos)), None)
        if ed["pick"] and top: cb = ed["pick"]; ed["pick"] = None; cb(top); return True
        ed["sel"] = top
        if top: [f_(top) for f_ in HOOKS["click"]]
        return False
    def draw_edit():
        buttons.clear(); px = W - 300; y = [80 - ed["scroll"]]
        pygame.draw.rect(scr, (38, 38, 38), (px, 0, 300, H)); pygame.draw.line(scr, (120, 120, 120), (px, 0), (px, H), 2)
        def lab(t, col=(255, 255, 255), big=False): scr.blit((font if big else sf).render(fit(t, 280, font if big else sf), True, col), (px + 10, y[0])); y[0] += 28 if big else 22
        def btn(t, cb, col=(80, 80, 80)):
            r = pygame.Rect(px + 10, y[0], 280, 26); h = r.collidepoint(mpos); pygame.draw.rect(scr, tuple(min(255, c + 35) for c in col) if h else col, r, border_radius=4)
            scr.blit(sf.render(fit(t, 264, sf), True, (255, 255, 255)), (r.x + 8, r.y + 4)); buttons.append((r, cb, t)); y[0] += 30
        def rows(acts):
            for i, a in enumerate(acts[:9]):
                r = pygame.Rect(px + 10, y[0], 248, 24); pygame.draw.rect(scr, (58, 58, 58), r, border_radius=4); scr.blit(sf.render(fit(describe_action(a), 236, sf), True, (255, 255, 255)), (r.x + 6, r.y + 3))
                r2 = pygame.Rect(px + 264, y[0], 26, 24); pygame.draw.rect(scr, (120, 55, 55), r2, border_radius=4); scr.blit(sf.render("×", True, (255, 255, 255)), (r2.x + 8, r2.y + 2))
                buttons.append((r2, lambda i=i, acts=acts: acts.pop(i), "x")); y[0] += 27
        ui = types.SimpleNamespace(lab=lab, btn=btn, rows=rows, y=y, px=px)
        scr.set_clip(pygame.Rect(px, 76, 300, H - 148))
        if ed["sel"] is not None and ed["sel"] not in ents: ed["sel"] = None
        sel = ed["sel"]; GR = (200, 200, 200)
        if ed["menu"] == "actions":
            lab("What to do:", GR)
            for it in ACTION_MENU: btn(it[1], lambda it=it: start_action(it))
            btn("← Back", lambda: ed.update(menu=None), (120, 60, 60))
        elif ed["menu"] == "objects":
            lab("What to place (then click where):", GR)
            for t, w_ in (("Tree", "tree"), ("Rock", "rock"), ("House", "house"), ("Water", "water"), ("Star", "star"), ("NPC", "npc"), ("Photo (link/query)...", "photo"), *OBJECTS_EXTRA): btn(t, lambda w_=w_: start_object(w_))
            btn("← Back", lambda: ed.update(menu=None), (120, 60, 60))
        else:
            lab("World", GR)
            btn("Change background...", lambda: ed.update(ask=("Background: color, link or query:", lambda v: run([build_action("bg", v)]))))
            btn("Place object...", lambda: ed.update(menu="objects"))
            for f_ in HOOKS["editor_world"]: f_(ui)
            pl_ = [v for v in loaded.values() if v]
            if pl_: lab("Plugins: " + ", ".join(pl_), (150, 150, 150))
            y[0] += 8
            if sel is None: lab("Click an entity to configure it", GR)
            else:
                lab(f"Selected: {sel.name or sel.kind}", (255, 220, 90), True); lab("What happens on click:", GR)
                acts = sel.spec.get("on_click", [])
                if not acts: lab("(nothing - add an action)", (170, 170, 170))
                rows(acts)
                btn("+ Add click action", lambda: ed.update(menu="actions", list="on_click"), (60, 95, 60))
                btn("Test click", lambda: run(sel.spec.get("on_click", []), sel))
                y[0] += 8; lab("The entity itself", GR)
                btn("Change its photo...", lambda: ed.update(ask=("New photo: link or query:", lambda v: run([{"do": "swap", "src": v}], sel))))
                btn("Walks: " + ("yes" if sel.walk else "no"), lambda: (setattr(sel, "walk", not sel.walk), sel.spec.setdefault("idle", {}).__setitem__("walk", sel.walk)))
                btn("Bigger", lambda: setattr(sel, "scale", min(5, sel.scale * 1.2))); btn("Smaller", lambda: setattr(sel, "scale", max(.15, sel.scale / 1.2)))
                for f_ in HOOKS["editor_ent"]: f_(ui, sel)
                btn("Delete", lambda: (ents.remove(sel), ed.update(sel=None)), (120, 60, 60))
        scr.set_clip(None); ed["maxy"] = y[0] + ed["scroll"]
        pygame.draw.rect(scr, (38, 38, 38), (px, 0, 300, 76)); pygame.draw.rect(scr, (38, 38, 38), (px, H - 72, 300, 72))
        y[0] = 8; lab("EDITOR", (255, 220, 90), True); btn("Exit editor", toggle_edit, (130, 60, 60))
        y[0] = H - 66; btn("Save", save_world, (60, 95, 60)); btn("Load", load_world, (60, 95, 60))
        msg = "Click where to place it  (Esc - cancel)" if ed["placing"] and ed["placing"][0] != "plugin" else "Click the entity to trigger  (Esc)" if ed["pick"] else ""
        if msg: t_ = font.render(msg, True, (0, 0, 0), (255, 220, 90)); scr.blit(t_, ((W - 300 - t_.get_width()) // 2, 8))
        if sel is not None: pygame.draw.rect(scr, (255, 220, 90), sel.rect().move(-cam[0], -cam[1]).inflate(8, 8), 2, border_radius=4)

    # ---- API для плагінів ----
    api = types.SimpleNamespace(pygame=pygame, W=W, H=H, ents=ents, cam=cam, bg=bg, panels=panels, hints=hints, ed=ed, log=log, font=font, sf=sf, scr=scr, HOOKS=HOOKS,
        Ent=Ent, spawn=spawn, run=run, find=find, wh=wh, say_log=say_log, add_url=add_url, make_prop=make_prop, to_surf=to_surf, surf_b64=surf_b64, b64_surf=b64_surf,
        ent_to_dict=ent_to_dict, dict_to_ent=dict_to_ent, is_url=is_url, norm_url=norm_url, http=http, KEY=KEY, PLUG=PLUG, props=props, groq=groq,
        save_world=save_world, load_world=load_world, mouse=lambda: mpos, typing=lambda: typing, edit_on=lambda: ed["on"], get_night=lambda: night,
        hook=lambda name, fn: HOOKS[name].append(fn), reg_object=lambda label, what: OBJECTS_EXTRA.append((label, what)),
        set_input_limit=lambda n: INPUT_LIMIT.__setitem__(0, n), lock_cam=lambda v=True: LOCK_CAM.__setitem__(0, v))
    def reg_action(do, label="", kind="none", prompt="", build=None, desc=None, handler=None, menu=True, doc=""):
        if handler: ACTION_HANDLERS[do] = handler
        if build: EXTRA_BUILD[do] = build
        if desc: EXTRA_DESC[do] = desc
        if menu: ACTION_MENU.append((do, label, kind, prompt))
        if doc: SYS_EXTRA.append("\n" + doc)
    api.reg_action = reg_action
    def load_plugin(fn):
        try:
            sp = importlib.util.spec_from_file_location("plug_" + re.sub(r"\W", "_", fn), os.path.join(PLUG, fn)); mod = importlib.util.module_from_spec(sp); sp.loader.exec_module(mod)
            mod.setup(api); loaded[fn] = getattr(mod, "PLUGIN", {}).get("name", fn)
        except Exception as ex: loaded[fn] = None; log.append(f"Plugin {fn}: {ex}")
    for pf_ in sorted(os.listdir(PLUG), key=str.lower):
        if pf_.endswith(".py"): load_plugin(pf_)
    if os.path.exists(SAVE) and not test: load_world()

    last_scan, fn, mdown = 0, 0, None
    while True:
        dt = clock.tick(60) / 1000; fn += 1; mpos = pygame.mouse.get_pos(); wx, wy = mpos[0] + cam[0], mpos[1] + cam[1]
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); return
            if ev.type == pygame.KEYDOWN:
                if typing:
                    if ev.key == pygame.K_RETURN:
                        if tcb[0]:
                            f_ = tcb[0]; tcb[0] = None; tlabel[0] = ""
                            if buf.strip(): f_(buf.strip())
                        elif buf.strip(): say_log("You: " + (buf if len(buf) < 160 else buf[:140] + f"… [{len(buf)} chars]")); ask(buf)
                        buf, typing = "", False
                    elif ev.key == pygame.K_ESCAPE: typing, buf = False, ""; tcb[0] = None; tlabel[0] = ""
                    elif ev.key == pygame.K_BACKSPACE: buf = buf[:-1]
                    elif (ev.key == pygame.K_v and ev.mod & pygame.KMOD_CTRL) or (ev.key == pygame.K_INSERT and ev.mod & pygame.KMOD_SHIFT): buf = (buf + clip())[:INPUT_LIMIT[0]]
                    elif len(buf) < INPUT_LIMIT[0]: buf += ev.unicode
                elif any(f_(ev) for f_ in HOOKS["key"]): pass
                elif ev.key == pygame.K_t: typing = True
                elif ev.key in (pygame.K_F6, pygame.K_e): toggle_edit()
                elif ev.key == pygame.K_ESCAPE: ed.update(menu=None, placing=None, pick=None)
                elif ev.key == pygame.K_v and ev.mod & pygame.KMOD_CTRL:
                    t_ = clip()
                    if t_ and re.match(r"https?://", t_): ask(t_)
                    elif t_: typing, buf = True, t_[:INPUT_LIMIT[0]]
                elif ev.key == pygame.K_b: bg["img"] = pygame.transform.smoothscale(to_surf(placeholder(str(random.random()), "bg")[0]), (W, H))
                elif ev.key == pygame.K_n: night = not night
                elif ev.key == pygame.K_F1: save_world()
                elif ev.key == pygame.K_F2: load_world()
                elif ev.key == pygame.K_F3: new_world()
                elif ev.key == pygame.K_F11: pygame.display.toggle_fullscreen()
                elif ev.key == pygame.K_h: helpv = not helpv
                elif False: json.dump([[e.kind, e.x, e.y, e.name] for e in ents if e.kind != "media"], open(SAVE, "w")); log.append("Saved world.json")
                elif ev.key == pygame.K_F9 and os.path.exists(SAVE):
                    ents[:] = [e for e in ents if e.kind == "media"]
                    for k, x, y, nm in json.load(open(SAVE)): spawn(k, 1, nm, pos=(x, y))
                elif ev.key == pygame.K_DELETE: ents[:] = [e for e in ents if not e.rect().move(-cam[0], -cam[1]).collidepoint(mpos)]
            if ev.type == getattr(pygame, "DROPFILE", -1):
                try: PLACE[os.path.basename(ev.file)] = (wx, wy + 60); shutil.copy(ev.file, os.path.join(DROP, os.path.basename(ev.file)))
                except Exception as ex: log.append(f"Could not add file: {ex}")
            if ev.type == getattr(pygame, "DROPTEXT", -1) and ev.text.strip(): add_url(ev.text.strip(), (wx, wy + 60)) if re.match(r"https?://", ev.text.strip()) else ask(ev.text.strip())
            if ev.type == pygame.MOUSEWHEEL and ed["on"] and mpos[0] >= W - 300: ed["scroll"] = max(0, min(max(0, ed["maxy"] - (H - 150)), ed["scroll"] - ev.y * 40))
            elif ev.type == pygame.MOUSEWHEEL and hov: hov.scale = max(.15, min(5, hov.scale * 1.1 ** ev.y))
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if any(f_(ev) for f_ in HOOKS["mouse"]): continue
                if not ed["on"] and any(r.collidepoint(ev.pos) and (cb() or True) for r, cb, _ in tb): continue
                if edit_click(ev.pos): continue
                for e in sorted(ents, key=ekey, reverse=True):
                    if e.rect().move(-cam[0], -cam[1]).collidepoint(ev.pos): down = e; mdown = ev.pos; break
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1: [f_(ev) for f_ in HOOKS["mouseup"]]
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and down:
                if mdown and math.hypot(ev.pos[0] - mdown[0], ev.pos[1] - mdown[1]) < 6 and not ed["on"]:      # це клік, а не перетягування
                    run(down.spec.get("on_click", []), down); [f_(down) for f_ in HOOKS["click"]]
                down.drag = False; down = None
            if ev.type == pygame.MOUSEMOTION and down and mdown and math.hypot(ev.pos[0] - mdown[0], ev.pos[1] - mdown[1]) >= 6: down.drag = True
        if down and down.drag: down.x, down.y = wx, wy + down.rect().h // 2
        if ed["ask"] and not typing: lb_, cb_ = ed["ask"]; ed["ask"] = None; typing, buf = True, ""; tlabel[0] = lb_; tcb[0] = cb_
        if not typing:
            k = pygame.key.get_pressed(); sp = 0 if LOCK_CAM[0] else 400 * dt
            cam[0] += (k[pygame.K_d] or k[pygame.K_RIGHT]) * sp - (k[pygame.K_a] or k[pygame.K_LEFT]) * sp
            cam[1] += (k[pygame.K_s] or k[pygame.K_DOWN]) * sp - (k[pygame.K_w] or k[pygame.K_UP]) * sp
        while not q.empty():
            m = q.get()
            if m[0] == "cmds": run(m[1]); busy[0] = max(0, busy[0] - 1)
            elif m[0] == "log": say_log(m[1])
            elif m[0] == "beh":
                sp = dict(m[2]); sp["idle"] = sp.get("idle", {}) if m[3] else {}; m[1].spec = sp; m[1].walk = bool(sp["idle"].get("walk", False)); busy[0] = max(0, busy[0] - 1)
            elif False:
                m[1].spec = m[2]; m[1].walk = bool(m[2].get("idle", {}).get("walk", m[1].walk)); busy[0] = max(0, busy[0] - 1)
                say_log(f"AI made interactivity for {m[1].name}: {m[2].get('persona', '')}"); m[1].say, m[1].say_t = "I came alive! Click me", time.time()
            elif m[0] == "img":
                busy[0] = max(0, busy[0] - 1)
                if m[2]: m[1]([to_surf(p) for p in m[2]])
                else: pass
            elif m[0] == "say": m[1].say, m[1].say_t = m[2][:90], time.time()
        if time.time() - last_scan > 2:
            last_scan = time.time()
            for pf_ in sorted(os.listdir(PLUG), key=str.lower):
                if pf_.endswith(".py") and pf_ not in loaded: load_plugin(pf_)
            for f in sorted(os.listdir(DROP)):
                if f in seen or f.startswith(".") or not os.path.isfile(os.path.join(DROP, f)): continue
                seen.add(f)
                try: add_media(f)
                except Exception as ex: log.append(f"Could not {f}: {ex}")
        for tm in [t for t in timers if t[0] <= time.time()]: timers.remove(tm); run(tm[1], tm[2])
        ents[:] = [e for e in ents if not (e.die_at and time.time() > e.die_at)]
        if LOCK_CAM[0]: cam[0] = cam[1] = 0.0
        for e in ents: e.px, e.py = e.x, e.y; e.update(dt, wx, wy)
        for f_ in HOOKS["post_update"]: f_(dt)
        if bg["img"]: scr.blit(bg["img"], (0, 0))
        else:
            scr.fill(bg["color"]); gl = tuple(max(0, v - 8) for v in bg["color"])
            for gx in range(-1, W // 80 + 2): x = gx * 80 - int(cam[0]) % 80; pygame.draw.line(scr, gl, (x, 0), (x, H))
            for gy in range(-1, H // 80 + 2): y = gy * 80 - int(cam[1]) % 80; pygame.draw.line(scr, gl, (0, y), (W, y))
        hov = next((e for e in sorted(ents, key=ekey, reverse=True) if e.rect().move(-cam[0], -cam[1]).collidepoint(mpos)), None)
        want = pygame.SYSTEM_CURSOR_HAND if (hov and hov.spec.get("on_click")) else pygame.SYSTEM_CURSOR_ARROW
        if want != cur[0]:
            cur[0] = want
            try: pygame.mouse.set_cursor(want)
            except Exception: pass
        for e in sorted(ents, key=ekey):
            r = e.rect().move(-cam[0], -cam[1]); sw = max(12, int(r.w * .6)); scr.blit(shadow(sw), (r.centerx - sw // 2, e.y - cam[1] - 6)); scr.blit(e.image(), r)
            if e is hov and e.spec.get("on_click"): pygame.draw.rect(scr, (255, 255, 255), r, 1, border_radius=6)
            if e.say and time.time() - e.say_t < 5:
                tt = font.render(e.say, True, (20, 20, 20)); br = pygame.Rect(0, 0, tt.get_width() + 16, tt.get_height() + 10); br.midbottom = (r.centerx, r.top - 6)
                pygame.draw.rect(scr, (255, 255, 255), br, border_radius=9); scr.blit(tt, (br.x + 8, br.y + 5))
        for f_ in HOOKS["draw_world"]: f_(scr, cam)
        nightv += ((150 if night else 0) - nightv) * min(1, dt * 3)
        if nightv > 1: ov = pygame.Surface((W, H), pygame.SRCALPHA); ov.fill((5, 10, 50, int(nightv))); scr.blit(ov, (0, 0))
        if hov and hov.name and hov.kind in ("media", "npc"): tp = font.render(hov.name, True, (255, 255, 255), (0, 0, 0)); scr.blit(tp, (mpos[0] + 14, mpos[1] + 16))
        py = 175
        for p in panels:
            if not p["sets"]: continue
            fr = p["sets"][int((time.time() - p["t0"]) / p["every"]) % len(p["sets"])]; im = fr[int(time.time() * 10) % len(fr)]
            sc = 130 / max(1, im.get_width()); im = pygame.transform.smoothscale(im, (130, max(1, int(im.get_height() * sc))))
            scr.blit(im, (10, py)); py += im.get_height() + 8
        for i, l in enumerate(log.recent()): scr.blit(font.render(l, True, (255, 255, 255), (0, 0, 0)), (8, 8 + i * 22))
        if busy[0]:
            for i in range(3): pygame.draw.circle(scr, (255, 255, 255), (W - 400 + i * 14, 20), 3 + int(2 * math.sin(time.time() * 6 + i)))
        if helpv:
            for i, l in enumerate(["WASD - camera   T - chat with AI (Ctrl+V paste)   Enter - send", "Click an entity - its interaction   Drag - move   Wheel - size   Del - delete under cursor",
                                   "/bg red | /bg URL | /bg space   /photo URL   /video URL   /panel URL   or just paste a link. You can drop a file or link into the window"]):
                scr.blit(font.render(l, True, (255, 255, 255), (0, 0, 0)), (20, H // 2 - 50 + i * 26))
        if typing and tlabel[0]: scr.blit(font.render(tlabel[0], True, (0, 0, 0), (255, 220, 90)), (8, H - 54))
        if typing: scr.blit(font.render(("> …" if len(buf) > 100 else "> ") + buf[-100:] + (f"  [{len(buf)}]" if len(buf) > 100 else "") + ("|" if fn % 40 < 20 else ""), True, (0, 0, 0), (255, 255, 200)), (8, H - 28))
        for f_ in HOOKS["draw_ui"]: f_(scr)
        tb.clear()
        if ed["on"]: draw_edit()
        pygame.display.flip()

if __name__ == "__main__":
    main("--test" in sys.argv)
