/* owner-login.js — Email/password login + MFA verification */

let _mfaToken = '';
let _mfaEmail = '';

document.addEventListener('DOMContentLoaded', () => {
  // Login form
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.style.display = 'none';

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) { showError(errEl, 'Enter email and password'); return; }

    try {
      const r = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await r.json();

      if (!r.ok) { showError(errEl, data.detail || 'Login failed'); return; }

      if (data.mfa_required) {
        // Show MFA step
        _mfaToken = data.mfa_token;
        _mfaEmail = data.email;
        document.getElementById('login-card').classList.add('hidden');
        document.getElementById('mfa-card').classList.remove('hidden');
        document.getElementById('mfa-code').focus();
        return;
      }

      window.location.href = '/owner';
    } catch (err) {
      showError(errEl, 'Connection error');
    }
  });

  // MFA form
  document.getElementById('mfa-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('mfa-error');
    errEl.style.display = 'none';

    const code = document.getElementById('mfa-code').value.trim();
    if (!code || code.length !== 6) { showError(errEl, 'Enter 6-digit code'); return; }

    try {
      const r = await fetch('/api/auth/mfa/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: _mfaEmail, code, mfa_token: _mfaToken }),
      });
      const data = await r.json();

      if (!r.ok) { showError(errEl, data.detail || 'Invalid code'); return; }

      window.location.href = '/owner';
    } catch (err) {
      showError(errEl, 'Connection error');
    }
  });

  // Forgot password
  document.getElementById('forgot-link').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('login-card').classList.add('hidden');
    document.getElementById('forgot-card').classList.remove('hidden');
    // Pre-fill email
    const email = document.getElementById('login-email').value;
    if (email) document.getElementById('forgot-email').value = email;
  });

  document.getElementById('back-to-login').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('forgot-card').classList.add('hidden');
    document.getElementById('login-card').classList.remove('hidden');
  });

  document.getElementById('forgot-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('forgot-error');
    const successEl = document.getElementById('forgot-success');
    errEl.style.display = 'none';
    successEl.style.display = 'none';

    const email = document.getElementById('forgot-email').value.trim();
    if (!email) { showError(errEl, 'Enter your email'); return; }

    try {
      const r = await fetch('/api/auth/password/forgot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await r.json();
      successEl.textContent = data.message || 'Check your email for a reset link.';
      successEl.style.display = 'block';
    } catch (err) {
      showError(errEl, 'Connection error');
    }
  });
});

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = 'block';
}
