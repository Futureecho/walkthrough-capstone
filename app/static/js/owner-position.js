/* owner-position.js — Position builder with camera viewfinder + alignment assist */

let propertyId = null;
let roomId = null;
let editIndex = null; // null = add mode, number = edit mode
let roomData = null;  // full room template object
let stream = null;
let capturedBlob = null;
let capturedUrl = null; // object URL for the accepted capture
let ghostActive = false;
let existingRefImage = null; // {id, thumbnail_url} when editing

// States: 'live' | 'frozen' | 'accepted'
let viewState = 'live';

// Alignment assist state
let alignCanvas = null;
let alignCtx = null;
let refGray = null;        // Float32Array of grayscale reference pixels
let alignInterval = null;
let goodFrames = 0;        // consecutive frames above threshold
const ALIGN_W = 64;
const ALIGN_H = 48;
const ALIGN_THRESHOLD = 0.95;  // NCC score to consider "aligned"
const AUTO_CAPTURE_FRAMES = 4; // ~1.2s of good alignment before auto-capture

const params = new URLSearchParams(window.location.search);

document.addEventListener('DOMContentLoaded', async () => {
  propertyId = params.get('property');
  roomId = params.get('room');
  editIndex = params.get('index') !== null ? parseInt(params.get('index'), 10) : null;

  if (!propertyId || !roomId) {
    alert('Missing room or property parameter');
    window.location.href = '/owner/properties';
    return;
  }

  // Wire up buttons
  document.getElementById('capture-btn').addEventListener('click', capturePhoto);
  document.getElementById('accept-btn').addEventListener('click', acceptPhoto);
  document.getElementById('retake-btn').addEventListener('click', retake);
  document.getElementById('ghost-btn').addEventListener('click', toggleTestGhost);
  document.getElementById('save-btn').addEventListener('click', savePosition);
  document.getElementById('discard-btn').addEventListener('click', discard);
  document.getElementById('discard-btn-top').addEventListener('click', discard);
  document.getElementById('position-name').addEventListener('input', onNameInput);

  // Prep alignment canvas (offscreen)
  alignCanvas = document.createElement('canvas');
  alignCanvas.width = ALIGN_W;
  alignCanvas.height = ALIGN_H;
  alignCtx = alignCanvas.getContext('2d', { willReadFrequently: true });

  await loadRoomData();
  await startCamera();
});

async function loadRoomData() {
  try {
    const r = await fetch(`/api/owner/properties/${propertyId}`);
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    if (!r.ok) throw new Error('Failed to load property');
    const prop = await r.json();

    roomData = (prop.room_templates || []).find(rt => rt.id === roomId);
    if (!roomData) {
      alert('Room template not found');
      discard();
      return;
    }

    document.getElementById('room-subtitle').textContent = roomData.name;

    // If editing, populate fields and show existing ref in viewfinder
    if (editIndex !== null && roomData.positions && roomData.positions[editIndex]) {
      const pos = roomData.positions[editIndex];
      document.getElementById('position-name').value = pos.label || '';
      onNameInput();

      const hint = pos.hint || pos.label;
      const refImages = roomData.reference_images || [];
      const ref = refImages.find(img => img.position_hint === hint);
      if (ref && ref.thumbnail_url) {
        existingRefImage = ref;
        capturedUrl = ref.thumbnail_url;
        setAcceptedState(ref.thumbnail_url);
      }
    }
  } catch (e) {
    document.getElementById('room-subtitle').textContent = 'Error loading room';
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
    document.getElementById('viewfinder').innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:var(--text-muted);font-size:.9rem;padding:1rem;text-align:center">
        Camera not available.<br>Use a mobile device to capture reference photos.
      </div>
    `;
  }
}

function onNameInput() {
  const name = document.getElementById('position-name').value.trim();
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  document.getElementById('guide-label').textContent = slug || 'position name';
  updateSaveState();
}

function updateSaveState() {
  const name = document.getElementById('position-name').value.trim();
  document.getElementById('save-btn').disabled = !name;
}

// ── Capture flow: live → frozen → accepted ───────────────

function capturePhoto() {
  const video = document.getElementById('camera');
  if (!video || !stream) return;

  stopAlignment();

  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  canvas.toBlob(blob => {
    capturedBlob = blob;
    existingRefImage = null;
    const url = URL.createObjectURL(blob);

    // Freeze: show still in viewfinder, hide video
    const frozen = document.getElementById('frozen-frame');
    frozen.src = url;
    frozen.style.display = 'block';
    document.getElementById('camera').style.display = 'none';

    // Swap buttons: hide Capture + Save/Discard + Ghost, show Accept/Retake
    document.getElementById('capture-btn').classList.add('hidden');
    document.getElementById('review-btns').classList.remove('hidden');
    document.getElementById('ghost-btn').classList.add('hidden');
    document.getElementById('bottom-btns').classList.add('hidden');
    removeGhostOverlay();
    hideAlignmentRing();

    viewState = 'frozen';
  }, 'image/jpeg', 0.92);
}

function acceptPhoto() {
  // Store the captured URL for ghost overlay use
  capturedUrl = document.getElementById('frozen-frame').src;

  // Keep frozen frame visible — don't resume live camera yet
  // Swap buttons: hide Accept/Retake, show Capture + Ghost + Save/Discard
  document.getElementById('review-btns').classList.add('hidden');
  document.getElementById('capture-btn').classList.remove('hidden');
  document.getElementById('ghost-btn').classList.remove('hidden');
  document.getElementById('bottom-btns').classList.remove('hidden');

  viewState = 'accepted';
  updateSaveState();
}

function retake() {
  capturedBlob = null;
  capturedUrl = null;
  existingRefImage = null;

  resumeLiveCamera();

  document.getElementById('ghost-btn').classList.add('hidden');
  removeGhostOverlay();
  stopAlignment();
  hideAlignmentRing();

  viewState = 'live';
  updateSaveState();
}

function resumeLiveCamera() {
  document.getElementById('frozen-frame').style.display = 'none';
  document.getElementById('camera').style.display = '';

  document.getElementById('capture-btn').classList.remove('hidden');
  document.getElementById('review-btns').classList.add('hidden');
  document.getElementById('bottom-btns').classList.remove('hidden');
}

function setAcceptedState(url) {
  // Used when editing with an existing ref image
  capturedUrl = url;
  document.getElementById('ghost-btn').classList.remove('hidden');
  viewState = 'accepted';
  updateSaveState();
}

// ── Ghost overlay on the viewfinder ──────────────────────

function toggleTestGhost() {
  const viewfinder = document.getElementById('viewfinder');
  const existing = viewfinder.querySelector('#ghost-overlay');

  if (existing) {
    // Turn off ghost — go back to frozen frame if we have one
    removeGhostOverlay();
    stopAlignment();
    hideAlignmentRing();

    // If we had a capture, show frozen frame again
    if (capturedUrl && viewState === 'accepted') {
      document.getElementById('frozen-frame').src = capturedUrl;
      document.getElementById('frozen-frame').style.display = 'block';
      document.getElementById('camera').style.display = 'none';
    }
    return;
  }

  if (!capturedUrl) return;

  // Switch to live camera with ghost overlay
  document.getElementById('frozen-frame').style.display = 'none';
  document.getElementById('camera').style.display = '';

  const img = document.createElement('img');
  img.id = 'ghost-overlay';
  img.alt = 'Ghost reference overlay';
  img.src = capturedUrl;
  viewfinder.appendChild(img);
  ghostActive = true;
  document.getElementById('ghost-btn').textContent = 'Hide Ghost Overlay';

  // Start alignment comparison
  prepareRefData(capturedUrl);
}

function removeGhostOverlay() {
  const existing = document.getElementById('ghost-overlay');
  if (existing) existing.remove();
  ghostActive = false;
  document.getElementById('ghost-btn').textContent = 'Test Ghost Overlay';
}

// ── Alignment assist (NCC on downscaled grayscale) ───────

function prepareRefData(url) {
  const img = new Image();
  if (!url.startsWith('blob:')) img.crossOrigin = 'anonymous';
  img.onload = () => {
    try {
      alignCtx.drawImage(img, 0, 0, ALIGN_W, ALIGN_H);
      const data = alignCtx.getImageData(0, 0, ALIGN_W, ALIGN_H);
      refGray = toGrayscale(data);
      goodFrames = 0;
      startAlignment();
      showAlignStatus('Alignment active');
    } catch (e) {
      showAlignStatus('Canvas error: ' + e.message);
    }
  };
  img.onerror = () => {
    showAlignStatus('Ref image failed to load');
  };
  img.src = url;
}

function showAlignStatus(msg) {
  const viewfinder = document.getElementById('viewfinder');
  let el = viewfinder.querySelector('#align-status');
  if (!el) {
    el = document.createElement('div');
    el.id = 'align-status';
    el.style.cssText = 'position:absolute;top:.5rem;right:.5rem;background:rgba(0,0,0,.7);color:#0f0;padding:.2rem .4rem;border-radius:4px;font-size:.7rem;z-index:12';
    viewfinder.appendChild(el);
  }
  el.textContent = msg;
  // Auto-hide after 3s
  setTimeout(() => { if (el.textContent === msg) el.remove(); }, 3000);
}

function startAlignment() {
  // Clear any existing interval but keep refGray (it was just set by caller)
  if (alignInterval) clearInterval(alignInterval);
  goodFrames = 0;
  alignInterval = setInterval(compareFrame, 300);
}

function stopAlignment() {
  if (alignInterval) { clearInterval(alignInterval); alignInterval = null; }
  refGray = null;
  goodFrames = 0;
}

function compareFrame() {
  const video = document.getElementById('camera');
  if (!video || video.paused || !refGray || !ghostActive) return;
  if (video.style.display === 'none') return;

  // Grab current frame, downscale, grayscale
  alignCtx.drawImage(video, 0, 0, ALIGN_W, ALIGN_H);
  const data = alignCtx.getImageData(0, 0, ALIGN_W, ALIGN_H);
  const liveGray = toGrayscale(data);

  const score = ncc(refGray, liveGray);
  const lighting = checkLighting(liveGray);
  const focus = checkFocus(liveGray, ALIGN_W, ALIGN_H);

  // Build issue list for display
  const issues = [];
  if (!lighting.ok) issues.push(lighting.issue);
  if (!focus.ok) issues.push(focus.issue);

  const allGood = score >= ALIGN_THRESHOLD && lighting.ok && focus.ok;
  updateAlignmentRing(score, issues);

  if (allGood) {
    goodFrames++;
    if (goodFrames >= AUTO_CAPTURE_FRAMES) {
      simulateLock();
    }
  } else {
    goodFrames = 0;
  }
}

function toGrayscale(imageData) {
  const len = imageData.width * imageData.height;
  const gray = new Float32Array(len);
  const d = imageData.data;
  for (let i = 0; i < len; i++) {
    gray[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
  }
  return gray;
}

function checkLighting(gray) {
  // Mean brightness should be 40–220, contrast (std dev) should be > 25
  const n = gray.length;
  let sum = 0;
  for (let i = 0; i < n; i++) sum += gray[i];
  const mean = sum / n;

  let variance = 0;
  for (let i = 0; i < n; i++) { const d = gray[i] - mean; variance += d * d; }
  const stdDev = Math.sqrt(variance / n);

  if (mean < 40) return { ok: false, issue: 'Too dark' };
  if (mean > 220) return { ok: false, issue: 'Too bright' };
  if (stdDev < 25) return { ok: false, issue: 'Low contrast' };
  return { ok: true };
}

function checkFocus(gray, w, h) {
  // Variance of Laplacian — measures sharpness
  // Laplacian kernel: [0,1,0; 1,-4,1; 0,1,0]
  let sum = 0, sumSq = 0, count = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const idx = y * w + x;
      const lap = -4 * gray[idx]
        + gray[idx - 1] + gray[idx + 1]
        + gray[idx - w] + gray[idx + w];
      sum += lap;
      sumSq += lap * lap;
      count++;
    }
  }
  const mean = sum / count;
  const variance = (sumSq / count) - (mean * mean);

  // Threshold tuned for 64x48 — blurry images score < 80
  if (variance < 80) return { ok: false, issue: 'Blurry' };
  return { ok: true };
}

function ncc(a, b) {
  let meanA = 0, meanB = 0;
  const n = a.length;
  for (let i = 0; i < n; i++) { meanA += a[i]; meanB += b[i]; }
  meanA /= n; meanB /= n;

  let num = 0, denA = 0, denB = 0;
  for (let i = 0; i < n; i++) {
    const da = a[i] - meanA;
    const db = b[i] - meanB;
    num += da * db;
    denA += da * da;
    denB += db * db;
  }
  const den = Math.sqrt(denA * denB);
  return den === 0 ? 0 : num / den;
}

function updateAlignmentRing(score, issues) {
  const viewfinder = document.getElementById('viewfinder');
  // Color based on score AND quality checks
  const hasIssues = issues && issues.length > 0;
  let color;
  if (score < 0.7 || hasIssues) color = 'rgba(255,68,102,0.7)';       // red
  else if (score < ALIGN_THRESHOLD) color = 'rgba(255,170,0,0.7)';     // yellow
  else color = 'rgba(0,214,143,0.8)';                                   // green

  viewfinder.style.boxShadow = `inset 0 0 0 3px ${color}, 0 0 12px ${color}`;

  // Update or create score label
  let label = viewfinder.querySelector('#align-score');
  if (!label) {
    label = document.createElement('div');
    label.id = 'align-score';
    label.style.cssText = 'position:absolute;top:.5rem;left:.5rem;background:rgba(0,0,0,.6);color:#fff;padding:.15rem .4rem;border-radius:4px;font-size:.75rem;z-index:10;font-variant-numeric:tabular-nums';
    viewfinder.appendChild(label);
  }
  const pct = `${Math.round(score * 100)}%`;
  const issueText = hasIssues ? ` · ${issues.join(' · ')}` : '';
  label.textContent = pct + issueText;
  label.style.color = hasIssues ? 'rgba(255,68,102,0.9)' : color;
}

function hideAlignmentRing() {
  const viewfinder = document.getElementById('viewfinder');
  viewfinder.style.boxShadow = '';
  const label = viewfinder.querySelector('#align-score');
  if (label) label.remove();
  const lockLabel = viewfinder.querySelector('#lock-label');
  if (lockLabel) lockLabel.remove();
}

function simulateLock() {
  // Pause alignment, freeze frame briefly, show lock indicator, then resume
  if (alignInterval) clearInterval(alignInterval);
  goodFrames = 0;

  const video = document.getElementById('camera');
  const frozen = document.getElementById('frozen-frame');
  const viewfinder = document.getElementById('viewfinder');

  // Freeze the current frame in the viewfinder
  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  frozen.src = canvas.toDataURL('image/jpeg', 0.92);
  frozen.style.display = 'block';
  video.style.display = 'none';

  // Solid green glow
  viewfinder.style.boxShadow = 'inset 0 0 0 4px rgba(0,214,143,0.9), 0 0 20px rgba(0,214,143,0.6)';

  // Show lock label
  let lockLabel = viewfinder.querySelector('#lock-label');
  if (!lockLabel) {
    lockLabel = document.createElement('div');
    lockLabel.id = 'lock-label';
    lockLabel.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,.7);color:#00d68f;padding:.4rem .8rem;border-radius:6px;font-size:1rem;font-weight:600;z-index:12;white-space:nowrap';
    viewfinder.appendChild(lockLabel);
  }
  lockLabel.textContent = 'Alignment Lock';

  // After 1.5s, resume live feed with ghost still active
  setTimeout(() => {
    lockLabel.remove();
    frozen.style.display = 'none';
    video.style.display = '';
    // Resume alignment checking
    if (ghostActive && refGray) {
      alignInterval = setInterval(compareFrame, 300);
    }
  }, 1500);
}

// ── Save / Discard ───────────────────────────────────────

async function savePosition() {
  const name = document.getElementById('position-name').value.trim();
  if (!name) return alert('Position name is required');

  const hint = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  const saveBtn = document.getElementById('save-btn');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    const positions = [...(roomData.positions || [])];
    const newPos = { label: name, hint: hint };

    if (editIndex !== null) {
      const oldHint = positions[editIndex]?.hint || positions[editIndex]?.label;
      if (oldHint && oldHint !== hint && existingRefImage) {
        await fetch(`/api/owner/reference-images/${existingRefImage.id}`, { method: 'DELETE' });
        existingRefImage = null;
      }
      positions[editIndex] = newPos;
    } else {
      positions.push(newPos);
    }

    const r = await fetch(`/api/owner/rooms/${roomId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ positions }),
    });
    if (!r.ok) throw new Error('Failed to update room template');

    if (capturedBlob) {
      const form = new FormData();
      form.append('file', capturedBlob, 'reference.jpg');
      form.append('position_hint', hint);
      const ur = await fetch(`/api/owner/rooms/${roomId}/reference-images`, {
        method: 'POST',
        body: form,
      });
      if (!ur.ok) throw new Error('Failed to upload reference photo');
    }

    window.location.href = `/owner/properties?property=${propertyId}`;
  } catch (e) {
    alert(e.message);
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save Position';
  }
}

function discard() {
  window.location.href = `/owner/properties?property=${propertyId}`;
}

window.addEventListener('beforeunload', () => {
  stopAlignment();
  if (stream) stream.getTracks().forEach(t => t.stop());
});
