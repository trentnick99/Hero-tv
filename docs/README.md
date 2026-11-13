# HERO TV: where things are

| Folder | What is in it |
|---|---|
| `herotv/` | The program: the server, the TV schedule, the library, sorting, cover art, weather, Roku and phone support. |
| `herotv/roulette/` | Movie Roulette, the guessing game (rules, pictures, phones). |
| `web/` | The screens: `app.js` + `app.css` (the TV), `roulette.js` + `roulette.css` (the game), `pair.html` and `play.html` (phones). |
| `roku/` | The Roku app. |
| `config/` | Channels, sorting keywords, collections: the files Settings changes. |
| `tests/`, `scripts/` | Automatic checks. `scripts/browser_*_test.py` drive a real browser. |
| `installer/`, `assets/` | The Windows installer and icon. |
| `*.bat` (top folder) | Double-click helpers. They stay in the top folder because existing installs, the updater and the guide all look for them there. |
| `docs/history/` | Notes from early reviews, kept for the record. |
