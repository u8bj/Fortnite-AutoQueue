'use strict';
const $ = id => document.getElementById(id);
const api = window.queue;
const sound = window.QueueSound.createSoundEngine();
try { sound.setMuted(localStorage.getItem('fortnite-ui-muted') === 'true'); } catch {}
function updateSoundButton() {
  const muted = sound.isMuted();
  $('sound-toggle').setAttribute('aria-pressed', String(muted));
  $('sound-toggle').setAttribute('aria-label', muted ? 'Enable interface sounds' : 'Mute interface sounds');
  $('sound-toggle').title = muted ? 'Enable interface sounds' : 'Mute interface sounds';
  $('sound-toggle').innerHTML = `<i data-lucide="${muted ? 'volume-x' : 'volume-2'}"></i>`;
  icons();
}

const state = { connected: false, active: false, busy: false, rounds: 0, templates: [], detections: [], missing: [], logs: [], elapsed: 0, startedAt: null, unsubscribe: null, admin: false };
const icons = () => window.lucide?.createIcons();
const readable = value => String(value || '').replace(/[_-]/g, ' ').replace(/^./, c => c.toUpperCase());
const errorText = error => error?.message || String(error || 'Something went wrong.');
const views = ['login', 'loading', 'dashboard'];
function showView(name) { views.forEach(view => $(`${view}-view`).hidden = view !== name); }
function notice(text, isError = false) { $('notice-text').textContent = text; $('notice').hidden = !text; $('notice').classList.toggle('error', isError); }
function appendLog(text, type = 'log') {
  const entry = { text: String(text), type, time: new Date() };
  state.logs.push(entry);
  if (state.logs.length > 300) state.logs.shift();
  const box = $('activity-log');
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.querySelector('.log-empty')?.remove();
  const row = document.createElement('div'); row.className = `log-entry ${type === 'warning' || type === 'error' ? type : ''}`;
  const time = document.createElement('time'); time.textContent = entry.time.toLocaleTimeString('en-GB');
  const textEl = document.createElement('span'); textEl.textContent = entry.text;
  row.append(time, textEl); box.append(row);
  while (box.children.length > 300) box.firstElementChild.remove();
  if (atBottom) box.scrollTop = box.scrollHeight;
  $('event-count').textContent = `${state.logs.length} event${state.logs.length === 1 ? '' : 's'}`;
}
async function command(name, payload = {}) {
  if (!state.connected) throw new Error('The local engine is disconnected. Leave the workspace and connect again.');
  const result = await api.command(name, payload);
  if (result?.ok === false) throw new Error(result.error || `${readable(name)} failed.`);
  return result;
}
function setActive(active) {
  if (active && !state.active) state.startedAt = Date.now();
  if (!active && state.active && state.startedAt) { state.elapsed += Date.now() - state.startedAt; state.startedAt = null; }
  state.active = Boolean(active);
  updateControls(); updateTimer();
}
function updateTimer() {
  const total = Math.floor((state.elapsed + (state.startedAt ? Date.now() - state.startedAt : 0)) / 1000);
  $('elapsed').textContent = [Math.floor(total / 3600), Math.floor(total % 3600 / 60), total % 60].map(n => String(n).padStart(2, '0')).join(':');
}
function updateControls() {
  const active = state.active;
  $('start-stop').disabled = state.busy || !state.connected || (!active && !$('mode-confirmed').checked);
  $('start-stop').classList.toggle('running', active);
  $('start-stop').innerHTML = `<i data-lucide="${state.busy ? 'loader-circle' : active ? 'square' : 'play'}"${state.busy ? ' class="spinning"' : ''}></i><span>${state.busy ? 'Working…' : active ? 'Stop queue' : 'Start queue'}</span><span class="button-shortcut">F8 TO STOP</span>`;
  $('mode-confirmed').disabled = active || state.busy;
  $('radar').classList.toggle('active', active);
  for (const id of ['poll-interval', 'team-end', 'debug-mode', 'save-settings', 'open-legacy']) $(id).disabled = active || state.busy || !state.connected;
  $('test-recognition').disabled = active || state.busy || !state.connected;
  $('settings-lock-label').textContent = active ? 'Stop session to edit' : 'Editable while stopped';
  $('connection-pill').textContent = state.connected ? '● Engine online' : 'Engine offline';
  $('engine-label').textContent = state.connected ? 'Engine connected' : 'Engine disconnected';
  $('engine-dot').style.background = state.connected ? '' : '#ff8b8b';
  if (!state.connected) { $('state-pill').textContent = 'Disconnected'; $('state-heading').textContent = 'Connection closed.'; $('state-description').textContent = 'Leave the workspace to reconnect the local engine.'; $('footer-state').textContent = 'OFFLINE'; }
  else if (active) { $('state-pill').textContent = 'Running'; $('state-heading').textContent = 'Next round, on repeat.'; $('state-description').textContent = 'Watching the game for the next queue opportunity.'; $('footer-state').textContent = 'ACTIVE'; }
  else { $('state-pill').textContent = 'Standby'; $('state-heading').textContent = 'Ready when you are.'; $('state-description').textContent = 'Choose your mode in Fortnite, then start your session.'; $('footer-state').textContent = 'STANDBY'; }
  icons();
}
function renderRecognition() {
  const list = $('template-list'); list.replaceChildren();
  const detections = new Map(state.detections.map(item => [item.id, item]));
  const templates = state.templates.length ? state.templates : state.detections;
  for (const template of templates) {
    const detection = detections.get(template.id);
    const available = template.available !== false && !state.missing.includes(template.id);
    const confirmed = Boolean(detection?.confirmed);
    const row = document.createElement('div'); row.className = 'template-row';
    const icon = document.createElement('span'); icon.className = 'template-icon'; icon.innerHTML = '<i data-lucide="scan-line"></i>';
    const name = document.createElement('div'); name.className = 'template-name'; name.textContent = template.title || readable(template.id);
    const id = document.createElement('span'); id.className = 'template-id'; id.textContent = template.id; name.append(id);
    const score = document.createElement('div'); score.className = 'template-score';
    score.textContent = typeof detection?.score === 'number' ? `${(detection.score * 100).toFixed(1)}%` : '—';
    const streak = document.createElement('small'); streak.textContent = typeof detection?.streak === 'number' ? `${detection.streak} consecutive` : detection ? 'Live scan' : 'Not scanned'; score.append(streak);
    const badge = document.createElement('span'); badge.className = `template-badge ${template.enabled === false ? '' : !available ? 'missing' : confirmed ? 'confirmed' : ''}`;
    const dot = document.createElement('span'); dot.className = 'tiny-dot'; badge.append(dot, document.createTextNode(template.enabled === false ? 'Disabled' : !available ? 'Missing file' : confirmed ? 'Confirmed' : 'Watching'));
    row.append(icon, name, score, badge); list.append(row);
  }
  if (!templates.length) { const empty = document.createElement('p'); empty.className = 'template-empty'; empty.textContent = 'No template information has been received.'; list.append(empty); }
  const confirmed = state.detections.filter(d => d.confirmed);
  $('detection-count').textContent = `${confirmed.length} confirmed`;
  const available = state.templates.filter(t => t.available !== false && !state.missing.includes(t.id)).length;
  $('template-health').textContent = state.templates.length ? `${available} / ${state.templates.length} templates available` : 'No templates reported';
  $('signal-title').textContent = confirmed.length ? confirmed.map(d => d.title || readable(d.id)).join(', ') : state.detections.length ? 'No confirmed screen cue' : 'Awaiting first scan';
  $('signal-description').textContent = state.missing.length ? `${state.missing.length} template file${state.missing.length === 1 ? '' : 's'} missing. Open Recognition for details.` : state.detections.length ? 'Recognition results from the most recent engine scan.' : 'Live cues appear while the engine scans.';
  $('recognition-summary-title').textContent = state.detections.length ? `${confirmed.length} confirmed screen cue${confirmed.length === 1 ? '' : 's'}` : 'Waiting for a scan';
  $('recognition-summary-text').textContent = state.detections.length ? 'Confidence and consecutive matches below reflect the latest local scan.' : 'Run a read-only test to inspect the current screen. No game input is sent.';
  icons();
}
function applySnapshot(data) {
  if (!data) return;
  if (typeof data.active === 'boolean') setActive(data.active);
  else if (typeof data.running === 'boolean') setActive(data.running);
  if (typeof data.rounds === 'number') { state.rounds = data.rounds; $('rounds').textContent = String(data.rounds); const unit = document.createElement('span'); unit.textContent = 'rounds'; $('rounds').append(unit); }
  if (typeof data.focused === 'boolean') $('focus-label').textContent = data.focused ? 'Fortnite focused' : 'Outside Fortnite';
  if (data.state) { $('state-pill').textContent = readable(data.state); $('footer-state').textContent = readable(data.state).toUpperCase(); }
  if (data.last_action) $('state-description').textContent = readable(data.last_action);
  if (data.error) notice(String(data.error), true);
  if (Array.isArray(data.templates)) { state.templates = data.templates; renderRecognition(); }
  if (Array.isArray(data.missing_templates)) { state.missing = data.missing_templates; renderRecognition(); }
  if (Array.isArray(data.detections)) { state.detections = data.detections; renderRecognition(); }
  else if (data.scores && typeof data.scores === 'object') {
    state.detections = Object.entries(data.scores).map(([id, score]) => ({ id, score, title: state.templates.find(template => template.id === id)?.title || readable(id), confirmed: Array.isArray(data.visible) && data.visible.includes(id) }));
    renderRecognition();
  }
  if (!state.active) {
    if (typeof data.poll_interval === 'number') $('poll-interval').value = String(data.poll_interval);
    if (typeof data.debug === 'boolean') $('debug-mode').checked = data.debug;
    if (typeof data.team_end_from_results === 'boolean') $('team-end').checked = data.team_end_from_results;
  }
}
function onEvent(event) {
  if (!event || typeof event !== 'object') return;
  switch (event.type) {
    case 'log': appendLog(event.text); break;
    case 'active': setActive(event.active); break;
    case 'status': applySnapshot(event); break;
    case 'recognition': applySnapshot(event); break;
    case 'warning': case 'error': appendLog(event.text, event.type); notice(event.text, event.type === 'error'); break;
    case 'bridge_closed': state.connected = false; setActive(false); appendLog(event.text || 'Local engine disconnected.', 'warning'); notice(event.text || 'Local engine disconnected. Leave the workspace to reconnect.', true); break;
  }
}
function setTab(name) {
  document.querySelector('.content').scrollTop = 0;
  document.querySelectorAll('.tab-panel').forEach(panel => panel.hidden = panel.id !== `tab-${name}`);
  document.querySelectorAll('[data-tab]').forEach(button => { const selected = button.dataset.tab === name; button.classList.toggle('selected', selected); if (selected) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); });
  $('page-title').textContent = { overview: 'Your session, in focus.', recognition: 'Know what the engine sees.', settings: 'Make it work your way.' }[name];
}
async function login(event) {
  event.preventDefault();
  const button = $('login-submit'); button.disabled = true; $('login-error').textContent = '';
  try {
    if (!api) throw new Error('The desktop bridge is unavailable. Open this preview with npm start.');
    const result = await api.login($('access-key').value);
    if (!result?.ok) throw new Error(result?.error || 'That access key does not match. Try again.');
    sound.play('login');
    showView('loading');
    state.unsubscribe?.(); state.unsubscribe = api.onEvent(onEvent);
    const handshake = await api.connect();
    if (handshake?.ok === false) throw new Error(handshake.error || 'Unable to connect to the local engine.');
    state.connected = true; state.admin = handshake.admin === true;
    state.templates = handshake.templates || []; state.missing = handshake.missing_templates || [];
    $('admin-notice').hidden = state.admin;
    $('version-label').textContent = handshake.version ? `v${String(handshake.version).replace(/^v/, '')}` : 'v3';
    if (handshake.config_warning) notice(String(handshake.config_warning));
    showView('dashboard'); document.querySelector('.content').scrollTop = 0; updateControls(); renderRecognition();
    appendLog('Local engine connected. Your session is stopped.');
    try { applySnapshot(await command('snapshot')); } catch (error) { appendLog(errorText(error), 'warning'); }
  } catch (error) {
    state.connected = false; state.unsubscribe?.(); state.unsubscribe = null;
    showView('login'); $('login-error').textContent = errorText(error); sound.play('error');
    const card = document.querySelector('.login-card'); card.classList.remove('shake'); void card.offsetWidth; card.classList.add('shake'); $('access-key').focus();
  } finally { button.disabled = false; }
}
$('login-form').addEventListener('submit', login);
$('reveal-key').addEventListener('click', () => { const visible = $('access-key').type === 'password'; $('access-key').type = visible ? 'text' : 'password'; $('reveal-key').setAttribute('aria-label', visible ? 'Hide access key' : 'Show access key'); $('reveal-key').setAttribute('aria-pressed', String(visible)); $('reveal-key').innerHTML = `<i data-lucide="${visible ? 'eye-off' : 'eye'}"></i>`; icons(); });
$('minimize').addEventListener('click', () => api?.minimize());
$('close').addEventListener('click', () => api?.close());
$('dismiss-notice').addEventListener('click', () => notice(''));
$('mode-confirmed').addEventListener('change', updateControls);
document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => setTab(button.dataset.tab)));
document.querySelectorAll('[data-go-tab]').forEach(button => button.addEventListener('click', () => setTab(button.dataset.goTab)));
$('start-stop').addEventListener('click', async () => {
  if (state.busy) return;
  const stopping = state.active;
  state.busy = true; updateControls(); notice('');
  try { const result = await command(stopping ? 'stop' : 'start', stopping ? {} : { mode_confirmed: $('mode-confirmed').checked }); setActive(stopping ? false : result.active !== false); applySnapshot(result); }
  catch (error) { notice(errorText(error), true); appendLog(errorText(error), 'error'); }
  finally { state.busy = false; updateControls(); }
});
$('test-recognition').addEventListener('click', async () => {
  state.busy = true; updateControls(); $('test-recognition').innerHTML = '<i data-lucide="loader-circle" class="spinning"></i><span>Scanning…</span>'; icons();
  try { const result = await command('test'); applySnapshot(result); appendLog('Read-only recognition test completed.'); }
  catch (error) { notice(errorText(error), true); appendLog(errorText(error), 'error'); }
  finally { state.busy = false; $('test-recognition').innerHTML = '<i data-lucide="scan-line"></i><span>Test recognition</span>'; updateControls(); }
});
$('settings-form').addEventListener('submit', async event => {
  event.preventDefault(); if (state.active || state.busy) return;
  const interval = Number($('poll-interval').value);
  if (!Number.isFinite(interval) || interval < .1 || interval > 5) { $('settings-message').textContent = 'Choose an interval between 0.1 and 5 seconds.'; return; }
  state.busy = true; updateControls(); $('settings-message').textContent = 'Applying settings…';
  try { await command('set_options', { poll_interval: interval, team_end_from_results: $('team-end').checked }); await command('set_debug', { enabled: $('debug-mode').checked }); applySnapshot(await command('snapshot')); $('settings-message').textContent = 'Settings applied to the local engine.'; appendLog('Engine settings updated.'); }
  catch (error) { $('settings-message').textContent = errorText(error); notice(errorText(error), true); }
  finally { state.busy = false; updateControls(); }
});
$('open-legacy').addEventListener('click', async () => {
  if (state.active || state.busy) return;
  try { const result = await api.openLegacy(); if (result?.ok === false) throw new Error(result.error); state.connected = false; setActive(false); notice('Separate capture app opened. Close it after calibration, then leave this workspace and sign in again. Closing Electron does not close that app.'); }
  catch (error) { notice(errorText(error), true); }
});
$('open-logs').addEventListener('click', async () => { try { const result = await api.openLogs(); if (result?.ok === false) throw new Error(result.error); } catch (error) { notice(errorText(error), true); } });
$('clear-log').addEventListener('click', () => { state.logs = []; $('activity-log').replaceChildren(); const empty = document.createElement('div'); empty.className = 'log-empty'; empty.textContent = 'Activity feed cleared. New events will appear here.'; $('activity-log').append(empty); $('event-count').textContent = '0 events'; });
$('logout').addEventListener('click', async () => {
  if (state.busy) return;
  state.busy = true; updateControls();
  try { const result = await api.logout(); if (result?.ok === false) throw new Error(result.error); state.unsubscribe?.(); state.unsubscribe = null; state.connected = false; setActive(false); state.elapsed = 0; state.detections = []; state.templates = []; state.missing = []; state.rounds = 0; $('rounds').innerHTML = '0<span>rounds</span>'; $('focus-label').textContent = 'Not reported'; $('clear-log').click(); $('mode-confirmed').checked = false; $('access-key').value = ''; $('login-error').textContent = ''; notice(''); setTab('overview'); showView('login'); $('access-key').focus(); }
  catch (error) { notice(errorText(error), true); }
  finally { state.busy = false; updateControls(); }
});
setInterval(updateTimer, 1000);
icons();


// Sounds are synthesized locally and initialized only by a user interaction.
document.addEventListener('pointerdown', event => {
  const target = event.target.closest('button, label.toggle, input[type="checkbox"]');
  if (event.button === 0 && target && !target.disabled && target.id !== 'sound-toggle') sound.play('click');
});
$('access-key').addEventListener('input', () => sound.play('type'));
$('sound-toggle').addEventListener('click', () => {
  sound.setMuted(!sound.isMuted());
  try { localStorage.setItem('fortnite-ui-muted', String(sound.isMuted())); } catch {}
  updateSoundButton();
  if (!sound.isMuted()) sound.play('click');
});
updateSoundButton();
