/* owner-dispatch.js — Multi-step work order dispatch workflow */

let sessionId = null;
let sessionData = null;
let propertyData = null;
let concerns = [];
let technicians = [];
let workOrderId = null;

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  sessionId = params.get('session');

  if (!sessionId) {
    document.getElementById('dispatch-subtitle').textContent = 'Error: No session specified';
    return;
  }

  // Check auth
  const authR = await fetch('/api/auth/me');
  if (authR.status === 401) { window.location.href = '/owner/login'; return; }

  await loadData();

  // Wire up events
  document.getElementById('add-tech-btn').addEventListener('click', showAddTechForm);
  document.getElementById('cancel-tech-btn').addEventListener('click', hideAddTechForm);
  document.getElementById('save-tech-btn').addEventListener('click', saveNewTech);
  document.getElementById('generate-btn').addEventListener('click', generateWorkOrder);
  document.getElementById('dispatch-btn').addEventListener('click', dispatchWorkOrder);
  document.getElementById('edit-btn').addEventListener('click', goBackToEdit);

  // Order type radio — show/hide NTE field
  document.querySelectorAll('input[name="order-type"]').forEach(radio => {
    radio.addEventListener('change', () => {
      document.getElementById('nte-field').style.display =
        document.querySelector('input[name="order-type"]:checked').value === 'nte' ? '' : 'none';
    });
  });

  // Set back links
  const reportUrl = `/owner/reports/${sessionId}`;
  document.getElementById('back-link').href = reportUrl;
  document.getElementById('cancel-link').href = reportUrl;
  document.getElementById('cancel-preview-link').href = reportUrl;
  document.getElementById('done-link').href = reportUrl;
});

async function loadData() {
  try {
    // Fetch session, property, concerns, technicians in parallel
    const [sr, cr, tr] = await Promise.all([
      fetch(`/api/sessions/${sessionId}`),
      fetch(`/api/owner/sessions/${sessionId}/concerns`),
      fetch('/api/owner/technicians'),
    ]);

    if (sr.status === 401) { window.location.href = '/owner/login'; return; }
    if (!sr.ok) throw new Error('Session not found');

    sessionData = await sr.json();
    concerns = cr.ok ? await cr.json() : [];
    technicians = tr.ok ? await tr.json() : [];

    // Fetch property
    const pr = await fetch(`/api/properties/${sessionData.property_id}`);
    propertyData = pr.ok ? await pr.json() : null;

    const label = propertyData ? propertyData.label : 'Property';
    document.getElementById('dispatch-subtitle').textContent = label;

    renderTechSelect();
    renderConcerns();
  } catch (e) {
    document.getElementById('dispatch-subtitle').textContent = 'Error loading data';
  }
}

function renderTechSelect() {
  const sel = document.getElementById('tech-select');
  sel.innerHTML = '<option value="">Select technician...</option>';
  technicians.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.id;
    opt.textContent = `${t.name} (${t.email})`;
    sel.appendChild(opt);
  });
}

function renderConcerns() {
  const div = document.getElementById('concerns-list');
  if (!concerns.length) {
    div.innerHTML = '<p class="text-muted">No concerns flagged for this session</p>';
    return;
  }

  div.innerHTML = '';
  concerns.forEach(c => {
    const row = document.createElement('label');
    row.className = 'concern-check-row';
    row.style.cssText = 'display:flex;align-items:center;gap:.75rem;padding:.5rem 0;border-bottom:1px solid var(--border);cursor:pointer';

    row.innerHTML = `
      <input type="checkbox" value="${esc(c.id)}" checked style="width:20px;height:20px;flex-shrink:0">
      ${c.thumbnail_path ? `<img src="/${esc(c.thumbnail_path)}" style="width:60px;height:45px;object-fit:cover;border-radius:4px;flex-shrink:0" alt="">` : ''}
      <div style="flex:1;min-width:0">
        <strong style="font-size:.9rem">${esc(c.title)}</strong>
        ${c.room ? `<br><span class="text-muted" style="font-size:.8rem">${esc(c.room)}</span>` : ''}
      </div>
    `;
    div.appendChild(row);
  });
}

// ── Add technician inline ───────────────────────────────

function showAddTechForm() {
  document.getElementById('add-tech-form').classList.remove('hidden');
  document.getElementById('add-tech-btn').classList.add('hidden');
  document.getElementById('new-tech-name').focus();
}

function hideAddTechForm() {
  document.getElementById('add-tech-form').classList.add('hidden');
  document.getElementById('add-tech-btn').classList.remove('hidden');
  document.getElementById('new-tech-name').value = '';
  document.getElementById('new-tech-email').value = '';
  document.getElementById('new-tech-phone').value = '';
}

async function saveNewTech() {
  const name = document.getElementById('new-tech-name').value.trim();
  const email = document.getElementById('new-tech-email').value.trim();
  const phone = document.getElementById('new-tech-phone').value.trim();

  if (!name || !email) { alert('Name and email are required'); return; }

  try {
    const r = await fetch('/api/owner/technicians', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, phone }),
    });
    if (!r.ok) throw new Error('Failed to create technician');
    const tech = await r.json();
    technicians.push(tech);
    renderTechSelect();
    document.getElementById('tech-select').value = tech.id;
    hideAddTechForm();
  } catch (e) {
    alert('Failed: ' + e.message);
  }
}

// ── Generate work order ─────────────────────────────────

async function generateWorkOrder() {
  const techId = document.getElementById('tech-select').value;
  if (!techId) { alert('Select a technician'); return; }

  const orderType = document.querySelector('input[name="order-type"]:checked').value;
  const nteAmount = orderType === 'nte' ? parseFloat(document.getElementById('nte-amount').value) || 0 : null;

  // Gather checked concern IDs
  const checkedIds = [];
  document.querySelectorAll('#concerns-list input[type="checkbox"]:checked').forEach(cb => {
    checkedIds.push(cb.value);
  });

  const btn = document.getElementById('generate-btn');
  btn.disabled = true;
  btn.textContent = 'Generating...';

  try {
    const body = {
      session_id: sessionId,
      technician_id: techId,
      contact_name: document.getElementById('contact-name').value.trim(),
      contact_phone: document.getElementById('contact-phone').value.trim(),
      order_type: orderType,
      nte_amount: nteAmount,
      included_concern_ids: checkedIds,
    };

    let r;
    if (workOrderId) {
      // Update existing
      r = await fetch(`/api/owner/work-orders/${workOrderId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } else {
      // Create new
      r = await fetch('/api/owner/work-orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    }

    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed');
    }

    const data = await r.json();
    workOrderId = data.id;

    // Load full work order for preview
    const woR = await fetch(`/api/owner/work-orders/${workOrderId}`);
    const wo = await woR.json();

    renderPreview(wo);
    showStep(2);
  } catch (e) {
    alert('Failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Work Order';
  }
}

// ── Preview ─────────────────────────────────────────────

function renderPreview(wo) {
  const tech = wo.technician || {};
  const prop = propertyData || {};
  const typeLabels = { nte: 'Not to Exceed', call_estimate: 'Call with Estimate', proceed: 'Proceed with Work' };

  let html = `
    <h2 style="text-align:center;color:var(--primary);margin-bottom:.75rem">WORK ORDER</h2>
    <table style="width:100%;font-size:.9rem;margin-bottom:1rem">
      <tr><td class="text-muted" style="width:130px;padding:.25rem 0">Property:</td><td>${esc(prop.label || '')}${prop.address ? ' — ' + esc(prop.address) : ''}</td></tr>
      <tr><td class="text-muted" style="padding:.25rem 0">Tenant:</td><td>${esc(sessionData.tenant_name || '')}${sessionData.tenant_name_2 ? ' & ' + esc(sessionData.tenant_name_2) : ''}</td></tr>
      <tr><td class="text-muted" style="padding:.25rem 0">Technician:</td><td>${esc(tech.name || '')} (${esc(tech.email || '')})</td></tr>
      <tr><td class="text-muted" style="padding:.25rem 0">Entry Contact:</td><td>${esc(wo.contact_name)}${wo.contact_phone ? ' — ' + esc(wo.contact_phone) : ''}</td></tr>
      <tr><td class="text-muted" style="padding:.25rem 0">Order Type:</td><td>${typeLabels[wo.order_type] || wo.order_type}</td></tr>
      ${wo.order_type === 'nte' && wo.nte_amount ? `<tr><td class="text-muted" style="padding:.25rem 0">NTE Amount:</td><td style="color:var(--danger);font-weight:600">$${wo.nte_amount.toFixed(2)}</td></tr>` : ''}
    </table>
  `;

  if (wo.concerns && wo.concerns.length > 0) {
    html += '<h3 style="margin-bottom:.5rem">Concerns</h3>';
    wo.concerns.forEach(c => {
      html += `
        <div class="concern-card">
          <div class="flex gap-1" style="align-items:flex-start">
            ${c.thumbnail_path ? `<img src="/${esc(c.thumbnail_path)}" style="width:80px;height:60px;object-fit:cover;border-radius:4px;flex-shrink:0" alt="">` : ''}
            <div>
              <strong>${esc(c.title)}</strong>
              ${c.room ? `<br><span class="text-muted" style="font-size:.85rem">${esc(c.room)}</span>` : ''}
              ${c.description ? `<p class="text-muted" style="font-size:.85rem;margin-top:.25rem">${esc(c.description)}</p>` : ''}
            </div>
          </div>
        </div>
      `;
    });
  }

  document.getElementById('wo-preview-content').innerHTML = html;
}

// ── Dispatch ────────────────────────────────────────────

async function dispatchWorkOrder() {
  if (!workOrderId) return;

  const btn = document.getElementById('dispatch-btn');
  btn.disabled = true;
  btn.textContent = 'Dispatching...';

  try {
    const r = await fetch(`/api/owner/work-orders/${workOrderId}/dispatch`, {
      method: 'POST',
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(data.detail || 'Dispatch failed');
    }

    showStep('done');
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Dispatch';
  }
}

// ── Navigation ──────────────────────────────────────────

function goBackToEdit() {
  showStep(1);
}

function showStep(step) {
  document.getElementById('step-configure').classList.toggle('hidden', step !== 1);
  document.getElementById('step-preview').classList.toggle('hidden', step !== 2);
  document.getElementById('step-done').classList.toggle('hidden', step !== 'done');

  // Update step dots
  document.querySelectorAll('.step-dot').forEach(dot => {
    const ds = parseInt(dot.dataset.step);
    dot.classList.toggle('active', ds === step || (step === 'done' && ds === 2));
  });
}

// ── Helpers ─────────────────────────────────────────────

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
