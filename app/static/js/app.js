/* app.js — Property selection + session management */

const API = {
  async get(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`GET ${url}: ${r.status}`);
    return r.json();
  },
  async post(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${url}: ${r.status}`);
    return r.json();
  },
};

let currentProperty = null;
let currentSession = null;

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadProperties();

  document.getElementById('property-select').addEventListener('change', onPropertyChange);
  document.getElementById('start-session-btn').addEventListener('click', onStartSession);
});

async function loadProperties() {
  try {
    const props = await API.get('/api/properties');
    const sel = document.getElementById('property-select');
    sel.innerHTML = '<option value="">— Select a property —</option>';
    props.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error('Failed to load properties:', e);
  }
}

async function onPropertyChange(e) {
  const id = e.target.value;
  if (!id) {
    document.getElementById('property-rooms').classList.add('hidden');
    document.getElementById('session-section').classList.add('hidden');
    document.getElementById('active-session').classList.add('hidden');
    document.getElementById('existing-sessions').classList.add('hidden');
    return;
  }

  currentProperty = await API.get(`/api/properties/${id}`);
  showPropertyRooms(currentProperty);
  document.getElementById('session-section').classList.remove('hidden');
  await loadExistingSessions(id);
}

function showPropertyRooms(prop) {
  const list = document.getElementById('room-list');
  list.innerHTML = '';
  prop.rooms.forEach(room => {
    const li = document.createElement('li');
    li.className = 'room-item';
    li.innerHTML = `<span>${room}</span><span class="room-status pending"></span>`;
    list.appendChild(li);
  });
  document.getElementById('property-rooms').classList.remove('hidden');
}

async function onStartSession() {
  if (!currentProperty) return;
  const type = document.getElementById('session-type').value;
  const tenant = document.getElementById('tenant-name').value;

  try {
    currentSession = await API.post(`/api/properties/${currentProperty.id}/sessions`, {
      type,
      tenant_name: tenant,
    });
    showActiveSession();
  } catch (e) {
    alert('Failed to create session: ' + e.message);
  }
}

function showActiveSession() {
  document.getElementById('session-section').classList.add('hidden');
  document.getElementById('active-session').classList.remove('hidden');
  document.getElementById('session-label').textContent = currentProperty.label;
  document.getElementById('session-type-badge').textContent = currentSession.type.replace('_', ' ');
  document.getElementById('session-tenant').textContent =
    currentSession.tenant_name ? `Tenant: ${currentSession.tenant_name}` : '';

  const list = document.getElementById('session-room-list');
  list.innerHTML = '';
  currentProperty.rooms.forEach(room => {
    const capture = (currentSession.captures || []).find(c => c.room === room);
    const status = capture ? capture.status : 'pending';
    const li = document.createElement('li');
    li.className = 'room-item';
    li.innerHTML = `
      <span>${room}</span>
      <div class="flex gap-1" style="align-items:center">
        <span class="room-status ${status}"></span>
        <a href="/capture?session=${currentSession.id}&room=${encodeURIComponent(room)}" class="btn btn-primary" style="padding:.4rem .8rem;font-size:.85rem">Capture</a>
      </div>
    `;
    list.appendChild(li);
  });
}

async function loadExistingSessions(propertyId) {
  // Load sessions via property's sessions
  try {
    const prop = await API.get(`/api/properties/${propertyId}`);
    const sessionsDiv = document.getElementById('sessions-list');
    sessionsDiv.innerHTML = '';
    // We need to get sessions — use the session IDs from captures or list endpoint
    // For now, show a note
    const sessions = prop.sessions || [];
    // Note: the property read doesn't include sessions by default in our schema,
    // but we can list them. For MVP, we'll use a separate approach.
    document.getElementById('existing-sessions').classList.add('hidden');
  } catch (e) {
    console.error(e);
  }
}
