/* tenant.js — Tenant landing page for inspection links */

let tenantToken = null;
let sessionData = null;

document.addEventListener('DOMContentLoaded', async () => {
  // Extract token from URL: /inspect/{token}
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  tenantToken = pathParts[pathParts.length - 1];
  if (!tenantToken || tenantToken === 'inspect') {
    showError('Invalid link');
    return;
  }

  await loadSession();
});

async function loadSession() {
  try {
    const r = await fetch(`/api/tenant/session?token=${encodeURIComponent(tenantToken)}`);
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      showError(data.detail || 'This link is invalid or has expired.');
      return;
    }

    sessionData = await r.json();
    renderSession();
  } catch (e) {
    showError('Connection error');
  }
}

function showError(msg) {
  document.getElementById('loading-card').classList.add('hidden');
  document.getElementById('error-card').classList.remove('hidden');
  document.getElementById('error-msg').textContent = msg;
  document.getElementById('header-subtitle').textContent = 'Error';
}

function renderSession() {
  document.getElementById('loading-card').classList.add('hidden');
  document.getElementById('session-info').classList.remove('hidden');
  document.getElementById('rooms-card').classList.remove('hidden');

  const typeLabel = sessionData.session_type === 'move_in' ? 'Move-In' : 'Move-Out';
  document.getElementById('header-subtitle').textContent = `${typeLabel} Inspection`;
  document.getElementById('property-label').textContent = sessionData.property_label;
  document.getElementById('property-address').textContent = sessionData.property_address || '';
  document.getElementById('session-type-badge').textContent = typeLabel;
  document.getElementById('tenant-info').textContent = sessionData.tenant_name || '';

  if (sessionData.expires_at) {
    const exp = new Date(sessionData.expires_at);
    document.getElementById('expires-info').textContent = `Link expires: ${exp.toLocaleString()}`;
  }

  // Build room list from room templates
  const roomList = document.getElementById('room-list');
  roomList.innerHTML = '';

  const templates = sessionData.room_templates || [];
  if (templates.length === 0) {
    roomList.innerHTML = '<li class="room-item text-muted">No rooms configured for this property</li>';
    return;
  }

  // Check which rooms already have captures
  const capturedRooms = {};
  (sessionData.captures || []).forEach(c => {
    capturedRooms[c.room] = c.status;
  });

  let allDone = true;
  templates.forEach(rt => {
    const status = capturedRooms[rt.name] || 'pending';
    if (status !== 'passed' && status !== 'needs_coverage') allDone = false;

    const li = document.createElement('li');
    li.className = 'room-item';
    li.style.cursor = status === 'passed' ? 'default' : 'pointer';

    const statusDot = status === 'passed' ? 'passed'
      : status === 'processing' ? 'processing'
      : status === 'failed' ? 'failed'
      : status === 'needs_coverage' ? 'needs_coverage'
      : 'pending';

    const is360 = rt.capture_mode === '360';
    const modeInfo = is360 ? '360° sweep' : `${rt.positions.length} position(s)`;

    li.innerHTML = `
      <div>
        <strong>${rt.name}</strong>
        <br><span class="text-muted" style="font-size:.85rem">${modeInfo}</span>
      </div>
      <div class="room-status ${statusDot}"></div>
    `;

    if (status !== 'passed') {
      li.addEventListener('click', () => {
        const base = is360 ? '/capture/360' : '/capture';
        window.location.href = `${base}?token=${encodeURIComponent(tenantToken)}&session=${sessionData.session_id}&room=${encodeURIComponent(rt.name)}`;
      });
    }
    roomList.appendChild(li);
  });

  // Show submit/done cards based on report status
  const reportStatus = sessionData.report_status;
  if (reportStatus === 'pending_review' || reportStatus === 'submitted') {
    document.getElementById('done-card').classList.remove('hidden');
  } else if (templates.length > 0) {
    // Show submit card if there are rooms (active session)
    document.getElementById('submit-card').classList.remove('hidden');
    document.getElementById('submit-report-btn').addEventListener('click', attemptSubmit);

    // Show concern button during active session
    const concernBtn = document.getElementById('concern-btn');
    concernBtn.style.display = '';
    concernBtn.addEventListener('click', () => {
      window.location.href = `/concern?token=${encodeURIComponent(tenantToken)}&session=${sessionData.session_id}&room=`;
    });

    // Load concern count
    loadConcernCount();
  }
}

async function loadConcernCount() {
  try {
    const r = await fetch(`/api/tenant/concerns?session_id=${sessionData.session_id}&token=${encodeURIComponent(tenantToken)}`);
    if (!r.ok) return;
    const concerns = await r.json();
    if (concerns.length > 0) {
      const badge = document.getElementById('concern-count');
      badge.textContent = concerns.length;
      badge.style.display = '';
    }
  } catch (e) { /* silent */ }
}

// ── Submit flow ──────────────────────────────────────────

function attemptSubmit() {
  const templates = sessionData.room_templates || [];
  const capturedRooms = {};
  (sessionData.captures || []).forEach(c => {
    capturedRooms[c.room] = c.status;
  });

  const incompleteRooms = [];
  const warningRooms = [];

  templates.forEach(rt => {
    const status = capturedRooms[rt.name] || 'pending';
    if (status === 'passed') return;
    if (status === 'needs_coverage') {
      warningRooms.push(rt.name);
    } else {
      incompleteRooms.push(rt.name);
    }
  });

  if (incompleteRooms.length > 0) {
    // Some rooms not even started or failed
    const list = incompleteRooms.map(n => `<li>${n}</li>`).join('');
    showModal(
      'Incomplete Rooms',
      `<p>The following rooms have not been completed:</p>
       <ul style="margin:.5rem 0 .5rem 1.25rem">${list}</ul>
       <p style="font-size:.85rem;color:var(--warning)">Being unable to provide all required photos may delay processing.</p>`,
      [
        { label: 'Return to Complete Photos', style: 'btn-outline', action: hideModal },
        { label: 'Accept and Submit', style: 'btn-warning', action: doSubmit },
      ]
    );
  } else if (warningRooms.length > 0) {
    // All rooms done but some have coverage warnings
    showModal(
      'Submit with Warnings?',
      `<p>Some rooms have incomplete coverage. You can still submit, but additional photos may be requested later.</p>`,
      [
        { label: 'Cancel', style: 'btn-outline', action: hideModal },
        { label: 'Submit Report', style: 'btn-primary', action: doSubmit },
      ]
    );
  } else {
    // All green
    showModal(
      'Submit Report?',
      `<p>All rooms have been inspected. Submit your report for review?</p>`,
      [
        { label: 'Cancel', style: 'btn-outline', action: hideModal },
        { label: 'Submit Report', style: 'btn-primary', action: doSubmit },
      ]
    );
  }
}

async function doSubmit() {
  hideModal();
  const btn = document.getElementById('submit-report-btn');
  btn.disabled = true;
  btn.textContent = 'Submitting...';

  try {
    const tokenParam = tenantToken ? `?token=${encodeURIComponent(tenantToken)}` : '';
    const r = await fetch(`/api/sessions/${sessionData.session_id}/status${tokenParam}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_status: 'pending_review' }),
    });
    if (!r.ok) throw new Error('Failed to submit');

    document.getElementById('submit-card').classList.add('hidden');
    document.getElementById('done-card').classList.remove('hidden');
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Submit Report';
    alert('Submit failed: ' + e.message);
  }
}

// ── Modal helpers ────────────────────────────────────────

function showModal(title, bodyHtml, buttons) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;

  const actions = document.getElementById('modal-actions');
  actions.innerHTML = '';
  buttons.forEach(b => {
    const btn = document.createElement('button');
    btn.className = `btn ${b.style} btn-block`;
    btn.textContent = b.label;
    btn.addEventListener('click', b.action);
    actions.appendChild(btn);
  });

  const modal = document.getElementById('submit-modal');
  modal.classList.remove('hidden');
  modal.style.display = 'flex';
}

function hideModal() {
  const modal = document.getElementById('submit-modal');
  modal.classList.add('hidden');
  modal.style.display = '';
}
