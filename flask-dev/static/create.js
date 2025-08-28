// static/create.js
const form     = document.getElementById('gen-form');
const promptEl = document.getElementById('prompt');
const iframe   = document.getElementById('preview');
const saveBtn  = document.getElementById('save-btn');

let currentHTML = '';

function render(html) {
  currentHTML = html || '';
  if (iframe) iframe.srcdoc = currentHTML;
}

async function generateOrRefine(prompt) {
  const isRefine = !!currentHTML.trim();
  const url  = isRefine ? '/api/generate/edit' : '/api/generate/full';
  const body = isRefine ? { prompt, html: currentHTML } : { prompt };

  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || 'Request failed');
  }
  const data = await resp.json();
  render(data.html);
  if (saveBtn) saveBtn.disabled = false;
}

if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const prompt = (promptEl?.value || '').trim();
    if (!prompt) return;

    const originalText = e.submitter ? e.submitter.textContent : '';
    if (e.submitter) e.submitter.textContent = currentHTML ? 'Refining…' : 'Generating…';
    form.querySelectorAll('button, textarea').forEach(el => (el.disabled = true));
    if (saveBtn) saveBtn.disabled = true;

    try {
      await generateOrRefine(prompt);
    } catch (err) {
      alert(err.message || 'Failed');
    } finally {
      form.querySelectorAll('button, textarea').forEach(el => (el.disabled = false));
      if (e.submitter) e.submitter.textContent = originalText || 'Generate / Refine';
    }
  });
}

if (saveBtn) {
  saveBtn.addEventListener('click', async () => {
    if (!currentHTML.trim()) return;
    const prompt = (promptEl?.value || '').trim();
    saveBtn.disabled = true;

    try {
      const resp = await fetch('/api/generate/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html: currentHTML, prompt })
      });
      const data = await resp.json();
      if (data.ok) {
        window.location.href = data.path;
      } else {
        throw new Error('Save failed');
      }
    } catch (err) {
      alert(err.message || 'Failed to save');
      saveBtn.disabled = false;
    }
  });
}
