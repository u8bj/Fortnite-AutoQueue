# Electron development preview

This is an unbundled open-source preview. Run it from source with npm start; no installer or standalone EXE has been built. Download source previews from the GitHub Releases page.

Use Node.js 22.12 or newer. From the project root:

```powershell
npm install
npm start
```

The local access key is **u8bj**. This shared key only gates the interface; it is not a license server or a secure account system. It is intentionally visible in the open source code. No login data is sent anywhere.

The HTML/CSS/JavaScript interface connects to the existing Python queue runtime over a private JSON-lines subprocess pipe. Fonts and icons are installed locally through npm; the interface does not depend on a CDN.

## Test safely

Opening the app, signing in and changing tabs sends no game input. Automation only begins after you confirm the mode and press Start. Opening the design preview does not require administrator rights. For actual queue automation, close the old tool, open your terminal as administrator, and run `npm start`. Python and the existing requirements must still be installed for this development preview.

**F8** remains the Python engine's emergency stop while automation is running. Closing or signing out of Electron shuts down its Python worker. Only one queue tool can hold the project's lock at a time. The original `start.bat` and Tkinter app remain available; close one version before using the other.

Use **Test recognition** with the engine stopped. It waits five seconds for you to switch to the desired game screen and sends no keyboard or mouse input. The calibration button closes the Electron backend and hands control to the existing template-capture application as a separate window. Quitting Electron does not close that separate application; stop it with F8 and close its window before reconnecting Electron.

## Code

- `main.cjs`: local window, narrow validated IPC API and Python subprocess lifecycle.
- `preload.cjs`: isolated renderer bridge; no generic IPC or Node access.
- `access.cjs`: fixed local-key validation and command allowlist.
- `bridge.py`: adapter to the existing guarded runtime; retains the original focus/input/stop behavior.
- `renderer/`: English HTML, CSS, icons, transitions and actual engine event rendering.

```powershell
npm test
py -m unittest test_desktop_bridge -v
```

There is intentionally no EXE build command yet.

## Interface sounds and theme

The preview uses a violet/black Fortnite theme. Typing in the key field, button presses, successful key validation and invalid login attempts have quiet synthesized sounds. No external audio files or network service are used. Use the speaker icon in the title bar to mute or unmute all interface sounds; the preference is saved on this PC. Audio is initialized only after interaction, and unavailable audio never blocks the interface.
