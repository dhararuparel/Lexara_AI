// Lexara AI Desktop Preload Script
// Used to securely bridge APIs if needed in the future

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ElectronAPI', {
  platform: process.platform,
  // Future native callbacks can be defined here
});
