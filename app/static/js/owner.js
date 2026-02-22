/* owner.js — Dashboard with admin panel */

let _currentUser = null;

document.addEventListener('DOMContentLoaded', async () => {
  // Get current user info
  try {
    const r = await fetch('/api/auth/me');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    _currentUser = await r.json();
    document.getElementById('user-info').textContent = _currentUser.display_name || _currentUser.email;

    // Show admin features if admin
    if (_currentUser.role === 'admin') {
      document.getElementById('admin-btn').classList.remove('hidden');
      document.getElementById('admin-panel').classList.remove('hidden');
      document.getElementById('export-card').classList.remove('hidden');
      loadUsers();
    }
  } catch (e) {
    window.location.href = '/owner/login';
    return;
  }

  await loadQueue();

  document.getElementById('logout-btn').addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/owner/login';
  });

  document.getElementById('admin-btn').addEventListener('click', () => {
    document.getElementById('admin-panel').scrollIntoView({ behavior: 'smooth' });
  });

  // Invite button
  document.getElementById('invite-btn').addEventListener('click', sendInvite);

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

async function loadQueue() {
  try {
    const r = await fetch('/api/owner/queue');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    const data = await r.json();
    renderQueue('pending-inspections', data.pending_inspections, 'No active inspections');
    renderQueue('pending-review', data.pending_review, 'No reports pending review');
  } catch (e) {
    document.getElementById('pending-inspections').innerHTML = '<p class="text-muted">Failed to load</p>';
    document.getElementById('pending-review').innerHTML = '<p class="text-muted">Failed to load</p>';
  }
}

function renderQueue(containerId, items, emptyMsg) {
  const div = document.getElementById(containerId);
  if (!items || items.length === 0) {
    div.innerHTML = `<p class="text-muted">${emptyMsg}</p>`;
    return;
  }

  div.innerHTML = '';
  items.forEach(item => {
    const el = document.createElement('div');
    el.className = 'room-item';
    el.style.cursor = 'pointer';
    el.innerHTML = `
      <div>
        <strong>${item.property_label || 'Unknown'}</strong>
        ${item.property_address ? `<br><span class="text-muted" style="font-size:.85rem">${item.property_address}</span>` : ''}
        <br><span class="text-muted" style="font-size:.85rem">
          ${item.tenant_name}${item.tenant_name_2 ? ' & ' + item.tenant_name_2 : ''}
          &middot; ${item.session_type.replace('_', '-')}
          &middot; ${item.room_count} room(s)
        </span>
      </div>
      ${reviewFlagBadge(item.review_flag)}
      <span class="badge ${statusBadge(item.report_status)}">${item.report_status}</span>
    `;
    el.addEventListener('click', () => {
      window.location.href = `/owner/reports/${item.session_id}`;
    });
    div.appendChild(el);
  });
}

function reviewFlagBadge(flag) {
  if (flag === 'manual_review') return '<span class="badge badge-amber">Manual Review</span>';
  if (flag === 'ai_review_complete') return '<span class="badge badge-ai-success">AI Reviewed</span>';
  return '';
}

function statusBadge(status) {
  switch (status) {
    case 'active': return 'badge-info';
    case 'pending_review': return 'badge-warning';
    case 'submitted': return 'badge-warning';
    case 'published': return 'badge-success';
    default: return 'badge-info';
  }
}

// ── Admin: Users ────────────────────────────────────────

async function loadUsers() {
  try {
    const r = await fetch('/api/admin/users');
    if (!r.ok) return;
    const users = await r.json();
    renderUsers(users);
  } catch (e) {
    document.getElementById('user-list').innerHTML = '<p class="text-muted">Failed to load users</p>';
  }
}

function renderUsers(users) {
  const div = document.getElementById('user-list');
  if (!users.length) { div.innerHTML = '<p class="text-muted">No users</p>'; return; }

  div.innerHTML = '';
  users.forEach(u => {
    const el = document.createElement('div');
    el.className = 'room-item';
    el.innerHTML = `
      <div>
        <strong>${u.display_name || u.email}</strong>
        <br><span class="text-muted" style="font-size:.85rem">${u.email}</span>
      </div>
      <div style="display:flex;gap:.5rem;align-items:center">
        <span class="badge ${u.role === 'admin' ? 'badge-info' : u.role === 'inspector' ? 'badge-success' : 'badge-warning'}">${u.role}</span>
        ${u.mfa_enabled ? '<span class="badge badge-success" style="font-size:.7rem">MFA</span>' : ''}
        ${!u.is_active ? '<span class="badge badge-danger" style="font-size:.7rem">Inactive</span>' : ''}
      </div>
    `;
    div.appendChild(el);
  });
}

async function sendInvite() {
  const email = document.getElementById('invite-email').value.trim();
  const role = document.getElementById('invite-role').value;
  const msgEl = document.getElementById('invite-msg');

  if (!email) { msgEl.style.color = 'var(--danger)'; msgEl.textContent = 'Enter an email'; return; }

  try {
    const r = await fetch('/api/admin/invite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role }),
    });
    const data = await r.json();
    if (!r.ok) {
      msgEl.style.color = 'var(--danger)';
      msgEl.textContent = data.detail || 'Invite failed';
      return;
    }
    msgEl.style.color = 'var(--success)';
    msgEl.textContent = `Invite sent to ${email}`;
    document.getElementById('invite-email').value = '';
  } catch (e) {
    msgEl.style.color = 'var(--danger)';
    msgEl.textContent = 'Connection error';
  }
}
