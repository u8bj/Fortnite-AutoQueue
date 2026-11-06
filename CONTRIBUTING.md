# Contributing

Run `py -m unittest discover -v` and `py -m compileall -q .` on Windows before submitting a change.
Keep the state machine independent of screenshots and Windows input.
Preserve foreground checks, F8 stopping, input release, and conservative team-elimination evidence.
Do not add game memory access, injection, anti-cheat bypass or anti-AFK behavior.
Private screenshot tests are optional and are not shipped; use synthetic fixtures for shareable regressions.
Describe reproduction steps and validation in your pull request. Redact player names in shared captures.
By submitting source code, you agree that your contribution is available under the project's MIT license.
