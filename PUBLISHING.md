# Publishing to GitHub

This directory is a public source export. The original calibrated desktop installation stays separate.

1. Sign in to GitHub and create a new public repository, for example `fortnite-autoqueue`.
2. Leave the automatic README, license and .gitignore options unchecked: they are already included here.
3. Choose **uploading an existing file** on the empty repository page.
4. Upload the **contents of this directory**, including `.gitignore`, `LICENSE`, `config.json`, `config.example.json`, the supplied PNGs under `templates/`, tests and synthetic fixtures. Do not upload the ZIP as a single repository file.
5. Review the file list, then commit the upload.

Alternatively, from this directory using Git:

```powershell
git init
git add .
git diff --cached --stat
git commit -m "Initial open-source release"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/fortnite-autoqueue.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your account name and create the empty repository first. Authenticate through GitHub's normal sign-in flow; never put credentials in source files.

The source export includes the supplied German recognition crops and their validated preset. Users should try these first and only capture replacements if recognition fails. Full personal screenshots, logs, template backups and internal project notes are excluded. Private screenshot tests are intentionally skipped without their local captures. The MIT license covers source code and synthetic fixtures, not Fortnite interface assets.
