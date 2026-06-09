/**
 * Lexara AI — PWA & Platform Integration
 * Handles Service Worker registration, install prompts, offline tracking, and native platform bridges.
 */

(function () {
  'use strict';

  // Global variables
  let deferredPrompt = null;
  const isCapacitor = !!window.Capacitor;
  const isElectron = navigator.userAgent.toLowerCase().includes('electron');

  // Register Service Worker for PWA
  if ('serviceWorker' in navigator && !isElectron) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then((registration) => {
          console.log('[PWA] Service Worker registered with scope:', registration.scope);
        })
        .catch((error) => {
          console.error('[PWA] Service Worker registration failed:', error);
        });
    });
  }

  // Intercept the browser's install prompt
  window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing on mobile
    e.preventDefault();
    // Stash the event so it can be triggered later
    deferredPrompt = e;
    
    // Show a custom installation prompt to the user
    showInstallPromotion();
  });

  // Log when PWA is successfully installed
  window.addEventListener('appinstalled', (evt) => {
    console.log('[PWA] Lexara AI was successfully installed!');
    deferredPrompt = null;
    showPwaNotification('✅ Lexara AI installed successfully!', 'success');
  });

  // Track online / offline connectivity status
  window.addEventListener('online', () => {
    showPwaNotification('🌐 Connection restored. Back online!', 'success');
  });

  window.addEventListener('offline', () => {
    showPwaNotification('📡 You are currently offline. Working from cached database.', 'warning');
  });

  // Helper function to show notifications using app toast or custom fallback
  function showPwaNotification(msg, type = 'info') {
    if (typeof window.toast === 'function') {
      window.toast(msg, type);
    } else {
      console.log(`[PWA Notification] [${type}] ${msg}`);
      let container = document.getElementById('toastContainer');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
      }
      
      const t = document.createElement('div');
      t.className = `toast ${type}`;
      t.style.padding = '10px 16px';
      t.style.background = type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : type === 'error' ? '#ef4444' : '#8b5cf6';
      t.style.color = '#fff';
      t.style.borderRadius = '8px';
      t.style.marginTop = '8px';
      t.style.fontSize = '0.85rem';
      t.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
      t.style.display = 'flex';
      t.style.alignItems = 'center';
      t.style.justifyContent = 'space-between';
      t.style.pointerEvents = 'auto';
      t.style.animation = 'toastIn 0.3s ease';
      
      const icon = type === 'success' ? '✅' : type === 'warning' ? '⚠️' : type === 'error' ? '❌' : 'ℹ️';
      t.innerHTML = `<span style="margin-right:8px">${icon}</span><span style="flex:1">${msg}</span><button style="background:none;border:none;color:#fff;cursor:pointer;margin-left:10px" onclick="this.parentElement.remove()">✕</button>`;
      
      container.appendChild(t);
      setTimeout(() => {
        t.style.opacity = '0';
        t.style.transition = 'opacity 0.25s ease';
        setTimeout(() => t.remove(), 250);
      }, 4000);
    }
  }

  // Display custom install promotion banner
  function showInstallPromotion() {
    // Check if promotional banner already exists
    if (document.getElementById('pwa-install-banner')) return;

    let banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.style.position = 'fixed';
    banner.style.bottom = '80px';
    banner.style.right = '20px';
    banner.style.background = 'rgba(30, 41, 59, 0.95)';
    banner.style.backdropFilter = 'blur(8px)';
    banner.style.border = '1px solid rgba(139, 92, 246, 0.4)';
    banner.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)';
    banner.style.borderRadius = '12px';
    banner.style.padding = '16px';
    banner.style.zIndex = '9999';
    banner.style.maxWidth = '320px';
    banner.style.display = 'flex';
    banner.style.flexDirection = 'column';
    banner.style.gap = '12px';
    banner.style.color = '#f8fafc';
    banner.style.animation = 'toastIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
    banner.style.fontFamily = 'system-ui, -apple-system, sans-serif';

    banner.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:40px;height:40px;border-radius:8px;background:linear-gradient(135deg,#8B5CF6,#22D3EE);display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:1.2rem;color:#fff">L</div>
        <div>
          <div style="font-weight:600;font-size:0.9rem">Lexara AI Desktop App</div>
          <div style="font-size:0.75rem;color:#94a3b8">Install on your device for instant offline access</div>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:8px">
        <button id="pwa-install-close" style="background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:0.8rem;padding:6px 12px;border-radius:6px;transition:color 0.2s">Dismiss</button>
        <button id="pwa-install-action" style="background:linear-gradient(135deg,#7c3aed,#8b5cf6);border:none;color:#fff;cursor:pointer;font-weight:600;font-size:0.8rem;padding:6px 14px;border-radius:6px;box-shadow:0 4px 10px rgba(124,58,237,0.3)">Install</button>
      </div>
    `;

    document.body.appendChild(banner);

    // Bind event listeners
    document.getElementById('pwa-install-close').addEventListener('click', () => {
      banner.style.opacity = '0';
      banner.style.transform = 'translateY(10px)';
      banner.style.transition = 'all 0.2s ease';
      setTimeout(() => banner.remove(), 200);
    });

    document.getElementById('pwa-install-action').addEventListener('click', async () => {
      if (!deferredPrompt) return;
      banner.remove();
      // Show the install prompt
      deferredPrompt.prompt();
      // Wait for the user to respond to the prompt
      const { outcome } = await deferredPrompt.userChoice;
      console.log(`[PWA] Install choice outcome: ${outcome}`);
      deferredPrompt = null;
    });
  }

  // Capacitor platform setup
  if (isCapacitor) {
    console.log('[Mobile] Running within Capacitor WebView');
    
    // Inject custom styling tweaks for mobile apps (e.g. status bar padding)
    const style = document.createElement('style');
    style.innerHTML = `
      body {
        padding-top: env(safe-area-inset-top, 20px) !important;
        padding-bottom: env(safe-area-inset-bottom, 20px) !important;
      }
      .mob-topbar {
        padding-top: calc(env(safe-area-inset-top, 0px) + 8px) !important;
      }
    `;
    document.head.appendChild(style);

    // Wire up connectivity monitoring via Capacitor Network plugin if available
    if (window.Capacitor.Plugins && window.Capacitor.Plugins.Network) {
      const Network = window.Capacitor.Plugins.Network;
      Network.addListener('networkStatusChange', (status) => {
        if (status.connected) {
          showPwaNotification('🌐 Native connection restored!', 'success');
        } else {
          showPwaNotification('📡 Device is offline. Check your native connection.', 'warning');
        }
      });
    }

    // Set up standard camera scanning helpers for mobile scanner button
    window.startMobileDocumentScan = async function() {
      if (!window.Capacitor.Plugins || !window.Capacitor.Plugins.Camera) {
        showPwaNotification('Camera plugin not loaded', 'error');
        return null;
      }

      const Camera = window.Capacitor.Plugins.Camera;
      try {
        const image = await Camera.getPhoto({
          quality: 90,
          allowEditing: true,
          resultType: 'dataUrl', // Base64 Data URL
          source: 'CAMERA'
        });
        
        return image.dataUrl;
      } catch (err) {
        console.error('[Capacitor Camera] Capture failed:', err);
        showPwaNotification('Camera capture cancelled or failed', 'warning');
        return null;
      }
    };
  }

  // Electron platform setup
  if (isElectron) {
    console.log('[Desktop] Running within Electron Wrapper');
    
    // Setup file drag-over indicators
    window.addEventListener('dragover', (e) => e.preventDefault(), false);
    window.addEventListener('drop', (e) => e.preventDefault(), false);
  }

})();
