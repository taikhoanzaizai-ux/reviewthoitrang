(() => {
  async function restoreLastVideo() {
    try {
      const r = await fetch('/api/cs_last_video', { cache: 'no-store' });
      const data = await r.json();
      if (!data.ok || !data.loaded) return;
      if (typeof meta !== 'undefined' && meta) return;

      meta = data.meta;
      video.src = data.url;
      video.load();
      clips = [defClip(0, meta.duration)];
      layers = [];
      selected = 0;
      selectedLayer = -1;
      playhead = 0;
      applyPreviewFrame();
      loadInspector();
      renderTimeline();
      seekTimeline(0);
      if (typeof setStatus === 'function') setStatus('Đã tự mở lại ' + data.name);
      console.log('[Codespaces] Restored last video:', data.name);
    } catch (e) {
      console.warn('[Codespaces] Restore last video failed', e);
    }
  }

  window.addEventListener('load', () => setTimeout(restoreLastVideo, 250));
})();
