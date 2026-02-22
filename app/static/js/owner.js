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

    // Show admin nav if admin
    if (_currentUser.role === 'admin') {
      const adminBtn = document.getElementById('admin-btn');
      if (adminBtn) adminBtn.classList.remove('hidden');
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

  // Schedule Walkthru
  initScheduleFlow();
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

// ── Schedule Walkthru ────────────────────────────────

let _schedulePropertyId = null;

function initScheduleFlow() {
  document.getElementById('schedule-start-btn').addEventListener('click', loadScheduleProperties);
  document.getElementById('sched-back-link').addEventListener('click', (e) => {
    e.preventDefault();
    showSchedulePicker();
  });
  document.getElementById('sched-generate-btn').addEventListener('click', generateTenantLink);
}

async function loadScheduleProperties() {
  const listDiv = document.getElementById('schedule-property-list');
  listDiv.innerHTML = '<div class="spinner"></div>';
  listDiv.classList.remove('hidden');
  document.getElementById('schedule-start-btn').classList.add('hidden');

  try {
    const r = await fetch('/api/owner/properties');
    if (!r.ok) throw new Error('Failed');
    const props = await r.json();

    if (!props.length) {
      listDiv.innerHTML = '<p class="text-muted">No properties — <a href="/owner/properties">create one first</a></p>';
      return;
    }

    listDiv.innerHTML = '';
    props.forEach(p => {
      const el = document.createElement('div');
      el.className = 'room-item';
      el.style.cursor = 'pointer';
      el.innerHTML = `
        <div>
          <strong>${esc(p.label)}</strong>
          ${p.address ? `<br><span class="text-muted" style="font-size:.85rem">${esc(p.address)}</span>` : ''}
        </div>
        <span class="text-muted" style="font-size:.85rem">${p.room_template_count} rooms</span>
      `;
      el.addEventListener('click', () => selectScheduleProperty(p));
      listDiv.appendChild(el);
    });
  } catch (e) {
    listDiv.innerHTML = '<p class="text-muted">Failed to load properties</p>';
  }
}

function selectScheduleProperty(prop) {
  _schedulePropertyId = prop.id;
  document.getElementById('schedule-prop-label').textContent = prop.label;
  document.getElementById('schedule-prop-addr').textContent = prop.address || '';
  document.getElementById('schedule-property-list').classList.add('hidden');
  document.getElementById('schedule-form').classList.remove('hidden');
  document.getElementById('schedule-result').classList.add('hidden');
  // Reset form
  document.getElementById('sched-tenant').value = '';
  document.getElementById('sched-tenant2').value = '';
  document.getElementById('sched-days').value = '7';
  document.getElementById('sched-type').value = 'move_in';
}

function showSchedulePicker() {
  _schedulePropertyId = null;
  document.getElementById('schedule-form').classList.add('hidden');
  document.getElementById('schedule-result').classList.add('hidden');
  document.getElementById('schedule-property-list').classList.remove('hidden');
}

async function generateTenantLink() {
  if (!_schedulePropertyId) return;
  const session_type = document.getElementById('sched-type').value;
  const tenant_name = document.getElementById('sched-tenant').value.trim();
  const tenant_name_2 = document.getElementById('sched-tenant2').value.trim();
  const duration_days = parseInt(document.getElementById('sched-days').value) || 7;

  if (!tenant_name) return alert('Tenant name is required');

  try {
    const r = await fetch(`/api/owner/properties/${_schedulePropertyId}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_type, tenant_name, tenant_name_2, duration_days }),
    });
    if (!r.ok) { const d = await r.json(); alert(d.detail || 'Failed'); return; }
    const data = await r.json();

    const fullUrl = `${window.location.origin}${data.url}`;
    const resultDiv = document.getElementById('schedule-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = `
      <strong>Tenant Link:</strong><br>
      <a href="${fullUrl}" target="_blank" style="word-break:break-all">${fullUrl}</a>
      <br><span class="text-muted" style="font-size:.85rem">Expires in ${duration_days} day(s)</span>
      <div class="flex gap-1 mt-1">
        <button class="btn btn-outline" id="sched-copy-btn" style="padding:.3rem .6rem;font-size:.85rem">Copy Link</button>
      </div>
      <div id="sched-qr" class="mt-1" style="text-align:center"></div>
      <p class="text-muted mt-1" style="font-size:.8rem;text-align:center">Scan with phone camera to open</p>
    `;

    document.getElementById('sched-copy-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(fullUrl).then(() => {
        document.getElementById('sched-copy-btn').textContent = 'Copied!';
        setTimeout(() => { document.getElementById('sched-copy-btn').textContent = 'Copy Link'; }, 2000);
      });
    });

    new QRCode(document.getElementById('sched-qr'), {
      text: fullUrl,
      width: 200,
      height: 200,
      correctLevel: QRCode.CorrectLevel.M,
    });
  } catch (e) {
    alert('Connection error');
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
