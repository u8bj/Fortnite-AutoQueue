const { test } = require('node:test');
const assert = require('node:assert/strict');
const { validKey, allowedCommand } = require('../access.cjs');

test('local key accepts u8bj and rejects incorrect or malformed input', () => {
  assert.equal(validKey('u8bj'), true);
  assert.equal(validKey(' u8bj '), true);
  for (const key of ['', 'wrong', 'U8BJ', null, {}, ['u8bj']]) assert.equal(validKey(key), false);
});
test('bridge exposes only the supported queue command vocabulary', () => {
  for (const name of ['start', 'stop', 'test', 'snapshot', 'set_debug', 'set_options']) assert.equal(allowedCommand(name), true);
  for (const name of ['exec', 'replay', 'shell', '__proto__', null]) assert.equal(allowedCommand(name), false);
});
