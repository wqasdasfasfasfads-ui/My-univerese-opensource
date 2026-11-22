# Contributing to My Universe

Thanks for your interest! Anyone can fork this project and change it however they like (MIT license). If you want to share your changes back, pull requests are welcome.

## Ways to help
- Report bugs or suggest ideas via Issues
- Share your own plugins
- Improve docs and translations
- Fix bugs / add features in `main.py`

## Setup

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt
cp config.example.json config.json   # add your Groq key
python main.py
```

## Rules
- **Never commit `config.json`, API keys or `world_save.json`.** They are in `.gitignore` — keep it that way. Check `git status` before every commit.
- Keep PRs focused: one feature or fix per PR.
- Test by running the game and trying your change in the editor (`E`).

## Writing a plugin

A plugin is a single `.py` file in `plugins/` with two things:

```python
PLUGIN = {"name": "myplugin", "version": "1.0"}

def setup(api):
    # called once at game start
    api.log.append("Hello from my plugin!")
```

Look at `plugins/github.py` (small) and `plugins/Gamer.py` / `extra_plugins/Braini.py` (bigger) for real examples.

What `api` gives you (see the `api = types.SimpleNamespace(...)` block in `main.py` for the full list):

- **World:** `ents`, `Ent`, `spawn`, `find`, `bg`, `cam`, `panels`, `W`, `H`
- **Hooks:** `api.hook(name, fn)` with names `post_update`, `draw_world`, `draw_ui`, `key`, `mouse`, `mouseup`, `click`, `place`, `save`, `load`, `new`, `url`, `editor_world`, `editor_ent`
- **Actions & objects:** `api.reg_action(...)` adds a click action (also visible to the AI via `doc=`), `api.reg_object(label, what)` adds a placeable object
- **Helpers:** `add_url`, `http`, `groq`, `say_log`, `save_world`, `load_world`, `set_input_limit`, `lock_cam`, `mouse()`, `edit_on()`
- **Rendering:** `pygame`, `scr`, `font`

If your plugin is experimental or niche, put it in `extra_plugins/` so it isn't enabled by default.

⚠️ Plugins run with full access to the user's machine. Keep them honest: no hidden network calls, no obfuscated code, no reading files outside the project.
