/* owner-property.js — Property management */

let currentPropertyId = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadProperties();

  document.getElementById('create-prop-btn').addEventListener('click', createProperty);
  document.getElementById('back-to-list').addEventListener('click', showList);
  document.getElementById('add-position-btn').addEventListener('click', addPositionField);
  document.getElementById('add-room-btn').addEventListener('click', addRoomTemplate);
});

async function loadProperties() {
  try {
    const r = await fetch('/api/owner/properties');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    const props = await r.json();
    renderPropertyList(props);
  } catch (e) {
    document.getElementById('property-list').innerHTML = '<p class="text-muted">Failed to load</p>';
  }
}

function renderPropertyList(props) {
  const div = document.getElementById('property-list');
  if (!props.length) {
    div.innerHTML = '<p class="text-muted">No properties yet</p>';
    return;
  }
  div.innerHTML = '';
  props.forEach(p => {
    const el = document.createElement('div');
    el.className = 'room-item';
    el.style.cursor = 'pointer';
    el.innerHTML = `
      <div>
        <strong>${p.label}</strong>
        ${p.address ? `<br><span class="text-muted" style="font-size:.85rem">${p.address}</span>` : ''}
      </div>
      <span class="text-muted" style="font-size:.85rem">${p.room_template_count} rooms &middot; ${p.session_count} sessions</span>
    `;
    el.addEventListener('click', () => showDetail(p.id));
    div.appendChild(el);
  });
}

async function createProperty() {
  const label = document.getElementById('prop-label').value.trim();
  const address = document.getElementById('prop-address').value.trim();
  if (!label) return alert('Label is required');

  const r = await fetch('/api/owner/properties', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label, address, rooms: [] }),
  });
  if (!r.ok) return alert('Failed to create property');
  document.getElementById('prop-label').value = '';
  document.getElementById('prop-address').value = '';
  await loadProperties();
}

async function showDetail(propertyId) {
  currentPropertyId = propertyId;
  const r = await fetch(`/api/owner/properties/${propertyId}`);
  if (!r.ok) return alert('Failed to load property');
  const prop = await r.json();

  document.getElementById('detail-label').textContent = prop.label;
  document.getElementById('detail-address').textContent = prop.address || 'No address';
  document.getElementById('property-detail').classList.remove('hidden');

  // Room templates
  renderRoomTemplates(prop.room_templates || []);

  // Hide list
  document.querySelector('#property-list').parentElement.classList.add('hidden');
  document.querySelector('#create-prop-btn').parentElement.classList.add('hidden');
}

function showList() {
  currentPropertyId = null;
  document.getElementById('property-detail').classList.add('hidden');
  document.querySelector('#property-list').parentElement.classList.remove('hidden');
  document.querySelector('#create-prop-btn').parentElement.classList.remove('hidden');
  loadProperties();
}

function renderRoomTemplates(templates) {
  const div = document.getElementById('room-template-list');
  if (!templates.length) {
    div.innerHTML = '<p class="text-muted">No room templates — add one below</p>';
    return;
  }
  div.innerHTML = '';
  templates.forEach(rt => {
    const el = document.createElement('div');
    el.className = 'room-item';
    el.style.flexWrap = 'wrap';
    const posLabels = (rt.positions || []).map(p => p.label || p.hint).join(', ');
    const refCount = rt.reference_image_count || 0;
    const refBadge = refCount > 0
      ? `<span class="text-muted" style="font-size:.75rem;margin-left:.5rem">${refCount} ref photo${refCount !== 1 ? 's' : ''}</span>`
      : '';
    el.innerHTML = `
      <div style="flex:1;min-width:0">
        <strong>${rt.name}</strong>${refBadge}
        <br><span class="text-muted" style="font-size:.85rem">${posLabels || 'No positions'}</span>
      </div>
      <div class="flex gap-1">
        <button class="btn btn-outline ref-photos-btn" style="padding:.2rem .5rem;font-size:.8rem" data-room-id="${rt.id}">Ref Photos</button>
        <button class="btn btn-outline edit-room-btn" style="padding:.2rem .5rem;font-size:.8rem" data-room-id="${rt.id}">Edit</button>
        <button class="btn btn-danger delete-room-btn" style="padding:.2rem .5rem;font-size:.8rem" data-room-id="${rt.id}">Delete</button>
      </div>
      <div id="ref-panel-${rt.id}" class="hidden" style="width:100%;margin-top:.5rem"></div>
    `;
    el.querySelector('.delete-room-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete room template "${rt.name}"?`)) return;
      await fetch(`/api/owner/rooms/${rt.id}`, { method: 'DELETE' });
      showDetail(currentPropertyId);
    });
    el.querySelector('.edit-room-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      showEditForm(el, rt);
    });
    el.querySelector('.ref-photos-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      toggleRefPhotos(rt);
    });
    div.appendChild(el);
  });
}

function showEditForm(container, rt) {
  const positionsHtml = (rt.positions || []).map((p, i) => `
    <div style="display:flex;gap:.5rem;margin-bottom:.5rem" class="edit-pos-row">
      <input type="text" placeholder="Position label" style="flex:1" class="edit-pos-label" value="${p.label || ''}">
      <input type="text" placeholder="Hint" style="flex:1" class="edit-pos-hint" value="${p.hint || ''}">
      <button class="btn btn-danger" style="padding:.2rem .5rem" onclick="this.parentElement.remove()">&times;</button>
    </div>
  `).join('');

  container.innerHTML = `
    <div style="width:100%;padding:.5rem 0">
      <input type="text" id="edit-room-name-${rt.id}" value="${rt.name}" placeholder="Room name" style="margin-bottom:.5rem">
      <div id="edit-positions-${rt.id}">${positionsHtml}</div>
      <button class="btn btn-outline" style="padding:.2rem .5rem;font-size:.8rem;margin-bottom:.5rem"
        onclick="addEditPositionField('${rt.id}')">+ Add Position</button>
      <div class="flex gap-1">
        <button class="btn btn-primary" style="flex:1;padding:.4rem;font-size:.85rem" onclick="saveRoomEdit('${rt.id}')">Save</button>
        <button class="btn" style="flex:1;padding:.4rem;font-size:.85rem;background:var(--border)" onclick="showDetail(currentPropertyId)">Cancel</button>
      </div>
    </div>
  `;
}

function addEditPositionField(roomId) {
  const container = document.getElementById(`edit-positions-${roomId}`);
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:.5rem;margin-bottom:.5rem';
  row.className = 'edit-pos-row';
  row.innerHTML = `
    <input type="text" placeholder="Position label" style="flex:1" class="edit-pos-label">
    <input type="text" placeholder="Hint" style="flex:1" class="edit-pos-hint">
    <button class="btn btn-danger" style="padding:.2rem .5rem" onclick="this.parentElement.remove()">&times;</button>
  `;
  container.appendChild(row);
}

async function saveRoomEdit(roomId) {
  const name = document.getElementById(`edit-room-name-${roomId}`).value.trim();
  if (!name) return alert('Room name is required');

  const posRows = document.querySelectorAll(`#edit-positions-${roomId} .edit-pos-row`);
  const positions = [];
  posRows.forEach(row => {
    const label = row.querySelector('.edit-pos-label').value.trim();
    const hint = row.querySelector('.edit-pos-hint').value.trim();
    if (label) positions.push({ label, hint: hint || label.toLowerCase().replace(/\s+/g, '-') });
  });

  const r = await fetch(`/api/owner/rooms/${roomId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, positions }),
  });
  if (!r.ok) return alert('Failed to update room template');
  showDetail(currentPropertyId);
}

function addPositionField() {
  const container = document.getElementById('new-room-positions');
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:.5rem;margin-bottom:.5rem';
  row.innerHTML = `
    <input type="text" placeholder="Position label" style="flex:1" class="pos-label">
    <input type="text" placeholder="Hint" style="flex:1" class="pos-hint">
    <button class="btn btn-danger" style="padding:.2rem .5rem">&times;</button>
  `;
  row.querySelector('button').addEventListener('click', () => row.remove());
  container.appendChild(row);
}

async function addRoomTemplate() {
  if (!currentPropertyId) return;
  const name = document.getElementById('new-room-name').value.trim();
  if (!name) return alert('Room name is required');

  const posRows = document.querySelectorAll('#new-room-positions > div');
  const positions = [];
  posRows.forEach(row => {
    const label = row.querySelector('.pos-label').value.trim();
    const hint = row.querySelector('.pos-hint').value.trim();
    if (label) positions.push({ label, hint: hint || label.toLowerCase().replace(/\s+/g, '-') });
  });

  const r = await fetch(`/api/owner/properties/${currentPropertyId}/rooms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, positions, display_order: 0 }),
  });
  if (!r.ok) return alert('Failed to add room template');

  document.getElementById('new-room-name').value = '';
  document.getElementById('new-room-positions').innerHTML = '';
  showDetail(currentPropertyId);
}


// ── Reference Photos ─────────────────────────────────────

async function toggleRefPhotos(rt) {
  const panel = document.getElementById(`ref-panel-${rt.id}`);
  if (!panel) return;

  // Toggle visibility
  if (!panel.classList.contains('hidden')) {
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');
  panel.innerHTML = '<p class="text-muted" style="font-size:.85rem">Loading...</p>';

  // Fetch existing reference images
  try {
    const r = await fetch(`/api/owner/rooms/${rt.id}/reference-images`);
    if (!r.ok) throw new Error('Failed to load');
    const images = await r.json();
    renderRefPanel(panel, rt, images);
  } catch (e) {
    panel.innerHTML = '<p class="text-muted" style="font-size:.85rem">Failed to load reference images</p>';
  }
}

function renderRefPanel(panel, rt, images) {
  const positions = rt.positions || [];
  if (!positions.length) {
    panel.innerHTML = '<p class="text-muted" style="font-size:.85rem">Add positions to this room template first</p>';
    return;
  }

  // Build hint → image map
  const imgMap = {};
  images.forEach(img => { imgMap[img.position_hint] = img; });

  let html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:.5rem;padding:.5rem 0">';
  positions.forEach(pos => {
    const hint = pos.hint || pos.label;
    const img = imgMap[hint];
    if (img && img.thumbnail_url) {
      html += `
        <div style="text-align:center">
          <div style="position:relative;display:inline-block">
            <img src="${img.thumbnail_url}" alt="${hint}"
              style="width:100px;height:75px;object-fit:cover;border-radius:4px;border:2px solid var(--primary)">
            <button onclick="deleteRefPhoto('${img.id}','${rt.id}')"
              style="position:absolute;top:-6px;right:-6px;background:var(--danger);color:#fff;border:none;border-radius:50%;width:20px;height:20px;font-size:12px;cursor:pointer;line-height:20px;padding:0">&times;</button>
          </div>
          <div style="font-size:.75rem;color:var(--text-secondary);margin-top:.2rem">${pos.label || hint}</div>
        </div>`;
    } else {
      html += `
        <div style="text-align:center">
          <label style="display:flex;align-items:center;justify-content:center;width:100px;height:75px;border:2px dashed var(--border);border-radius:4px;cursor:pointer;margin:0 auto;font-size:.8rem;color:var(--text-secondary)">
            + Add
            <input type="file" accept="image/*" capture="environment" style="display:none"
              onchange="uploadRefPhoto('${rt.id}','${hint}',this.files[0])">
          </label>
          <div style="font-size:.75rem;color:var(--text-secondary);margin-top:.2rem">${pos.label || hint}</div>
        </div>`;
    }
  });
  html += '</div>';
  panel.innerHTML = html;
}

async function uploadRefPhoto(roomId, hint, file) {
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  form.append('position_hint', hint);

  try {
    const r = await fetch(`/api/owner/rooms/${roomId}/reference-images`, {
      method: 'POST',
      body: form,
    });
    if (!r.ok) throw new Error('Upload failed');

    // Refresh the panel — need to re-fetch the room template data
    await showDetail(currentPropertyId);
    // Re-open the panel after refresh
    const panel = document.getElementById(`ref-panel-${roomId}`);
    if (panel && panel.classList.contains('hidden')) {
      // Find the rt data and toggle
      const propR = await fetch(`/api/owner/properties/${currentPropertyId}`);
      if (propR.ok) {
        const prop = await propR.json();
        const rt = (prop.room_templates || []).find(t => t.id === roomId);
        if (rt) toggleRefPhotos(rt);
      }
    }
  } catch (e) {
    alert('Failed to upload reference photo');
  }
}

async function deleteRefPhoto(imageId, roomId) {
  if (!confirm('Delete this reference photo?')) return;
  try {
    const r = await fetch(`/api/owner/reference-images/${imageId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Delete failed');

    // Refresh
    await showDetail(currentPropertyId);
    const propR = await fetch(`/api/owner/properties/${currentPropertyId}`);
    if (propR.ok) {
      const prop = await propR.json();
      const rt = (prop.room_templates || []).find(t => t.id === roomId);
      if (rt) toggleRefPhotos(rt);
    }
  } catch (e) {
    alert('Failed to delete reference photo');
  }
}

