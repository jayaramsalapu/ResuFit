/* Shared Auth Modal & State Gating for ResuFit */

(function() {
    // Ensure window.APP_AUTH exists
    window.APP_AUTH = window.APP_AUTH || { authenticated: false, email: '' };

    // IndexedDB Storage Helper for Pending File Preservations
    window.ResuFitStorage = {
        async setPendingFile(file, actionType, extraData = {}) {
            if (!file) return;
            return new Promise((resolve, reject) => {
                const req = indexedDB.open('ResuFitPendingDB', 1);
                req.onupgradeneeded = (e) => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains('pendingActions')) {
                        db.createObjectStore('pendingActions', { keyPath: 'id' });
                    }
                };
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    const tx = db.transaction('pendingActions', 'readwrite');
                    const store = tx.objectStore('pendingActions');
                    store.put({
                        id: 'pending_file',
                        file: file,
                        fileName: file.name,
                        fileType: file.type,
                        actionType: actionType,
                        extraData: extraData,
                        timestamp: Date.now()
                    });
                    tx.oncomplete = () => resolve();
                    tx.onerror = () => reject(tx.error);
                };
                req.onerror = () => reject(req.error);
            });
        },
        async getPendingFile() {
            return new Promise((resolve) => {
                const req = indexedDB.open('ResuFitPendingDB', 1);
                req.onupgradeneeded = (e) => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains('pendingActions')) {
                        db.createObjectStore('pendingActions', { keyPath: 'id' });
                    }
                };
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains('pendingActions')) {
                        resolve(null);
                        return;
                    }
                    const tx = db.transaction('pendingActions', 'readonly');
                    const store = tx.objectStore('pendingActions');
                    const getReq = store.get('pending_file');
                    getReq.onsuccess = () => resolve(getReq.result || null);
                    getReq.onerror = () => resolve(null);
                };
                req.onerror = () => resolve(null);
            });
        },
        async clearPendingFile() {
            return new Promise((resolve) => {
                const req = indexedDB.open('ResuFitPendingDB', 1);
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    if (db.objectStoreNames.contains('pendingActions')) {
                        const tx = db.transaction('pendingActions', 'readwrite');
                        tx.objectStore('pendingActions').delete('pending_file');
                        tx.oncomplete = () => resolve();
                    } else resolve();
                };
                req.onerror = () => resolve();
            });
        }
    };

    // Inject CSS for auth modal if not already present
    if (!document.getElementById('auth-modal-styles')) {
        const style = document.createElement('style');
        style.id = 'auth-modal-styles';
        style.innerHTML = `
            .resufit-modal-overlay {
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                background: rgba(0, 0, 0, 0.55);
                backdrop-filter: blur(8px);
                z-index: 99999;
                display: flex; align-items: center; justify-content: center;
                opacity: 0; transition: opacity 0.25s ease;
            }
            .resufit-modal-overlay.active { opacity: 1; }
            .resufit-modal-card {
                background: #FFFFFF;
                border-radius: 24px;
                padding: 32px;
                width: 90%; max-width: 440px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
                transform: scale(0.92); transition: transform 0.25s ease;
                font-family: 'DM Sans', system-ui, -apple-system, sans-serif;
                position: relative;
                color: #1F1F1F;
            }
            .resufit-modal-overlay.active .resufit-modal-card { transform: scale(1); }
            .resufit-modal-close {
                position: absolute; top: 16px; right: 20px;
                background: none; border: none; font-size: 24px;
                cursor: pointer; color: #666; line-height: 1;
            }
            .resufit-modal-title { font-size: 22px; font-weight: 700; color: #1F1F1F; margin-bottom: 6px; }
            .resufit-modal-subtitle { font-size: 14px; color: #555; margin-bottom: 20px; }
            .resufit-modal-tabs { display: flex; gap: 12px; margin-bottom: 20px; border-bottom: 1px solid #eee; }
            .resufit-modal-tab {
                padding: 8px 16px; border: none; background: none; font-weight: 600; cursor: pointer;
                color: #666; border-bottom: 2px solid transparent; font-size: 14px;
            }
            .resufit-modal-tab.active { color: #0B57D0; border-bottom-color: #0B57D0; }
            .resufit-form-group { margin-bottom: 16px; text-align: left; }
            .resufit-form-group label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #333; }
            .resufit-form-input {
                width: 100%; padding: 12px; border-radius: 12px; border: 1px solid #ccc;
                font-size: 14px; box-sizing: border-box; outline: none;
            }
            .resufit-form-input:focus { border-color: #0B57D0; box-shadow: 0 0 0 3px rgba(11,87,208,0.15); }
            .resufit-btn-primary {
                width: 100%; padding: 12px; background: #0B57D0; color: #fff; border: none;
                border-radius: 12px; font-weight: 700; font-size: 15px; cursor: pointer; margin-top: 8px;
            }
            .resufit-btn-primary:hover { background: #0842A0; }
            .resufit-btn-google {
                width: 100%; padding: 12px; background: #fff; color: #333; border: 1px solid #ccc;
                border-radius: 12px; font-weight: 600; font-size: 14px; cursor: pointer; margin-top: 12px;
                display: flex; align-items: center; justify-content: center; gap: 10px;
            }
            .resufit-btn-google:hover { background: #f8f9fa; }
            .resufit-modal-error {
                background: #ffebe9; color: #d93025; padding: 10px; border-radius: 8px;
                font-size: 13px; margin-bottom: 14px; display: none; text-align: left;
            }
        `;
        document.head.appendChild(style);
    }

    let pendingCallback = null;

    window.requireAuth = function(onAuthenticatedCallback) {
        if (window.APP_AUTH && window.APP_AUTH.authenticated) {
            if (typeof onAuthenticatedCallback === 'function') {
                onAuthenticatedCallback();
            }
            return true;
        }

        pendingCallback = onAuthenticatedCallback;
        showAuthModal();
        return false;
    };

    function showAuthModal() {
        let modal = document.getElementById('resufit-auth-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'resufit-auth-modal';
            modal.className = 'resufit-modal-overlay';
            modal.innerHTML = `
                <div class="resufit-modal-card">
                    <button class="resufit-modal-close" onclick="window.closeAuthModal()">&times;</button>
                    <div class="resufit-modal-title">Sign In Required</div>
                    <div class="resufit-modal-subtitle">Please log in to continue your action.</div>
                    
                    <div id="modal-error" class="resufit-modal-error"></div>

                    <div class="resufit-modal-tabs">
                        <button class="resufit-modal-tab active" id="tab-login-btn" onclick="switchAuthTab('login')">Sign In</button>
                        <button class="resufit-modal-tab" id="tab-reg-btn" onclick="switchAuthTab('register')">Create Account</button>
                    </div>

                    <form id="resufit-modal-form" onsubmit="handleAuthModalSubmit(event)">
                        <div class="resufit-form-group">
                            <label>Email address</label>
                            <input type="email" id="modal-email" class="resufit-form-input" placeholder="name@example.com" required>
                        </div>
                        <div class="resufit-form-group">
                            <label>Password</label>
                            <input type="password" id="modal-password" class="resufit-form-input" placeholder="••••••••" required>
                        </div>
                        <div class="resufit-form-group" id="modal-confirm-group" style="display:none;">
                            <label>Re-enter Password</label>
                            <input type="password" id="modal-confirm-password" class="resufit-form-input" placeholder="••••••••">
                        </div>
                        <button type="submit" class="resufit-btn-primary" id="modal-submit-btn">Sign In</button>
                    </form>

                    <button type="button" class="resufit-btn-google" onclick="window.handleGoogleLoginClick()">
                        <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                        Continue with Google
                    </button>
                </div>
            `;
            document.body.appendChild(modal);
        }
        setTimeout(() => modal.classList.add('active'), 10);
    }

    window.closeAuthModal = function() {
        const modal = document.getElementById('resufit-auth-modal');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 250);
        }
    };

    window.handleGoogleLoginClick = async function() {
        const fileInput = document.querySelector('input[type="file"]');
        if (fileInput && fileInput.files && fileInput.files.length > 0) {
            try {
                await window.ResuFitStorage.setPendingFile(fileInput.files[0], window.location.pathname);
            } catch (e) {
                console.warn("Could not preserve file before Google auth redirect", e);
            }
        }
        const currentPath = window.location.pathname + window.location.search;
        window.location.href = '/google/login?next=' + encodeURIComponent(currentPath);
    };

    let activeAuthTab = 'login';
    window.switchAuthTab = function(tab) {
        activeAuthTab = tab;
        const confirmGrp = document.getElementById('modal-confirm-group');
        const submitBtn = document.getElementById('modal-submit-btn');
        const errDiv = document.getElementById('modal-error');
        if (errDiv) errDiv.style.display = 'none';

        if (tab === 'register') {
            document.getElementById('tab-reg-btn').classList.add('active');
            document.getElementById('tab-login-btn').classList.remove('active');
            confirmGrp.style.display = 'block';
            submitBtn.textContent = 'Create Account';
        } else {
            document.getElementById('tab-login-btn').classList.add('active');
            document.getElementById('tab-reg-btn').classList.remove('active');
            confirmGrp.style.display = 'none';
            submitBtn.textContent = 'Sign In';
        }
    };

    window.handleAuthModalSubmit = async function(e) {
        e.preventDefault();
        const errDiv = document.getElementById('modal-error');
        if (errDiv) errDiv.style.display = 'none';

        const email = document.getElementById('modal-email').value;
        const password = document.getElementById('modal-password').value;
        const confirmPassword = document.getElementById('modal-confirm-password').value;

        const endpoint = activeAuthTab === 'register' ? '/api/register' : '/api/login';
        const payload = activeAuthTab === 'register' 
            ? { email, password, confirm_password: confirmPassword }
            : { email, password };

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok && data.success) {
                window.APP_AUTH.authenticated = true;
                window.APP_AUTH.email = data.email || email;
                window.closeAuthModal();

                if (typeof pendingCallback === 'function') {
                    const cb = pendingCallback;
                    pendingCallback = null;
                    cb();
                }
            } else {
                if (errDiv) {
                    errDiv.textContent = data.error || 'Authentication failed';
                    errDiv.style.display = 'block';
                }
            }
        } catch(err) {
            if (errDiv) {
                errDiv.textContent = 'Network error. Please try again.';
                errDiv.style.display = 'block';
            }
        }
    };
})();
