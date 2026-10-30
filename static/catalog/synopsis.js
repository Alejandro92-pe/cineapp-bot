/* Visual excerpts only. The full text stays in the DOM; no catalogue requests. */
window.CatalogSynopsis = (() => {
  const records = new Map();
  let frame = 0;
  function refresh() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => records.forEach((record, host) => {
      if (!host.isConnected) { observer?.unobserve(record.copy); records.delete(host); return; }
      if (!record.copy.getClientRects().length) return;
      const clipped = record.copy.scrollHeight > record.copy.clientHeight + 1;
      record.button.hidden = !record.expanded && !clipped && document.activeElement !== record.button;
    }));
  }
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(refresh) : null;
  function dispose(scope) {
    records.forEach((record, host) => {
      if (scope === host || scope.contains(host)) { observer?.unobserve(record.copy); records.delete(host); }
    });
  }
  let sequence = 0;
  function set(host, text, { title = 'Sinopsis', episode = false } = {}) {
    if (!host) return;
    dispose(host);
    host.replaceChildren();
    host.classList.add('qh-synopsis');
    host.classList.toggle('qh-synopsis-episode', episode);
    const copy = document.createElement('p');
    copy.id = 'qh-synopsis-' + (++sequence); copy.className = 'qh-synopsis-copy';
    copy.textContent = text || 'Sin sinopsis disponible.';
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'qh-synopsis-toggle'; button.hidden = true;
    button.textContent = 'Ver más'; button.setAttribute('aria-controls', copy.id);
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', 'Ver más: ' + title);
    const record = { copy, button, expanded: false };
    button.onclick = () => {
      record.expanded = !record.expanded;
      host.classList.toggle('is-expanded', record.expanded);
      button.textContent = record.expanded ? 'Ver menos' : 'Ver más';
      button.setAttribute('aria-expanded', String(record.expanded));
      button.setAttribute('aria-label', button.textContent + ': ' + title);
      // Collapse can move the button out of view; keep the same reading control reachable.
      if (!record.expanded) button.scrollIntoView({block:'nearest'});
      refresh();
    };
    host.classList.remove('is-expanded'); host.append(copy, button);
    records.set(host, record); observer?.observe(copy); refresh();
  }
  window.addEventListener('resize', refresh);
  return { set, dispose, refresh };
})();
