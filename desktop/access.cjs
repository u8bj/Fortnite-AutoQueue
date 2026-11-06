'use strict';
// This shared local key is a presentation gate, not an account/authentication service.
exports.validKey = value => typeof value === 'string' && value.trim() === 'u8bj';
const commands = new Set(['start', 'stop', 'test', 'snapshot', 'set_debug', 'set_options']);
exports.allowedCommand = value => typeof value === 'string' && commands.has(value);
