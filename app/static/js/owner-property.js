/* owner-property.js — Property management with position builder navigation */

let currentPropertyId = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadProperties();

  document.getElementById('create-prop-btn').addEventListener('click', createProperty);
  document.getElementById('back-to-list').addEventListener('click', showList);
  document.getElementById('add-room-btn').addEventListener('click', addRoomTemplate);

  // Auto-open property detail if ?property=ID is present
  const params = new URLSearchParams(window.location.search);
  const autoOpen = params.get('property');
  if (autoOpen) {
    showDetail(autoOpen);
  }
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
        <strong>${esc(p.label)}</strong>
        ${p.address ? `<br><span class="text-muted" style="font-size:.85rem">${esc(p.address)}</span>` : ''}
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

  renderRoomTemplates(prop.room_templates || []);

  // Hide list
  document.querySelector('#property-list').parentElement.classList.add('hidden');
  document.querySelector('#create-prop-btn').parentElement.classList.add('hidden');
}

function showList() {
  currentPropertyId = null;
  // Clear ?property= from URL
  history.replaceState(null, '', '/owner/properties');
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
    const card = document.createElement('div');
    card.style.cssText = 'border:1px solid var(--border);border-radius:var(--radius);padding:.75rem;margin-bottom:.75rem';

    // Room header with name + actions
    const header = document.createElement('div');
    header.className = 'flex-between mb-1';
    header.innerHTML = `
      <strong>${esc(rt.name)}</strong>
      <div class="flex gap-1">
        <button class="btn btn-ghost" style="padding:.2rem .5rem;font-size:.8rem" data-action="rename">Rename</button>
        <button class="btn btn-danger" style="padding:.2rem .5rem;font-size:.8rem" data-action="delete-room">Delete</button>
      </div>
    `;
    header.querySelector('[data-action="rename"]').addEventListener('click', () => editRoomName(rt.id, rt.name));
    header.querySelector('[data-action="delete-room"]').addEventListener('click', () => deleteRoom(rt.id, rt.name));
    card.appendChild(header);

    // Capture mode selector
    const modeRow = document.createElement('div');
    modeRow.className = 'flex-between mb-1';
    modeRow.style.cssText = 'padding:.4rem 0';
    const modeLabel = document.createElement('span');
    modeLabel.className = 'text-muted';
    modeLabel.style.fontSize = '.85rem';
    modeLabel.textContent = 'Capture mode:';
    const modeSelect = document.createElement('select');
    modeSelect.style.cssText = 'width:auto;margin:0;padding:.2rem .5rem;font-size:.85rem';
    modeSelect.innerHTML = `
      <option value="traditional"${rt.capture_mode !== '360' ? ' selected' : ''}>Traditional</option>
      <option value="360"${rt.capture_mode === '360' ? ' selected' : ''}>360°</option>
    `;
    modeSelect.addEventListener('change', async () => {
      const r = await fetch(`/api/owner/rooms/${rt.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capture_mode: modeSelect.value }),
      });
      if (r.ok) showDetail(currentPropertyId);
      else alert('Failed to update capture mode');
    });
    modeRow.appendChild(modeLabel);
    modeRow.appendChild(modeSelect);
    card.appendChild(modeRow);

    const is360 = rt.capture_mode === '360';

    if (is360) {
      // 360 mode — show sector info instead of positions
      const note = document.createElement('p');
      note.className = 'text-muted';
      note.style.cssText = 'font-size:.85rem;padding:.4rem 0';
      note.textContent = '360° panoramic — 12 sectors captured automatically';
      card.appendChild(note);
    } else {
      // Traditional mode — show positions

      // Build ref image map from inline data
      const refMap = {};
      (rt.reference_images || []).forEach(img => { refMap[img.position_hint] = img; });

      // Position rows
      const positions = rt.positions || [];
      if (positions.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'text-muted';
        empty.style.fontSize = '.85rem';
        empty.textContent = 'No positions yet';
        card.appendChild(empty);
      } else {
        positions.forEach((pos, idx) => {
          const hint = pos.hint || pos.label;
          const ref = refMap[hint];
          const row = document.createElement('div');
          row.className = 'flex-between';
          row.style.cssText = 'padding:.4rem 0;border-bottom:1px solid var(--border);align-items:center';

          const left = document.createElement('div');
          left.className = 'flex gap-1';
          left.style.alignItems = 'center';

          if (ref && ref.thumbnail_url) {
            left.innerHTML = `<img src="${esc(ref.thumbnail_url)}" style="width:48px;height:36px;object-fit:cover;border-radius:3px;border:1px solid var(--primary);flex-shrink:0">`;
          } else {
            left.innerHTML = `<div style="width:48px;height:36px;border:1px dashed var(--border);border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:.6rem;color:var(--text-muted);flex-shrink:0">No ref</div>`;
          }
          const label = document.createElement('span');
          label.style.fontSize = '.9rem';
          label.textContent = pos.label || hint;
          left.appendChild(label);

          const right = document.createElement('div');
          right.className = 'flex gap-1';
          right.innerHTML = `
            <button class="btn btn-ghost" style="padding:.2rem .5rem;font-size:.8rem" data-action="edit">Edit</button>
            <button class="btn btn-danger" style="padding:.2rem .5rem;font-size:.8rem" data-action="delete">Delete</button>
          `;
          right.querySelector('[data-action="edit"]').addEventListener('click', () => editPosition(rt.id, idx));
          right.querySelector('[data-action="delete"]').addEventListener('click', () => deletePosition(rt.id, idx, hint));

          row.appendChild(left);
          row.appendChild(right);
          card.appendChild(row);
        });
      }

      // + Add Position button
      const addBtn = document.createElement('button');
      addBtn.className = 'btn btn-outline';
      addBtn.style.cssText = 'padding:.3rem .6rem;font-size:.85rem;margin-top:.5rem;width:100%';
      addBtn.textContent = '+ Add Position';
      addBtn.addEventListener('click', () => addPosition(rt.id));
      card.appendChild(addBtn);
    }

    div.appendChild(card);
  });
}

// ── Navigation to position builder ───────────────────────

function addPosition(roomId) {
  window.location.href = `/owner/position?room=${roomId}&property=${currentPropertyId}`;
}

function editPosition(roomId, index) {
  window.location.href = `/owner/position?room=${roomId}&property=${currentPropertyId}&index=${index}`;
}

// ── Position / Room actions ──────────────────────────────

async function deletePosition(roomId, index, hint) {
  if (!confirm(`Delete position "${hint}"?`)) return;

  // Fetch current room template
  const r = await fetch(`/api/owner/properties/${currentPropertyId}`);
  if (!r.ok) return alert('Failed to load property');
  const prop = await r.json();
  const rt = (prop.room_templates || []).find(t => t.id === roomId);
  if (!rt) return;

  // Remove position from array
  const positions = [...(rt.positions || [])];
  positions.splice(index, 1);

  // Update room template
  const ur = await fetch(`/api/owner/rooms/${roomId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ positions }),
  });
  if (!ur.ok) return alert('Failed to update room template');

  // Delete reference image if exists
  const refImages = (rt.reference_images || []).filter(img => img.position_hint === hint);
  for (const img of refImages) {
    await fetch(`/api/owner/reference-images/${img.id}`, { method: 'DELETE' });
  }

  showDetail(currentPropertyId);
}

async function deleteRoom(roomId, name) {
  if (!confirm(`Delete room "${name}" and all its positions?`)) return;
  const r = await fetch(`/api/owner/rooms/${roomId}`, { method: 'DELETE' });
  if (!r.ok) return alert('Failed to delete room');
  showDetail(currentPropertyId);
}

async function editRoomName(roomId, currentName) {
  const newName = prompt('Rename room:', currentName);
  if (!newName || newName.trim() === currentName) return;
  const r = await fetch(`/api/owner/rooms/${roomId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName.trim() }),
  });
  if (!r.ok) return alert('Failed to rename room');
  showDetail(currentPropertyId);
}

// ── Simplified add room (name only) ─────────────────────

async function addRoomTemplate() {
  if (!currentPropertyId) return;
  const name = document.getElementById('new-room-name').value.trim();
  if (!name) return alert('Room name is required');

  const r = await fetch(`/api/owner/properties/${currentPropertyId}/rooms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, positions: [], display_order: 0 }),
  });
  if (!r.ok) return alert('Failed to add room template');
  document.getElementById('new-room-name').value = '';
  showDetail(currentPropertyId);
}

// ── Helpers ──────────────────────────────────────────────

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
