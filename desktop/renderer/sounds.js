(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.QueueSound = factory();
})(globalThis, function () {
  'use strict';
  function createSoundEngine(contextFactory = () => new globalThis.AudioContext()) {
    let context, master, muted = false, lastTyping = 0;
    const patterns = {
      click: [[780, 0, .045, 'sine', .16]],
      type: [[1060, 0, .026, 'sine', .12]],
      login: [[440, 0, .19, 'sine', .22], [554.37, .075, .19, 'sine', .20],
              [659.25, .15, .22, 'sine', .18], [880, .225, .28, 'sine', .14]],
      error: [[220, 0, .11, 'triangle', .14], [174.61, .1, .16, 'triangle', .12]]
    };
    return {
      setMuted(value) { muted = Boolean(value); if (master && context) master.gain.setValueAtTime(muted ? 0 : .22, context.currentTime); },
      isMuted() { return muted; },
      async play(name) {
        if (muted || !Object.hasOwn(patterns, name)) return false;
        if (name === 'type') {
          const now = Date.now();
          if (now - lastTyping < 35) return false;
          lastTyping = now;
        }
        try {
          if (!context) {
            context = contextFactory();
            master = context.createGain();
            master.gain.setValueAtTime(.22, context.currentTime);
            master.connect(context.destination);
          }
          if (context.state === 'suspended') await context.resume();
          if (muted || context.state === 'closed') return false;
          const start = context.currentTime + .005;
          for (const [frequency, offset, duration, type, volume] of patterns[name]) {
            const oscillator = context.createOscillator();
            const envelope = context.createGain();
            oscillator.type = type;
            oscillator.frequency.setValueAtTime(frequency, start + offset);
            envelope.gain.setValueAtTime(.0001, start + offset);
            envelope.gain.exponentialRampToValueAtTime(volume, start + offset + .006);
            envelope.gain.exponentialRampToValueAtTime(.0001, start + offset + duration);
            oscillator.connect(envelope); envelope.connect(master);
            oscillator.onended = () => { oscillator.disconnect(); envelope.disconnect(); };
            oscillator.start(start + offset); oscillator.stop(start + offset + duration + .01);
          }
          return true;
        } catch { return false; }
      }
    };
  }
  return { createSoundEngine };
});
