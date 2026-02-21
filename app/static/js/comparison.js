/* comparison.js — Spotlight overlay, Accept/Add Context, close-up prompt */

let comparisonData = null;
let allCandidates = [];
let currentCandidateIdx = 0;
let sessionId = null;

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const compId = params.get('id');
  sessionId = params.get('session');
  if (!compId) return;

  try {
    const r = await fetch(`/api/comparisons/${compId}`);
    if (!r.ok) throw new Error('Comparison not found');
    comparisonData = await r.json();
    allCandidates = comparisonData.candidates || [];
    renderComparison();
  } catch (e) {
    document.getElementById('comparison-content').innerHTML =
      `<p class="text-muted">Error: ${e.message}</p>`;
  }
});

function renderComparison() {
  const div = document.getElementById('comparison-content');
  div.innerHTML = `
    <div class="flex-between mb-1">
      <h2>${comparisonData.room}</h2>
      <span class="badge badge-info">${comparisonData.status}</span>
    </div>
  `;

  if (allCandidates.length === 0) {
    div.innerHTML += '<p class="text-muted mt-2">No candidate differences identified.</p>';
    return;
  }

  allCandidates.forEach((cand, i) => {
    const confPct = Math.round(cand.confidence * 100);
    const card = document.createElement('div');
    card.className = 'card';
    card.id = `candidate-${cand.id}`;

    let statusBadge = 'badge-warning';
    let statusText = cand.followup_status;
    if (cand.tenant_response === 'confirm') { statusBadge = 'badge-danger'; statusText = 'confirmed'; }
    else if (cand.tenant_response === 'context') { statusBadge = 'badge-info'; statusText = 'context added'; }
    else if (cand.tenant_response === 'disagree') { statusBadge = 'badge-success'; statusText = 'disagreed'; }

    // Build spotlight + reference pair
    let imageHtml = '';
    if (cand.crop_path) {
      imageHtml = `
        <div class="spotlight-container">
          ${buildSpotlightImage(cand)}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex-between mb-1">
        <strong>Candidate #${i + 1}</strong>
        <span class="badge ${statusBadge}">${statusText}</span>
      </div>
      <p class="text-muted">Confidence: ${confPct}%</p>
      ${cand.reason_codes ? `<p class="text-muted" style="font-size:.85rem">Indicators: ${cand.reason_codes.join(', ')}</p>` : ''}
      ${imageHtml}
      ${cand.tenant_response
        ? renderExistingResponse(cand)
        : renderFollowupForm(cand.id)
      }
    `;
    div.appendChild(card);
  });

  checkAllReviewed();
}

function buildSpotlightImage(cand) {
  // Show the crop image with a spotlight effect using CSS
  const region = cand.region_json || {};
  const x = region.x || 0;
  const y = region.y || 0;
  const w = region.w || 100;
  const h = region.h || 100;

  // Calculate circle center and radius from region
  const cx = x + w / 2;
  const cy = y + h / 2;
  const radius = Math.max(w, h) / 2 + 10;

  return `
    <div class="comparison-pair">
      <div>
        <div class="spotlight-wrapper" style="position:relative;display:inline-block;width:100%">
          <img src="/${cand.crop_path}" alt="Move-out region"
               style="width:100%;border-radius:4px;display:block">
          <div class="spotlight-ring" style="
            position:absolute;
            left:calc(50% - ${radius}px);
            top:calc(50% - ${radius}px);
            width:${radius * 2}px;
            height:${radius * 2}px;
            border:3px solid #FFD700;
            border-radius:50%;
            pointer-events:none;
            box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);
          "></div>
        </div>
        <div class="label">Move-Out — Flagged Area</div>
      </div>
      <div>
        ${cand.crop_path ? `<img src="/${cand.crop_path.replace('move_out', 'move_in')}" alt="Move-in reference"
          style="width:100%;border-radius:4px" onerror="this.style.display='none'">` : ''}
        <div class="label">Move-In — Reference</div>
      </div>
    </div>
  `;
}

function renderExistingResponse(cand) {
  const responseLabel = cand.tenant_response === 'confirm' ? 'Accepted'
    : cand.tenant_response === 'context' ? 'Context Added' : 'Disagreed';
  return `
    <div class="mt-1" style="padding:.5rem;background:#f0f9ff;border-radius:var(--radius)">
      <p><strong>Your response:</strong> ${responseLabel}</p>
      ${cand.tenant_comment ? `<p class="text-muted" style="font-size:.85rem">${cand.tenant_comment}</p>` : ''}
    </div>
  `;
}

function renderFollowupForm(candidateId) {
  return `
    <div class="mt-1" id="form-${candidateId}">
      <div class="context-box hidden" id="context-${candidateId}">
        <textarea id="comment-${candidateId}" placeholder="Add context (optional, 200 char max)"
          rows="2" maxlength="200"
          style="width:100%;padding:.5rem;border:1px solid var(--border);border-radius:4px;font-size:.9rem;resize:vertical"></textarea>
        <div class="text-muted" style="font-size:.75rem;text-align:right" id="charcount-${candidateId}">0 / 200</div>
      </div>
      <div class="flex gap-1 mt-1">
        <button class="btn btn-success" style="flex:1;padding:.5rem"
          onclick="showContextAndRespond('${candidateId}','confirm')">Accept</button>
        <button class="btn btn-outline" style="flex:1;padding:.5rem"
          onclick="showContextAndRespond('${candidateId}','context')">Add Context</button>
      </div>
    </div>
  `;
}

function showContextAndRespond(candidateId, response) {
  const contextBox = document.getElementById(`context-${candidateId}`);
  const textarea = document.getElementById(`comment-${candidateId}`);

  // If context box not yet visible, show it first (for Add Context)
  if (response === 'context' && contextBox.classList.contains('hidden')) {
    contextBox.classList.remove('hidden');
    textarea.focus();

    // Set up char counter
    textarea.addEventListener('input', () => {
      document.getElementById(`charcount-${candidateId}`).textContent =
        `${textarea.value.length} / 200`;
    });

    // Replace buttons to include submit
    const form = document.getElementById(`form-${candidateId}`);
    const btnDiv = form.querySelector('.flex.gap-1');
    btnDiv.innerHTML = `
      <button class="btn btn-success" style="flex:1;padding:.5rem"
        onclick="submitResponse('${candidateId}','confirm')">Accept</button>
      <button class="btn btn-primary" style="flex:1;padding:.5rem"
        onclick="submitResponse('${candidateId}','context')">Submit Context</button>
    `;
    return;
  }

  // For Accept, submit immediately (context box optional)
  submitResponse(candidateId, response);
}

async function submitResponse(candidateId, response) {
  const comment = document.getElementById(`comment-${candidateId}`)?.value || '';

  try {
    const r = await fetch(`/api/candidates/${candidateId}/response`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response, comment }),
    });
    if (!r.ok) throw new Error('Failed');

    // Replace form with result
    const form = document.getElementById(`form-${candidateId}`);
    const responseLabel = response === 'confirm' ? 'Accepted' : 'Context Added';
    form.innerHTML = `
      <div style="padding:.5rem;background:#f0f9ff;border-radius:var(--radius)">
        <p><strong>Your response:</strong> ${responseLabel}</p>
        ${comment ? `<p class="text-muted" style="font-size:.85rem">${comment}</p>` : ''}
      </div>
      ${renderCloseupPrompt(candidateId)}
    `;

    // Update local data
    const cand = allCandidates.find(c => c.id === candidateId);
    if (cand) {
      cand.tenant_response = response;
      cand.tenant_comment = comment;
    }

    checkAllReviewed();
  } catch (e) {
    alert('Failed to submit response: ' + e.message);
  }
}

function renderCloseupPrompt(candidateId) {
  return `
    <div class="mt-1 closeup-prompt" id="closeup-${candidateId}"
         style="padding:.5rem;background:#fffbeb;border:1px solid #fbbf24;border-radius:var(--radius)">
      <p style="font-size:.85rem"><strong>Optional:</strong> Take a close-up of this area from a different angle</p>
      <div class="flex gap-1 mt-1">
        <label class="btn btn-outline" style="flex:1;padding:.4rem;font-size:.85rem;cursor:pointer">
          Upload Photo
          <input type="file" accept="image/*" capture="environment" style="display:none"
            onchange="uploadCloseup('${candidateId}', this)">
        </label>
        <button class="btn" style="flex:1;padding:.4rem;font-size:.85rem;background:var(--border)"
          onclick="skipCloseup('${candidateId}')">Skip</button>
      </div>
    </div>
  `;
}

async function uploadCloseup(candidateId, input) {
  const file = input.files[0];
  if (!file) return;

  const form = new FormData();
  form.append('file', file);

  try {
    const r = await fetch(`/api/candidates/${candidateId}/closeup`, {
      method: 'POST',
      body: form,
    });
    if (!r.ok) throw new Error('Upload failed');

    const prompt = document.getElementById(`closeup-${candidateId}`);
    prompt.innerHTML = '<p class="text-muted" style="font-size:.85rem">Close-up uploaded!</p>';
  } catch (e) {
    alert('Failed to upload close-up: ' + e.message);
  }
}

function skipCloseup(candidateId) {
  const prompt = document.getElementById(`closeup-${candidateId}`);
  prompt.remove();
}

function checkAllReviewed() {
  const allReviewed = allCandidates.every(c => c.tenant_response);
  if (allReviewed && allCandidates.length > 0) {
    const div = document.getElementById('comparison-content');
    // Check if already showing done message
    if (!document.getElementById('all-reviewed-msg')) {
      const doneCard = document.createElement('div');
      doneCard.className = 'card';
      doneCard.id = 'all-reviewed-msg';
      doneCard.style.background = '#dcfce7';
      doneCard.innerHTML = `
        <h2 style="color:var(--success)">All Items Reviewed</h2>
        <p class="text-muted">Your responses have been recorded. The report is being prepared for owner review.</p>
      `;
      div.appendChild(doneCard);
    }

    // Auto-finalize session
    if (sessionId) {
      finalizeSession();
    }
  }
}

async function finalizeSession() {
  try {
    // Mark session as submitted (all candidates reviewed by tenant)
    // Link stays active until owner publishes or time expires
    await fetch(`/api/sessions/${sessionId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_status: 'pending_review' }),
    });
  } catch (e) {
    // Non-critical
  }
}
