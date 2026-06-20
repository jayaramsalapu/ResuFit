// PWA Helper Script
// Handles Service Worker Registration and Install Banner Prompt

// 1. Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then((reg) => {
        console.log('[PWA] Service Worker registered with scope:', reg.scope);
      })
      .catch((err) => {
        console.error('[PWA] Service Worker registration failed:', err);
      });
  });
}

// 2. Install Banner Prompt Implementation
let deferredPrompt = null;

// Track if install banner is active
window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent the default browser mini-infobar from showing
  e.preventDefault();
  // Stash the event so it can be triggered later.
  deferredPrompt = e;
  
  // Show the install banner if not dismissed in the last 24 hours
  const dismissedTime = localStorage.getItem('resufit_pwa_dismissed');
  const now = Date.now();
  
  // If never dismissed, or dismissed more than 24 hours ago
  if (!dismissedTime || (now - parseInt(dismissedTime) > 24 * 60 * 60 * 1000)) {
    showInstallBanner();
  }
});

function showInstallBanner() {
  // Check if banner already exists
  if (document.getElementById('pwa-install-banner')) return;

  // Create banner container
  const banner = document.createElement('div');
  banner.id = 'pwa-install-banner';
  
  // Styling
  banner.style.position = 'fixed';
  banner.style.bottom = '24px';
  banner.style.left = '50%';
  banner.style.transform = 'translate(-50%, 100px)'; // start offscreen
  banner.style.transition = 'transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s';
  banner.style.opacity = '0';
  banner.style.background = '#ffffff';
  banner.style.border = '1px solid rgba(0,0,0,0.06)';
  banner.style.boxShadow = '0 12px 30px rgba(0,0,0,0.15)';
  banner.style.borderRadius = '16px';
  banner.style.padding = '16px 20px';
  banner.style.display = 'flex';
  banner.style.alignItems = 'center';
  banner.style.justifyContent = 'space-between';
  banner.style.gap = '20px';
  banner.style.zIndex = '99999';
  banner.style.width = 'calc(100% - 32px)';
  banner.style.maxWidth = '460px';
  banner.style.fontFamily = "'DM Sans', sans-serif";

  // HTML content
  banner.innerHTML = `
    <div style="display:flex; align-items:center; gap:12px; text-align:left;">
      <img src="/static/icons/icon-192.png" alt="ResuFit Logo" style="width:40px; height:40px; border-radius:8px; flex-shrink:0;">
      <div>
        <div style="font-weight:700; font-size:14px; color:#1F1F1F;">Install ResuFit</div>
        <div style="font-size:12px; color:#444746; margin-top:2px;">Get quick access & offline support!</div>
      </div>
    </div>
    <div style="display:flex; align-items:center; gap:8px;">
      <button id="pwa-btn-later" style="background:transparent; border:none; color:#444746; font-size:13px; font-weight:600; padding:8px 12px; cursor:pointer; border-radius:8px; font-family:inherit;">Later</button>
      <button id="pwa-btn-install" style="background:#0B57D0; border:none; color:#ffffff; font-size:13px; font-weight:600; padding:8px 16px; cursor:pointer; border-radius:100px; font-family:inherit; box-shadow:0 2px 6px rgba(11,87,208,0.25);">Install</button>
    </div>
  `;

  document.body.appendChild(banner);

  // Trigger enter animation
  setTimeout(() => {
    banner.style.transform = 'translate(-50%, 0)';
    banner.style.opacity = '1';
  }, 100);

  // Install button handler
  document.getElementById('pwa-btn-install').addEventListener('click', () => {
    if (!deferredPrompt) return;
    // Show the install prompt
    deferredPrompt.prompt();
    // Wait for the user to respond to the prompt
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('[PWA] User accepted the install prompt');
      } else {
        console.log('[PWA] User dismissed the install prompt');
      }
      deferredPrompt = null;
      hideInstallBanner();
    });
  });

  // Later button handler
  document.getElementById('pwa-btn-later').addEventListener('click', () => {
    localStorage.setItem('resufit_pwa_dismissed', Date.now().toString());
    hideInstallBanner();
  });
}

function hideInstallBanner() {
  const banner = document.getElementById('pwa-install-banner');
  if (banner) {
    banner.style.transform = 'translate(-50%, 100px)';
    banner.style.opacity = '0';
    setTimeout(() => {
      banner.remove();
    }, 400);
  }
}

// Log successful installation
window.addEventListener('appinstalled', (evt) => {
  console.log('[PWA] ResuFit was successfully installed!');
  hideInstallBanner();
});
