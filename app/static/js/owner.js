/* owner.js — Dashboard with admin panel */

let _currentUser = null;

document.addEventListener('DOMContentLoaded', async () => {
  // Get current user info
  try {
    const r = await fetch('/api/auth/me');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    _currentUser = await r.json();
    const userInfoEl = document.getElementById('user-info');
    if (userInfoEl) userInfoEl.textContent = _currentUser.display_name || _currentUser.email;

    // Show admin features if admin
    if (_currentUser.role === 'admin') {
      const adminBtn = document.getElementById('admin-btn');
      if (adminBtn) adminBtn.classList.remove('hidden');
      const adminPanel = document.getElementById('admin-panel');
      if (adminPanel) adminPanel.classList.remove('hidden');
      const exportCard = document.getElementById('export-card');
      if (exportCard) exportCard.classList.remove('hidden');
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
      <span class="badge ${statusBadge(item.report_status)}">${item.report_status.replace(/_/g, ' ')}</span>
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

// ── Admin: Generate Link ────────────────────────────────

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
