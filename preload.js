const { contextBridge } = require('electron');

// Not: window-minimize/maximize/close kaldirildi -- main process'te ipcMain.handle
// karsiligi yoktu ve UI bunlari hic cagirmiyordu (native baslik cubugu kullaniliyor).
contextBridge.exposeInMainWorld('electronAPI', {
    isDev: (process.env.DEBUG || '').trim() === '*',
    platform: process.platform
});
