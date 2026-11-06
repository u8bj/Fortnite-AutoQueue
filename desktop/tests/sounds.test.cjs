const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createSoundEngine } = require('../renderer/sounds.js');

function audio() {
  let oscillators = 0;
  const parameter = () => ({ setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} });
  const context = { currentTime: 1, state: 'running', destination: {},
    createGain: () => ({ gain: parameter(), connect() {} }),
    createOscillator: () => { oscillators++; return { frequency: parameter(), connect() {}, start() {}, stop() {} }; }
  };
  return { context, count: () => oscillators };
}
test('sound is lazy and muting prevents audio allocation and playback', async () => {
  let created = 0;
  const fixture = audio();
  const sound = createSoundEngine(() => { created++; return fixture.context; });
  assert.equal(created, 0);
  sound.setMuted(true);
  assert.equal(await sound.play('login'), false);
  assert.equal(created, 0);
  sound.setMuted(false);
  assert.equal(await sound.play('click'), true);
  assert.equal(created, 1);
  assert.equal(fixture.count(), 1);
});
test('login chime uses multiple notes and unsupported sounds are rejected', async () => {
  const fixture = audio();
  const sound = createSoundEngine(() => fixture.context);
  assert.equal(await sound.play('unknown'), false);
  assert.equal(await sound.play('login'), true);
  assert.equal(fixture.count(), 4);
  assert.equal(await sound.play('error'), true);
  assert.equal(fixture.count(), 6);
});
test('missing audio hardware or browser denial never interrupts the interface', async () => {
  const sound = createSoundEngine(() => { throw new Error('Audio unavailable'); });
  assert.equal(await sound.play('type'), false);
});
