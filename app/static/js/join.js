/* join.js — Handle shareable invite + referral links */

let _joinType = null;

document.addEventListener('DOMContentLoaded', async () => {
  const token = window.location.pathname.split('/join/')[1];
  if (!token) { showInvalid(); return; }

  try {
    const r = await fetch(`/api/join/${token}`);
    document.getElementById('loading-card').classList.add('hidden');

    if (!r.ok) { showInvalid(); return; }

    const data = await r.json();
    _joinType = data.type;

    if (data.type === 'invite') {
      document.getElementById('join-heading').textContent = `Join ${data.company_name}`;
      document.getElementById('join-subtitle').textContent = `You've been invited as: ${data.role}`;
    } else {
      document.getElementById('join-heading').textContent = 'Start Your Company';
      document.getElementById('join-subtitle').textContent =
        `Referred by ${data.referred_by}. Create your company and admin account.`;
      document.getElementById('company-name-group').classList.remove('hidden');
      document.getElementById('company-name').required = true;
    }

    document.getElementById('join-card').classList.remove('hidden');
  } catch (e) {
    showInvalid();
  }

  document.getElementById('join-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('join-error');
    errEl.style.display = 'none';

    const display_name = document.getElementById('display-name').value.trim();
    const email = document.getElementById('join-email').value.trim();
    const password = document.getElementById('join-password').value;
    const confirm = document.getElementById('join-confirm').value;
    const company_name = document.getElementById('company-name').value.trim();

    if (!display_name) { showError(errEl, 'Name is required'); return; }
    if (!email) { showError(errEl, 'Email is required'); return; }
    if (password.length < 8) { showError(errEl, 'Password must be at least 8 characters'); return; }
    if (password !== confirm) { showError(errEl, 'Passwords do not match'); return; }
    if (_joinType === 'referral' && !company_name) { showError(errEl, 'Company name is required'); return; }

    try {
      const r = await fetch(`/api/join/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name, email, password, company_name }),
      });
      const data = await r.json();
      if (!r.ok) { showError(errEl, data.detail || 'Failed'); return; }

      document.getElementById('join-card').classList.add('hidden');
      if (data.type === 'referral') {
        document.getElementById('success-msg').textContent =
          `Your company "${data.company_name}" has been created. You can now log in.`;
      }
      document.getElementById('success-card').classList.remove('hidden');
    } catch (err) {
      showError(errEl, 'Connection error');
    }
  });
});

function showInvalid() {
  document.getElementById('loading-card').classList.add('hidden');
  document.getElementById('invalid-card').classList.remove('hidden');
}

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = 'block';
}
