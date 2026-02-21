/* owner.js — Owner dashboard */

document.addEventListener('DOMContentLoaded', async () => {
  await loadQueue();

  document.getElementById('logout-btn').addEventListener('click', async () => {
    await fetch('/api/owner/logout', { method: 'POST' });
    window.location.href = '/owner/login';
  });
});

async function loadQueue() {
  try {
    const r = await fetch('/api/owner/queue');
    if (r.status === 401) {
      window.location.href = '/owner/login';
      return;
    }
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
