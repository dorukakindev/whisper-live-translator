/* Depolama izni/kotasi arayuzun acilisini durdurmasin. */
(function () {
    'use strict';
    const fallback = new Map();
    let warned = false;
    function warn() {
        if (warned) return;
        warned = true;
        console.warn('Kalici ayarlar kullanilamiyor; degisiklikler bu pencere kapaninca kaybolabilir.');
        const show = () => {
            if (typeof window.showAlert === 'function') window.showAlert('Kalıcı ayarlar kullanılamıyor; değişiklikler yalnız bu pencerede tutuluyor.', 'warning');
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', show, { once: true });
        else show();
    }
    window.whisperStorage = {
        getItem(key) {
            if (fallback.has(key)) return fallback.get(key);
            try { return window.localStorage.getItem(key); }
            catch (_) { warn(); return null; }
        },
        setItem(key, value) {
            value = String(value);
            try { window.localStorage.setItem(key, value); fallback.delete(key); return true; }
            catch (_) { fallback.set(key, value); warn(); return false; }
        },
        removeItem(key) {
            try { window.localStorage.removeItem(key); fallback.delete(key); return true; }
            catch (_) { fallback.set(key, null); warn(); return false; }
        }
    };
})();
