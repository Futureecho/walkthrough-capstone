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
    addThumbnail(data.thumbnail_path, data.seq);
    currentPosition++;
    updateGuideLabel();
    updatePhotoCount();
  } catch (e) {
    alert('Upload failed: ' + e.message);
  }
}

function addThumbnail(thumbPath, seq) {
  const grid = document.getElementById('thumbnails');
  const img = document.createElement('img');
  img.src = '/' + thumbPath;
  img.alt = `Photo ${seq}`;
  img.className = 'quality-pending';
  img.dataset.seq = seq;
  grid.appendChild(img);
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
  for (const [imgId, info] of Object.entries(images)) {
    const status = info.status === 'accepted' ? 'passed' : 'failed';
    const badge = status === 'passed' ? 'badge-success' : 'badge-danger';
    const div = document.createElement('div');
    div.className = 'flex-between mb-1';
    div.innerHTML = `
      <span class="text-muted">Image</span>
      <span class="badge ${badge}">${info.status}</span>
    `;
    results.appendChild(div);
  }

  // Update thumbnail borders
  const thumbs = document.querySelectorAll('#thumbnails img');
  const imgEntries = Object.entries(images);
  thumbs.forEach((img, i) => {
    if (i < imgEntries.length) {
      const status = imgEntries[i][1].status === 'accepted' ? 'quality-passed' : 'quality-failed';
      img.className = status;
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

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  if (ws) ws.close();
  if (stream) stream.getTracks().forEach(t => t.stop());
});
