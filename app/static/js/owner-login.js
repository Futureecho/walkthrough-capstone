/* owner-login.js — Setup (first-run) and login */

document.addEventListener('DOMContentLoaded', async () => {
  // Check if setup is needed
  try {
    const r = await fetch('/api/owner/status');
    const data = await r.json();

    document.getElementById('loading-card').classList.add('hidden');

    if (data.setup_required) {
      document.getElementById('page-subtitle').textContent = 'First-Time Setup';
      document.getElementById('setup-card').classList.remove('hidden');
    } else {
      document.getElementById('page-subtitle').textContent = 'Sign In';
      document.getElementById('login-card').classList.remove('hidden');
    }
  } catch (e) {
    document.getElementById('loading-card').innerHTML =
      '<p style="color:var(--danger)">Failed to connect to server</p>';
  }

  // Setup form
  document.getElementById('setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('setup-error');
    errEl.style.display = 'none';

    const username = document.getElementById('setup-username').value.trim();
    const password = document.getElementById('setup-password').value;
    const confirm = document.getElementById('setup-confirm').value;
    const hint = document.getElementById('setup-hint').value.trim();

    if (!username) { showError(errEl, 'Username is required'); return; }
    if (password.length < 6) { showError(errEl, 'Password must be at least 6 characters'); return; }
    if (password !== confirm) { showError(errEl, 'Passwords do not match'); return; }

    try {
      const r = await fetch('/api/owner/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, password_hint: hint }),
      });
      const data = await r.json();
      if (!r.ok) { showError(errEl, data.detail || 'Setup failed'); return; }

      // Auto-logged in — go to dashboard
      window.location.href = '/owner';
    } catch (err) {
      showError(errEl, 'Connection error');
    }
  });

  // Login form
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.style.display = 'none';

    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    if (!username || !password) { showError(errEl, 'Enter username and password'); return; }

    try {
      const r = await fetch('/api/owner/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await r.json();
      if (!r.ok) { showError(errEl, data.detail || 'Login failed'); return; }

      window.location.href = '/owner';
    } catch (err) {
      showError(errEl, 'Connection error');
    }
  });

  // Forgot password link
  document.getElementById('forgot-link').addEventListener('click', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    try {
      const r = await fetch(`/api/owner/hint?username=${encodeURIComponent(username)}`);
      const data = await r.json();
      const hintBox = document.getElementById('hint-box');
      const hintText = document.getElementById('hint-text');
      if (data.hint) {
        hintText.textContent = data.hint;
      } else {
        hintText.textContent = 'No hint was set for this account.';
      }
      hintBox.classList.remove('hidden');
    } catch (err) {
      // silent
    }
  });
});

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = 'block';
}
