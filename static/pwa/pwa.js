(() => {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
        .catch((error) => console.error('PWA service worker registration failed:', error));
    });
  }

  const banner = document.getElementById('pwaInstallBanner');
  const installButton = document.getElementById('pwaInstallButton');
  const dismissButton = document.getElementById('pwaInstallDismiss');
  const iosHelp = document.getElementById('pwaIosHelp');
  let deferredPrompt = null;

  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  const dismissed = localStorage.getItem('pwa-install-dismissed') === '1';
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);

  if (isStandalone || dismissed || !banner) return;

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;
    banner.hidden = false;
    installButton.hidden = false;
    if (iosHelp) iosHelp.hidden = true;
  });

  if (isIos) {
    banner.hidden = false;
    installButton.hidden = true;
    if (iosHelp) iosHelp.hidden = false;
  }

  installButton?.addEventListener('click', async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    banner.hidden = true;
  });

  dismissButton?.addEventListener('click', () => {
    localStorage.setItem('pwa-install-dismissed', '1');
    banner.hidden = true;
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    banner.hidden = true;
  });
})();
