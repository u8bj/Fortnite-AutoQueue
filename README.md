# Fortnite Auto-Queue

An open-source Windows desktop tool for Fortnite queue management. A violet-and-black **Electron interface** connects to a Python screen-recognition engine, keeping the existing queue logic and calibrated German templates.

**[Download v0.2.0 Preview](https://github.com/u8bj/Fortnite-AutoQueue/releases/tag/v0.2.0-preview)** · [Setup](#getting-started) · [Contributing](CONTRIBUTING.md)

> This release is a source preview launched with `npm start`. A standalone EXE or installer has not been built. The interface is English; the included game-text templates are German.

## The desktop experience

- **Violet / black theme:** animated login, loading transition, hover effects and local icon/font assets.
- **Local key screen:** enter **`u8bj`** to open the workspace. This shared key is a local presentation gate, not a secure account or license service.
- **Interface sounds:** quiet synthesized sounds for typing, button presses and successful or unsuccessful key entry. The speaker button mutes all interface sounds and remembers your preference.
- **Live dashboard:** actual engine state, confirmed rounds, active-session time, focus information and activity logs.
- **Recognition panel:** inspect templates, confidence and consecutive matches, or run a read-only screen-recognition test.
- **Settings:** adjust scan interval, debug logging and result-screen inference while the engine is stopped.
- **Advanced capture:** open the original calibration application when a template needs replacing.

Fonts, icons and interface sounds run locally. No external account, hosted login service or CDN is needed while using the app. Dependency installation requires an internet connection.

## Queue flow

1. Recognize the lobby and ready up with **P** after mode confirmation.
2. Press **Space once** when the Battle Bus jump instruction is confirmed.
3. Monitor the match without movement or combat input.
4. Recognize spectating, wait for teammates, and return to active-match monitoring if the player is rebooted.
5. After confirmed whole-team elimination, optionally skip XP and select **Return to Lobby**.
6. Wait for the actual lobby before readying up again. **Play Again is never clicked.**

Temporary capture or recognition errors produce warnings and resynchronization rather than immediate shutdown. Unknown screens and timeouts alone do not authorize inputs or prove team elimination.

## Requirements

| Component | Requirement |
| --- | --- |
| Operating system | Windows 10 or Windows 11 |
| Node.js | 22.12 or newer, with npm |
| Python | 3.10 or newer, with the Windows `py` launcher |
| Display mode | Fortnite in Windowed Fullscreen on the primary monitor |
| Game language | German for the included recognition templates |
| Bindings | P = Ready/Play; Space = jump |
| Intended mode | Battle Royale / Zero Build / Squads / Unranked / Fill enabled |

The included crops were calibrated at approximately 1920 × 1080. Detection scales templates with resolution, but different layouts, UI scaling and game updates can affect recognition.

## Getting started

Download and extract the [preview ZIP](https://github.com/u8bj/Fortnite-AutoQueue/releases/tag/v0.2.0-preview), or clone the repository. Open a terminal **inside the project folder**, then run:

```powershell
py -m pip install -r requirements.txt
npm install
npm start
```

The first Electron launch may download its runtime. Keep the terminal open while using this development preview. If PowerShell blocks `npm.ps1`, use `npm.cmd install` and `npm.cmd start` instead.

1. Enter **`u8bj`** on the key screen.
2. Check the selected mode in Fortnite.
3. Confirm the mode checkbox in the dashboard.
4. Click **Start queue**. The desktop minimizes so Fortnite can take focus.
5. Press **F8** whenever you want to stop.

Opening the app, entering the key or changing tabs does **not** start game automation.

### Permissions and actual gameplay

The interface preview works without administrator rights. For actual queue automation, close the app, open your terminal **as administrator**, return to the project folder and run `npm start`. The Electron adapter checks elevation and Fortnite focus before starting.

Only one version of the tool can run against this project at a time. Close any old Python/Tkinter window before connecting Electron. Closing or leaving the Electron workspace shuts down its Python bridge.

### Original Python interface

The existing interface remains available through `start.bat`. It installs missing Python dependencies and requests Windows elevation. Review and approve the prompt yourself. Close Electron before using it.

## Included templates — try these first

**Twelve German recognition crops and their calibrated `config.json` are included. You do not need to take new screenshots as a normal setup step.**

First try **Test recognition** with the engine stopped. It gives you five seconds to switch to the desired game screen and then checks recognition without sending game inputs.

Only if detection fails on your setup:

1. Check German game text, Windowed Fullscreen, the primary monitor and your UI layout.
2. Open **Settings → Advanced capture**.
3. In the separate calibration app, select **Capture template** and choose the failing cue.
4. After the countdown, drag a tight box around static text. **Enter** saves; **Escape/F8** cancels.
5. Test against matching and unrelated scenes. Replace only cues that fail.

Exclude player names, changing numbers and animated backgrounds. A template recognizing its own source image is not independent evidence of live reliability.

Advanced capture disconnects Electron's bridge and opens the original application separately. Close that application when finished, then leave and reopen the Electron workspace to reconnect. Closing Electron does not close that separate app.

## State handling and controls

- The existing Python state machine, detector, focus checks and guarded P/Space routines are retained.
- A successful jump input switches directly to passive monitoring; no free-fall screenshot is required.
- Own-player death or spectating does not establish that the whole team has been eliminated.
- Reboot recovery requires repeated active-match evidence without conflicting death, spectator or result cues, and sends no input.
- Result actions require team-end evidence. The supplied preset enables final-result-screen inference; verify it against your game interface.
- Missing Fortnite focus pauses automation. **F8** and PyAutoGUI's screen-corner fail-safe remain available during automation.
- Stop/start in the same process preserves consumed inputs. Fully closing the app loses its in-memory session history.

## Local files and privacy

| Location | Purpose |
| --- | --- |
| `config.json` | Included German preset; saved settings update this local file |
| `config.example.json` | Reference copy of the included preset |
| `templates/` | Included crops; local replacement backups use `templates/originals/` |
| `tests/captures/` | Optional private full-screen captures; not distributed |
| `logs/` | Rotating logs and bounded debug screenshots; not distributed |
| `node_modules/` | npm-installed dependencies; not committed |

Full captures, logs, backups and build output are ignored by Git. Debug frames may be saved for recognition errors even when regular debug mode is off. The bundled config and supplied crop filenames are intentionally tracked; review modifications before committing. Redact personal information before sharing captures or logs.

## Development

```powershell
npm ci
npm test
py -m unittest discover -v
py -m compileall -q .
```

JavaScript tests cover the key/command gate and sound behavior. Python tests cover the state machine, detector, guarded input, lifecycle and Electron adapter. Private screenshot regressions skip when their local captures are absent. Synthetic fixtures test software mechanics, not live-game accuracy.

| Source | Responsibility |
| --- | --- |
| `desktop/main.cjs`, `preload.cjs` | Electron window, restricted IPC and Python worker lifecycle |
| `desktop/renderer/` | HTML, CSS, renderer logic and synthesized sounds |
| `desktop/bridge.py` | JSON-lines adapter around the existing Python runtime |
| `queue_engine.py`, `vision.py` | State machine and template detection |
| `runtime.py`, `game_input.py` | Screenshots, orchestration and guarded Windows input |
| `settings.py` | Configuration validation and cue catalog |
| `autoqueue.py`, `launch.py` | Original UI, calibration and elevated launcher |

The renderer has no Node integration and uses restricted IPC with context isolation and sandboxing. The shared key is public by design and is not authentication. There is no EXE build command in this preview.

## Project status

This experimental community project is not affiliated with Epic Games. Offline tests do not guarantee unattended reliability, compatibility with future game updates or compliance with a game's current policies.

The tool uses visible screenshots and standard Windows input. It does not read or modify Fortnite memory or files, inject into the game, or provide movement, combat or anti-AFK automation.

## License

Project source code and synthetic fixtures use the [MIT License](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Fortnite names, trademarks and interface artwork belong to their respective owners. Included interface crops are outside the project's MIT license; no rights to those assets are granted. Full personal game screenshots are not distributed.
