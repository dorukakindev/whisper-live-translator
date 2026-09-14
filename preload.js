const { contextBridge, ipcRenderer } = require('electron');

// Not: window-minimize/maximize/close kaldirildi -- main process'te ipcMain.handle
// karsiligi yoktu ve UI bunlari hic cagirmiyordu (native baslik cubugu kullaniliyor).
contextBridge.exposeInMainWorld('electronAPI', {
    isDev: (process.env.DEBUG || '').trim() === '*',
    platform: process.platform,
    overlayControl: action => ipcRenderer.invoke('overlay-control', action),
    onOverlayState: callback => {
        const listener = (_event, state) => callback(state);
        ipcRenderer.on('overlay-state', listener);
        return () => ipcRenderer.removeListener('overlay-state', listener);
    }
});
