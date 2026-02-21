/* comparison.js — Display comparison results and candidate follow-ups */

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const compId = params.get('id');
  if (!compId) return;

  try {
    const r = await fetch(`/api/comparisons/${compId}`);
    if (!r.ok) throw new Error('Comparison not found');
    const comp = await r.json();
    renderComparison(comp);
  } catch (e) {
    document.getElementById('comparison-content').innerHTML =
      `<p class="text-muted">Error: ${e.message}</p>`;
  }
});

function renderComparison(comp) {
  const div = document.getElementById('comparison-content');
  div.innerHTML = `
    <div class="flex-between mb-1">
      <h2>${comp.room}</h2>
      <span class="badge badge-info">${comp.status}</span>
    </div>
  `;

  if (!comp.candidates || comp.candidates.length === 0) {
    div.innerHTML += '<p class="text-muted mt-2">No candidate differences identified.</p>';
    return;
  }

  comp.candidates.forEach((cand, i) => {
    const confPct = Math.round(cand.confidence * 100);
    const statusClass = cand.tenant_response === 'confirm' ? 'badge-danger'
      : cand.tenant_response === 'disagree' ? 'badge-success' : 'badge-warning';

    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="flex-between mb-1">
        <strong>Candidate #${i + 1}</strong>
        <span class="badge ${statusClass}">${cand.followup_status}</span>
      </div>
      <p class="text-muted">Confidence: ${confPct}%</p>
      ${cand.reason_codes ? `<p class="text-muted">Indicators: ${cand.reason_codes.join(', ')}</p>` : ''}
      ${cand.crop_path ? `<img src="/${cand.crop_path}" alt="Candidate region" style="max-width:100%;margin:.5rem 0">` : ''}
      ${cand.tenant_response
        ? `<p>Tenant: <strong>${cand.tenant_response}</strong>${cand.tenant_comment ? ' — ' + cand.tenant_comment : ''}</p>`
        : renderFollowupForm(cand.id)
      }
    `;
    div.appendChild(card);
  });
}

function renderFollowupForm(candidateId) {
  return `
    <div class="mt-1" id="form-${candidateId}">
      <textarea id="comment-${candidateId}" placeholder="Optional comment" rows="2"
        style="width:100%;padding:.5rem;border:1px solid var(--border);border-radius:4px;font-size:.9rem;margin-bottom:.5rem"></textarea>
      <div class="flex gap-1">
        <button class="btn btn-success" style="flex:1;padding:.5rem" onclick="respond('${candidateId}','confirm')">Confirm</button>
        <button class="btn btn-outline" style="flex:1;padding:.5rem" onclick="respond('${candidateId}','disagree')">Disagree</button>
      </div>
    </div>
  `;
}

async function respond(candidateId, response) {
  const comment = document.getElementById(`comment-${candidateId}`)?.value || '';
  try {
    const r = await fetch(`/api/candidates/${candidateId}/response`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response, comment }),
    });
    if (!r.ok) throw new Error('Failed');
    const form = document.getElementById(`form-${candidateId}`);
    form.innerHTML = `<p>Tenant: <strong>${response}</strong>${comment ? ' — ' + comment : ''}</p>`;
  } catch (e) {
    alert('Failed to submit response: ' + e.message);
  }
}
