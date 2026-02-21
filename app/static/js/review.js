/* review.js — Display capture review with quality and coverage results */

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const captureId = params.get('capture');

  if (!captureId) {
    return; // Nothing to show
  }

  try {
    // Fetch capture status and guidance in parallel
    const [statusRes, guidanceRes] = await Promise.all([
      fetch(`/api/captures/${captureId}/status`),
      fetch(`/api/captures/${captureId}/guidance`),
    ]);
    const status = await statusRes.json();
    const guidance = await guidanceRes.json();

    document.getElementById('review-content').classList.remove('hidden');
    document.getElementById('review-room').textContent = `Capture: ${captureId}`;

    // Coverage bar
    const pct = guidance.coverage_pct || 0;
    document.getElementById('review-coverage-fill').style.width = pct + '%';
    document.getElementById('review-coverage-text').textContent = pct + '% coverage';

    // Guidance instructions
    const guidDiv = document.getElementById('review-guidance');
    guidDiv.innerHTML = '';
    if (guidance.instructions && guidance.instructions.length) {
      guidance.instructions.forEach(inst => {
        const p = document.createElement('p');
        p.className = 'text-muted';
        p.textContent = inst;
        guidDiv.appendChild(p);
      });
    } else {
      guidDiv.innerHTML = '<p class="badge badge-success">Coverage complete</p>';
    }

    // Quality summary
    const qDiv = document.getElementById('quality-summary');
    const metrics = status.metrics_json || {};
    if (metrics.images) {
      for (const [imgId, info] of Object.entries(metrics.images)) {
        const badge = info.status === 'accepted' ? 'badge-success' : 'badge-danger';
        const div = document.createElement('div');
        div.className = 'flex-between mb-1';
        div.innerHTML = `
          <span class="text-muted">Image</span>
          <span class="badge ${badge}">${info.status}</span>
        `;
        qDiv.appendChild(div);
      }
    } else {
      qDiv.innerHTML = '<p class="text-muted">Quality check not yet run</p>';
    }

  } catch (e) {
    console.error('Failed to load review data:', e);
  }
});
