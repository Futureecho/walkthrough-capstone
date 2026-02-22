/* owner-settings.js — AI provider settings + MFA management */

let _mfaSecret = '';

document.addEventListener('DOMContentLoaded', async () => {
  // Check auth
  const authR = await fetch('/api/auth/me');
  if (authR.status === 401) { window.location.href = '/owner/login'; return; }

  await loadSettings();
  await loadMFAStatus();

  document.getElementById('save-btn').addEventListener('click', saveSettings);
  document.getElementById('mfa-verify-btn').addEventListener('click', enableMFA);
  document.getElementById('mfa-disable-btn').addEventListener('click', disableMFA);
});

async function loadSettings() {
  try {
    const r = await fetch('/api/owner/settings');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    const data = await r.json();

    document.getElementById('llm-provider').value = data.llm_provider || 'openai';
    document.getElementById('default-days').value = data.default_link_days || 7;

    document.getElementById('openai-status').textContent = data.openai_api_key_set ? 'Key saved' : '';
    document.getElementById('anthropic-status').textContent = data.anthropic_api_key_set ? 'Key saved' : '';
    document.getElementById('gemini-status').textContent = data.gemini_api_key_set ? 'Key saved' : '';
    document.getElementById('grok-status').textContent = data.grok_api_key_set ? 'Key saved' : '';
  } catch (e) {
    document.getElementById('save-msg').textContent = 'Failed to load settings';
  }
}

async function saveSettings() {
  const body = {
    llm_provider: document.getElementById('llm-provider').value,
    default_link_days: parseInt(document.getElementById('default-days').value) || 7,
  };

  const openaiKey = document.getElementById('openai-key').value;
  const anthropicKey = document.getElementById('anthropic-key').value;
  const geminiKey = document.getElementById('gemini-key').value;
  const grokKey = document.getElementById('grok-key').value;

  if (openaiKey) body.openai_api_key = openaiKey;
  if (anthropicKey) body.anthropic_api_key = anthropicKey;
  if (geminiKey) body.gemini_api_key = geminiKey;
  if (grokKey) body.grok_api_key = grokKey;

  try {
    const r = await fetch('/api/owner/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error('Save failed');
    document.getElementById('save-msg').textContent = 'Settings saved!';
    document.getElementById('save-msg').style.color = 'var(--success)';

    document.getElementById('openai-key').value = '';
    document.getElementById('anthropic-key').value = '';
    document.getElementById('gemini-key').value = '';
    document.getElementById('grok-key').value = '';

    await loadSettings();
  } catch (e) {
    document.getElementById('save-msg').textContent = 'Failed to save';
    document.getElementById('save-msg').style.color = 'var(--danger)';
  }
}

// ── MFA ──────────────────────────────────────────────────

async function loadMFAStatus() {
  const statusArea = document.getElementById('mfa-status-area');
  try {
    const r = await fetch('/api/auth/me');
    if (!r.ok) return;
    const user = await r.json();

    // Check if MFA is enabled by trying to look at the user info
    // The /me endpoint doesn't expose mfa_enabled, so check via the admin endpoint or infer
    // For now, show setup/disable based on user state
    // We need a way to check MFA status — let's use the admin users list or a dedicated endpoint
    // Simple approach: try MFA setup; if user already has MFA it means it's enabled
    statusArea.innerHTML = '';

    // Fetch user details from admin if admin, otherwise just show setup option
    const adminR = await fetch('/api/admin/users');
    if (adminR.ok) {
      const users = await adminR.json();
      const me = users.find(u => u.id === user.user_id);
      if (me && me.mfa_enabled) {
        statusArea.innerHTML = '<p style="color:var(--success);font-weight:600">MFA is enabled</p>';
        document.getElementById('mfa-disable').classList.remove('hidden');
        return;
      }
    }

    // Not enabled — show setup
    statusArea.innerHTML = '<p class="text-muted">MFA is not enabled. Set it up for extra security.</p>';
    showMFASetup();
  } catch (e) {
    statusArea.innerHTML = '<p class="text-muted">MFA status unavailable</p>';
    showMFASetup();
  }
}

async function showMFASetup() {
  try {
    const r = await fetch('/api/auth/mfa/setup', { method: 'POST' });
    if (!r.ok) return;
    const data = await r.json();
    _mfaSecret = data.secret;

    document.getElementById('mfa-secret-text').textContent = data.secret;

    // Load QR code
    const qrDiv = document.getElementById('mfa-qr');
    const img = document.createElement('img');
    img.src = `/api/auth/mfa/qr?secret=${encodeURIComponent(data.secret)}`;
    img.alt = 'MFA QR Code';
    img.style.maxWidth = '200px';
    qrDiv.innerHTML = '';
    qrDiv.appendChild(img);

    document.getElementById('mfa-setup').classList.remove('hidden');
  } catch (e) {
    // silent
  }
}

async function enableMFA() {
  const code = document.getElementById('mfa-verify-code').value.trim();
  const msgEl = document.getElementById('mfa-setup-msg');

  if (!code || code.length !== 6) {
    msgEl.style.color = 'var(--danger)';
    msgEl.textContent = 'Enter the 6-digit code';
    return;
  }

  try {
    const r = await fetch('/api/auth/mfa/enable-with-secret', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret: _mfaSecret, code }),
    });
    const data = await r.json();
    if (!r.ok) {
      msgEl.style.color = 'var(--danger)';
      msgEl.textContent = data.detail || 'Failed to enable MFA';
      return;
    }
    msgEl.style.color = 'var(--success)';
    msgEl.textContent = 'MFA enabled successfully!';
    document.getElementById('mfa-setup').classList.add('hidden');
    await loadMFAStatus();
  } catch (e) {
    msgEl.style.color = 'var(--danger)';
    msgEl.textContent = 'Connection error';
  }
}

async function disableMFA() {
  const password = document.getElementById('mfa-disable-password').value;
  const code = document.getElementById('mfa-disable-code').value.trim();
  const msgEl = document.getElementById('mfa-disable-msg');

  if (!password || !code) {
    msgEl.style.color = 'var(--danger)';
    msgEl.textContent = 'Enter password and code';
    return;
  }

  try {
    const r = await fetch('/api/auth/mfa/disable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password, code }),
    });
    const data = await r.json();
    if (!r.ok) {
      msgEl.style.color = 'var(--danger)';
      msgEl.textContent = data.detail || 'Failed to disable MFA';
      return;
    }
    msgEl.style.color = 'var(--success)';
    msgEl.textContent = 'MFA disabled';
    document.getElementById('mfa-disable').classList.add('hidden');
    await loadMFAStatus();
  } catch (e) {
    msgEl.style.color = 'var(--danger)';
    msgEl.textContent = 'Connection error';
  }
}
