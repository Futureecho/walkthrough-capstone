/* capture.js — Camera access, guided capture, upload, WebSocket status */

// Default fallback positions (used when no room template)
const DEFAULT_POSITIONS = [
  'center-from-door', 'center-opposite-wall',
  'corner-left-near', 'corner-right-near',
  'corner-left-far', 'corner-right-far',
  'ceiling', 'floor',
];

// Dynamic positions — loaded from room template if available
let guidedPositions = [...DEFAULT_POSITIONS];

let sessionId = null;
let roomName = null;
let captureId = null;
let currentPosition = 0;
let ws = null;
let stream = null;
let tenantToken = null;

// Quality retry tracking
let failureCounts = {};       // position index → number of quality failures
let forceAccepted = new Set(); // position indices that were force-accepted
let pendingRetakes = [];      // position indices that need retaking

// Ghost overlay state
let ghostMap = {};      // orientation_hint → thumbnail_url
let ghostVisible = true;
let roomTemplateId = null; // cached from room template lookup

// Helper: append token query param for tenant auth
function tokenParam(sep = '?') {
  return tenantToken ? `${sep}token=${encodeURIComponent(tenantToken)}` : '';
}

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  sessionId = params.get('session');
  roomName = params.get('room');
  tenantToken = params.get('token');

  if (!sessionId || !roomName) {
    alert('Missing session or room parameter');
    window.location.href = '/';
    return;
  }

  // If token provided, load room template positions dynamically
  if (tenantToken) {
    await loadRoomTemplatePositions();
  }

  document.getElementById('room-title').textContent = roomName;
  updateGuideLabel();

  // Start camera
  await startCamera();

  // Create capture record
  await createCapture();

  // Load ghost overlay for move-out sessions
  await loadGhostOverlay();

  // Connect WebSocket
  connectWebSocket();

  // Button handlers
  document.getElementById('capture-btn').addEventListener('click', capturePhoto);
  document.getElementById('submit-btn').addEventListener('click', submitCapture);
  document.getElementById('force-submit-btn').addEventListener('click', forceSubmit);

  // Fix back link for tenant flow
  if (tenantToken) {
    document.getElementById('back-link').href = `/inspect/${tenantToken}`;
  }
});

async function loadRoomTemplatePositions() {
  if (!tenantToken) return;
  try {
    const r = await fetch(`/api/tenant/rooms?token=${encodeURIComponent(tenantToken)}`);
    if (!r.ok) return;
    const rooms = await r.json();

    // Find matching room template by name
    const template = rooms.find(rt => rt.name === roomName);
    if (template) {
      roomTemplateId = template.id;
      if (template.positions && template.positions.length > 0) {
        guidedPositions = template.positions.map(p => p.hint || p.label);
      }
    }
  } catch (e) {
    // Fall back to defaults
  }
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1920 },
        height: { ideal: 1440 },
      },
      audio: false,
    });
    document.getElementById('camera').srcObject = stream;
  } catch (e) {
    alert('Camera access denied: ' + e.message);
  }
}

async function createCapture() {
  try {
    const r = await fetch(`/api/captures${tokenParam()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, room: roomName }),
    });
    const data = await r.json();
    captureId = data.id;
  } catch (e) {
    alert('Failed to create capture: ' + e.message);
  }
}

function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/api/ws/${sessionId}`);

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    handleWSMessage(msg);
  };

  ws.onclose = () => {
    // Reconnect after 2s
    setTimeout(connectWebSocket, 2000);
  };
}

function handleWSMessage(msg) {
  if (msg.capture_id !== captureId) return;

  switch (msg.event) {
    case 'image_uploaded':
      break;
    case 'quality_update':
      showQualityResults(msg.data);
      break;
    case 'coverage_update':
      showCoverageResults(msg.data);
      break;
    case 'error':
      alert('Error: ' + (msg.data?.message || 'Unknown error'));
      break;
  }
}

async function capturePhoto() {
  if (!stream || !captureId) return;

  const video = document.getElementById('camera');
  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  // Convert to blob
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
  const hint = currentPosition < guidedPositions.length
    ? guidedPositions[currentPosition] : `extra-${currentPosition + 1}`;

  // Upload
  const form = new FormData();
  form.append('file', blob, `photo_${currentPosition + 1}.jpg`);
  form.append('orientation_hint', hint);
  if (tenantToken) form.append('token', tenantToken);

  try {
    const r = await fetch(`/api/captures/${captureId}/images${tokenParam()}`, {
      method: 'POST',
      body: form,
    });
    const data = await r.json();

    // Add thumbnail (yellow border if force-accepted position)
    const cssClass = forceAccepted.has(currentPosition) ? 'quality-warning' : 'quality-pending';
    addThumbnail(data.thumbnail_path, data.seq, data.id, cssClass);

    // Clear retake prompt if we just retook a photo
    hideRetakePrompt();

    currentPosition++;
    updateGuideLabel();
    updateGhostImage();
    updatePhotoCount();
  } catch (e) {
    alert('Upload failed: ' + e.message);
  }
}

function addThumbnail(thumbPath, seq, imageId, cssClass) {
  const grid = document.getElementById('thumbnails');
  const wrapper = document.createElement('div');
  wrapper.className = 'thumb-wrapper';
  wrapper.dataset.imageId = imageId || '';
  wrapper.dataset.seq = seq;
  const img = document.createElement('img');
  img.src = '/' + thumbPath;
  img.alt = `Photo ${seq}`;
  img.className = cssClass || 'quality-pending';
  wrapper.appendChild(img);
  grid.appendChild(wrapper);
}

function updateGuideLabel() {
  const label = document.getElementById('guide-label');
  const total = guidedPositions.length;
  if (currentPosition < total) {
    const posLabel = guidedPositions[currentPosition];
    label.textContent = `${posLabel} (${currentPosition + 1}/${total})`;
  } else {
    label.textContent = `Extra photo ${currentPosition + 1}`;
  }
}

function updatePhotoCount() {
  const total = guidedPositions.length;
  document.getElementById('photo-count').textContent = `${currentPosition} / ${total}`;
  if (currentPosition >= 1) {
    document.getElementById('submit-btn').classList.remove('hidden');
  }
  if (currentPosition >= total) {
    document.getElementById('capture-subtitle').textContent = `All ${total} positions captured! Add extras or submit.`;
  }
}

async function submitCapture() {
  if (!captureId) return;
  document.getElementById('submit-btn').disabled = true;
  document.getElementById('submit-btn').textContent = 'Processing...';
  document.getElementById('force-submit-btn').classList.add('hidden');
  hideRetakePrompt();

  try {
    await fetch(`/api/captures/${captureId}/submit${tokenParam()}`, { method: 'POST' });
    // Results come via WebSocket, but poll as fallback for mobile Safari
    startResultPolling();
  } catch (e) {
    alert('Submit failed: ' + e.message);
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit for Review';
  }
}

let pollingTimer = null;
let pollingAttempts = 0;

function startResultPolling() {
  pollingAttempts = 0;
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(pollCaptureStatus, 2000);
}

async function pollCaptureStatus() {
  pollingAttempts++;
  if (pollingAttempts > 30) {
    clearInterval(pollingTimer);
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit for Review';
    alert('Processing timed out. Please try submitting again.');
    return;
  }

  try {
    const r = await fetch(`/api/captures/${captureId}/status${tokenParam()}`);
    if (!r.ok) return;
    const data = await r.json();

    // Still processing — keep polling
    if (data.status === 'processing') return;

    // Got results — stop polling
    clearInterval(pollingTimer);

    if (data.metrics_json && data.metrics_json.images) {
      // Quality results available — show them if not already shown
      if (!document.querySelector('#quality-results .mb-1')) {
        showQualityResults(data.metrics_json);
      }
    }

    if (data.coverage_json && data.coverage_json.coverage_pct !== undefined) {
      if (!document.querySelector('#coverage-card:not(.hidden)')) {
        showCoverageResults(data.coverage_json);
      }
    }

    // If status is failed and no quality card shown yet, show results from metrics
    if (data.status === 'failed' && data.metrics_json) {
      if (!document.querySelector('#quality-results .mb-1')) {
        showQualityResults(data.metrics_json);
      }
    }

    // If passed/needs_coverage but submit still says Processing, update it
    if (data.status === 'passed' || data.status === 'needs_coverage') {
      if (!data.coverage_json) {
        // Coverage not done yet, keep polling
        pollingTimer = setInterval(pollCaptureStatus, 2000);
      }
    }
  } catch (e) {
    // Network error — keep polling
  }
}

async function forceSubmit() {
  // Mark all pending retakes as force-accepted
  pendingRetakes.forEach(posIdx => {
    forceAccepted.add(posIdx);
  });
  pendingRetakes = [];

  // Update thumbnails to yellow for force-accepted
  const wrappers = document.querySelectorAll('#thumbnails .thumb-wrapper');
  wrappers.forEach(wrapper => {
    const img = wrapper.querySelector('img');
    if (img && img.classList.contains('quality-failed')) {
      img.className = 'quality-warning';
    }
  });

  // Submit
  document.getElementById('force-submit-btn').classList.add('hidden');
  hideRetakePrompt();
  await submitCapture();
}

function showQualityResults(data) {
  const card = document.getElementById('quality-card');
  card.classList.remove('hidden');
  const results = document.getElementById('quality-results');
  results.innerHTML = '';

  const images = data.images || {};
  let failedPositions = [];
  let imgIndex = 0;

  for (const [imgId, info] of Object.entries(images)) {
    imgIndex++;
    const isForced = forceAccepted.has(imgIndex - 1);
    const status = info.status === 'accepted' ? 'passed' : (isForced ? 'warning' : 'failed');
    const badge = status === 'passed' ? 'badge-success'
      : status === 'warning' ? 'badge-warning' : 'badge-danger';
    const statusLabel = status === 'warning' ? 'accepted (warning)' : info.status;

    const div = document.createElement('div');
    div.className = 'mb-1';
    let html = `
      <div class="flex-between">
        <span class="text-muted">Photo ${imgIndex}</span>
        <span class="badge ${badge}">${statusLabel}</span>
      </div>
    `;
    if (info.reasons && info.reasons.length > 0 && !isForced) {
      html += '<div class="quality-reasons">';
      for (const r of info.reasons) {
        html += `
          <div class="quality-reason">
            <strong>${r.issue}</strong>
            <span class="text-muted"> — ${r.detail}</span>
            <div class="quality-tip">${r.tip}</div>
          </div>
        `;
      }
      html += '</div>';

      // Track this as a failed position
      failedPositions.push({ index: imgIndex - 1, imgId, reasons: info.reasons });
    }
    div.innerHTML = html;
    results.appendChild(div);
  }

  // Update thumbnail borders
  const wrappers = document.querySelectorAll('#thumbnails .thumb-wrapper');
  const imgEntries = Object.entries(images);
  wrappers.forEach((wrapper, i) => {
    if (i < imgEntries.length) {
      const [imgId, info] = imgEntries[i];
      const img = wrapper.querySelector('img');
      const isForced = forceAccepted.has(i);
      if (info.status === 'accepted') {
        img.className = 'quality-passed';
      } else if (isForced) {
        img.className = 'quality-warning';
      } else {
        img.className = 'quality-failed';
      }
      wrapper.dataset.imageId = imgId;
    }
  });

  // Handle failures — auto-delete and prompt retake
  if (failedPositions.length > 0) {
    handleQualityFailures(failedPositions);
  } else {
    // All passed (or force-accepted) — re-enable submit
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit for Review';
  }
}

async function handleQualityFailures(failedPositions) {
  // Increment failure counts
  const retakeNeeded = [];
  const canForce = [];

  for (const fp of failedPositions) {
    failureCounts[fp.index] = (failureCounts[fp.index] || 0) + 1;
    if (failureCounts[fp.index] >= 2) {
      canForce.push(fp);
    }
    retakeNeeded.push(fp);
  }

  // Auto-delete failed images and reset position
  for (const fp of retakeNeeded) {
    if (canForce.includes(fp)) continue; // Don't auto-delete if force is available
    const wrapper = document.querySelector(`#thumbnails .thumb-wrapper[data-image-id="${fp.imgId}"]`);
    if (wrapper) {
      try {
        await fetch(`/api/captures/${captureId}/images/${fp.imgId}${tokenParam()}`, { method: 'DELETE' });
        wrapper.remove();
        currentPosition--;
      } catch (e) { /* continue */ }
    }
  }

  // Set position back to first failed position that needs retake
  const firstRetake = retakeNeeded.find(fp => !canForce.includes(fp));
  if (firstRetake) {
    currentPosition = firstRetake.index;
    updateGuideLabel();
    updateGhostImage();
    updatePhotoCount();

    // Show retake prompt
    const reason = firstRetake.reasons.map(r => r.issue).join(', ');
    showRetakePrompt(`Photo ${firstRetake.index + 1} (${guidedPositions[firstRetake.index] || 'position'}) failed: ${reason}`);
  }

  // Re-enable submit button
  document.getElementById('submit-btn').disabled = false;
  document.getElementById('submit-btn').textContent = 'Submit for Review';

  // Show force submit if any position has 2+ failures
  pendingRetakes = canForce.map(fp => fp.index);
  if (canForce.length > 0) {
    document.getElementById('force-submit-btn').classList.remove('hidden');
    if (!firstRetake || retakeNeeded.every(fp => canForce.includes(fp))) {
      // All failures are force-eligible, show prompt
      showRetakePrompt(`Photos failed quality check twice. You can retake or force submit with warnings.`);
    }
  }
}

function showRetakePrompt(msg) {
  const prompt = document.getElementById('retake-prompt');
  document.getElementById('retake-reason').textContent = msg;
  prompt.classList.remove('hidden');
}

function hideRetakePrompt() {
  document.getElementById('retake-prompt').classList.add('hidden');
}

function showCoverageResults(data) {
  const card = document.getElementById('coverage-card');
  card.classList.remove('hidden');
  document.getElementById('coverage-fill').style.width = data.coverage_pct + '%';
  document.getElementById('coverage-text').textContent = `${data.coverage_pct}% coverage`;

  const instDiv = document.getElementById('coverage-instructions');
  instDiv.innerHTML = '';
  if (data.instructions && data.instructions.length > 0) {
    data.instructions.forEach(inst => {
      const p = document.createElement('p');
      p.className = 'text-muted';
      p.textContent = inst;
      instDiv.appendChild(p);
    });
  } else {
    instDiv.innerHTML = '<p class="text-muted">Coverage complete!</p>';
  }

  // Re-enable submit for additional photos if needed
  if (!data.complete) {
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit for Review';
    document.getElementById('capture-subtitle').textContent = 'More photos needed — see coverage below';
  } else {
    document.getElementById('submit-btn').textContent = 'Done!';
    document.getElementById('capture-subtitle').textContent = 'Quality and coverage passed!';

    // If tenant flow, navigate back to tenant landing after delay
    if (tenantToken) {
      setTimeout(() => {
        window.location.href = `/inspect/${tenantToken}`;
      }, 2000);
    }
  }
}

async function deleteImage(imageId, wrapper) {
  if (!captureId) return;
  try {
    const r = await fetch(`/api/captures/${captureId}/images/${imageId}${tokenParam()}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Delete failed');
    wrapper.remove();
    currentPosition--;
    updatePhotoCount();
    updateGhostImage();
  } catch (e) {
    alert('Failed to delete image: ' + e.message);
  }
}

// ── Ghost overlay ────────────────────────────────────────

async function loadGhostOverlay() {
  if (!sessionId || !roomName) return;
  try {
    // Fetch session to get property_id
    const sr = await fetch(`/api/sessions/${sessionId}${tokenParam()}`);
    if (!sr.ok) return;
    const sess = await sr.json();

    // Fetch reference images (owner refs for all types, move-in fallback for move-out)
    let url = `/api/captures/reference-images?property_id=${encodeURIComponent(sess.property_id)}&room=${encodeURIComponent(roomName)}`;
    if (roomTemplateId) url += `&room_template_id=${encodeURIComponent(roomTemplateId)}`;
    url += tokenParam('&');
    const rr = await fetch(url);
    if (!rr.ok) return;
    const refs = await rr.json();
    if (!refs.length) return;

    // Build hint → url map
    ghostMap = {};
    refs.forEach(r => { ghostMap[r.orientation_hint] = r.thumbnail_url; });

    // Create overlay image
    const viewfinder = document.getElementById('viewfinder');
    const img = document.createElement('img');
    img.id = 'ghost-overlay';
    img.alt = 'Reference overlay';
    viewfinder.appendChild(img);

    // Create toggle button
    const btn = document.createElement('button');
    btn.id = 'ghost-toggle';
    btn.title = 'Toggle reference overlay';
    btn.textContent = '\u{1F441}';
    btn.addEventListener('click', toggleGhost);
    viewfinder.appendChild(btn);

    // Set initial ghost image
    updateGhostImage();
  } catch (e) {
    // Ghost overlay is non-critical; fail silently
  }
}

function updateGhostImage() {
  const img = document.getElementById('ghost-overlay');
  if (!img) return;
  const hint = currentPosition < guidedPositions.length
    ? guidedPositions[currentPosition] : null;
  if (hint && ghostMap[hint]) {
    img.src = ghostMap[hint];
    img.style.display = '';
  } else {
    img.style.display = 'none';
  }
}

function toggleGhost() {
  const img = document.getElementById('ghost-overlay');
  const btn = document.getElementById('ghost-toggle');
  if (!img || !btn) return;
  ghostVisible = !ghostVisible;
  img.style.opacity = ghostVisible ? '0.30' : '0';
  btn.classList.toggle('ghost-toggle-off', !ghostVisible);
}

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  if (ws) ws.close();
  if (stream) stream.getTracks().forEach(t => t.stop());
});
