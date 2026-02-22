/* owner-position.js — Position builder with camera viewfinder */

let propertyId = null;
let roomId = null;
let editIndex = null; // null = add mode, number = edit mode
let roomData = null;  // full room template object
let stream = null;
let capturedBlob = null;
let ghostActive = false;
let existingRefImage = null; // {id, thumbnail_url} when editing

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
  document.getElementById('retake-btn').addEventListener('click', retake);
  document.getElementById('ghost-btn').addEventListener('click', toggleTestGhost);
  document.getElementById('save-btn').addEventListener('click', savePosition);
  document.getElementById('discard-btn').addEventListener('click', discard);
  document.getElementById('discard-btn-top').addEventListener('click', discard);
  document.getElementById('position-name').addEventListener('input', onNameInput);

  // Set page title
  document.getElementById('page-title').textContent = editIndex !== null ? 'Edit Position' : 'Add Position';

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

    // If editing, populate fields
    if (editIndex !== null && roomData.positions && roomData.positions[editIndex]) {
      const pos = roomData.positions[editIndex];
      document.getElementById('position-name').value = pos.label || '';
      onNameInput();

      // Load existing reference image
      const hint = pos.hint || pos.label;
      const refImages = roomData.reference_images || [];
      const ref = refImages.find(img => img.position_hint === hint);
      if (ref && ref.thumbnail_url) {
        existingRefImage = ref;
        showPreview(ref.thumbnail_url);
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
    // Camera not available — still allow file-based workflow in edit mode
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

  // Enable save if we have a name and either a capture or existing ref
  updateSaveState();
}

function updateSaveState() {
  const name = document.getElementById('position-name').value.trim();
  const hasPhoto = capturedBlob || existingRefImage;
  document.getElementById('save-btn').disabled = !name;
}

function capturePhoto() {
  const video = document.getElementById('camera');
  if (!video || !stream) return;

  const canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  canvas.toBlob(blob => {
    capturedBlob = blob;
    existingRefImage = null; // new capture replaces existing
    const url = URL.createObjectURL(blob);
    showPreview(url);
  }, 'image/jpeg', 0.92);
}

function showPreview(url) {
  document.getElementById('preview-img').src = url;
  document.getElementById('preview-card').classList.remove('hidden');
  document.getElementById('ghost-btn').classList.remove('hidden');
  updateSaveState();
}

function retake() {
  capturedBlob = null;
  existingRefImage = null;
  document.getElementById('preview-card').classList.add('hidden');
  document.getElementById('ghost-btn').classList.add('hidden');
  removeGhostOverlay();
  updateSaveState();
}

function toggleTestGhost() {
  const previewCard = document.getElementById('preview-card');
  const existing = previewCard.querySelector('#ghost-overlay');

  if (existing) {
    removeGhostOverlay();
    return;
  }

  // Overlay ghost on the preview image container
  const previewImg = document.getElementById('preview-img');
  if (!previewImg.src) return;

  // Make preview card position-relative for overlay
  previewCard.style.position = 'relative';
  previewCard.style.overflow = 'hidden';

  const img = document.createElement('img');
  img.id = 'ghost-overlay';
  img.alt = 'Ghost reference overlay';
  img.src = previewImg.src;
  previewCard.appendChild(img);
  ghostActive = true;
  document.getElementById('ghost-btn').textContent = 'Hide Ghost Overlay';
}

function removeGhostOverlay() {
  const existing = document.getElementById('ghost-overlay');
  if (existing) existing.remove();
  ghostActive = false;
  document.getElementById('ghost-btn').textContent = 'Test Ghost Overlay';
}

async function savePosition() {
  const name = document.getElementById('position-name').value.trim();
  if (!name) return alert('Position name is required');

  const hint = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  const saveBtn = document.getElementById('save-btn');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    // Build updated positions array
    const positions = [...(roomData.positions || [])];
    const newPos = { label: name, hint: hint };

    if (editIndex !== null) {
      // Check if hint changed — need to clean up old ref image
      const oldHint = positions[editIndex]?.hint || positions[editIndex]?.label;
      if (oldHint && oldHint !== hint && existingRefImage) {
        // Old hint differs, delete old ref image
        await fetch(`/api/owner/reference-images/${existingRefImage.id}`, { method: 'DELETE' });
        existingRefImage = null;
      }
      positions[editIndex] = newPos;
    } else {
      positions.push(newPos);
    }

    // Update room template positions
    const r = await fetch(`/api/owner/rooms/${roomId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ positions }),
    });
    if (!r.ok) throw new Error('Failed to update room template');

    // Upload reference photo if captured
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

    // Navigate back to property page
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

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  if (stream) stream.getTracks().forEach(t => t.stop());
});
