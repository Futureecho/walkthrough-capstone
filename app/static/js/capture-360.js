/* capture-360.js — 360° panoramic capture with compass tracking */

const SECTOR_COUNT = 12;
const SECTOR_SIZE = 360 / SECTOR_COUNT; // 30°
const MIN_SECTORS_DONE = 10;

let tenantToken = null;
let sessionId = null;
let roomName = null;
let captureId = null;
let stream = null;

// Sector state: null = uncaptured, 'captured' = done
let sectors = new Array(SECTOR_COUNT).fill(null);

// Compass
let currentHeading = null;
let currentSector = null;
let compassAvailable = false;

// Auto-capture
let stableStart = null;
let stableSector = null;
const STABLE_THRESHOLD = 5;  // ±5° heading stability
const STABLE_DURATION = 1200; // 1.2s hold
let lastStableHeading = null;

// Pano strip throttle
let lastPanoDrawTime = 0;
const PANO_DRAW_INTERVAL = 66; // ~15fps

// Quality check canvas
let qualityCanvas = null;
let qualityCtx = null;

// Helper: append token query param
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

  document.getElementById('room-title').textContent = `${roomName} — 360°`;

  // Fix back links for tenant flow
  if (tenantToken) {
    document.getElementById('back-link-bottom').href = `/inspect/${tenantToken}`;
  }

  // Quality check canvas (offscreen)
  qualityCanvas = document.createElement('canvas');
  qualityCanvas.width = 64;
  qualityCanvas.height = 48;
  qualityCtx = qualityCanvas.getContext('2d', { willReadFrequently: true });

  await startCamera();
  await createCapture();
  initCompass();
  drawPanoStrip();

  document.getElementById('capture-btn').addEventListener('click', manualCapture);
  document.getElementById('done-btn').addEventListener('click', finishCapture);
});

// ── Camera ────────────────────────────────────────────────
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

// ── Capture record ────────────────────────────────────────
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

// ── Compass ───────────────────────────────────────────────
function initCompass() {
  if (typeof DeviceOrientationEvent !== 'undefined' &&
      typeof DeviceOrientationEvent.requestPermission === 'function') {
    // iOS — needs user gesture
    const card = document.getElementById('compass-card');
    card.classList.remove('hidden');
    document.getElementById('compass-btn').addEventListener('click', async () => {
      try {
        const perm = await DeviceOrientationEvent.requestPermission();
        if (perm === 'granted') {
          card.classList.add('hidden');
          startTracking();
        } else {
          alert('Compass permission denied. You can still capture manually.');
        }
      } catch (e) {
        alert('Compass error: ' + e.message);
        card.classList.add('hidden');
      }
    });
  } else if ('DeviceOrientationEvent' in window) {
    // Android / desktop — no permission needed
    startTracking();
  }
  // No compass at all — manual mode only
}

function startTracking() {
  compassAvailable = true;

  // Try absolute orientation first (gives true north)
  if ('ondeviceorientationabsolute' in window) {
    window.addEventListener('deviceorientationabsolute', handleOrientation);
  } else {
    window.addEventListener('deviceorientation', handleOrientation);
  }
}

function handleOrientation(e) {
  let heading;
  if (e.webkitCompassHeading !== undefined) {
    // iOS Safari
    heading = e.webkitCompassHeading;
  } else if (e.absolute && e.alpha !== null) {
    // Android absolute
    heading = (360 - e.alpha) % 360;
  } else if (e.alpha !== null) {
    // Relative fallback
    heading = e.alpha;
  } else {
    return;
  }

  currentHeading = Math.round(heading * 10) / 10;
  currentSector = Math.floor(currentHeading / SECTOR_SIZE) % SECTOR_COUNT;

  updateHeadingLabel();

  const now = performance.now();
  if (now - lastPanoDrawTime >= PANO_DRAW_INTERVAL) {
    drawPanoStrip();
    lastPanoDrawTime = now;
  }

  checkAutoCapture();
}

function updateHeadingLabel() {
  const label = document.getElementById('heading-label');
  if (currentHeading !== null) {
    label.textContent = `Heading: ${Math.round(currentHeading)}° · Sector: ${currentSector + 1}`;
  }
}

// ── Panoramic strip ───────────────────────────────────────
function drawPanoStrip() {
  const canvas = document.getElementById('pano-strip');
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  // Background
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, w, h);

  const sectorWidth = w / SECTOR_COUNT; // 60px per sector

  // Draw sectors
  for (let i = 0; i < SECTOR_COUNT; i++) {
    const x = i * sectorWidth;
    if (sectors[i]) {
      // Captured — green
      ctx.fillStyle = '#00d68f';
      ctx.fillRect(x, 0, sectorWidth, h);
    } else {
      // Uncaptured — subtle red tint
      ctx.fillStyle = '#2e0a14';
      ctx.fillRect(x, 0, sectorWidth, h);
    }

    // Sector divider
    ctx.strokeStyle = '#333';
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();

    // Sector label
    ctx.fillStyle = sectors[i] ? '#000' : '#555';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${i + 1}`, x + sectorWidth / 2, h / 2 + 3);
  }

  // Current heading marker
  if (currentHeading !== null) {
    const markerX = (currentHeading / 360) * w;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(markerX, 0);
    ctx.lineTo(markerX, h);
    ctx.stroke();

    // Small triangle at top
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.moveTo(markerX - 4, 0);
    ctx.lineTo(markerX + 4, 0);
    ctx.lineTo(markerX, 6);
    ctx.closePath();
    ctx.fill();

    ctx.lineWidth = 1;
  }
}

// ── Auto-capture ──────────────────────────────────────────
function checkAutoCapture() {
  if (currentHeading === null || currentSector === null) return;
  if (sectors[currentSector]) return; // Already captured

  const now = performance.now();

  if (lastStableHeading === null ||
      Math.abs(angleDiff(currentHeading, lastStableHeading)) > STABLE_THRESHOLD) {
    // Heading moved — reset stability
    lastStableHeading = currentHeading;
    stableStart = now;
    stableSector = currentSector;
    return;
  }

  // Heading stable — check duration
  if (stableSector === currentSector && (now - stableStart) >= STABLE_DURATION) {
    // Auto-capture this sector
    doCapture(currentSector);
    // Reset stability
    stableStart = null;
    lastStableHeading = null;
    stableSector = null;
  }
}

function angleDiff(a, b) {
  let d = a - b;
  while (d > 180) d -= 360;
  while (d < -180) d += 360;
  return d;
}

// ── Capture logic ─────────────────────────────────────────
async function doCapture(sectorIndex) {
  if (!stream || !captureId) return;
  if (sectors[sectorIndex]) return; // Already done

  const video = document.getElementById('camera');
  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);

  // Quality check on downscaled version
  qualityCtx.drawImage(canvas, 0, 0, 64, 48);
  const imageData = qualityCtx.getImageData(0, 0, 64, 48);
  const gray = toGrayscale(imageData);
  const lighting = checkLighting(gray);
  const focus = checkFocus(gray, 64, 48);

  if (!lighting.ok || !focus.ok) {
    // Skip auto-capture if quality is bad — don't interrupt user
    return;
  }

  // Mark captured immediately for UI feedback
  sectors[sectorIndex] = 'captured';
  drawPanoStrip();
  updateProgress();
  flashViewfinder();

  // Convert to blob and upload
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
  const hint = `sector_${sectorIndex}`;

  const form = new FormData();
  form.append('file', blob, `sector_${sectorIndex}.jpg`);
  form.append('orientation_hint', hint);
  if (tenantToken) form.append('token', tenantToken);

  try {
    await fetch(`/api/captures/${captureId}/images${tokenParam()}`, {
      method: 'POST',
      body: form,
    });
  } catch (e) {
    // Upload failed — un-mark sector
    sectors[sectorIndex] = null;
    drawPanoStrip();
    updateProgress();
  }

  updateGapGuidance();
}

function manualCapture() {
  // Determine which sector to assign
  let targetSector;

  if (currentSector !== null && !sectors[currentSector]) {
    // Use compass heading
    targetSector = currentSector;
  } else {
    // No compass or current sector already captured — find first uncaptured
    targetSector = sectors.findIndex(s => s === null);
    if (targetSector === -1) return; // All done
  }

  doCapture(targetSector);
}

// ── UI updates ────────────────────────────────────────────
function updateProgress() {
  const done = sectors.filter(s => s !== null).length;
  document.getElementById('capture-subtitle').textContent = `${done} of ${SECTOR_COUNT} sectors`;

  const doneBtn = document.getElementById('done-btn');
  doneBtn.textContent = `Done — ${done}/${SECTOR_COUNT} captured`;
  doneBtn.disabled = done < MIN_SECTORS_DONE;
}

function updateGapGuidance() {
  const guide = document.getElementById('gap-guide');
  const remaining = [];
  for (let i = 0; i < SECTOR_COUNT; i++) {
    if (!sectors[i]) remaining.push(i);
  }

  if (remaining.length === 0) {
    guide.textContent = 'All sectors captured!';
    return;
  }

  if (currentSector === null) {
    guide.textContent = `${remaining.length} sector(s) remaining`;
    return;
  }

  // Find nearest uncaptured sector
  let nearestIdx = remaining[0];
  let nearestDist = SECTOR_COUNT;

  for (const idx of remaining) {
    const cw = (idx - currentSector + SECTOR_COUNT) % SECTOR_COUNT;
    const ccw = (currentSector - idx + SECTOR_COUNT) % SECTOR_COUNT;
    const dist = Math.min(cw, ccw);
    if (dist < nearestDist) {
      nearestDist = dist;
      nearestIdx = idx;
    }
  }

  if (nearestIdx === currentSector) {
    guide.textContent = 'Hold steady to auto-capture this sector';
  } else {
    // Determine direction
    const cw = (nearestIdx - currentSector + SECTOR_COUNT) % SECTOR_COUNT;
    const ccw = (currentSector - nearestIdx + SECTOR_COUNT) % SECTOR_COUNT;
    if (cw <= ccw) {
      guide.textContent = `Turn right → to fill sector ${nearestIdx + 1} (${remaining.length} remaining)`;
    } else {
      guide.textContent = `← Turn left to fill sector ${nearestIdx + 1} (${remaining.length} remaining)`;
    }
  }
}

function flashViewfinder() {
  const vf = document.getElementById('viewfinder');
  vf.style.boxShadow = '0 0 0 4px var(--success)';
  setTimeout(() => { vf.style.boxShadow = ''; }, 400);
}

// ── Done flow ─────────────────────────────────────────────
async function finishCapture() {
  // Submit the capture for processing
  if (captureId) {
    try {
      await fetch(`/api/captures/${captureId}/submit${tokenParam()}`, { method: 'POST' });
    } catch (e) {
      // Non-critical — capture images are already uploaded
    }
  }

  // Navigate back to room list
  if (tenantToken) {
    window.location.href = `/inspect/${tenantToken}`;
  } else {
    window.location.href = '/';
  }
}

// ── Quality gates (same logic as owner-position.js) ──────
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

  if (variance < 80) return { ok: false, issue: 'Blurry' };
  return { ok: true };
}

// ── Cleanup ───────────────────────────────────────────────
window.addEventListener('beforeunload', () => {
  if (stream) stream.getTracks().forEach(t => t.stop());
});
