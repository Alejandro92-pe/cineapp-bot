/* Same-origin API client. Session secret stays in an HttpOnly cookie. */
(() => {
  const originalFetch = window.fetch.bind(window);
  const state = {authenticated: false, user: null, is_admin: false, csrf_token: null};
  let refreshing = null;
  function syncSession() {
    if (!refreshing) refreshing = refresh().finally(() => { refreshing = null; });
    return refreshing;
  }
  window.fetch = async function(input, options = {}) {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.origin !== location.origin) throw new Error('La aplicación solo consulta su propio servidor.');
    const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
    const method = (options.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (!['GET', 'HEAD'].includes(method) && state.csrf_token) headers.set('X-CSRF-Token', state.csrf_token);
    const accountBefore = state.user?.id;
    const retryInput = input instanceof Request ? input.clone() : input;
    let response = await originalFetch(input, {...options, headers, credentials:'same-origin'});
    // Only retry a request explicitly rejected BEFORE its handler ran. Never
    // replay network errors/payments with an uncertain outcome or another user.
    if (response.status === 403 && !url.pathname.startsWith('/api/auth/')) {
      const failure = await response.clone().json().catch(() => ({}));
      if (failure.code === 'csrf_refresh_required') {
        await syncSession();
        if (accountBefore && state.authenticated && state.user?.id === accountBefore) {
          headers.set('X-CSRF-Token', state.csrf_token);
          response = await originalFetch(retryInput, {...options, headers, credentials:'same-origin'});
        }
      }
    }
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
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') syncSession().catch(() => {});
  });
})();
