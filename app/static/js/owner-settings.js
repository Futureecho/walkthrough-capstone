/* owner-settings.js — AI provider settings */

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  document.getElementById('save-btn').addEventListener('click', saveSettings);
});

async function loadSettings() {
  try {
    const r = await fetch('/api/owner/settings');
    if (r.status === 401) { window.location.href = '/owner/login'; return; }
    const data = await r.json();

    document.getElementById('llm-provider').value = data.llm_provider || 'openai';
    document.getElementById('default-days').value = data.default_link_days || 7;

    document.getElementById('openai-status').textContent = data.openai_api_key_set ? 'Key saved' : '';
    document.getElementById('anthropic-status').textContent = data.anthropic_api_key_set ? 'Key saved' : '';
    document.getElementById('gemini-status').textContent = data.gemini_api_key_set ? 'Key saved' : '';
    document.getElementById('grok-status').textContent = data.grok_api_key_set ? 'Key saved' : '';
  } catch (e) {
    document.getElementById('save-msg').textContent = 'Failed to load settings';
  }
}

async function saveSettings() {
  const body = {
    llm_provider: document.getElementById('llm-provider').value,
    default_link_days: parseInt(document.getElementById('default-days').value) || 7,
  };

  // Only send keys if user typed something
  const openaiKey = document.getElementById('openai-key').value;
  const anthropicKey = document.getElementById('anthropic-key').value;
  const geminiKey = document.getElementById('gemini-key').value;
  const grokKey = document.getElementById('grok-key').value;

  if (openaiKey) body.openai_api_key = openaiKey;
  if (anthropicKey) body.anthropic_api_key = anthropicKey;
  if (geminiKey) body.gemini_api_key = geminiKey;
  if (grokKey) body.grok_api_key = grokKey;

  try {
    const r = await fetch('/api/owner/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error('Save failed');
    document.getElementById('save-msg').textContent = 'Settings saved!';
    document.getElementById('save-msg').style.color = 'var(--success)';

    // Clear key inputs
    document.getElementById('openai-key').value = '';
    document.getElementById('anthropic-key').value = '';
    document.getElementById('gemini-key').value = '';
    document.getElementById('grok-key').value = '';

    await loadSettings();
  } catch (e) {
    document.getElementById('save-msg').textContent = 'Failed to save';
    document.getElementById('save-msg').style.color = 'var(--danger)';
  }
}
