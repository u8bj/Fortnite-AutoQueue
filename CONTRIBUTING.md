# Contributing

Use Windows, Python 3.10+ and Node.js 22.12+. Install Python dependencies with `py -m pip install -r requirements.txt` and JavaScript dependencies with `npm ci`.

Before submitting a change:

```powershell
npm test
py -m unittest discover -v
py -m compileall -q .
```

Launch the interface with `npm start`; the local key is `u8bj`. Do not start live game automation during automated tests.

Keep the state machine independent of screenshots and Windows input. Preserve P/Space behavior, focus checks, F8 stopping, input release, consumed-action flags and conservative team-elimination evidence. Preserve Electron context isolation, sandboxing and the narrow IPC allowlist. Do not expose unrestricted shell, filesystem or IPC access to the renderer.

Do not add game memory access, injection, anti-cheat bypass or anti-AFK behavior. Private screenshot regressions are optional and are not distributed; use synthetic fixtures for shareable tests.

Describe the problem, resulting behavior and validation in your pull request. Redact player names and personal information before sharing captures. Never commit credentials, logs, full captures, node_modules or build output.

By submitting project source, you agree that your contribution is available under the MIT License. Fortnite assets and third-party packages retain their respective rights and licenses.
