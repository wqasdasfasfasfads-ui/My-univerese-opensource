# -*- coding: utf-8 -*-
"""Braini: an entity gets its own simple "brain" (like a fly's, but unique). Click - a window on the left about it."""
PLUGIN = {"name": "Braini", "version": "1.0"}
import math, random, time, textwrap

TRAITS = (("curiosity", "curiosity"), ("fear", "fear"), ("energy", "energy"), ("social", "sociability"))
STATES = {"wander": "wandering", "flee": "fleeing", "seek": "seeking light/water", "inspect": "inspecting", "rest": "resting"}
THINK = {"wander": ["Going wherever my eyes point.", "Nothing special.", "That way? No, that way."], "rest": ["Tired. I'll stand a bit.", "Need a rest."],
         "flee": ["Scary! Running!", "Don't come near!"], "seek": ["I see something bright!", "I want to go there, it's better."], "inspect": ["What's that?", "I'll get closer."]}


def setup(api):
    pg = api.pygame; W, H = api.W, api.H; ents = api.ents; S = {"show": None, "rect": None, "close": None}

    def new_brain():
        r = random.Random(); seed = r.randint(1, 10 ** 6); r.seed(seed)
        return {"seed": seed, "traits": {k: round(r.uniform(.15, .95), 2) for k, _ in TRAITS}, "needs": {"energy": 1.0, "hunger": .2, "boredom": .1},
                "mood": 0.0, "state": "wander", "thought": "I exist.", "log": [], "mem": {"touched": 0, "seen": []}, "until": 0, "vx": 0.0, "vy": 0.0, "hx": 1.0, "hy": 0.0, "age": 0.0, "tt": 0.0}
    def think(b, t):
        if t != b["thought"]: b["thought"] = t; b["log"] = (b["log"] + [t])[-8:]
    def give(e):
        if "x_brain" not in e.spec: e.spec["x_brain"] = new_brain(); e.walk = False; e.spec.setdefault("idle", {})["walk"] = False
    def clamp(v, a=0.0, b=1.0): return max(a, min(b, v))

    def post(dt):
        if api.edit_on(): return
        mx, my = api.mouse(); mx += api.cam[0]; my += api.cam[1]; now = time.time()
        for e in list(ents):
            b = e.spec.get("x_brain")
            if not b or e.spec.get("x_player") or e.drag or (e.spec.get("x_patrol") or {}).get("on"): continue
            t = b["traits"]; n = b["needs"]; b["age"] += dt; b["tt"] += dt; dmx, dmy = mx - e.x, my - e.y; dm = math.hypot(dmx, dmy) or 1
            if b["tt"] > .45:                                    # decision every ~0.45 s: simple and fast, like an insect
                b["tt"] = 0
                others = [o for o in ents if o is not e and o.kind not in ("wall", "temp")]
                food = [o for o in others if o.kind in ("star", "water")]; near = min(others, key=lambda o: math.hypot(o.x - e.x, o.y - e.y), default=None)
                if b["state"] == "rest" and n["energy"] > .7: b["until"] = 0
                if now >= b["until"]:
                    if n["energy"] < .15: b.update(state="rest", until=now + 5); think(b, random.choice(THINK["rest"]))
                    elif dm < 120 and t["fear"] > .55: b.update(state="flee", until=now + 1.6); think(b, random.choice(THINK["flee"]))
                    elif n["hunger"] > .6 and food:
                        f = min(food, key=lambda o: math.hypot(o.x - e.x, o.y - e.y)); b.update(state="seek", tx=f.x, ty=f.y, until=now + 4); think(b, random.choice(THINK["seek"]))
                    elif n["boredom"] * t["curiosity"] > .3 and near:
                        b.update(state="inspect", tx=near.x, ty=near.y + 20, until=now + 4); think(b, random.choice(THINK["inspect"]))
                        if near.name and near.name not in b["mem"]["seen"]: b["mem"]["seen"] = (b["mem"]["seen"] + [near.name])[-6:]
                    else:
                        a = random.uniform(0, 6.283); b.update(state="wander", hx=math.cos(a), hy=math.sin(a), until=now + random.uniform(.6, 1.6))
                        if random.random() < .25: think(b, random.choice(THINK["wander"]))
            st = b["state"]; sp = 40 + 90 * n["energy"] * (.5 + t["energy"]); ax = ay = 0.0
            if st == "flee": ax, ay, sp = -dmx / dm, -dmy / dm, sp * 1.8
            elif st in ("seek", "inspect"):
                dx, dy = b.get("tx", e.x) - e.x, b.get("ty", e.y) - e.y; d = math.hypot(dx, dy) or 1; ax, ay = dx / d, dy / d
                if d < 45:
                    if st == "seek": n["hunger"] = 0; think(b, "Nice place. I'm full."); b["mood"] = clamp(b["mood"] + .2, -1, 1)
                    else: n["boredom"] = 0; think(b, "Had a look. Nothing scary.")
                    b.update(state="wander", until=0)
            elif st == "wander": ax, ay = b["hx"], b["hy"]
            moving = st != "rest"
            b["vx"] += (ax * sp - b["vx"]) * min(1, 4 * dt) + (random.uniform(-18, 18) if moving else 0)
            b["vy"] += (ay * sp - b["vy"]) * min(1, 4 * dt) + (random.uniform(-18, 18) if moving else 0)
            if not moving: b["vx"] *= .8; b["vy"] *= .8
            e.x = clamp(e.x + b["vx"] * dt, 30, W - 30); e.y = clamp(e.y + b["vy"] * dt, 70, H - 10)
            n["energy"] = clamp(n["energy"] - dt * (.012 if moving else -.05)); n["hunger"] = clamp(n["hunger"] + dt * .008)
            n["boredom"] = clamp(n["boredom"] + dt * (.012 if st == "wander" else -.03)); b["mood"] *= (1 - .05 * dt)

    def on_click(e):
        b = e.spec.get("x_brain")
        if not b: return
        S["show"] = e
        if api.edit_on(): return
        m = b["mem"]; t = b["traits"]; m["touched"] += 1
        if t["fear"] > .55: b.update(state="flee", until=time.time() + 3); b["mood"] = clamp(b["mood"] - .3, -1, 1); think(b, "Ouch! Don't touch me!")
        else: b["mood"] = clamp(b["mood"] + .2 + .2 * t["social"], -1, 1); think(b, random.choice(["You touched me. Hi!", "Oh, someone is nearby.", "I've been noticed!"]))

    def h_brain(c, tg):
        if tg: give(tg); S["show"] = tg
    api.reg_action("brain", "Give a brain (Braini)", handler=h_brain, build=lambda v: {"do": "brain"}, desc=lambda a: "Give a brain",
                   doc='{"do":"brain","target":"name"} - give an entity its own brain (Braini); on click a window about its thoughts and state appears on the left')

    def ed_ent(ui, sel):
        has = "x_brain" in sel.spec
        ui.btn("Brain (Braini): " + ("has one - remove" if has else "add"), lambda: sel.spec.pop("x_brain", None) if has else give(sel))

    def draw_world(scr, cam):
        e = S["show"]
        if e is not None and e in ents: pg.draw.rect(scr, (255, 255, 255), e.rect().move(-cam[0], -cam[1]).inflate(10, 10), 1, border_radius=4)

    def draw_ui(scr):
        e = S["show"]
        if e is None: return
        b = e.spec.get("x_brain")
        if e not in ents or not b: S["show"] = None; return
        r = pg.Rect(14, H - 404, 290, 340); S["rect"] = r; S["close"] = pg.Rect(r.right - 28, r.y + 6, 22, 22); f, sf = api.font, api.sf; x = r.x + 12; y = r.y + 10
        pg.draw.rect(scr, (36, 36, 36), r); pg.draw.rect(scr, (140, 140, 140), r, 1)
        scr.blit(f.render(f"Brain: {e.name or e.kind}", True, (255, 255, 255)), (x, y)); pg.draw.rect(scr, (120, 55, 55), S["close"], border_radius=3); scr.blit(sf.render("×", True, (255, 255, 255)), (S["close"].x + 7, S["close"].y + 2)); y += 30
        def bar(label, v, lo=0.0):
            nonlocal y
            scr.blit(sf.render(label, True, (210, 210, 210)), (x, y)); br = pg.Rect(x + 116, y + 4, 150, 10); pg.draw.rect(scr, (70, 70, 70), br)
            pg.draw.rect(scr, (200, 200, 200), (br.x, br.y, int(br.w * clamp((v - lo) / (1 - lo))), br.h)); y += 20
        n = b["needs"]; bar("Mood", b["mood"], -1.0); bar("Energy", n["energy"]); bar("Hunger", n["hunger"]); bar("Boredom", n["boredom"])
        y += 4
        for k, ru in TRAITS: bar(ru, b["traits"][k])
        y += 4; scr.blit(sf.render("State: " + STATES.get(b["state"], b["state"]), True, (255, 220, 90)), (x, y)); y += 22
        for ln in textwrap.wrap("Thinking: " + b["thought"], 38)[:3]: scr.blit(sf.render(ln, True, (255, 255, 255)), (x, y)); y += 18
        m = b["mem"]; y += 4; scr.blit(sf.render(f"Touched: {m['touched']} times   Age: {int(b['age'])} s", True, (200, 200, 200)), (x, y)); y += 18
        if m["seen"]: scr.blit(sf.render("Saw: " + ", ".join(m["seen"])[:34], True, (200, 200, 200)), (x, y))
    def mouse(ev):
        r = S["rect"]
        if S["show"] is None or r is None or not r.collidepoint(ev.pos): return False
        if S["close"].collidepoint(ev.pos): S["show"] = None
        return True

    for n_, f_ in (("post_update", post), ("click", on_click), ("editor_ent", ed_ent), ("draw_world", draw_world), ("draw_ui", draw_ui), ("mouse", mouse)): api.hook(n_, f_)
