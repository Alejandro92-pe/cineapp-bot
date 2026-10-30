/* Load playback and episode controls only when a title is opened. */
(() => {
  const resources = [
    '/static/downloads.js', '/static/catalog/episodes.js?v=synopsis-1', '/static/catalog/synopsis.js?v=1',
    '/static/catalog/episode-downloads.js', '/static/catalog/trailers.js',
    '/static/catalog/player-screen.js?v=2', '/static/catalog/playback.js?v=screen-1'
  ];
  const loaded = new Map();
  function script(src) {
    if (!loaded.has(src)) loaded.set(src, new Promise((resolve, reject) => {
      const node = document.createElement('script');
      node.src = src;
      node.onload = resolve;
      node.onerror = () => { loaded.delete(src); node.remove(); reject(new Error('No se pudieron cargar los controles. Vuelve a abrir el tÃ­tulo.')); };
      document.head.append(node);
    }));
    return loaded.get(src);
  }
  window.DetailAssets = {ready: () => Promise.all(resources.map(script))};
})();
