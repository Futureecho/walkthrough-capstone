/* capture.js — Camera access, guided capture, upload, WebSocket status */

const GUIDED_POSITIONS = [
  'center-from-door', 'center-opposite-wall',
  'corner-left-near', 'corner-right-near',
  'corner-left-far', 'corner-right-far',
  'ceiling', 'floor',
];

let sessionId = null;
let roomName = null;
let captureId = null;
let currentPosition = 0;
let ws = null;
let stream = null;

// Ghost overlay state
let ghostMap = {};      // orientation_hint → thumbnail_url
let ghostVisible = true;

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  sessionId = params.get('session');
  roomName = params.get('room');

  if (!sessionId || !roomName) {
    alert('Missing session or room parameter');
    window.location.href = '/';
    return;
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
});

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
    const r = await fetch('/api/captures', {
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
      // Already handled locally
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
  const hint = currentPosition < GUIDED_POSITIONS.length
    ? GUIDED_POSITIONS[currentPosition] : `extra-${currentPosition + 1}`;

  // Upload
  const form = new FormData();
  form.append('file', blob, `photo_${currentPosition + 1}.jpg`);
  form.append('orientation_hint', hint);

  try {
    const r = await fetch(`/api/captures/${captureId}/images`, {
      method: 'POST',
      body: form,
    });
    const data = await r.json();

    // Add thumbnail
    addThumbnail(data.thumbnail_path, data.seq, data.id);
    currentPosition++;
    updateGuideLabel();
    updateGhostImage();
    updatePhotoCount();
  } catch (e) {
    alert('Upload failed: ' + e.message);
  }
}

function addThumbnail(thumbPath, seq, imageId) {
  const grid = document.getElementById('thumbnails');
  const wrapper = document.createElement('div');
  wrapper.className = 'thumb-wrapper';
  wrapper.dataset.imageId = imageId || '';
  wrapper.dataset.seq = seq;
  const img = document.createElement('img');
  img.src = '/' + thumbPath;
  img.alt = `Photo ${seq}`;
  img.className = 'quality-pending';
  wrapper.appendChild(img);
  grid.appendChild(wrapper);
}

function updateGuideLabel() {
  const label = document.getElementById('guide-label');
  if (currentPosition < GUIDED_POSITIONS.length) {
    label.textContent = `${GUIDED_POSITIONS[currentPosition]} (${currentPosition + 1}/8)`;
  } else {
    label.textContent = `Extra photo ${currentPosition + 1}`;
  }
}

function updatePhotoCount() {
  document.getElementById('photo-count').textContent = `${currentPosition} / 8`;
  if (currentPosition >= 1) {
    document.getElementById('submit-btn').classList.remove('hidden');
  }
  if (currentPosition >= 8) {
    document.getElementById('capture-subtitle').textContent = 'All 8 positions captured! Add extras or submit.';
  }
}

async function submitCapture() {
  if (!captureId) return;
  document.getElementById('submit-btn').disabled = true;
  document.getElementById('submit-btn').textContent = 'Processing...';

  try {
    await fetch(`/api/captures/${captureId}/submit`, { method: 'POST' });
    // Results come via WebSocket
  } catch (e) {
    alert('Submit failed: ' + e.message);
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Submit for Review';
  }
}

function showQualityResults(data) {
  const card = document.getElementById('quality-card');
  card.classList.remove('hidden');
  const results = document.getElementById('quality-results');
  results.innerHTML = '';

  const images = data.images || {};
  let imgIndex = 0;
  for (const [imgId, info] of Object.entries(images)) {
    imgIndex++;
    const status = info.status === 'accepted' ? 'passed' : 'failed';
    const badge = status === 'passed' ? 'badge-success' : 'badge-danger';
    const div = document.createElement('div');
    div.className = 'mb-1';
    let html = `
      <div class="flex-between">
        <span class="text-muted">Photo ${imgIndex}</span>
        <span class="badge ${badge}">${info.status}</span>
      </div>
    `;
    // Show rejection reasons and tips
    if (info.reasons && info.reasons.length > 0) {
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
    }
    div.innerHTML = html;
    results.appendChild(div);
  }

  // Update thumbnail borders and add delete buttons for rejected
  const wrappers = document.querySelectorAll('#thumbnails .thumb-wrapper');
  const imgEntries = Object.entries(images);
  wrappers.forEach((wrapper, i) => {
    if (i < imgEntries.length) {
      const [imgId, info] = imgEntries[i];
      const img = wrapper.querySelector('img');
      const status = info.status === 'accepted' ? 'quality-passed' : 'quality-failed';
      img.className = status;
      wrapper.dataset.imageId = imgId;

      // Add delete button for rejected images
      if (info.status === 'rejected' && !wrapper.querySelector('.delete-btn')) {
        const btn = document.createElement('button');
        btn.className = 'delete-btn';
        btn.textContent = '\u00D7';
        btn.title = 'Delete and retake';
        btn.onclick = (e) => { e.stopPropagation(); deleteImage(imgId, wrapper); };
        wrapper.appendChild(btn);
      }
    }
  });
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
  }
}

async function deleteImage(imageId, wrapper) {
  if (!captureId) return;
  try {
    const r = await fetch(`/api/captures/${captureId}/images/${imageId}`, { method: 'DELETE' });
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
    // Fetch session to get property_id and type
    const sr = await fetch(`/api/sessions/${sessionId}`);
    if (!sr.ok) return;
    const sess = await sr.json();
    if (sess.type !== 'move_out') return;

    // Fetch reference images from the move-in session
    const rr = await fetch(
      `/api/captures/reference-images?property_id=${encodeURIComponent(sess.property_id)}&room=${encodeURIComponent(roomName)}`
    );
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
  const hint = currentPosition < GUIDED_POSITIONS.length
    ? GUIDED_POSITIONS[currentPosition] : null;
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
  img.style.opacity = ghostVisible ? '0.15' : '0';
  btn.classList.toggle('ghost-toggle-off', !ghostVisible);
}

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  if (ws) ws.close();
  if (stream) stream.getTracks().forEach(t => t.stop());
});
