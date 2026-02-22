/* capture-360.js — 360° panoramic capture with compass tracking */

const SECTOR_COUNT = 12;
const SECTOR_SIZE = 360 / SECTOR_COUNT; // 30°
const MIN_SECTORS_DONE = 10;

let tenantToken = null;
let sessionId = null;
let roomName = null;
let captureId = null;
let stream = null;
let previewMode = false; // owner preview — no uploads

// Sector state: null = uncaptured, 'captured' = done
let sectors = new Array(SECTOR_COUNT).fill(null);

// Compass
let currentHeading = null;
let currentSector = null;
let compassAvailable = false;

// Auto-capture — relaxed for handheld use
let stableStart = null;
let stableSector = null;
const STABLE_THRESHOLD = 10; // ±10° heading stability (phones jitter)
const STABLE_DURATION = 800;  // 0.8s hold (was 1.2 — too long handheld)
let lastStableHeading = null;

// Pano strip
let lastPanoDrawTime = 0;
const PANO_DRAW_INTERVAL = 66; // ~15fps
let panoBuffer = null;   // offscreen canvas accumulating grayscale frames
let panoBufferCtx = null;
let sampleCanvas = null; // tiny canvas for grabbing video column
let sampleCtx = null;

// Quality check canvas
let qualityCanvas = null;
let qualityCtx = null;

// Guidance state
let lastGuidanceIssue = null;
let guidanceClearTimer = null;

// Helper: append token query param
function tokenParam(sep = '?') {
  return tenantToken ? `${sep}token=${encodeURIComponent(tenantToken)}` : '';
}

// ── Init ──────────────────────────────────────────────────
let roomTemplateId = null;
let sectorBlobs = {}; // Store captured blobs for owner upload

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  sessionId = params.get('session');
  roomName = params.get('room');
  tenantToken = params.get('token');
  roomTemplateId = params.get('room_template_id');

  // Preview mode when no session (owner testing the capture experience)
  previewMode = !sessionId;

  document.getElementById('room-title').textContent = `${roomName || 'Room'} — 360°`;

  // Fix back links
  if (tenantToken) {
    document.getElementById('back-link-bottom').href = `/inspect/${tenantToken}`;
  } else {
    const propId = params.get('property');
    if (propId) {
      document.getElementById('back-link-bottom').href = `/owner/properties?property=${propId}`;
    }
  }

  // Offscreen canvases
  qualityCanvas = document.createElement('canvas');
  qualityCanvas.width = 64;
  qualityCanvas.height = 48;
  qualityCtx = qualityCanvas.getContext('2d', { willReadFrequently: true });

  // Pano buffer — accumulates grayscale camera frames as user pans
  panoBuffer = document.createElement('canvas');
  panoBuffer.width = 720;
  panoBuffer.height = 48;
  panoBufferCtx = panoBuffer.getContext('2d', { willReadFrequently: true });
  // Start dark
  panoBufferCtx.fillStyle = '#0a0a15';
  panoBufferCtx.fillRect(0, 0, 720, 48);

  // Sample canvas — grabs a thin vertical strip from video
  sampleCanvas = document.createElement('canvas');
  sampleCanvas.width = 4;
  sampleCanvas.height = 48;
  sampleCtx = sampleCanvas.getContext('2d');

  await startCamera();
  if (!previewMode) await createCapture();
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
    sampleVideoToPano();
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

// ── Live panoramic strip ─────────────────────────────────
// Samples a thin column from the live video and paints it into
// the pano buffer at the current heading position, building up
// a grayscale preview as the user rotates.

function sampleVideoToPano() {
  if (currentHeading === null || !stream) return;
  const video = document.getElementById('camera');
  if (!video.videoWidth) return; // not ready yet

  // Grab center column of video, scaled to 4×48
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  const colX = Math.floor(vw / 2) - 2; // center 4px
  sampleCtx.drawImage(video, colX, 0, 4, vh, 0, 0, 4, 48);

  // Convert to grayscale with slight blue tint for aesthetics
  const imgData = sampleCtx.getImageData(0, 0, 4, 48);
  const d = imgData.data;
  for (let i = 0; i < d.length; i += 4) {
    const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
    const val = Math.round(gray * 0.7); // dim slightly
    d[i] = val;
    d[i + 1] = val;
    d[i + 2] = Math.min(255, val + 15); // subtle blue
  }
  sampleCtx.putImageData(imgData, 0, 0);

  // Paint into pano buffer at heading position
  const x = Math.round((currentHeading / 360) * 720);
  panoBufferCtx.drawImage(sampleCanvas, 0, 0, 4, 48, x - 2, 0, 4, 48);
}

function drawPanoStrip() {
  const canvas = document.getElementById('pano-strip');
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  // Draw accumulated grayscale buffer as base
  ctx.drawImage(panoBuffer, 0, 0);

  const sectorWidth = w / SECTOR_COUNT; // 60px per sector

  // Overlay captured sectors with translucent green
  for (let i = 0; i < SECTOR_COUNT; i++) {
    if (sectors[i]) {
      const x = i * sectorWidth;
      ctx.fillStyle = 'rgba(0, 214, 143, 0.45)';
      ctx.fillRect(x, 0, sectorWidth, h);
    }
  }

  // Sector dividers + labels
  for (let i = 0; i < SECTOR_COUNT; i++) {
    const x = i * sectorWidth;
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();

    ctx.fillStyle = sectors[i] ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.3)';
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

    // Triangle marker at top
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.moveTo(markerX - 5, 0);
    ctx.lineTo(markerX + 5, 0);
    ctx.lineTo(markerX, 7);
    ctx.closePath();
    ctx.fill();

    ctx.lineWidth = 1;
  }
}

// ── Auto-capture ──────────────────────────────────────────
function checkAutoCapture() {
  if (currentHeading === null || currentSector === null) return;
  if (sectors[currentSector]) {
    // Already captured — guide to next sector
    updateGapGuidance();
    return;
  }

  const now = performance.now();

  if (lastStableHeading === null ||
      Math.abs(angleDiff(currentHeading, lastStableHeading)) > STABLE_THRESHOLD) {
    // Heading moved — reset stability
    lastStableHeading = currentHeading;
    stableStart = now;
    stableSector = currentSector;
    setGuidance('Hold steady to capture...', 'info');
    return;
  }

  // Heading stable — show countdown feedback
  const elapsed = now - stableStart;
  if (stableSector === currentSector && elapsed < STABLE_DURATION) {
    const pct = Math.round((elapsed / STABLE_DURATION) * 100);
    setGuidance(`Holding... ${pct}%`, 'info');
    return;
  }

  // Stable long enough — attempt capture
  if (stableSector === currentSector && elapsed >= STABLE_DURATION) {
    doCapture(currentSector);
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
  if (!stream) return;
  if (!previewMode && !captureId) return;
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

  if (!lighting.ok) {
    setGuidance(lightingGuidance(lighting.issue), 'warn');
    return;
  }
  if (!focus.ok) {
    setGuidance('Blurry — hold phone steady and level', 'warn');
    return;
  }

  // Mark captured
  sectors[sectorIndex] = 'captured';
  drawPanoStrip();
  updateProgress();
  flashViewfinder();
  setGuidance(`Sector ${sectorIndex + 1} captured!`, 'success');

  // Store blob for owner reference upload
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
  if (previewMode && roomTemplateId) {
    sectorBlobs[sectorIndex] = blob;
  }

  // Upload (skip in preview mode)
  if (!previewMode) {
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
      setGuidance('Upload failed — will retry', 'warn');
    }
  }

  // Brief pause then show next gap guidance
  setTimeout(() => updateGapGuidance(), 1200);
}

function manualCapture() {
  let targetSector;

  if (currentSector !== null && !sectors[currentSector]) {
    targetSector = currentSector;
  } else {
    // No compass or current sector already captured — find first uncaptured
    targetSector = sectors.findIndex(s => s === null);
    if (targetSector === -1) return;
  }

  // Skip quality gates for manual capture — user explicitly chose to capture
  forceCapture(targetSector);
}

async function forceCapture(sectorIndex) {
  if (!stream) return;
  if (sectors[sectorIndex]) return;

  const video = document.getElementById('camera');
  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  sectors[sectorIndex] = 'captured';
  drawPanoStrip();
  updateProgress();
  flashViewfinder();
  setGuidance(`Sector ${sectorIndex + 1} captured!`, 'success');

  const blob2 = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
  if (previewMode && roomTemplateId) {
    sectorBlobs[sectorIndex] = blob2;
  }

  if (!previewMode) {
    const form = new FormData();
    form.append('file', blob2, `sector_${sectorIndex}.jpg`);
    form.append('orientation_hint', `sector_${sectorIndex}`);
    if (tenantToken) form.append('token', tenantToken);

    try {
      await fetch(`/api/captures/${captureId}/images${tokenParam()}`, {
        method: 'POST',
        body: form,
      });
    } catch (e) {
      sectors[sectorIndex] = null;
      drawPanoStrip();
      updateProgress();
    }
  }

  setTimeout(() => updateGapGuidance(), 1200);
}

// ── Guidance ──────────────────────────────────────────────
function setGuidance(text, level) {
  const guide = document.getElementById('gap-guide');
  guide.textContent = text;

  guide.style.color = level === 'warn' ? 'var(--warning)'
    : level === 'success' ? 'var(--success)'
    : 'var(--text-muted)';

  // Clear transient messages after a delay
  clearTimeout(guidanceClearTimer);
  if (level === 'success' || level === 'warn') {
    guidanceClearTimer = setTimeout(() => updateGapGuidance(), 2500);
  }
}

function lightingGuidance(issue) {
  switch (issue) {
    case 'Too dark': return 'Too dark — turn on lights or open blinds';
    case 'Too bright': return 'Too bright — avoid pointing at windows';
    case 'Low contrast': return 'Low contrast — aim at a more detailed area';
    default: return 'Lighting issue — adjust room lighting';
  }
}

// ── UI updates ────────────────────────────────────────────
function updateProgress() {
  const done = sectors.filter(s => s !== null).length;
  document.getElementById('capture-subtitle').textContent = `${done} of ${SECTOR_COUNT} sectors`;

  const doneBtn = document.getElementById('done-btn');
  doneBtn.textContent = `Done — ${done}/${SECTOR_COUNT} captured`;
  doneBtn.disabled = previewMode ? false : done < MIN_SECTORS_DONE;
}

function updateGapGuidance() {
  const remaining = [];
  for (let i = 0; i < SECTOR_COUNT; i++) {
    if (!sectors[i]) remaining.push(i);
  }

  if (remaining.length === 0) {
    setGuidance('All sectors captured!', 'success');
    return;
  }

  if (currentSector === null) {
    setGuidance(`${remaining.length} sector(s) remaining — pan slowly`, 'info');
    return;
  }

  if (!sectors[currentSector]) {
    setGuidance('Hold steady to auto-capture this sector', 'info');
    return;
  }

  // Find next uncaptured sector — prefer clockwise (right)
  let bestIdx = null;
  let bestCW = SECTOR_COUNT + 1;

  for (const idx of remaining) {
    const cw = (idx - currentSector + SECTOR_COUNT) % SECTOR_COUNT;
    if (cw < bestCW) {
      bestCW = cw;
      bestIdx = idx;
    }
  }

  // Only suggest left if clockwise distance > 6 sectors (more than halfway around)
  const ccw = (currentSector - bestIdx + SECTOR_COUNT) % SECTOR_COUNT;
  if (ccw < bestCW) {
    setGuidance(`← Turn left to sector ${bestIdx + 1} (${remaining.length} left)`, 'info');
  } else {
    setGuidance(`Turn right → to sector ${bestIdx + 1} (${remaining.length} left)`, 'info');
  }
}

function flashViewfinder() {
  const vf = document.getElementById('viewfinder');
  vf.style.boxShadow = '0 0 0 4px var(--success)';
  setTimeout(() => { vf.style.boxShadow = ''; }, 400);
}

// ── Done flow ─────────────────────────────────────────────
async function finishCapture() {
  if (captureId) {
    try {
      await fetch(`/api/captures/${captureId}/submit${tokenParam()}`, { method: 'POST' });
    } catch (e) { /* non-critical */ }
  }

  // Owner mode: upload captured sectors as reference images
  if (previewMode && roomTemplateId && Object.keys(sectorBlobs).length > 0) {
    setGuidance('Saving reference images...', 'info');
    try {
      // Delete existing 360 references first
      const existingR = await fetch(`/api/owner/rooms/${roomTemplateId}/reference-images`);
      if (existingR.ok) {
        const existing = await existingR.json();
        for (const img of existing) {
          if (img.id) {
            await fetch(`/api/owner/reference-images/${img.id}`, { method: 'DELETE' }).catch(() => {});
          }
        }
      }

      // Upload each captured sector as a reference image
      for (const [idx, blob] of Object.entries(sectorBlobs)) {
        const form = new FormData();
        form.append('file', blob, `sector_${idx}.jpg`);
        form.append('position_hint', `sector_${idx}`);

        await fetch(`/api/owner/rooms/${roomTemplateId}/reference-images`, {
          method: 'POST',
          body: form,
        });
      }
    } catch (e) {
      console.warn('Failed to save reference images:', e);
    }
  }

  if (tenantToken) {
    window.location.href = `/inspect/${tenantToken}`;
  } else {
    const params = new URLSearchParams(window.location.search);
    const propId = params.get('property');
    window.location.href = propId ? `/owner/properties?property=${propId}` : '/';
  }
}

// ── Quality gates (relaxed for handheld 360 panning) ─────
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

  if (mean < 30) return { ok: false, issue: 'Too dark' };
  if (mean > 230) return { ok: false, issue: 'Too bright' };
  if (stdDev < 18) return { ok: false, issue: 'Low contrast' };
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

  // Threshold 40 (was 80) — handheld panning has slight motion blur
  if (variance < 40) return { ok: false, issue: 'Blurry' };
  return { ok: true };
}

// ── Cleanup ───────────────────────────────────────────────
window.addEventListener('beforeunload', () => {
  if (stream) stream.getTracks().forEach(t => t.stop());
});
