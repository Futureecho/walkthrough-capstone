/* owner-report.js — Owner report review page */

let reportSessionId = null;
let reportData = null;
let allDiscrepancies = [];

document.addEventListener('DOMContentLoaded', async () => {
  // Extract session_id from URL: /owner/reports/{session_id}
  const pathParts = window.location.pathname.split('/');
  reportSessionId = pathParts[pathParts.length - 1];
  if (!reportSessionId) {
    document.getElementById('report-header').innerHTML = '<p class="text-muted">Invalid report URL</p>';
    return;
  }

  await loadReport();

  document.getElementById('publish-btn').addEventListener('click', publishReport);
  document.getElementById('dispatch-btn').addEventListener('click', () => {
    window.location.href = `/owner/dispatch?session=${reportSessionId}`;
  });
  document.getElementById('reactivate-btn').addEventListener('click', reactivateReport);
  document.getElementById('cancel-btn').addEventListener('click', cancelReport);
  document.getElementById('pdf-yes').addEventListener('click', generatePdf);
  document.getElementById('pdf-no').addEventListener('click', () => {
    document.getElementById('pdf-modal').classList.add('hidden');
    window.location.href = '/owner';
  });
});

async function loadReport() {
  try {
    // Fetch session detail
    const sr = await fetch(`/api/sessions/${reportSessionId}`);
    if (sr.status === 401) { window.location.href = '/owner/login'; return; }
    if (!sr.ok) throw new Error('Session not found');
    const session = await sr.json();

    // Fetch property
    const pr = await fetch(`/api/properties/${session.property_id}`);
    const property = await pr.json();

    // Fetch comparisons for this property
    const cr = await fetch(`/api/comparisons?property_id=${session.property_id}`);
    const comparisons = cr.ok ? await cr.json() : [];

    // Fetch concerns
    const conR = await fetch(`/api/owner/sessions/${reportSessionId}/concerns`);
    const concerns = conR.ok ? await conR.json() : [];

    reportData = { session, property, comparisons, concerns };
    renderReport();
    renderConcerns(concerns);
    await loadWorkOrders();
  } catch (e) {
    document.getElementById('report-header').innerHTML =
      `<p class="text-muted">Error loading report: ${e.message}</p>`;
  }
}

function reviewFlagBadge(flag) {
  if (flag === 'manual_review') return '<span class="badge badge-amber">Manual Review</span>';
  if (flag === 'ai_review_complete') return '<span class="badge badge-ai-success">AI Reviewed</span>';
  return '';
}

function renderReport() {
  const { session, property, comparisons } = reportData;

  // Header
  const typeLabel = session.type === 'move_in' ? 'Move-In' : 'Move-Out';
  document.getElementById('report-subtitle').textContent =
    `${property.label} — ${typeLabel}`;

  document.getElementById('report-header').innerHTML = `
    <div class="flex-between mb-1">
      <h2>${property.label}</h2>
      <div>${reviewFlagBadge(session.review_flag)} <span class="badge ${session.report_status === 'published' ? 'badge-success' : 'badge-warning'}">${session.report_status}</span></div>
    </div>
    <p class="text-muted">${property.address || ''}</p>
    <p class="mt-1"><strong>Tenant:</strong> ${session.tenant_name}${session.tenant_name_2 ? ' & ' + session.tenant_name_2 : ''}</p>
    <p class="text-muted" style="font-size:.85rem">${typeLabel} &middot; ${new Date(session.created_at).toLocaleDateString()}</p>
  `;

  // Room details
  const roomDiv = document.getElementById('room-details');
  roomDiv.innerHTML = '';
  allDiscrepancies = [];

  // Group captures by room
  const capturesByRoom = {};
  (session.captures || []).forEach(c => {
    capturesByRoom[c.room] = c;
  });

  // Group comparisons by room
  const compByRoom = {};
  comparisons.forEach(comp => {
    compByRoom[comp.room] = comp;
  });

  const rooms = Object.keys(capturesByRoom);
  if (rooms.length === 0) {
    roomDiv.innerHTML = '<div class="card"><p class="text-muted">No captures yet</p></div>';
    document.getElementById('actions-card').classList.remove('hidden');
    return;
  }

  rooms.forEach(room => {
    const capture = capturesByRoom[room];
    const comp = compByRoom[room];
    const card = document.createElement('div');
    card.className = 'card';

    let html = `<div class="report-room-header">${room}</div>`;

    // Status
    const statusLabel = capture.status.replace(/_/g, ' ');
    html += `<div class="flex-between mb-1">
      <span class="text-muted">Status: ${statusLabel}</span>
      <span class="badge ${capture.status === 'passed' ? 'badge-success' : 'badge-warning'}">${statusLabel}</span>
    </div>`;

    // Candidates from comparison
    if (comp && comp.candidates && comp.candidates.length > 0) {
      comp.candidates.forEach((cand, i) => {
        allDiscrepancies.push(cand);
        const confPct = Math.round(cand.confidence * 100);
        const accepted = cand.owner_accepted;
        const cardClass = accepted === true ? 'accepted'
          : accepted === false ? 'deleted' : '';

        html += `
          <div class="discrepancy-card ${cardClass}" id="disc-${cand.id}">
            <div class="flex-between mb-1">
              <strong>Discrepancy #${i + 1}</strong>
              <span class="text-muted">${confPct}% confidence</span>
            </div>
            ${cand.reason_codes ? `<p class="text-muted" style="font-size:.85rem">Indicators: ${cand.reason_codes.join(', ')}</p>` : ''}
            ${cand.crop_path ? `<img src="/${cand.crop_path}" alt="Region" style="max-width:100%;border-radius:4px;margin:.5rem 0">` : ''}
            ${cand.tenant_response ? `
              <div style="padding:.4rem;background:#f0f9ff;border-radius:4px;margin:.5rem 0">
                <span class="text-muted" style="font-size:.85rem">Tenant: <strong>${cand.tenant_response}</strong></span>
                ${cand.tenant_comment ? `<br><span class="text-muted" style="font-size:.85rem">${cand.tenant_comment}</span>` : ''}
              </div>
            ` : ''}
            <div class="flex gap-1 mt-1">
              <button class="btn ${accepted === true ? 'btn-danger' : 'btn-outline'}" style="flex:1;padding:.4rem;font-size:.85rem"
                onclick="toggleAccept('${cand.id}', true)">
                ${accepted === true ? 'Accepted' : 'Accept Discrepancy'}
              </button>
              <button class="btn ${accepted === false ? 'btn-success' : 'btn-outline'}" style="flex:1;padding:.4rem;font-size:.85rem"
                onclick="toggleAccept('${cand.id}', false)">
                ${accepted === false ? 'Deleted' : 'Delete Discrepancy'}
              </button>
            </div>
            ${accepted === true ? `
              <div class="mt-1">
                <label class="text-muted" style="font-size:.8rem">Repair cost ($)</label>
                <input type="number" class="cost-input" id="cost-${cand.id}" value="${cand.repair_cost || 0}"
                  min="0" step="0.01" onchange="updateCost('${cand.id}')">
                <label class="text-muted" style="font-size:.8rem;display:block;margin-top:.25rem">Owner notes</label>
                <textarea id="notes-${cand.id}" rows="2"
                  style="width:100%;padding:.4rem;border:1px solid var(--border);border-radius:4px;font-size:.85rem;resize:vertical"
                  onchange="updateNotes('${cand.id}')">${cand.owner_notes || ''}</textarea>
              </div>
            ` : ''}
          </div>
        `;
      });
    } else if (session.type === 'move_out') {
      html += '<p class="text-muted" style="font-size:.85rem;padding:.5rem 0">No discrepancies found for this room</p>';
    }

    card.innerHTML = html;
    roomDiv.appendChild(card);
  });

  // Show summary + actions
  document.getElementById('summary-card').classList.remove('hidden');
  document.getElementById('actions-card').classList.remove('hidden');
  updateSummary();
}

async function toggleAccept(candidateId, accepted) {
  try {
    const r = await fetch(`/api/owner/candidates/${candidateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner_accepted: accepted }),
    });
    if (!r.ok) throw new Error('Failed');

    // Update local data
    const cand = allDiscrepancies.find(c => c.id === candidateId);
    if (cand) cand.owner_accepted = accepted;

    // Re-render (simpler than DOM patching)
    renderReport();
  } catch (e) {
    alert('Failed to update: ' + e.message);
  }
}

async function updateCost(candidateId) {
  const cost = parseFloat(document.getElementById(`cost-${candidateId}`).value) || 0;
  try {
    await fetch(`/api/owner/candidates/${candidateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repair_cost: cost }),
    });
    const cand = allDiscrepancies.find(c => c.id === candidateId);
    if (cand) cand.repair_cost = cost;
    updateSummary();
  } catch (e) { /* silent */ }
}

async function updateNotes(candidateId) {
  const notes = document.getElementById(`notes-${candidateId}`).value;
  try {
    await fetch(`/api/owner/candidates/${candidateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner_notes: notes }),
    });
  } catch (e) { /* silent */ }
}

function updateSummary() {
  const flagged = allDiscrepancies.length;
  const accepted = allDiscrepancies.filter(c => c.owner_accepted === true).length;
  const totalCost = allDiscrepancies
    .filter(c => c.owner_accepted === true)
    .reduce((sum, c) => sum + (c.repair_cost || 0), 0);

  document.getElementById('sum-flagged').textContent = flagged;
  document.getElementById('sum-accepted').textContent = accepted;
  document.getElementById('sum-cost').textContent = `$${totalCost.toFixed(2)}`;

  // Enable publish if all discrepancies have been reviewed
  const allReviewed = allDiscrepancies.every(c => c.owner_accepted !== null && c.owner_accepted !== undefined);
  const publishBtn = document.getElementById('publish-btn');
  publishBtn.disabled = !allReviewed && allDiscrepancies.length > 0;

  // If already published or cancelled, update buttons
  const cancelBtn = document.getElementById('cancel-btn');
  const reactivateBtn = document.getElementById('reactivate-btn');
  if (reportData && reportData.session.report_status === 'published') {
    publishBtn.textContent = 'Published';
    publishBtn.disabled = true;
    cancelBtn.classList.add('hidden');
  } else if (reportData && reportData.session.report_status === 'cancelled') {
    publishBtn.classList.add('hidden');
    cancelBtn.classList.add('hidden');
  }
}

function renderConcerns(concerns) {
  if (!concerns || concerns.length === 0) return;

  const card = document.getElementById('concerns-card');
  card.classList.remove('hidden');
  const list = document.getElementById('concerns-list');
  list.innerHTML = '';

  concerns.forEach(c => {
    const div = document.createElement('div');
    div.className = 'concern-card';
    div.innerHTML = `
      <div class="flex gap-1" style="align-items:flex-start">
        ${c.thumbnail_path ? `<img src="/${c.thumbnail_path}" style="width:80px;height:60px;object-fit:cover;border-radius:4px;flex-shrink:0" alt="">` : ''}
        <div>
          <strong>${c.title}</strong>
          ${c.room ? `<br><span class="text-muted" style="font-size:.85rem">${c.room}</span>` : ''}
          ${c.description ? `<p class="text-muted" style="font-size:.85rem;margin-top:.25rem">${c.description}</p>` : ''}
        </div>
      </div>
    `;
    list.appendChild(div);
  });
}

async function loadWorkOrders() {
  try {
    const r = await fetch(`/api/owner/sessions/${reportSessionId}/work-orders`);
    if (!r.ok) return;
    const workOrders = await r.json();
    if (!workOrders.length) return;

    const card = document.getElementById('work-orders-card');
    card.classList.remove('hidden');
    const list = document.getElementById('work-orders-list');
    list.innerHTML = '';

    workOrders.forEach(wo => {
      const div = document.createElement('div');
      div.className = 'room-item';
      const statusBadge = wo.status === 'dispatched'
        ? '<span class="badge badge-success">Dispatched</span>'
        : '<span class="badge badge-warning">Draft</span>';
      const typeLabels = { nte: 'NTE', call_estimate: 'Call Est.', proceed: 'Proceed' };
      div.innerHTML = `
        <div>
          <strong>Work Order</strong>
          <br><span class="text-muted" style="font-size:.85rem">${typeLabels[wo.order_type] || wo.order_type} &middot; ${new Date(wo.created_at).toLocaleDateString()}</span>
        </div>
        ${statusBadge}
      `;
      list.appendChild(div);
    });
  } catch (e) { /* silent */ }
}

async function publishReport() {
  if (!reportSessionId) return;
  try {
    const r = await fetch(`/api/owner/sessions/${reportSessionId}/publish`, {
      method: 'POST',
    });
    if (!r.ok) throw new Error('Publish failed');

    // Show PDF modal
    document.getElementById('pdf-modal').classList.remove('hidden');
    document.getElementById('pdf-modal').style.display = 'flex';
  } catch (e) {
    alert('Failed to publish: ' + e.message);
  }
}

async function reactivateReport() {
  const days = prompt('Link duration (days):', '7');
  if (!days) return;

  try {
    const r = await fetch(`/api/owner/sessions/${reportSessionId}/reactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration_days: parseInt(days) || 7 }),
    });
    if (!r.ok) throw new Error('Failed');
    const data = await r.json();
    const fullUrl = `${window.location.origin}${data.url}`;
    showLinkResult(fullUrl, parseInt(days) || 7);
    await loadReport();
  } catch (e) {
    alert('Failed to reactivate: ' + e.message);
  }
}

async function cancelReport() {
  if (!confirm('Cancel this report? The tenant link will be deactivated.')) return;

  try {
    const r = await fetch(`/api/owner/sessions/${reportSessionId}/cancel`, {
      method: 'POST',
    });
    if (!r.ok) throw new Error('Failed');
    window.location.href = '/owner';
  } catch (e) {
    alert('Failed to cancel: ' + e.message);
  }
}

function showLinkResult(fullUrl, days) {
  const resultDiv = document.getElementById('link-result');
  resultDiv.classList.remove('hidden');
  resultDiv.innerHTML = `
    <strong>Tenant Link:</strong><br>
    <a href="${fullUrl}" target="_blank" style="word-break:break-all">${fullUrl}</a>
    <br><span class="text-muted" style="font-size:.85rem">Expires in ${days} day(s)</span>
    <div class="flex gap-1 mt-1">
      <button class="btn btn-outline" style="padding:.3rem .6rem;font-size:.85rem">Copy Link</button>
    </div>
    <div id="report-link-qr" class="mt-1" style="text-align:center"></div>
    <p class="text-muted mt-1" style="font-size:.8rem;text-align:center">Scan with phone camera to open</p>
  `;
  resultDiv.querySelector('button').addEventListener('click', () => {
    navigator.clipboard.writeText(fullUrl);
  });
  new QRCode(document.getElementById('report-link-qr'), {
    text: fullUrl,
    width: 200,
    height: 200,
    correctLevel: QRCode.CorrectLevel.M,
  });
}

async function generatePdf() {
  try {
    const r = await fetch(`/api/owner/sessions/${reportSessionId}/pdf`, {
      method: 'POST',
    });
    if (!r.ok) throw new Error('PDF generation failed');

    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${reportSessionId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);

    document.getElementById('pdf-modal').classList.add('hidden');
    window.location.href = '/owner';
  } catch (e) {
    alert('Failed to generate PDF: ' + e.message);
  }
}
