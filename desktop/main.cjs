'use strict';
const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const readline = require('node:readline');
const { validKey, allowedCommand } = require('./access.cjs');

const base = path.resolve(__dirname, '..');
const page = pathToFileURL(path.join(__dirname, 'renderer', 'index.html')).href;
let window, child, connecting, authenticated = false, closing = false;
let sequence = 0;
const pending = new Map();
const emit = event => { if (window && !window.isDestroyed()) window.webContents.send('queue:event', event); };
function trusted(event, requiresLogin = true) {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || event.senderFrame.url !== page) throw new Error('Untrusted desktop request.');
  if (requiresLogin && !authenticated) throw new Error('Enter your access key first.');
}
function connect() {
  if (connecting) return connecting;
  connecting = new Promise((resolve, reject) => {
    let settled = false;
    let stderr = '';
    const process = spawn('py', ['-u', path.join(__dirname, 'bridge.py')], { cwd: base, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    child = process;
    const timer = setTimeout(() => { if (!settled) { settled = true; reject(new Error('Python did not respond. Install requirements.txt, close the old tool, and reconnect.')); shutdown(); } }, 20000);
    const fail = message => {
      clearTimeout(timer);
      if (!settled) { settled = true; reject(new Error(message)); }
    };
    process.on('error', error => fail(`Could not launch Python: ${error.message}`));
    process.stderr.on('data', chunk => { stderr = (stderr + chunk.toString()).slice(-4000); });
    process.stdin.on('error', () => {});
    const lines = readline.createInterface({ input: process.stdout });
    lines.on('line', line => {
      if (line.length > 1000000) return;
      let event;
      try { event = JSON.parse(line); } catch { return; }
      if (event.type === 'ready') {
        clearTimeout(timer);
        if (!settled) { settled = true; resolve(event); }
      } else if (event.type === 'boot_error') { fail(event.text); emit({ type: 'error', text: event.text }); }
      else if (event.type === 'response') {
        const task = pending.get(event.id);
        if (task) { pending.delete(event.id); clearTimeout(task.timer); event.error ? task.reject(new Error(event.error)) : task.resolve(event.result); }
      } else emit(event);
    });
    process.on('exit', () => {
      clearTimeout(timer);
      if (child === process) { child = null; connecting = null; }
      fail(stderr || 'The Python engine disconnected. Close any old tool window and try again.');
      for (const [id, task] of pending) { clearTimeout(task.timer); task.reject(new Error('The Python engine disconnected.')); pending.delete(id); }
      if (!closing) emit({ type: 'bridge_closed', text: stderr || 'Engine disconnected. Reconnect to continue.' });
    });
  });
  connecting.catch(() => { connecting = null; });
  return connecting;
}
function command(name, payload = {}) {
  if (!child || child.killed || !child.stdin.writable) return Promise.reject(new Error('Connect the Python engine first.'));
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('Engine request timed out.')); }, 20000);
    pending.set(id, { resolve, reject, timer });
    child.stdin.write(JSON.stringify({ id, command: name, payload }) + '\n');
  });
}
async function shutdown() {
  const process = child;
  if (!process) return;
  const exited = new Promise(resolve => process.once('exit', resolve));
  if (process.stdin.writable) process.stdin.end(JSON.stringify({ command: 'shutdown' }) + '\n');
  await Promise.race([exited, new Promise(resolve => setTimeout(resolve, 3500))]);
  if (child === process) process.kill();
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { window.restore(); window.focus(); } });
  app.whenReady().then(() => {
    window = new BrowserWindow({ width: 1320, height: 880, minWidth: 1000, minHeight: 700,
      frame: false, autoHideMenuBar: true, backgroundColor: '#090d0c', title: 'Fortnite | Queue Control', show: false,
      webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true }
    });
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    window.webContents.on('will-navigate', event => event.preventDefault());
    window.webContents.session.setPermissionRequestHandler((_, __, callback) => callback(false));
    window.webContents.on('render-process-gone', () => shutdown());
    window.once('ready-to-show', () => window.show());
    window.loadURL(page);

    ipcMain.handle('queue:login', (event, key) => {
      trusted(event, false);
      authenticated = validKey(key);
      return authenticated ? { ok: true } : { ok: false, error: 'That key is not valid. Try again.' };
    });
    ipcMain.handle('queue:connect', event => { trusted(event); return connect(); });
    ipcMain.handle('queue:command', async (event, name, payload = {}) => {
      trusted(event);
      if (!allowedCommand(name)) throw new Error('Unsupported queue command.');
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('Invalid command payload.');
      if (name === 'start') window.minimize();
      try { return await command(name, payload); }
      catch (error) { if (name === 'start') { window.restore(); window.focus(); } throw error; }
    });
    ipcMain.handle('queue:logout', async event => { trusted(event); await shutdown(); authenticated = false; return { ok: true }; });
    ipcMain.handle('queue:logs', async event => { trusted(event); const error = await shell.openPath(path.join(base, 'logs')); if (error) throw new Error(error); });
    ipcMain.handle('queue:legacy', async event => {
      trusted(event); await shutdown();
      const legacy = spawn('py', [path.join(base, 'launch.py')], { cwd: base, windowsHide: true, detached: false, stdio: 'ignore' });
      legacy.on('error', error => emit({ type: 'error', text: error.message }));
      return { ok: true };
    });
    ipcMain.handle('window:minimize', event => { trusted(event, false); window.minimize(); });
    ipcMain.handle('window:close', event => { trusted(event, false); app.quit(); });
  });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', event => {
    if (closing) return;
    event.preventDefault(); closing = true;
    shutdown().finally(() => app.quit());
  });
}
