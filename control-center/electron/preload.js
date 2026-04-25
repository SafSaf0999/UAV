const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  version: process.versions.electron
})
