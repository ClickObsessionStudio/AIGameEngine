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

const trailerBtn = document.getElementById('trailer-btn');

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body || {})
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok || data.ok === false) {
    const msg = (data && (data.error || data.message)) || (await resp.text());
    throw new Error(msg || `Request to ${url} failed`);
  }
  return data;
}

if (trailerBtn) {
  trailerBtn.addEventListener('click', async () => {
    try {
      trailerBtn.disabled = true;
      trailerBtn.textContent = 'Generating trailer…';

      // Prefer the user prompt; you could also summarize currentHTML here if you want.
      const summary = (promptEl?.value || '').trim() || 'Arcade browser game trailer.';
      const titleForFile = 'game'; // you can pass the real title from server after save

      // 1) Generate trailer (local only; Vercel returns 501)
      const gen = await postJSON('/api/trailer/generate', {
        summary,
        title: titleForFile,
        duration: 6,
        resolution: '768P'
      });

      // Optional: show a link to the local MP4
      const mp4Url = gen.video_url;

      // 2) Upload to YouTube (local only; will OAuth on first run)
      trailerBtn.textContent = 'Uploading to YouTube…';
      const up = await postJSON('/api/trailer/upload', {
        filename: gen.filename,
        title: `Trailer – ${summary.slice(0, 40)}`,
        description: summary,
        privacy: 'unlisted'
      });

      trailerBtn.textContent = 'Done';
      alert(`Uploaded! ${up.watch_url}`);
      // You might also want to show the link in the UI:
      console.log('YouTube:', up.watch_url, 'Local MP4:', mp4Url);
    } catch (err) {
      alert(err.message || 'Trailer step failed');
    } finally {
      trailerBtn.textContent = '🎬 Upload Game Trailer';
      trailerBtn.disabled = false;
    }
  });
}