// Context-specific encoding for the legacy template strings.
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function jsonAttr(value) { return escapeHtml(JSON.stringify(value)); }
function safeImageSrc(value) {
  try {
    const url=new URL(value || '/static/placeholder.svg',location.origin);
    if (!['https:','http:'].includes(url.protocol)) return '/static/placeholder.svg';
    if (url.protocol==='http:' && url.origin!==location.origin) return '/static/placeholder.svg';
    return url.href.replace(/'/g,'%27').replace(/"/g,'%22');
  } catch { return '/static/placeholder.svg'; }
}
function safeImageUrl(value) { return escapeHtml(safeImageSrc(value)); }
