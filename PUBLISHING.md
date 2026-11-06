# Source release checklist

The current release is a source preview, not a standalone EXE.

1. Update package.json, package-lock.json, README, changelog and desktop documentation.
2. Run npm ci, npm test, and py -m unittest discover -v on Windows. Check syntax and the preview UI without starting live automation.
3. Review staged files: include source, lockfiles, the calibrated preset and selected crops. Exclude node_modules, personal full captures, logs, backups and build output.
4. Commit and push a normal update without rewriting history.
5. Create a preview tag and GitHub prerelease for the tested commit. Attach a ZIP produced from tracked files, not the working directory.
6. Verify the public download and its hash. Confirm the archive contains package.json, package-lock.json, desktop/, Python source, config and templates.

The MIT License covers project source and synthetic fixtures. Preserve third-party notices and the separate ownership of Fortnite interface assets.
