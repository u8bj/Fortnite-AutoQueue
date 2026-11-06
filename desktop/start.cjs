'use strict';
const { spawn } = require('node:child_process');
const electron = require('electron');
const path = require('node:path');
const env = { ...process.env };
// Some development hosts set this for their own Electron process.
delete env.ELECTRON_RUN_AS_NODE;
const child = spawn(electron, [path.resolve(__dirname, '..')], { stdio: 'inherit', env });
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
