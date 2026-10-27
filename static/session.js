/* Same-origin API client. Session secret stays in an HttpOnly cookie. */
(() => {
  const originalFetch = window.fetch.bind(window);
  const state = {authenticated: false, user: null, is_admin: false, csrf_token: null};
  window.fetch = async function(input, options = {}) {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.origin !== location.origin) throw new Error('La aplicación solo consulta su propio servidor.');
    const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
    const method = (options.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (!['GET', 'HEAD'].includes(method) && state.csrf_token) headers.set('X-CSRF-Token', state.csrf_token);
    const response = await originalFetch(input, {...options, headers, credentials:'same-origin'});
    if (url.pathname.startsWith('/api/auth/') || url.pathname === '/api/admin/login') {
      const previousAccount = state.user?.id;
      const payload = await response.clone().json().catch(() => ({}));
      if (response.ok && 'authenticated' in payload) Object.assign(state, payload);
      if (response.ok && url.pathname === '/api/auth/logout') Object.assign(state, {authenticated:false,user:null,is_admin:false,csrf_token:null});
      if (previousAccount !== state.user?.id) window.dispatchEvent(new Event('session-changed'));
    }
    return response;
  };
  async function refresh() {
    const response = await fetch('/api/auth/me');
    if (!response.ok) throw new Error('No se pudo comprobar la sesión.');
    return response.json();
  }
  async function telegram() {
    const initData = window.Telegram?.WebApp?.initData;
    if (!initData) throw new Error('Abre esta página desde el bot para verificar Telegram.');
    const response = await fetch('/api/auth/telegram', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({init_data:initData})});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'No se pudo verificar Telegram.');
    return payload;
  }
  const ready = refresh().then(async () => {
    if (!state.authenticated && window.Telegram?.WebApp?.initData) await telegram();
    return state;
  }).catch(error => { state.error = error.message; return state; });
  window.AccountSession = {state, ready, refresh, telegram};
})();
