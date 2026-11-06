'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('queue', {
  login: key => ipcRenderer.invoke('queue:login', key),
  connect: () => ipcRenderer.invoke('queue:connect'),
  command: (name, payload = {}) => ipcRenderer.invoke('queue:command', name, payload),
  onEvent: callback => {
    const listener = (_, value) => callback(value);
    ipcRenderer.on('queue:event', listener);
    return () => ipcRenderer.removeListener('queue:event', listener);
  },
  minimize: () => ipcRenderer.invoke('window:minimize'),
  close: () => ipcRenderer.invoke('window:close'),
  openLogs: () => ipcRenderer.invoke('queue:logs'),
  openLegacy: () => ipcRenderer.invoke('queue:legacy'),
  logout: () => ipcRenderer.invoke('queue:logout')
});
