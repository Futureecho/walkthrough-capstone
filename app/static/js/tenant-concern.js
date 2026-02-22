/* tenant-concern.js — Tenant concern capture page */

let tenantToken = null;
let sessionId = null;
let roomName = null;
let stream = null;
let capturedBlob = null;

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  tenantToken = params.get('token');
  sessionId = params.get('session');
  roomName = params.get('room') || '';

  if (roomName) {
    document.getElementById('room-label').textContent = roomName;
  }

  await startCamera();

  document.getElementById('capture-btn').addEventListener('click', capturePhoto);
  document.getElementById('retake-btn').addEventListener('click', retakePhoto);
  document.getElementById('submit-btn').addEventListener('click', submitConcern);
  document.getElementById('back-btn').addEventListener('click', goBack);

  // Character counters
  const titleInput = document.getElementById('concern-title');
  const descInput = document.getElementById('concern-desc');

  titleInput.addEventListener('input', () => {
    document.getElementById('title-counter').textContent = `${titleInput.value.length}/50`;
  });
  descInput.addEventListener('input', () => {
    document.getElementById('desc-counter').textContent = `${descInput.value.length}/200`;
  });
});

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1440 } },
      audio: false,
    });
    document.getElementById('camera').srcObject = stream;
  } catch (e) {
    alert('Camera access denied: ' + e.message);
  }
}

function capturePhoto() {
  if (!stream) return;

  const video = document.getElementById('camera');
  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  canvas.toBlob(blob => {
    capturedBlob = blob;
    const url = URL.createObjectURL(blob);
    document.getElementById('preview-img').src = url;
    document.getElementById('step-camera').classList.add('hidden');
    document.getElementById('step-details').classList.remove('hidden');
  }, 'image/jpeg', 0.92);
}

function retakePhoto() {
  capturedBlob = null;
  document.getElementById('step-details').classList.add('hidden');
  document.getElementById('step-camera').classList.remove('hidden');
}

async function submitConcern() {
  const title = document.getElementById('concern-title').value.trim();
  if (!title) {
    alert('Please enter a title for the concern');
    return;
  }
  if (!capturedBlob) {
    alert('Please take a photo first');
    return;
  }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = 'Submitting...';

  const form = new FormData();
  form.append('file', capturedBlob, 'concern.jpg');
  form.append('title', title);
  form.append('description', document.getElementById('concern-desc').value.trim());
  form.append('session_id', sessionId);
  form.append('room', roomName);
  if (tenantToken) form.append('token', tenantToken);

  try {
    const tokenParam = tenantToken ? `?token=${encodeURIComponent(tenantToken)}` : '';
    const r = await fetch(`/api/tenant/concerns${tokenParam}`, {
      method: 'POST',
      body: form,
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to submit');
    }

    // Stop camera
    if (stream) stream.getTracks().forEach(t => t.stop());

    document.getElementById('step-details').classList.add('hidden');
    document.getElementById('step-done').classList.remove('hidden');
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Submit Concern';
    alert('Submit failed: ' + e.message);
  }
}

function goBack() {
  if (tenantToken) {
    window.location.href = `/inspect/${tenantToken}`;
  } else {
    window.history.back();
  }
}

window.addEventListener('beforeunload', () => {
  if (stream) stream.getTracks().forEach(t => t.stop());
});
