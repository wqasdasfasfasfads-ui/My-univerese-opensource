# -*- coding: utf-8 -*-
"""Gamer: pages (screens), walls with collision, arrow-key control, A->B routes, touch actions, Game Over."""
PLUGIN = {"name": "Gamer", "version": "1.0"}
import math, time


def setup(api):
    pg = api.pygame; W, H = api.W, api.H; ents = api.ents; ed = api.ed
    G = {"over": False, "was_edit": False, "pages": {(0, 0): {"ents": None, "bg": None, "night": False}}, "cur": (0, 0), "wall": None, "pick": None, "last": {}, "touch": {}}
    api.lock_cam(True)                                   # with Gamer the world is pages, the camera does not move

    # ---------- collisions ----------
    def feet(e, x=None, y=None):
        r = e.rect(); w = max(14, int(r.w * .5)); x = e.x if x is None else x; y = e.y if y is None else y
        return pg.Rect(int(x - w / 2), int(y - 14), w, 14)
    def walls(): return [w for w in ents if w.kind == "wall"]
    def hit(box, ws, me=None): return any(box.colliderect(w.rect()) for w in ws if w is not me)
    def resolve(e, ox, oy, ws):
        if not ws or (e.x, e.y) == (ox, oy) or not hit(feet(e), ws, e): return
        if hit(feet(e, ox, oy), ws, e): return           # already inside - let it get out
        nx, ny = e.x, e.y
        if not hit(feet(e, nx, oy), ws, e): e.y = oy
        elif not hit(feet(e, ox, ny), ws, e): e.x = ox
        else: e.x, e.y = ox, oy

    def make_wall(x0, y0, x1, y1):
        w = max(abs(x1 - x0), 14); h = max(abs(y1 - y0), 14); sf = pg.Surface((int(w), int(h)))
        sf.fill((95, 95, 100)); pg.draw.rect(sf, (55, 55, 60), sf.get_rect(), 2)
        e = api.Ent([sf.convert()], (x0 + x1) / 2, max(y0, y1) if abs(y1 - y0) > 14 else max(y0, y1) + 7, "wall", "wall", False); e.spec = {}; ents.append(e); return e

    # ---------- player ----------
    def player(): return next((e for e in ents if e.spec.get("x_player")), None)
    def set_player(e, on=True):
        for o in ents: o.spec.pop("x_player", None)
        if on: e.spec["x_player"] = True; e.walk = False

    # ---------- pages ----------
    def store():
        p = G["pages"][G["cur"]]; p["ents"] = list(ents); p["bg"] = {"color": tuple(api.bg["color"]), "img": api.bg["img"]}; p["night"] = api.get_night()
    def go(new, plr=None):
        if plr in ents: ents.remove(plr)
        store(); G["cur"] = new; p = G["pages"][new]; ents[:] = p["ents"] or []
        if plr is not None: ents.append(plr)
        if p["bg"]: api.bg.update(color=p["bg"]["color"], img=p["bg"]["img"])
        api.run([{"do": "sky", "mode": "night" if p["night"] else "day"}]); ed.update(sel=None); G["touch"].clear()
    def neigh(side):
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[side]; c = G["cur"]; return (c[0] + dx, c[1] + dy)
    def add_or_go(side):
        n = neigh(side)
        if n not in G["pages"]: G["pages"][n] = {"ents": [], "bg": {"color": tuple(api.bg["color"]), "img": None}, "night": False}
        go(n)

    def step_player(P, dx, dy, dt):
        n = math.hypot(dx, dy)
        if not n: return
        ox, oy = P.x, P.y; P.x += dx / n * 210 * dt; P.y += dy / n * 210 * dt
        resolve(P, ox, oy, walls())
        side = "left" if P.x < 6 else "right" if P.x > W - 6 else "up" if P.y < 30 else "down" if P.y > H - 2 else None
        if side:
            nb = neigh(side)
            if nb in G["pages"]:
                if side == "left": P.x = W - 20
                elif side == "right": P.x = 20
                elif side == "up": P.y = H - 6
                else: P.y = 40
                go(nb, P)
            else: P.x = min(max(P.x, 6), W - 6); P.y = min(max(P.y, 30), H - 2)

    def post(dt):
        if api.edit_on(): G["was_edit"] = True; return
        if G["was_edit"]:                                    # just entered play mode: remember this state for "restart"
            G["was_edit"] = False; G["over"] = False; api.save_world()
        if G["over"]: return                                 # Game Over: everything freezes
        ws = walls(); P = player()
        if P and not api.typing():
            k = pg.key.get_pressed()
            step_player(P, (k[pg.K_RIGHT] or k[pg.K_d]) - (k[pg.K_LEFT] or k[pg.K_a]), (k[pg.K_DOWN] or k[pg.K_s]) - (k[pg.K_UP] or k[pg.K_w]), dt)
        now = time.time()
        for e in list(ents):
            sp = e.spec.get("x_patrol")
            if sp and sp.get("on") and e is not P and e.kind != "wall":
                tx, ty = sp["b"] if sp.get("to", "b") == "b" else sp["a"]; dx, dy = tx - e.x, ty - e.y; d = math.hypot(dx, dy)
                if d < 5:
                    mode = sp.get("end", "loop"); to = sp.get("to", "b")
                    if mode == "loop": sp["to"] = "a" if to == "b" else "b"
                    elif to == "b":                                          # reached B
                        if mode == "vanish": ents.remove(e); G["touch"].pop(id(e), None); continue
                        if mode == "return": sp["to"] = "a"                  # goes back to A and stops there
                        else: sp["on"] = False; sp["done"] = True            # stay: remains at B
                    else: sp["on"] = False; sp["to"] = "b"; sp["done"] = True  # return: came back to A
                else:
                    s_ = min(d, sp.get("speed", 80) * dt); nx, ny = e.x + dx / d * s_, e.y + dy / d * s_
                    if P and feet(e, nx, ny).inflate(10, 10).colliderect(feet(P)):          # player in the way
                        if now - G["last"].get(id(e), 0) > 1.5: G["last"][id(e)] = now; api.run(e.spec.get("x_blocked", []), e)
                    else: e.x, e.y = nx, ny
            if e.kind not in ("wall", "temp") and e is not P: resolve(e, getattr(e, "px", e.x), getattr(e, "py", e.y), ws)
        if P:
            pf = feet(P).inflate(8, 8)
            for e in list(ents):
                lst = e.spec.get("x_touch")
                if e is P or not lst: continue
                h = pf.colliderect(e.rect()); was = G["touch"].get(id(e), False)
                if h and not was: api.run(lst, e)
                G["touch"][id(e)] = h

    # ---------- actions ----------
    def h_control(c, tg):
        if tg: set_player(tg, c.get("on", True))
    def h_patrol(c, tg):
        sp = tg.spec.get("x_patrol") if tg else None
        if sp is not None:
            on = c.get("on"); sp["on"] = (not sp.get("on")) if on is None else bool(on); tg.walk = False
            if sp["on"] and sp.get("end", "loop") != "loop":                 # new "one-shot" start: from A again
                sp["to"] = "b"
                if sp.pop("done", False): tg.x, tg.y = sp["a"]
            elif sp["on"]: sp.pop("done", None)
    api.reg_action("control", "Control with arrow keys (Gamer)", build=lambda v: {"do": "control", "on": True}, desc=lambda a: "Control with arrow keys", handler=h_control,
                   doc='{"do":"control","target":"name"} - control this entity with the arrow keys (Gamer)')
    api.reg_action("patrol", "", menu=False, handler=h_patrol, desc=lambda a: ("Start route: " if a.get("on") else "Stop route: ") + str(a.get("target")),
                   doc='{"do":"patrol","target":"name","on":true} - start/stop the A->B route of an entity (Gamer)')
    api.reg_action("patrol_on", "Start an entity's route (click it)", "pick", build=lambda n: {"do": "patrol", "target": n, "on": True}, menu=True)
    api.reg_action("patrol_off", "Stop an entity's route (click it)", "pick", build=lambda n: {"do": "patrol", "target": n, "on": False}, menu=True)
    def h_over(c, tg): G["over"] = True
    api.reg_action("gameover", "Game Over (show screen)", build=lambda v: {"do": "gameover"}, desc=lambda a: "Game Over", handler=h_over,
                   doc='{"do":"gameover"} - show the GAME OVER screen and freeze the game (click or R restarts) (Gamer)')
    def restart():
        G["over"] = False; api.load_world()
    api.reg_object("Wall (drag with the mouse)", "wall")

    # ---------- editor ----------
    ENDS = {"loop": "back and forth forever", "stay": "stays at B", "vanish": "disappears at B", "return": "returns to A and stops"}
    def cycle_end(sp):
        ks = list(ENDS); sp["end"] = ks[(ks.index(sp.get("end", "loop")) + 1) % len(ks)]; sp["to"] = "b"; sp.pop("done", None)
    def set_wait(sp, w):
        sp["wait"] = w; sp["on"] = not w; sp["to"] = "b"; sp.pop("done", None)
    def pick_touch(sel):
        def cb(t):
            if t is sel: return
            sel.spec.setdefault("x_touch", []).append({"do": "patrol", "target": t.name, "on": True})
        ed["pick"] = cb
    def ed_world(ui): ui.lab(f"Page {G['cur'][0]},{G['cur'][1]}  (total {len(G['pages'])})", (160, 160, 160))
    def ed_ent(ui, sel):
        if sel.kind == "wall": return
        pl = bool(sel.spec.get("x_player")); sp = sel.spec.get("x_patrol"); ui.y[0] += 6; ui.lab("Gamer", (200, 200, 200))
        ui.btn("Arrow-key control: " + ("yes" if pl else "no"), lambda: set_player(sel, not pl))
        ui.btn("Route A→B: set (2 clicks)", lambda: G.update(pick={"ent": sel, "pts": []}))
        if sp:
            ui.btn("Route: " + ("moving" if sp.get("on") else "stopped"), lambda: sp.__setitem__("on", not sp.get("on")))
            ui.btn("Start: " + ("after touch" if sp.get("wait") else "immediately"), lambda: set_wait(sp, not sp.get("wait")))
            ui.btn("At the end (B): " + ENDS[sp.get("end", "loop")], lambda: cycle_end(sp))
            ui.btn("Remove route", lambda: sel.spec.pop("x_patrol", None))
        ui.lab("When the player touches it:", (200, 200, 200)); ui.rows(sel.spec.setdefault("x_touch", []))
        ui.btn("+ Touch action", lambda: ed.update(menu="actions", list="x_touch"), (60, 95, 60))
        ui.btn("On touch START walking (click an entity)", lambda: pick_touch(sel), (60, 95, 60))
        ui.btn("On touch: GAME OVER", lambda: sel.spec.setdefault("x_touch", []).append({"do": "gameover"}), (120, 60, 60))
        if sp:
            ui.lab("If the player blocks the route:", (200, 200, 200)); ui.rows(sel.spec.setdefault("x_blocked", []))
            ui.btn("+ Blocked action", lambda: ed.update(menu="actions", list="x_blocked"), (60, 95, 60))
    def tabs():
        c = (W - 300) // 2
        return [(pg.Rect(0, H // 2 - 16, 26, 32), "left"), (pg.Rect(W - 326, H // 2 - 16, 26, 32), "right"), (pg.Rect(c - 16, 0, 32, 26), "up"), (pg.Rect(c - 16, H - 26, 32, 26), "down")]
    def mouse(ev):
        if G["over"]: restart(); return True
        if not ed["on"] or ev.pos[0] >= W - 300: return False
        for r, side in tabs():
            if r.collidepoint(ev.pos): add_or_go(side); return True
        if G["pick"]:
            pts = G["pick"]["pts"]; pts.append(list(ev.pos))
            if len(pts) == 2:
                e = G["pick"]["ent"]; e.spec["x_patrol"] = {"a": pts[0], "b": pts[1], "speed": 80, "on": True, "to": "b"}; e.x, e.y = pts[0]; e.walk = False; G["pick"] = None
            return True
        if ed["placing"] == ("plugin", "wall"): G["wall"] = [ev.pos, ev.pos]; return True
        return False
    def mouseup(ev):
        w = G["wall"]
        if w:
            (x0, y0), (x1, y1) = w[0], ev.pos; G["wall"] = None
            if abs(x1 - x0) + abs(y1 - y0) > 8: make_wall(x0, y0, x1, y1)
    def key(ev):
        if G["over"]:
            if ev.key in (pg.K_r, pg.K_RETURN, pg.K_SPACE): restart()
            return True
        if ev.key == pg.K_ESCAPE: G.update(pick=None, wall=None)
        return False
    def draw_world(scr, cam):
        if not ed["on"]: return
        for e in ents:
            sp = e.spec.get("x_patrol")
            if sp:
                a, b = tuple(sp["a"]), tuple(sp["b"]); pg.draw.line(scr, (255, 220, 90), a, b, 1); pg.draw.circle(scr, (255, 220, 90), a, 5, 1); pg.draw.circle(scr, (255, 220, 90), b, 5)
        if G["wall"]:
            (x0, y0), (x1, y1) = G["wall"][0], api.mouse(); pg.draw.rect(scr, (255, 255, 255), pg.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)), 1)
    BIG = {}
    def draw_ui(scr):
        if G["over"]:
            if not BIG: BIG["a"] = pg.font.Font(None, 150); BIG["b"] = pg.font.Font(None, 40)
            ov = pg.Surface((W, H), pg.SRCALPHA); ov.fill((0, 0, 0, 200)); scr.blit(ov, (0, 0))
            t = BIG["a"].render("GAME OVER", True, (220, 30, 30)); scr.blit(t, t.get_rect(center=(W // 2, H // 2 - 30)))
            t = BIG["b"].render("Click or press R to restart", True, (255, 255, 255)); scr.blit(t, t.get_rect(center=(W // 2, H // 2 + 60)))
            return
        if not ed["on"]: return
        mp = api.mouse()
        for r, side in tabs():
            pg.draw.rect(scr, (110, 110, 110) if r.collidepoint(mp) else (70, 70, 70), r, border_radius=4)
            t = api.font.render("+" if neigh(side) not in G["pages"] else {"left": "<", "right": ">", "up": "^", "down": "v"}[side], True, (255, 255, 255)); scr.blit(t, t.get_rect(center=r.center))
        msg = ("Click point " + ("A" if not G["pick"]["pts"] else "B")) if G["pick"] else "Drag the mouse to draw a wall  (Esc)" if ed["placing"] == ("plugin", "wall") else ""
        if msg: t = api.font.render(msg, True, (0, 0, 0), (255, 220, 90)); scr.blit(t, ((W - 300 - t.get_width()) // 2, 38))

    # ---------- saving ----------
    def save(d):
        store()
        d["gamer"] = {"cur": list(G["cur"]), "pages": {f"{k[0]},{k[1]}": {"ents": [api.ent_to_dict(e) for e in p["ents"] if e.kind != "temp"],
                      "bg": {"color": list(p["bg"]["color"]), "img": api.surf_b64(p["bg"]["img"]) if p["bg"]["img"] else None}, "night": p["night"]} for k, p in G["pages"].items()}}
    def load(d):
        g = d.get("gamer"); G["pages"] = {}; G["touch"].clear()
        if not g: G["pages"][(0, 0)] = {"ents": None, "bg": None, "night": False}; G["cur"] = (0, 0); return
        cur = tuple(g["cur"]); G["cur"] = cur
        for k, p in g["pages"].items():
            key_ = tuple(int(v) for v in k.split(","))
            bgd = {"color": tuple(p["bg"]["color"]), "img": api.b64_surf(p["bg"]["img"]) if p["bg"]["img"] else None}
            G["pages"][key_] = {"ents": None if key_ == cur else [api.dict_to_ent(o) for o in p["ents"]], "bg": bgd, "night": p["night"]}
    def new():
        G["pages"] = {(0, 0): {"ents": None, "bg": None, "night": False}}; G["cur"] = (0, 0); G["pick"] = G["wall"] = None

    for n_, f_ in (("post_update", post), ("editor_world", ed_world), ("editor_ent", ed_ent), ("mouse", mouse), ("mouseup", mouseup), ("key", key),
                   ("draw_world", draw_world), ("draw_ui", draw_ui), ("save", save), ("load", load), ("new", new)): api.hook(n_, f_)
    api.gamer = {"G": G, "step_player": step_player, "make_wall": make_wall, "add_or_go": add_or_go, "set_player": set_player, "player": player, "feet": feet}
