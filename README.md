# 🌌 My Universe

A 2D sandbox world where your photos and videos become living characters, controlled with a built-in AI chat (powered by [Groq](https://groq.com)). Build scenes, little games and interactive stories — with the mouse or just by asking the AI.

Free and open source (MIT). Fork it, break it, make it yours.

## Quick start

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt
cp config.example.json config.json      # Windows: copy config.example.json config.json
```

Open `config.json` and paste your Groq API key (free at https://console.groq.com/keys), or set it as an environment variable instead:

```bash
export GROQ_API_KEY=your_key_here       # Windows (PowerShell): $env:GROQ_API_KEY="your_key_here"
```

Run:

```bash
python main.py
```

> Without a key the game still works locally — you just get only simple commands instead of the AI.
> `config.json` is git-ignored, so your key will never be committed.

## Controls

| Key / action | What it does |
|---|---|
| `WASD` | Move camera |
| `T` | Chat with the AI (`Ctrl+V` to paste) |
| Click an entity | Run its interaction |
| Drag | Move an entity |
| Mouse wheel over an entity | Change size |
| `Del` | Delete |
| `E` | Editor on/off |
| `H` | Help |
| `F1` / `F2` / `F3` | Save / Load / New world |
| `F11` | Fullscreen |

Your world is saved to `world_save.json` and loaded automatically on start (delete it to start fresh).

## Adding your own media

Drop photos/videos into `drop_here/` → they become `photo{number}.png` / `video{number}`. Originals are moved to `drop_here/originals/`.
Nothing is animated unless you ask: *"make photo1234 fly"*.

Examples to type in the chat:
- `find a photo of a cat`
- `put 3 trees on the left`
- `make photo1234 change the background and show a photo from <URL> when clicked`

Quick commands (no AI): `/bg red`, `/bg #ff8800`, `/bg https://...`, `/bg space`, `/photo URL`, `/video URL`, `/panel URL`, `/show URL`, `/night`, `/day`.

Click actions: `swap, cycle, bg, add, panel, show, play, trigger, slide, orbit, follow, flee, after, random, jump, spin, grow, shrink, shake, flip, move, talk, say`.

Supported links: raw.github.com, github.com/.../blob/..., imgur.com/ID, Google Drive, Dropbox, giphy.com. YouTube is not supported directly (use a direct `.mp4`/`.gif`).

## Editor (`E`)

Everything with the mouse, no code. Click an entity to select it, then use the panel on the right: **+ Add click action**, change background, place objects, change photo, size, walking, delete. Use *Test click* to try an action. Save / Load buttons are at the bottom of the panel.

## Plugins

Any `.py` file in `plugins/` is loaded automatically (new files appear in a couple of seconds).

| Plugin | Location | What it does |
|---|---|---|
| **github** | `plugins/github.py` | 60000-character input line, paste several links at once, GitHub links (images, repo folders, `.py` plugins) |
| **Gamer** | `plugins/Gamer.py` | Pages (screens), walls with collision, arrow-key control, A→B routes, touch actions, Game Over |
| **Braini** | `extra_plugins/Braini.py` | Gives entities a simple "insect-like" brain with individual traits. Copy it into `plugins/` to enable |

⚠️ **A plugin is arbitrary Python code that runs on your machine.** Only install plugins you have read and trust.

Want to write one? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing

Pull requests, issues and forks are all welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Content filter

The built-in AI prompt blocks only two topics: drugs and weapons. This is controlled by the `BANNED` regex at the top of `main.py` — if you fork the project, you decide your own rules.

## License

[MIT](LICENSE) — do whatever you like, just keep the copyright notice.
