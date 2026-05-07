/**
 * Soil Mineralogy AI - Preload Script
 * =====================================
 * Bridge seguro entre o processo Electron e a webpage.
 * Expõe apenas as APIs necessárias via contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  selectFiles: () => ipcRenderer.invoke('select-files'),
  openDocsFolder: () => ipcRenderer.invoke('open-docs-folder'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
});
