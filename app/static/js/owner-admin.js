/* owner-admin.js — Admin user management page */

let _currentUser = null;

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const r = await fetch('/api/auth/me');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    _currentUser = await r.json();

    if (_currentUser.role !== 'admin') {
      window.location.href = '/owner';
      return;
    }
  } catch (e) {
    window.location.href = '/owner/login';
    return;
  }

  await loadUsers();

  // Invite link buttons
  document.getElementById('invite-admin-btn').addEventListener('click', () => generateLink('admin'));
  document.getElementById('invite-inspector-btn').addEventListener('click', () => generateLink('inspector'));
  document.getElementById('invite-referral-btn').addEventListener('click', () => generateLink('referral'));

  // Export button
  document.getElementById('export-full-btn').addEventListener('click', async () => {
    try {
      const r = await fetch('/api/owner/export/full');
      if (!r.ok) throw new Error('Export failed');
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'company_export.zip'; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Export failed: ' + e.message);
    }
  });
});

async function loadUsers() {
  const div = document.getElementById('user-list');
  try {
    const r = await fetch('/api/admin/users');
    if (!r.ok) { div.innerHTML = '<p class="text-muted">Failed to load users</p>'; return; }
    const users = await r.json();
    renderUsers(users);
  } catch (e) {
    div.innerHTML = '<p class="text-muted">Failed to load users</p>';
  }
}

function renderUsers(users) {
  const div = document.getElementById('user-list');
  if (!users.length) { div.innerHTML = '<p class="text-muted">No users</p>'; return; }

  div.innerHTML = '';
  users.forEach(u => {
    const el = document.createElement('div');
    el.className = 'room-item';
    el.style.alignItems = 'center';

    const isSelf = u.id === _currentUser.user_id;

    el.innerHTML = `
      <div style="flex:1">
        <strong>${esc(u.display_name || u.email)}</strong>
        <br><span class="text-muted" style="font-size:.85rem">${esc(u.email)}</span>
        ${u.mfa_enabled ? ' <span class="badge badge-success" style="font-size:.7rem">MFA</span>' : ''}
        ${!u.is_active ? ' <span class="badge badge-danger" style="font-size:.7rem">Inactive</span>' : ''}
      </div>
      <div style="display:flex;gap:.5rem;align-items:center">
        <select class="role-select" data-user-id="${u.id}" style="width:auto;padding:.3rem .5rem;font-size:.85rem" ${isSelf || !u.is_active ? 'disabled' : ''}>
          <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
          <option value="inspector" ${u.role === 'inspector' ? 'selected' : ''}>Inspector</option>
        </select>
        ${!isSelf && u.is_active ? `<button class="btn delete-btn" data-user-id="${u.id}" style="padding:.3rem .6rem;font-size:.85rem;background:var(--danger);color:#fff">Remove</button>` : ''}
      </div>
    `;
    div.appendChild(el);
  });

  // Role change handlers
  div.querySelectorAll('.role-select').forEach(sel => {
    sel.addEventListener('change', async (e) => {
      const userId = e.target.dataset.userId;
      const role = e.target.value;
      try {
        const r = await fetch(`/api/admin/users/${userId}/role`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role }),
        });
        const data = await r.json();
        if (!r.ok) { alert(data.detail || 'Failed'); await loadUsers(); }
      } catch (err) {
        alert('Connection error');
        await loadUsers();
      }
    });
  });

  // Delete handlers
  div.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const userId = e.target.dataset.userId;
      if (!confirm('Remove this user? They will be deactivated.')) return;
      try {
        const r = await fetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
        const data = await r.json();
        if (!r.ok) { alert(data.detail || 'Failed'); return; }
        await loadUsers();
      } catch (err) {
        alert('Connection error');
      }
    });
  });
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

// ── Generate Invite Link ────────────────────────────────

async function generateLink(type) {
  const resultDiv = document.getElementById('link-result');
  const urlInput = document.getElementById('link-url');

  try {
    const r = await fetch('/api/admin/invite-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type }),
    });
    const data = await r.json();
    if (!r.ok) { alert(data.detail || 'Failed'); return; }

    const fullUrl = `${window.location.origin}${data.url}`;
    urlInput.value = fullUrl;
    resultDiv.classList.remove('hidden');

    document.getElementById('copy-link-btn').onclick = () => {
      navigator.clipboard.writeText(fullUrl).then(() => {
        document.getElementById('copy-link-btn').textContent = 'Copied!';
        setTimeout(() => { document.getElementById('copy-link-btn').textContent = 'Copy'; }, 2000);
      });
    };
  } catch (e) {
    alert('Connection error');
  }
}
