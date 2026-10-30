(() => {
  const CHUNK_SIZE = 4 * 1024 * 1024;

  async function sendChunk(uploadId, index, blob) {
    const fd = new FormData();
    fd.append('upload_id', uploadId);
    fd.append('index', String(index));
    fd.append('chunk', blob, `chunk-${index}.bin`);
    const r = await fetch('/api/cs_upload_chunk', { method: 'POST', body: fd });
    let data;
    try { data = await r.json(); }
    catch (_) { throw new Error(`Chunk ${index + 1}: backend không trả JSON (HTTP ${r.status}).`); }
    if (!r.ok || !data.ok) throw new Error(data.error || `Chunk ${index + 1} lỗi.`);
  }

  async function finalize(uploadId, file, totalChunks) {
    const r = await fetch('/api/cs_upload_finalize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: uploadId, filename: file.name, total_chunks: totalChunks })
    });
    let data;
    try { data = await r.json(); }
    catch (_) { throw new Error(`Finalize: backend không trả JSON (HTTP ${r.status}).`); }
    if (!r.ok || !data.ok) throw new Error(data.error || 'Không ghép được video.');
    return data;
  }

  async function chunkedPickVideo() {
    const input = document.getElementById('videoFileInput');
    if (!input) return { ok: false, error: 'Không tìm thấy input video.' };

    return new Promise((resolve) => {
      input.value = '';
      input.onchange = async () => {
        const file = input.files && input.files[0];
        if (!file) { resolve({ ok: false, cancelled: true }); return; }

        try {
          const total = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
          const uploadId = `cs-${Date.now()}-${Math.random().toString(36).slice(2)}`;
          for (let i = 0; i < total; i++) {
            const start = i * CHUNK_SIZE;
            const end = Math.min(file.size, start + CHUNK_SIZE);
            const blob = file.slice(start, end);
            if (typeof setStatus === 'function') {
              setStatus(`Đang nạp video ${Math.round((i / total) * 100)}% • ${i + 1}/${total}`);
            }
            await sendChunk(uploadId, i, blob);
          }
          if (typeof setStatus === 'function') setStatus('Đang ghép video và đọc metadata...');
          const data = await finalize(uploadId, file, total);
          if (typeof setStatus === 'function') setStatus('Đã nạp video 100%');
          resolve(data);
        } catch (e) {
          resolve({ ok: false, error: e && e.message ? e.message : String(e) });
        }
      };
      input.click();
    });
  }

  function installOverride() {
    if (!window.pywebview || !window.pywebview.api) {
      setTimeout(installOverride, 100);
      return;
    }
    window.pywebview.api.pick_video = chunkedPickVideo;
    console.log('[Codespaces] Chunked video uploader enabled');
  }

  installOverride();
})();
