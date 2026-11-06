# Fortnite Auto-Queue

A Python desktop tool for Windows that handles Fortnite's queue flow through screen recognition and standard keyboard and mouse input.

It readies up from the lobby, jumps from the Battle Bus, monitors match progress, and returns to the lobby after the team is eliminated.

## Features

- **Automatic ready-up:** presses P when the lobby is recognized.
- **Battle Bus detection:** presses Space once when the jump prompt appears.
- **Match monitoring:** observes the game after jumping without controlling movement or combat.
- **Spectating detection:** waits while teammates are still playing.
- **Reboot detection:** switches back to active-match monitoring when the player is rebooted.
- **Result handling:** optionally skips the XP animation and selects Return to Lobby after confirmed team elimination.
- **Queue loop:** waits for the lobby before readying up again.
- **Error recovery:** continues monitoring after temporary capture or recognition errors.
- **Emergency stop:** press F8 to stop the tool, including while Fortnite has focus.
- **English interface:** includes settings, recognition testing, template capture, and activity logs.

## Included Templates

German recognition templates and their calibrated settings are included.

**Try these templates first. You do not need to take new screenshots unless recognition fails on your setup.**

The included templates require German game text. Different interface layouts, UI scaling, or Fortnite updates may require replacement templates. Use **Test recognition** to check detection without sending game input.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Fortnite in Windowed Fullscreen on the primary monitor
- German game language for the included templates
- P assigned to Ready/Play
- Space assigned to jump

The intended game mode is Battle Royale, Zero Build, Squads, Unranked, with Fill enabled.

## Getting Started

1. Download and extract the project.
2. Run `start.bat`.
3. Review and approve the Windows administrator prompt.
4. Select the correct mode in Fortnite.
5. Confirm the mode checkbox in the tool.
6. Click **START**.

Press **F8** whenever you want to stop.

## How It Works

The tool matches screenshots against small interface templates and uses repeated detections to determine the current game state.

It uses ordinary Windows input and does not read or modify Fortnite's memory or game files.

After jumping, it only monitors the match. It does not automate movement, aiming, combat, or anti-AFK actions.

## Project Status

This project is experimental. Recognition depends on the visible game interface, and game updates may require recalibration.

The tool is an independent community project and is not affiliated with Epic Games.

## License

Source code and synthetic test fixtures are available under the MIT License.

Fortnite trademarks and interface assets belong to their respective owners. The included game-interface crops are not covered by the MIT License.
