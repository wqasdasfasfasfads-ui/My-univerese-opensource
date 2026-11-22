# -*- coding: utf-8 -*-
"""github: input line up to 60000 characters; paste links right in the editor; GitHub links: images, repo folders, .py plugins."""
PLUGIN = {"name": "github", "version": "1.0"}
import re, json, os, threading

IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def setup(api):
    api.set_input_limit(60000)
    GH = re.compile(r"https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)(?:/(tree|blob|raw)/([^/\s]+)/?([^\s?#]*))?", re.I)

    def install(url):
        def work():
            try:
                code = api.http(url, timeout=20).decode("utf8", "ignore")
                if "def setup" not in code: api.log.append("This is not a plugin (no setup)"); return
                name = re.sub(r"[^\w.-]", "_", os.path.basename(url.split("?")[0])) or "plugin.py"
                api.ed.update(ask=(f"Install plugin {name}? It will RUN code from the internet. Type YES:", lambda v: confirm(v, name, code)))
            except Exception as ex: api.log.append(f"GitHub: {str(ex)[:70]}")
        threading.Thread(target=work, daemon=True).start()
    def confirm(v, name, code):
        if v.strip().lower() in ("yes", "y", "так", "да"): open(os.path.join(api.PLUG, name), "w", encoding="utf-8").write(code); api.log.append(f"Plugin {name} installed")

    def folder(owner, repo, ref, path, pos):
        def work():
            try:
                j = json.loads(api.http(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}" + (f"?ref={ref}" if ref else ""), timeout=15))
                imgs = [f for f in j if isinstance(j, list) and f.get("type") == "file" and f["name"].lower().endswith(IMG)][:8]
                for f in imgs: api.add_url(f["download_url"], pos)
                api.log.append(f"GitHub: images added: {len(imgs)}" if imgs else "GitHub: no images in the folder")
            except Exception as ex: api.log.append(f"GitHub: {str(ex)[:70]}")
        threading.Thread(target=work, daemon=True).start()

    def on_url(u, pos):
        m = GH.match(u)
        if m:
            owner, repo, kind, ref, path = m.groups(); path = path or ""
            if kind in ("blob", "raw") and path.lower().endswith(".py"): install(api.norm_url(u)); return True
            if kind in (None, "tree"): folder(owner, repo, ref, path, pos); return True
        if re.match(r"https?://raw\.githubusercontent\.com/.+\.py(\?|$)", u): install(u); return True
        return False
    api.hook("url", on_url)

    def paste(v):
        urls = re.findall(r"https?://[^\s\"'<>]+", v)
        for u in urls[:20]: api.add_url(u)
        if not urls: api.say_log(f"Text of {len(v)} chars - no links, nothing to add")
    def ed_world(ui): ui.btn("Paste links (GitHub / any)...", lambda: api.ed.update(ask=("Paste links (up to 60000 chars, several allowed):", paste)))
    api.hook("editor_world", ed_world)
