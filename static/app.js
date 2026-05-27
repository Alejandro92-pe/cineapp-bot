// ============ CONFIGURACION ============
const API_BASE_URL = "https://cineapp-bot.onrender.com";
const TELEGRAM_BOT_USERNAME = "Popcornqh_admin_bot";    
const ADMIN_ID = 5824989040;

const tg = window.Telegram.WebApp;
tg.expand();

const userId = tg.initDataUnsafe?.user?.id;
const userLang = tg.initDataUnsafe?.user?.language_code || 'es';

// Si estamos en navegador (no en Telegram) y somos admin, redirigir al panel admin
(function checkBrowserAdmin() {
  const isInTelegram = !!(tg.initDataUnsafe?.user?.id);
  if (!isInTelegram) {
    const path = window.location.pathname;
    // Solo redirigir si estamos en la raíz, no si ya estamos en /static/admin.html
    if (!path.includes('admin')) {
      // Mostrar botón de acceso admin en navegador
      window.addEventListener('DOMContentLoaded', function() {
        const hint = document.createElement('a');
        hint.href = '/static/admin.html';
        hint.style.cssText = 'position:fixed;bottom:72px;right:12px;background:#e8b04b;color:#1a1200;font-size:11px;font-weight:600;padding:6px 12px;border-radius:20px;text-decoration:none;z-index:9999;opacity:0.9';
        hint.textContent = '⚙ Admin';
        document.body.appendChild(hint);
      });
    }
  }
})();

// Variables globales
let usuarioActual = null;
let membresiaActiva = null;
let planesMembresias = [];
let paginaActual = 1;
const LIMITE = 20;
let busquedaActual = "";
let totalPaginas = 1;
let cargando = false;

const LIMITE_INICIAL = 20;
const LIMITE_SCROLL = 5;

let limiteActual = LIMITE_INICIAL;

// ============ correccion hasta qui esta bien ============
// ============ INICIALIZACIÓN ============
async function iniciar() {

console.log("🎬 Iniciando app...");

// Mostrar spinner de carga inicial
const contenedor = document.getElementById('contenido');
if (contenedor) {
    contenedor.innerHTML = `<div class="app-loading"><div class="spinner"></div><span>Cargando...</span></div>`;
}

try {

const planesRes = await fetch(`${API_BASE_URL}/api/planes`);
planesMembresias = await planesRes.json();

if (userId) {

const userRes = await fetch(`${API_BASE_URL}/api/usuario`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ telegram_id: userId })
});

const userData = await userRes.json();

usuarioActual = userData.usuario;
membresiaActiva = userData.membresia;

}

// ── Inicializar user chip premium ──
inicializarUserChip();

} catch (error) {

console.error("Error cargando datos:", error);

}

actualizarBadge();

configurarFooter();

configurarEventosFooter();

cambiarVista('inicio');

}

function actualizarBadge(){
  // ahora lo maneja inicializarUserChip()
  inicializarUserChip();
}

// ============ AVATARES PERSONALIZADOS ============
// Aquí puedes agregar/cambiar los avatares — son SVG paths inline
const AVATARES_CUSTOM = [
  { id: 'fox',    emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 2l2 4H2L4 2zm16 0l2 4h-4l2-4zM12 4C7 4 3 8 3 13c0 3.3 1.8 6.2 4.5 7.8L7 23h10l-.5-2.2C19.2 19.2 21 16.3 21 13c0-5-4-9-9-9zm-3 8a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm6 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm-3 4c-1.1 0-2-.4-2.7-1h5.4c-.7.6-1.6 1-2.7 1z"/></svg>' },
  { id: 'wolf',   emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 3l3 6H2l4 5v3c2 1 4 1.5 6 1.5s4-.5 6-1.5v-3l4-5h-3l3-6-5 3c-1-.3-2-.5-5-.5s-4 .2-5 .5L2 3zm10 10a1 1 0 110 2 1 1 0 010-2z"/></svg>' },
  { id: 'dragon', emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16.5 6.5C15.8 4.2 14 2 12 2 9 2 7 4.5 7 7c0 1 .3 2 .7 2.8C6 11 5 13 5 15c0 3.9 3.1 7 7 7s7-3.1 7-7c0-2-.8-3.8-2-5.1l-.5-.4zM12 19c-2.2 0-4-1.8-4-4 0-1 .4-2 1-2.7.6.4 1.3.7 2 .7s1.4-.3 2-.7c.6.7 1 1.7 1 2.7 0 2.2-1.8 4-4 4z"/></svg>' },
  { id: 'ghost',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a9 9 0 00-9 9v11l3-3 3 3 3-3 3 3 3-3v-11a9 9 0 00-9-9zm-3 9a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm6 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3z"/></svg>' },
  { id: 'cat',    emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 4v5l2 2c0 5 4 9 8 9s8-4 8-9l2-2V4l-4 3c-1-.5-2-.8-3-1l-1-2h-4l-1 2c-1 .2-2 .5-3 1L2 4zm7 7a1 1 0 110 2 1 1 0 010-2zm6 0a1 1 0 110 2 1 1 0 010-2zm-3 3c-1 0-1.7-.4-2.2-1h4.4c-.5.6-1.2 1-2.2 1z"/></svg>' },
  { id: 'alien',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.1 2 5 5.8 5 10.5c0 2.1.7 4 1.8 5.5L8 22h8l1.2-6c1.1-1.5 1.8-3.4 1.8-5.5C19 5.8 15.9 2 12 2zm-2.5 8a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm5 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm-2.5 5c-2 0-3-.8-3-.8s1-.2 3-.2 3 .2 3 .2-1 .8-3 .8z"/></svg>' },
  { id: 'robot',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a2 2 0 012 2v1h3a2 2 0 012 2v10a2 2 0 01-2 2H7a2 2 0 01-2-2V7a2 2 0 012-2h3V4a2 2 0 012-2zM9 9a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm-5 5h4v1H10v-1z"/></svg>' },
  { id: 'ninja',  emoji: null, svg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8 2 5 5 5 9c0 2.4 1.2 4.5 3 5.7V22h8v-7.3C17.8 13.5 19 11.4 19 9c0-4-3-7-7-7zm-2 8a1 1 0 110 2 1 1 0 010-2zm4 0a1 1 0 110 2 1 1 0 010-2zm-2 3c-.8 0-1.5-.3-2-.7h4c-.5.4-1.2.7-2 .7z"/></svg>' },
];

// Avatar guardado en localStorage (clave por userId)
function getAvatarKey() { return `avatar_${userId || 'guest'}`; }
function getAvatarSeleccionado() { return localStorage.getItem(getAvatarKey()) || 'tg'; }
function setAvatarSeleccionado(id) { localStorage.setItem(getAvatarKey(), id); }

function inicializarUserChip() {
  const chip     = document.getElementById('userChip');
  const ucAvatar = document.getElementById('ucAvatar');
  const ucName   = document.getElementById('ucName');
  const ucBadge  = document.getElementById('ucBadge');
  if (!chip) return;

  const user = tg.initDataUnsafe?.user;
  const nombre = user?.first_name || usuarioActual?.nombre || 'Perfil';
  if (ucName) ucName.textContent = nombre;

  // Badge de membresía
  if (ucBadge) {
    const planNombre = membresiaActiva?.membresias_planes?.nombre;
    const starSVG = `<svg viewBox="0 0 24 24" width="9" height="9" fill="currentColor"><path d="M12 1l3 7h7l-5.5 4 2 7L12 15l-6.5 4 2-7L2 8h7z"/></svg>`;
    if (planNombre) {
      ucBadge.innerHTML = `${starSVG} ${planNombre.toUpperCase()}`;
      ucBadge.className = 'uc-badge vip';
    } else {
      ucBadge.innerHTML = `${starSVG} Sin membresía`;
      ucBadge.className = 'uc-badge';
    }
  }

  // Avatar
  renderizarAvatarChip(ucAvatar, user);
}

function renderizarAvatarChip(container, tgUser) {
  if (!container) return;
  const seleccionado = getAvatarSeleccionado();

  if (seleccionado === 'tg' && tgUser?.photo_url) {
    container.innerHTML = `<img src="${tgUser.photo_url}" alt="avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
  } else {
    const av = AVATARES_CUSTOM.find(a => a.id === seleccionado);
    if (av) {
      container.innerHTML = av.svg;
    } else {
      // fallback: inicial del nombre
      const user = tg.initDataUnsafe?.user;
      const inicial = (user?.first_name || usuarioActual?.nombre || 'U')[0].toUpperCase();
      container.innerHTML = `<span style="font-size:16px;font-weight:700;color:#e8b04b">${inicial}</span>`;
    }
  }
}

function configurarEventosFooter(){

document.querySelectorAll('.footer-item').forEach(item => {

item.addEventListener('click', () => {

const vista = item.dataset.destino || item.dataset.vista;

if (vista === 'mas') {
    abrirMenuMas();
    return;
}

window.cambiarVista(vista);

});

});

}

function obtenerSaludo() {

const hora = new Date().getHours();

if (hora < 12) return "¡Buenos días!";
if (hora < 19) return "¡Buenas tardes!";
return "¡Buenas noches!";

}

function renderHero() {

const saludo = obtenerSaludo();
const nombre = usuarioActual?.nombre || "Usuario";

let html = `
<div class="hero" style="background-image:url('/static/hero-bg.jpg')">
<div class="hero-content">
`;

if(membresiaActiva){

html += `
<h2>${saludo}</h2>
<h1>${nombre}</h1>
<p>Disfruta del contenido</p>
`;

}else{

html += `
<h1>BIENVENIDO</h1>
<p>Disfruta de Series, Películas y más...</p>
<button class="hero-btn" onclick="cambiarVista('membresias')">
Accede Ahora
</button>
`;

}

html += `
</div>
</div>
`;

return html;

}

// ============ CONFIGURAR FOOTER ============
function configurarFooter() {
    const items = document.querySelectorAll('.footer-item');

    items.forEach(item => {
        if (item.dataset.vista === 'pedidos') {

            const span = item.querySelector('span');

            if (userId == ADMIN_ID) {
                span.innerText = 'Admin';
                item.dataset.destino = 'admin';
            } else {
                span.innerText = 'Pedidos';
                item.dataset.destino = 'pedidos';
            }
        }
    });
}

// ============ CAMBIAR VISTA ============
window.cambiarVista = async function(vista) {
    console.log("📱 Vista:", vista);
    
    // Actualizar clase activa en footer
    document.querySelectorAll('.footer-item').forEach(el => {
    el.classList.remove('activo');
    if (el.dataset.vista === vista) {
        el.classList.add('activo');
    }
    });
    
    const contenedor = document.getElementById('contenido');
    
    if (vista === 'inicio') {
        contenedor.innerHTML = `
        ${renderHero()}
            <h2 class="titulo-seccion">Tendencias</h2>
            <div id="tendencias" class="tendencias-container"></div>
            <div id="contenidoGeneros"></div>
        `;
        cargarTendencias();
        cargarGeneros();
        buscarContenido(1);
    }

    else if (vista === 'explorar') {
        tipoActual = tipoActual || 'todo';
        const tipoInicial = tipoActual;
        paginaActual = 1;
        totalPaginas = 1;
        cargando = false;
        window.filtroGenero = window.filtroGenero || '';
        window.filtroAnio   = window.filtroAnio   || '';

        contenedor.innerHTML = `
            <div class="buscador">
                <input type="text" id="buscarInput" placeholder="Buscar película o serie..." oninput="onBuscarInput()">
                <span>🔍</span>
            </div>

            <!-- Tabs de tipo -->
            <div class="tabs" style="overflow-x:auto;flex-wrap:nowrap;scrollbar-width:none">
                <div class="tab ${tipoInicial==='todo'?'activo':''}"     onclick="cambiarTipo('todo', event)">Todo</div>
                <div class="tab ${tipoInicial==='pelicula'?'activo':''}" onclick="cambiarTipo('pelicula', event)">Películas</div>
                <div class="tab ${tipoInicial==='serie'?'activo':''}"    onclick="cambiarTipo('serie', event)">Series</div>
                <div class="tab ${tipoInicial==='biblico'?'activo':''}"  onclick="cambiarTipo('biblico', event)">Bíblico</div>
                <div class="tab ${tipoInicial==='anime'?'activo':''}"    onclick="cambiarTipo('anime', event)">Anime</div>
                <div class="tab ${tipoInicial==='Peliculas anime'?'activo':''}" onclick="cambiarTipo('Peliculas anime', event)">Pel. Anime</div>
            </div>

            <!-- Filtros combinados: Género + Año -->
            <div id="filtros-extra" style="display:flex;gap:8px;padding:8px 0 4px;overflow-x:auto;scrollbar-width:none">
                <select id="filtroGeneroSel" onchange="aplicarFiltrosExtra()"
                    style="flex:1;min-width:120px;padding:8px 10px;border-radius:10px;
                    border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.06);
                    color:#f0f0f2;font-size:13px;outline:none;cursor:pointer">
                    <option value="">🎭 Género</option>
                </select>
                <select id="filtroAnioSel" onchange="aplicarFiltrosExtra()"
                    style="flex:1;min-width:100px;padding:8px 10px;border-radius:10px;
                    border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.06);
                    color:#f0f0f2;font-size:13px;outline:none;cursor:pointer">
                    <option value="">📅 Año</option>
                    ${Array.from({length: 35}, (_,i) => new Date().getFullYear() - i)
                        .map(y => `<option value="${y}" ${window.filtroAnio==y?'selected':''}>${y}</option>`).join('')}
                </select>
                <button id="btnLimpiarFiltros" onclick="limpiarFiltrosExtra()"
                    style="padding:8px 12px;border-radius:10px;border:1px solid rgba(255,255,255,0.1);
                    background:rgba(255,255,255,0.04);color:rgba(255,255,255,0.5);font-size:12px;
                    cursor:pointer;white-space:nowrap;display:${window.filtroGenero||window.filtroAnio?'block':'none'}">
                    ✕ Limpiar
                </button>
            </div>

            <div id="generosExplorar"></div>
            <div id="resultados" class="grid" style="display:none;"></div>
            <div id="scroll-loader" class="scroll-loader" style="display:none;">
                <div class="spinner"></div>
            </div>
        `;

        // Poblar géneros en el select
        _poblarSelectGeneros();

        cargarGenerosEnContenedor('generosExplorar');
        if (tipoInicial !== 'todo' || window.filtroGenero || window.filtroAnio) {
            mostrarResultadosExplorar();
        }
        activarScrollInfinito();
    }
    
    else if (vista === 'membresias') {
    let html = `<div class="membresias-wrap">

        <!-- OFERTA ESPECIAL -->
        <div class="mem-oferta-card">
            <div class="mem-oferta-titulo">OFERTA ESPECIAL</div>
            <div class="mem-oferta-subtitulo">Oferta termina en:</div>
            <div class="mem-oferta-row">
                <div class="mem-pct-wrap">
                    <span class="mem-pct-num">50</span><span class="mem-pct-sym">%<br>OFF</span>
                </div>
                <div class="mem-contador">
                    <div class="mem-bloque" id="horas">00</div>
                    <span class="mem-sep">h</span>
                    <div class="mem-bloque" id="minutos">00</div>
                    <span class="mem-sep">m</span>
                    <div class="mem-bloque" id="segundos">00</div>
                    <span class="mem-sep">s</span>
                </div>
            </div>
            <div class="mem-cupon-row">
                <span class="mem-cupon-label">Código de Dto</span>
                <button class="mem-cupon-btn" onclick="copiarCodigo('QH50OFF')">
                    <small>Copiar código</small>
                    QH50OFF
                </button>
            </div>
            <div class="mem-oferta-instruccion">Usa este código al pagar con tarjeta</div>
        </div>

        
     <div class="tutorial-pago">
    <h3>🎥 Tutorial de cómo pagar con:</h3>
    <div class="tutorial-botones">
        <button onclick="verTutorialYape()">📱 Yape / Plin</button>
        <button onclick="verTutorialTarjeta()">💳 Tarjeta</button>
    </div>
     </div>
    

        <div class="planes-nueva">
        
    `;
    
    planesMembresias.forEach(p => {
        const precioSolesOriginal    = p.precio_soles;
        const precioDolaresOriginal  = p.precio_dolares;
        const precioSolesDescuento   = Math.round(precioSolesOriginal * 0.5);
        const precioDolaresDescuento = (precioDolaresOriginal * 0.5).toFixed(2);

        html += `
        <div class="plan-nueva">
            <div class="plan-nueva-nombre">${p.nombre.toUpperCase()}</div>
            <div class="plan-nueva-dur">${p.duracion_dias} días . ${p.pedidos_por_mes} pedidos</div>
            <div class="plan-nueva-precios">
                <span class="pn-orig">$${precioDolaresOriginal}</span>
                <span class="pn-desc">$${precioDolaresDescuento}</span>
                <br>
                <span class="pn-orig">S/${precioSolesOriginal}</span>
                <span class="pn-desc">S/ ${precioSolesDescuento}</span>
            </div>
            <div class="plan-nueva-btns">
                <button class="btn-yape-plin" onclick="pagarPeru('${p.nombre}', ${precioSolesDescuento})">
                    <span class="btn-paga-con">Paga con</span> <strong>Yape o Plin</strong>
                </button>
                <button class="btn-tarjeta-nueva" onclick="pagarInternacional('${p.nombre}')">
                    <span class="btn-paga-con">Paga con</span> <strong>Tarjeta y mas</strong>
                </button>
            </div>
        </div>
        `;
    });

    html += `</div>
        <button class="btn-verificar" onclick="verificarCompra()">🔎 Verificar compra</button>
    </div>`;

    contenedor.innerHTML = html;
    iniciarContadorOferta();
}
    
    else if (vista === 'pedidos') {
        // Si es admin, redirigir a admin
        if (userId == ADMIN_ID) {
            cambiarVista('admin');
            return;
        }

        // Usar los datos ya cargados en usuarioActual
        let usuario = usuarioActual;
        if (!usuario) {
            // Si por alguna razón no está cargado, lo obtenemos del backend
            const userRes = await fetch(`${API_BASE_URL}/api/usuario`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ telegram_id: userId })
            });
            const userData = await userRes.json();
            usuario = userData.usuario;
            membresiaActiva = userData.membresia;
        }

        // Si no existe en la BD, mostramos mensaje de "Necesitas membresía"
        if (!usuario) {
            contenedor.innerHTML = `
                <div class="text-center p-20 text-gris">
                    🔒 Necesitas una membresía activa<br>
                    <small>Los pedidos están disponibles desde el plan Silver</small><br>
                    <button class="btn-comprar" onclick="cambiarVista('membresias')">
                        Ver Membresías
                    </button>
                </div>
            `;
            return;
        }

        // Verificar membresía activa (ya debería estar en membresiaActiva)
        if (!membresiaActiva) {
            contenedor.innerHTML = `
                <div class="text-center p-20 text-gris">
                    🔒 Necesitas una membresía activa<br>
                    <small>Los pedidos están disponibles desde el plan Silver</small><br>
                    <button class="btn-comprar" onclick="cambiarVista('membresias')">
                        Ver Membresías
                    </button>
                </div>
            `;
            return;
        }

        const plan = membresiaActiva.membresias_planes;
        const pedidosExtra = membresiaActiva.pedidos_extra || 0;
        const limiteBase = plan.pedidos_por_mes;
        const limiteTotal = limiteBase + pedidosExtra;

        // Si el plan base es 0 y no hay pedidos extra (usuario sin pedidos)
        if (limiteBase === 0 && pedidosExtra === 0) {
            contenedor.innerHTML = `
                <div class="perfil-card">
                    <h3>🔒 Plan ${plan.nombre.toUpperCase()}</h3>
                    <p>Tu plan no incluye pedidos.</p>
                    <p>Actualiza a <strong>Silver o superior</strong> para solicitar películas.</p>
                    <button class="btn-comprar" onclick="cambiarVista('membresias')">
                        Mejorar Plan
                    </button>
                </div>
            `;
            return;
        }

        // Obtener pedidos del usuario desde el backend
        const pedidosRes = await fetch(`${API_BASE_URL}/api/mis_pedidos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ telegram_id: userId })
        });
        const pedidosData = await pedidosRes.json();
        const todosPedidos = pedidosData.pedidos || [];

        // Filtrar pedidos dentro del período de la membresía actual
        const inicio = new Date(membresiaActiva.fecha_inicio);
        const fin = new Date(); // hasta ahora
        const pedidosPeriodo = todosPedidos.filter(p => {
            const fecha = new Date(p.fecha_pedido);
            return fecha >= inicio && fecha <= fin;
        });

        const usados = pedidosData.usados || 0;
        const restantes = limiteTotal - usados;

        // Si ya no quedan pedidos
        if (restantes <= 0) {

    contenedor.innerHTML = `
        <div class="perfil-card">
            <p>📊 Usados: ${usados}/${limiteTotal}</p>
            <p class="text-gris">⚠️ Alcanzaste el límite de tu plan</p>
        </div>

        <div class="pedidos-form">
            <h3>🎬 Pedir Película/Serie</h3>
            <input type="text" disabled placeholder="Límite alcanzado">
            <select disabled>
                <option>Película</option>
            </select>
            <button disabled class="btn-pedir disabled">
                Límite alcanzado
            </button>
        </div>

        <div id="listaPedidos"></div>
    `;

    cargarPedidos();
    return;
        }
        // Mostrar formulario de pedido
        contenedor.innerHTML = `
            <div class="perfil-card">
                <p>📊 Usados: ${usados}/${limiteTotal} | 🎟 Restantes: ${restantes}</p>
            </div>
            <div class="pedidos-form">
                <h3>🎬 Pedir Película/Serie</h3>
                <input type="text" id="tituloPedido" placeholder="Título">
                <select id="tipoPedido">
                    <option value="pelicula">Película</option>
                    <option value="serie">Serie</option>
                </select>
                <button class="btn-pedir" onclick="enviarPedido()">Solicitar</button>
            </div>
            <div id="listaPedidos"></div>
        `;

        cargarPedidos();
    }
    
    else if (vista === 'perfil') {
        await renderizarPerfil(contenedor);
    }
    
    else if (vista === 'buscar') {
    tipoActual = 'todo';
    contenedor.innerHTML = `
        <div class="buscador">
            <input type="text" id="buscarInput" placeholder="Escribe Títulos o géneros" oninput="onBuscarInput()" autofocus>

            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
        </div>

        <!-- Categorías rápidas (se ocultan cuando hay texto) -->
        <div id="categoriasBuscar" class="buscar-categorias">
            <div class="buscar-cat-item" onclick="filtrarPorTipo('disponible')">Disponible para descargar</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('serie')">Series Tv</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('accion')">Acción</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('anime')">Anime</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('peliculas anime')">Películas Anime</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('ciencia ficcion')">Ciencia Ficción</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('comedia')">Comedias</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('drama')">Dramas</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('terror')">Terror Suspense</div>
            <div class="buscar-cat-item" onclick="filtrarPorTipo('familia')">Familia Niños</div>
        </div>

        <!-- Resultados -->
        <div id="resultados" class="grid" style="display:none;"></div>
        <div id="paginacion"></div>
    `;}

    else if (vista === 'mas') {
        // Mostrar overlay menú Más
        abrirMenuMas();
        return; // no actualizar footer
    }
    
    else if (vista === 'admin') {
        if (userId != ADMIN_ID) {
            contenedor.innerHTML = '<div class="text-center p-20 text-gris">⛔ Acceso no autorizado</div>';
            return;
        }

        contenedor.innerHTML = `
            <div class="admin-dashboard">
                <h2>👑 Panel de Administración</h2>
                
                <!-- Pestañas -->
                <div class="admin-tabs">
                    <div class="tab activo" onclick="cambiarAdminTab('membresias')">💰 Membresías</div>
                    <div class="tab" onclick="cambiarAdminTab('pedidos')">📦 Pedidos</div>
                    <div class="tab" onclick="cambiarAdminTab('usuarios')">👥 Usuarios</div>
                </div>
                
                <!-- Contenido dinámico -->
                <div id="admin-contenido" class="admin-contenido"></div>
            </div>
        `;
        
        // Cargar primera pestaña
        cambiarAdminTab('membresias');
    }
};



// ============ FAVORITOS ============
function getFavoritosKey() { return `favs_${userId || 'guest'}`; }
function getFavoritos() {
  try { return JSON.parse(localStorage.getItem(getFavoritosKey()) || '[]'); } catch { return []; }
}
function toggleFavorito(item) {
  const favs = getFavoritos();
  const idx = favs.findIndex(f => f.id === item.id);
  if (idx >= 0) favs.splice(idx, 1);
  else favs.unshift({ ...item });  // guardar objeto completo para que descarga/fuente/tmdb_id estén disponibles
  localStorage.setItem(getFavoritosKey(), JSON.stringify(favs.slice(0, 200)));
  return idx < 0; // true si se agregó
}
function esFavorito(itemId) { return getFavoritos().some(f => f.id === itemId); }

window.toggleFavBtn = function(itemId, item, btn) {
  const ahora = toggleFavorito(item);
  btn.innerHTML = ahora ? favHeartSVG(true) : favHeartSVG(false);
  btn.classList.toggle('fav-active', ahora);
};

function favHeartSVG(active) {
  return active
    ? `<svg viewBox="0 0 24 24" width="18" height="18" fill="#e8b04b"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.27 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.08C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.77-3.4 6.86-8.55 11.53L12 21.35z"/></svg>`
    : `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.27 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.08C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.77-3.4 6.86-8.55 11.53L12 21.35z"/></svg>`;
}

// ============ HISTORIAL ============
function getHistorialKey() { return `hist_${userId || 'guest'}`; }
function getHistorial() {
  try { return JSON.parse(localStorage.getItem(getHistorialKey()) || '[]'); } catch { return []; }
}
function agregarAlHistorial(item) {
  const hist = getHistorial().filter(h => h.id !== item.id);
  hist.unshift({ ...item, visto_en: Date.now() });  // guardar objeto completo
  localStorage.setItem(getHistorialKey(), JSON.stringify(hist.slice(0, 50)));
}

// ============ PERFIL PREMIUM ============
async function renderizarPerfil(contenedor) {
  const user = tg.initDataUnsafe?.user;
  const nombre = user?.first_name || usuarioActual?.nombre || 'Usuario';
  const planNombre = membresiaActiva?.membresias_planes?.nombre?.toUpperCase() || null;
  const vence = membresiaActiva?.fecha_fin
    ? new Date(membresiaActiva.fecha_fin).toLocaleDateString('es-PE')
    : null;
  const favs = getFavoritos();
  const hist = getHistorial();
  const selAvatar = getAvatarSeleccionado();

  const SVG_USER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="16" height="16"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  const SVG_STAR = `<svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13"><path d="M12 1l3 7h7l-5.5 4 2 7L12 15l-6.5 4 2-7L2 8h7z"/></svg>`;
  const SVG_HEART = `<svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.27 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.08C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.77-3.4 6.86-8.55 11.53L12 21.35z"/></svg>`;
  const SVG_CLOCK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="15" height="15"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>`;
  const SVG_PLAY = `<svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M8 5v14l11-7z"/></svg>`;
  const SVG_CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M20 6L9 17l-5-5"/></svg>`;
  const SVG_UPGRADE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M12 19V5M5 12l7-7 7 7"/></svg>`;
  const SVG_DOWN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M12 5v14M5 12l7 7 7-7"/></svg>`;

  // Avatar actual
  const avatarHTML = (() => {
    if (selAvatar === 'tg' && user?.photo_url) {
      return `<img src="${user.photo_url}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
    }
    const av = AVATARES_CUSTOM.find(a => a.id === selAvatar);
    return av ? av.svg : SVG_USER;
  })();

  // Generar selector de avatares
  const tgOpcion = `<div class="pav-item ${selAvatar === 'tg' ? 'selected' : ''}" onclick="seleccionarAvatar('tg')" title="Foto de Telegram">
    ${user?.photo_url ? `<img src="${user.photo_url}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">` : `<svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg>`}
  </div>`;

  const avsHTML = AVATARES_CUSTOM.map(av =>
    `<div class="pav-item ${selAvatar === av.id ? 'selected' : ''}" onclick="seleccionarAvatar('${av.id}')">${av.svg}</div>`
  ).join('');

  // Favoritos row
  const favsHTML = favs.length === 0
    ? `<p class="perf-empty">Aún no tienes favoritos. Toca ${SVG_HEART} en cualquier tarjeta.</p>`
    : `<div class="perf-scroll-row">${favs.slice(0,10).map(f => `
        <div class="perf-mini-card" onclick='abrirModalContenido(${JSON.stringify(f).replace(/'/g, "\'")})'>
          <div class="perf-mini-img" style="${f.imagen_url ? `background-image:url('${f.imagen_url}')` : 'background:#1e1e2a'}">
            ${!f.imagen_url ? SVG_PLAY : ''}
          </div>
          <div class="perf-mini-title">${f.titulo}</div>
        </div>`).join('')}
      </div>`;

  // Historial row
  const histHTML = hist.length === 0
    ? `<p class="perf-empty">Todavía no has abierto nada. Aparecerá aquí cuando explores contenido.</p>`
    : `<div class="perf-scroll-row">${hist.slice(0,10).map(h => {
        const hace = tiempoRelativo(h.visto_en);
        return `<div class="perf-mini-card" onclick='abrirModalContenido(${JSON.stringify(h).replace(/'/g, "\'")})'>
          <div class="perf-mini-img" style="${h.imagen_url ? `background-image:url('${h.imagen_url}')` : 'background:#1e1e2a'}">
            ${!h.imagen_url ? SVG_PLAY : ''}
            <span class="perf-mini-time">${hace}</span>
          </div>
          <div class="perf-mini-title">${h.titulo}</div>
        </div>`;
      }).join('')}
      </div>`;

  // Estadísticas
  const pedidosUsados = usuarioActual?.pedidos_mes || 0;
  const pedidosTotal  = membresiaActiva?.membresias_planes?.pedidos_por_mes || 0;

  contenedor.innerHTML = `
  <div class="perf-page">

    <!-- Hero -->
    <div class="perf-hero">
      <div class="perf-av-ring" id="perfAvRing">${avatarHTML}</div>
      <div class="perf-hero-info">
        <div class="perf-hero-name">${nombre}</div>
        ${planNombre
          ? `<div class="perf-hero-plan">${SVG_STAR} ${planNombre}${vence ? ` · ${vence}` : ''}</div>`
          : `<div class="perf-hero-plan no-plan">Sin membresía activa</div>`}
      </div>
    </div>

    <!-- Stats -->
    <div class="perf-stats">
      <div class="perf-stat">
        <span class="perf-stat-n">${favs.length}</span>
        <span class="perf-stat-l">${SVG_HEART} Favoritos</span>
      </div>
      <div class="perf-stat-sep"></div>
      <div class="perf-stat">
        <span class="perf-stat-n">${hist.length}</span>
        <span class="perf-stat-l">${SVG_CLOCK} Vistos</span>
      </div>
      <div class="perf-stat-sep"></div>
      <div class="perf-stat">
        <span class="perf-stat-n">${pedidosTotal}</span>
        <span class="perf-stat-l">${SVG_CHECK} Pedidos</span>
      </div>
    </div>

    <!-- Selector avatar -->
    <div class="perf-section">
      <div class="perf-section-title">Elige tu avatar</div>
      <div class="perf-avatars" id="perfAvatarGrid">
        ${tgOpcion}
        ${avsHTML}
      </div>
    </div>

    <!-- Favoritos -->
    <div class="perf-section">
      <div class="perf-section-title">${SVG_HEART} Mis favoritos <span class="perf-count">${favs.length}</span></div>
      ${favsHTML}
    </div>

    <!-- Historial -->
    <div class="perf-section">
      <div class="perf-section-title">${SVG_CLOCK} Estabas viendo <span class="perf-count">${hist.length}</span></div>
      ${histHTML}
    </div>

    <!-- Membresía info -->
    <div class="perf-section">
      <div class="perf-section-title">${SVG_STAR} Membresía</div>
      <div class="perf-mem-card">
        ${planNombre ? `
          <div class="perf-mem-name">${planNombre}</div>
          <div class="perf-mem-vence">Vence: ${vence}</div>
              <div class="perf-mem-btns">
            <button class="perf-btn-ghost" onclick="subirPlan()">${SVG_UPGRADE} Subir plan</button>
            <button class="perf-btn-ghost" onclick="bajarPlan()">${SVG_DOWN} Bajar plan</button>
          </div>
        ` : `
          <div class="perf-mem-empty">No tienes membresía activa. Activa una para acceder al contenido completo.</div>
          <button class="perf-btn-gold" onclick="cambiarVista('membresias')">${SVG_STAR} Ver planes</button>
        `}
      </div>
    </div>

    <div style="height:20px"></div>
  </div>`;
}

function tiempoRelativo(timestamp) {
  const diff = Date.now() - timestamp;
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'ahora';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

window.seleccionarAvatar = function(id) {
  setAvatarSeleccionado(id);
  // Actualizar grid visual
  document.querySelectorAll('.pav-item').forEach(el => el.classList.remove('selected'));
  event?.target?.closest('.pav-item')?.classList.add('selected');
  // Actualizar hero avatar
  const ring = document.getElementById('perfAvRing');
  if (ring) {
    const user = tg.initDataUnsafe?.user;
    if (id === 'tg' && user?.photo_url) {
      ring.innerHTML = `<img src="${user.photo_url}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
    } else {
      const av = AVATARES_CUSTOM.find(a => a.id === id);
      if (av) ring.innerHTML = av.svg;
    }
  }
  // Actualizar chip del header
  const ucAvatar = document.getElementById('ucAvatar');
  const user = tg.initDataUnsafe?.user;
  renderizarAvatarChip(ucAvatar, user);
};

// ============ FUNCIONES DE ADMIN ============
window.cambiarAdminTab = async function(tab) {
    // Actualizar pestañas
    document.querySelectorAll('.admin-tabs .tab').forEach(t => t.classList.remove('activo'));
    document.querySelectorAll('.admin-tabs .tab').forEach(t => {
        if (t.textContent.includes(tab === 'membresias' ? 'Membresías' : 
                                   tab === 'pedidos' ? 'Pedidos' : 'Usuarios')) {
            t.classList.add('activo');
        }
    });

    const contenedor = document.getElementById('admin-contenido');
    
    if (tab === 'membresias') {
        await cargarMembresiasPendientes(contenedor);
    } else if (tab === 'pedidos') {
        await cargarPedidosAdmin(contenedor);
    } else if (tab === 'usuarios') {
        await cargarUsuariosAdmin(contenedor);
    }
};

// 1. Membresías pendientes (aprobaciones)
async function cargarMembresiasPendientes(contenedor) {
    contenedor.innerHTML = '<div class="text-center p-20">⏳ Cargando solicitudes...</div>';
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/pagos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: userId })
        });
        const pagos = await response.json();

        let html = `
            <div style="margin-bottom: 20px;">
                <h3>💰 Solicitudes de Membresía Pendientes</h3>
                <p style="color: #aaa;">Total: ${pagos?.length || 0} pendientes</p>
            </div>
        `;

        if (!pagos || pagos.length === 0) {
            html += '<p class="text-gris">No hay solicitudes pendientes</p>';
        } else {
            html += '<div class="lista-solicitudes">';
            pagos.forEach(p => {
                const fecha = new Date(p.created_at).toLocaleString();
                html += `
                    <div class="perfil-item" style="margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong>Usuario ID:</strong> ${p.usuario_id}<br>
                                <strong>Plan:</strong> ${p.membresia_comprada}<br>
                                <strong>Monto:</strong> S/${p.monto}<br>
                                <small>${fecha}</small>
                            </div>
                            <button class="btn-comprar" onclick="aprobarPago(${p.id})" style="width: auto; padding: 8px 15px;">
                                ✅ Aprobar
                            </button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }
        contenedor.innerHTML = html;
    } catch (error) {
        contenedor.innerHTML = '<p class="text-gris">❌ Error cargando solicitudes</p>';
    }
}

// 2. Pedidos (gestión)
async function cargarPedidosAdmin(contenedor) {
    contenedor.innerHTML = '<div class="text-center p-20">⏳ Cargando pedidos...</div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/admin_pedidos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: userId })
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.error);

        const pendientes = result.pedidos.filter(p => p.estado === 'pendiente');
        const entregados = result.pedidos.filter(p => p.estado === 'entregado');

        let html = `
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <button class="tab ${!window.filtroPedidos || window.filtroPedidos === 'todos' ? 'activo' : ''}" onclick="filtrarPedidos('todos')">📋 Todos (${result.total})</button>
                <button class="tab ${window.filtroPedidos === 'pendientes' ? 'activo' : ''}" onclick="filtrarPedidos('pendientes')">⏳ Pendientes (${pendientes.length})</button>
                <button class="tab ${window.filtroPedidos === 'entregados' ? 'activo' : ''}" onclick="filtrarPedidos('entregados')">✅ Entregados (${entregados.length})</button>
            </div>
            <div id="pedidos-lista"></div>
        `;
        
        contenedor.innerHTML = html;
        window.pedidosData = result.pedidos;
        filtrarPedidos('todos');
        
    } catch (error) {
        contenedor.innerHTML = '<p class="text-gris">❌ Error cargando pedidos</p>';
    }
}

window.filtrarPedidos = function(filtro) {
    window.filtroPedidos = filtro;
    const lista = document.getElementById('pedidos-lista');
    if (!lista || !window.pedidosData) return;
    
    // Actualizar pestañas de filtro
    document.querySelectorAll('#admin-contenido .tab').forEach(btn => btn.classList.remove('activo'));
    event?.target.classList.add('activo');
    
    let filtrados = window.pedidosData;
    if (filtro === 'pendientes') filtrados = window.pedidosData.filter(p => p.estado === 'pendiente');
    else if (filtro === 'entregados') filtrados = window.pedidosData.filter(p => p.estado === 'entregado');
    
    if (filtrados.length === 0) {
        lista.innerHTML = '<p class="text-gris">No hay pedidos</p>';
        return;
    }
    
    let html = '';
    filtrados.forEach(p => {
        const isPend  = p.estado === 'pendiente';
        const color   = isPend ? '#f59e0b' : '#10b981';
        const iconEst = isPend ? '⏳' : '✅';
        const labelEst = isPend ? 'Pendiente' : 'Entregado';
        html += `
        <div class="pedido-card" style="
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-left: 3px solid ${color};
            border-radius: 12px;
            padding: 14px 14px 12px;
            margin-bottom: 10px;
            transition: background 0.15s;
        ">
            <!-- Cabecera: título + badge estado -->
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:10px">
                <div style="flex:1;min-width:0">
                    <div style="font-weight:700;font-size:14px;color:#f0f0f2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                        🎬 ${p.titulo}
                    </div>
                    <div style="font-size:11px;color:rgba(255,255,255,0.4);margin-top:2px">
                        ${p.tipo} · ${p.fecha}
                    </div>
                </div>
                <span style="
                    font-size:11px;font-weight:600;white-space:nowrap;
                    background:${color}22;color:${color};
                    border:1px solid ${color}44;
                    border-radius:20px;padding:3px 10px;flex-shrink:0
                ">${iconEst} ${labelEst}</span>
            </div>

            <!-- Info usuario -->
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:8px">
                <div style="width:28px;height:28px;border-radius:50%;background:rgba(232,176,75,0.2);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#e8b04b;flex-shrink:0">
                    ${(p.usuario.nombre||'?')[0].toUpperCase()}
                </div>
                <div style="flex:1;min-width:0">
                    <div style="font-size:12px;font-weight:600;color:#f0f0f2">${p.usuario.nombre || 'Usuario'}</div>
                    <div style="font-size:10px;color:rgba(255,255,255,0.35)">
                        ID ${p.usuario.telegram_id} · 💎 ${p.usuario.membresia || 'Sin plan'}
                    </div>
                </div>
            </div>

            <!-- Timeline -->
            <div style="display:flex;align-items:center;gap:0;margin-bottom:${isPend ? '12px' : '0'}">
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px">
                    <div style="width:18px;height:18px;border-radius:50%;background:#e8b04b;display:flex;align-items:center;justify-content:center">
                        <svg width="9" height="9" viewBox="0 0 24 24" fill="white"><path d="M20 6L9 17l-5-5"/><path stroke="white" stroke-width="3" stroke-linecap="round" fill="none" d="M20 6L9 17l-5-5"/></svg>
                    </div>
                    <span style="font-size:9px;color:rgba(255,255,255,0.4)">Enviado</span>
                </div>
                <div style="flex:1;height:1px;background:${isPend ? 'rgba(255,255,255,0.1)' : '#10b981'};margin:0 4px;margin-bottom:14px"></div>
                <div style="display:flex;flex-direction:column;align-items:center;gap:2px">
                    <div style="width:18px;height:18px;border-radius:50%;background:${isPend ? 'rgba(255,255,255,0.1)' : '#10b981'};display:flex;align-items:center;justify-content:center">
                        ${isPend
                            ? '<div style="width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.3)"></div>'
                            : '<svg width="9" height="9" viewBox="0 0 24 24" fill="none"><path stroke="white" stroke-width="3" stroke-linecap="round" d="M20 6L9 17l-5-5"/></svg>'
                        }
                    </div>
                    <span style="font-size:9px;color:${isPend ? 'rgba(255,255,255,0.25)' : '#10b981'}">Entregado</span>
                </div>
            </div>

            ${isPend ? `
            <button onclick="marcarEntregado(${p.id})" style="
                width:100%;padding:8px;border-radius:8px;border:none;
                background:rgba(16,185,129,0.15);color:#10b981;
                font-size:12px;font-weight:600;cursor:pointer;
                border:1px solid rgba(16,185,129,0.3);
                transition:background 0.15s;
            " onmouseover="this.style.background='rgba(16,185,129,0.25)'"
               onmouseout="this.style.background='rgba(16,185,129,0.15)'">
                ✅ Marcar como entregado
            </button>` : ''}
        </div>`;
    });
    lista.innerHTML = html;
};

window.marcarEntregado = async function(pedidoId) {
    if (!confirm("¿Marcar este pedido como entregado?")) return;
    
    const btn = event.target;
    btn.disabled = true;
    btn.innerText = "⏳";
    
    try {
        const response = await fetch(`${API_BASE_URL}/marcar_entregado`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pedido_id: pedidoId, admin_id: userId })
        });

        if (!response.ok) throw new Error("Error");
        
        alert("✅ Pedido marcado como entregado");
        // Recargar la pestaña de pedidos
        cargarPedidosAdmin(document.getElementById('admin-contenido'));
    } catch (error) {
        alert("❌ Error");
    }
};

// 3. Usuarios (opcional)
async function cargarUsuariosAdmin(contenedor) {
    contenedor.innerHTML = '<div class="text-center p-20">⏳ Cargando usuarios...</div>';
    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/usuarios`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: userId })
        });
        const usuarios = await response.json();

        let html = '<h3>👥 Usuarios Registrados</h3>';
        
        if (!usuarios || usuarios.length === 0) {
            html += '<p class="text-gris">No hay usuarios</p>';
        } else {
            html += '<div class="lista-usuarios">';
            usuarios.forEach(u => {
                const fechaRegistro = u.fecha_registro || u.created_at || u.fecha_creacion;
                const fechaStr = fechaRegistro ? new Date(fechaRegistro).toLocaleDateString() : 'Desconocida';
                
                html += `
                    <div class="perfil-item">
                        <strong>${u.nombre || 'Sin nombre'}</strong><br>
                        <small>ID: ${u.telegram_id}</small><br>
                        <small>💎 ${u.membresia_tipo || 'Sin plan'} • ${u.membresia_activa ? '✅ Activa' : '❌ Inactiva'}</small><br>
                        <small>📅 Registro: ${fechaStr}</small>
                    </div>
                `;
            });
            html += '</div>';
        }
        contenedor.innerHTML = html;
    } catch (error) {
        console.error("Error cargando usuarios:", error);
        contenedor.innerHTML = '<p class="text-gris">❌ Error cargando usuarios</p>';
    }
}

// ============ BUSCADOR — carga inicial 20 + scroll de 5 ============
let totalItemsBackend = 0;
let totalItemsFiltro  = 0;

window.buscarContenido = async function(pagina = 1) {
    paginaActual = pagina;
    busquedaActual = document.getElementById('buscarInput')?.value || '';
    const offset = (paginaActual - 1) * LIMITE;

    const response = await fetch(`${API_BASE_URL}/api/contenido`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            busqueda: busquedaActual,
            tipo:     tipoActual,
            limit:    LIMITE,
            offset,
            genero:   window.filtroGenero || '',
            anio:     window.filtroAnio   || '',
        })
    });

    const result        = await response.json();
    const data          = result.data;
    // Guardar catálogo completo para poblar el select de géneros
    if (!window._todoCatalogo) window._todoCatalogo = [];
    window._todoCatalogo = [...window._todoCatalogo, ...(data || [])];
    totalItemsBackend   = result.total || 0;
    totalPaginas        = Math.ceil(totalItemsBackend / LIMITE);

    const grid = document.getElementById('resultados');
    if (!grid) return;

    if (!data || data.length === 0) {
        grid.innerHTML = '<div class="text-center p-20 text-gris">😢 No se encontraron resultados</div>';
        return;
    }

    grid.innerHTML = data.map(item => tarjetaHTML(item)).join('');

    // No renderizar paginación numérica — usa scroll infinito en explorar
};


function ratingBadgeHTML(rating) {
    if (!rating || rating === 0) return '';
    const score = parseFloat(rating).toFixed(1);
    const color = score >= 7 ? '#2ecc71' : score >= 5 ? '#f1c40f' : '#e74c3c';
    return `<div class="rating-badge" style="--rating-color:${color}">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="${color}">
            <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>
        </svg>
        <span>${score}</span>
    </div>`;
}

function tarjetaHTML(item) {
    const isFav = esFavorito(item.id);
    const heartActive = `<svg viewBox="0 0 24 24" width="16" height="16" fill="#e8b04b"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.27 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.08C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.77-3.4 6.86-8.55 11.53L12 21.35z"/></svg>`;
    const heartInactive = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="rgba(255,255,255,0.7)" stroke-width="1.8"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.27 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.08C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.77-3.4 6.86-8.55 11.53L12 21.35z"/></svg>`;
    const ij = JSON.stringify(item).replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
    return `
        <div class="tarjeta" onclick='abrirModalContenido(${JSON.stringify(item).replace(/'/g, "\\'")})'>
            <div class="tarjeta-imagen">
                <img src="${item.imagen_url}" loading="lazy">
                ${ratingBadgeHTML(item.rating)}
                <button class="fav-btn${isFav ? ' fav-active' : ''}" onclick='event.stopPropagation();toggleFavBtn(${item.id},${JSON.stringify(item).replace(/'/g, "\\'")},this)'>${isFav ? heartActive : heartInactive}</button>
            </div>
            <div class="tarjeta-info">
                <div class="tarjeta-titulo">${item.titulo}</div>
                <div class="tarjeta-detalle">${item.tipo}${item.año ? ' • ' + item.año : ''}${item.genero ? ' • ' + item.genero : ''}</div>
            </div>
        </div>
    `;
}

window.cambiarTipo = function(tipo, e) {
    tipoActual = tipo;
    paginaActual = 1;
    totalPaginas = 1;
    totalItemsBackend = 0;
    cargando = false;
    busquedaActual = '';
    document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('activo'));
    if (e) e.target.classList.add('activo');
    const generosEl = document.getElementById('generosExplorar');
    const resultadosEl = document.getElementById('resultados');
    if (generosEl) generosEl.style.display = 'none';
    if (resultadosEl) { resultadosEl.style.display = ''; resultadosEl.innerHTML = ''; }
    buscarContenido(1);
};

window.abrirVideo = function(enlace) {

    if (!membresiaActiva) {
        document.getElementById("modal-vip-bloqueo").classList.add("active");
        return;
    }

    if (enlace) tg.openLink(enlace);
};

function cerrarModalVIP(){
    document.getElementById("modal-vip-bloqueo").classList.remove("active");
}

function irAMembresias(){
    cerrarModalVIP();
    cambiarVista('membresias');
}

// ============ PAGOS ============
let planPagoActual = null;

window.pagarPeru = function(plan, precio) {
    planPagoActual = { plan, precio };
    document.getElementById('modalPago').classList.add('active');
};

window.cerrarModalPago = function() {
    document.getElementById('modalPago').classList.remove('active');
};

window.irAlBot = function() {

    if (!planPagoActual) return;

    const { plan, precio } = planPagoActual;

    cerrarModalPago();

    // guardar URL para usar luego
    window.urlBotPago = `https://t.me/${TELEGRAM_BOT_USERNAME}?start=pago_${plan}_${precio}`;

    mostrarConfirmacionPago();
};

function mostrarConfirmacionPago() {
    const div = document.createElement("div");

    div.innerHTML = `
    <div style="
        position:fixed;
        top:0;
        left:0;
        width:100%;
        height:100%;
        background:rgba(0,0,0,0.9);
        display:flex;
        align-items:center;
        justify-content:center;
        z-index:99999;
        color:white;
        text-align:center;
    ">
        <div>
            <h2>✅ Pago enviado por confirmar</h2>
            <p>Ahora regresa al bot y envia el vucher ⬆</p>

            <button onclick="abrirBotManual()" class="btn-ir-bot">
           🤖 Ir al bot
            </button>
        </div>
    </div>
    `;

    document.body.appendChild(div);
}

function abrirBotManual() {

    if (!window.urlBotPago) return;

    const url = window.urlBotPago;

    try {
        if (window.Telegram?.WebApp) {

            Telegram.WebApp.openTelegramLink(url);

            setTimeout(() => {
                Telegram.WebApp.close();
            }, 300);

        } else {
            window.open(url, "_blank");
        }

    } catch (e) {
        window.location.href = url;
    }
}

window.copiarNumero = function(num) {
    try { navigator.clipboard.writeText(num); } catch(e) {}
    const inp = document.createElement('input');
    inp.value = num; document.body.appendChild(inp); inp.select();
    document.execCommand('copy'); document.body.removeChild(inp);
    try {
        tg.showPopup({ title: '✅ Copiado', message: `Número ${num} copiado.`, buttons: [{ type: 'ok' }] });
    } catch (e) { alert('Copiado: ' + num); }
};

window.pagarInternacional = function(plan) {
    window.planSeleccionado = plan;
    const modal = document.getElementById("modal-email");
    modal.style.display = "flex";
    const inp = document.getElementById("email-input");
    if (inp && usuarioActual?.email) inp.value = usuarioActual.email;
};

function _validarEmailModal() {
    const email = document.getElementById("email-input")?.value?.trim();
    const inp   = document.getElementById("email-input");
    if (!email || !email.includes("@")) {
        if (inp) { inp.style.borderColor = "#e74c3c"; inp.placeholder = "Ingresa un email válido"; }
        return null;
    }
    if (inp) inp.style.borderColor = "";
    return email;
}

window.confirmarPagoBMC = async function() {
    const email = _validarEmailModal();
    if (!email) return;
    const btn = document.querySelector(".bmc-btn");
    if (btn) { btn.disabled = true; btn.style.opacity = "0.6"; }
    try {
        const resp = await fetch(`${API_BASE_URL}/crear_pago_tarjeta`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ telegram_id: userId, plan: window.planSeleccionado.toLowerCase(), email })
        });
        const data = await resp.json();
        if (!resp.ok) { alert("Error: " + (data.error || "desconocido")); return; }
        cerrarModal();
        tg.openLink(data.url);
    } catch(e) { alert("Error de conexión"); }
    finally { if (btn) { btn.disabled = false; btn.style.opacity = ""; } }
};

window.confirmarPagoPayPal = async function() {
    const email = _validarEmailModal();
    if (!email) return;

    const btn = document.querySelector(".pp-btn");
    const nombreBtn = btn ? btn.querySelector(".mpb-nombre") : null;
    const descBtn   = btn ? btn.querySelector(".mpb-desc")   : null;
    if (btn) { btn.disabled = true; btn.style.opacity = "0.7"; }
    if (nombreBtn) nombreBtn.textContent = "Creando suscripción...";
    if (descBtn)   descBtn.textContent   = "Conectando con PayPal";

    try {
        const resp = await fetch(`${API_BASE_URL}/api/admin/marketing/crear_pago_paypal`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                telegram_id: userId,
                plan: window.planSeleccionado.toLowerCase(),
                email,
                modo: "suscripcion"   // ← suscripción mensual recurrente
            })
        });
        const data = await resp.json();

        // Si no hay plan_id configurado, caer a pago único
        if (!resp.ok && data.error && data.error.includes("PAYPAL_PLAN_ID")) {
            console.warn("Plan ID no configurado, usando pago único como fallback");
            const resp2 = await fetch(`${API_BASE_URL}/api/admin/marketing/crear_pago_paypal`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    telegram_id: userId,
                    plan: window.planSeleccionado.toLowerCase(),
                    email,
                    modo: "unico"
                })
            });
            const data2 = await resp2.json();
            if (!resp2.ok) { alert("Error PayPal: " + (data2.error || "desconocido")); return; }
            cerrarModal();
            _abrirPayPal(data2.url);
            return;
        }

        if (!resp.ok) {
            alert("Error PayPal: " + (data.error || "desconocido"));
            return;
        }

        cerrarModal();
        _abrirPayPal(data.url, data.tipo === "suscripcion");

    } catch(e) {
        alert("Error de conexión: " + e.message);
    } finally {
        if (btn) { btn.disabled = false; btn.style.opacity = ""; }
        if (nombreBtn) nombreBtn.textContent = "PayPal";
        if (descBtn)   descBtn.textContent   = "Suscripción mensual · Cancela cuando quieras";
    }
};

function _abrirPayPal(url, esSuscripcion = false) {
    try { tg.openLink(url); } catch(e) { window.open(url, "_blank"); }
    setTimeout(() => {
        try {
            tg.showPopup({
                title: esSuscripcion ? "Suscripción PayPal" : "PayPal abierto",
                message: esSuscripcion
                    ? "Completa la suscripción en el navegador. Se renovará automáticamente cada mes. Tu membresía se activará en segundos."
                    : "Completa el pago en el navegador. Tu membresía se activará automáticamente al finalizar.",
                buttons: [{ type: "ok" }]
            });
        } catch(e) {}
    }, 800);
}

async function confirmarPago() { await confirmarPagoBMC(); }

function cerrarModal() {
    document.getElementById("modal-email").style.display = "none";
}



// ============ PEDIDOS (usuario) ============
window.enviarPedido = async function() {
    const titulo = document.getElementById("tituloPedido")?.value;
    const tipo = document.getElementById("tipoPedido")?.value;

    if (!titulo) return alert("❌ Escribe un título");

    try {
        const response = await fetch(`${API_BASE_URL}/crear_pedido`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ telegram_id: userId, titulo, tipo })
        });

        const result = await response.json();

        if (!response.ok) {
            alert("❌ " + result.error);
            return;
        }

        alert("✅ Pedido enviado");
        document.getElementById("tituloPedido").value = "";
        cargarPedidos();

    } catch (error) {
        alert("❌ Error enviando pedido");
    }
};

async function cargarPedidos() {
    if (!userId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/mis_pedidos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ telegram_id: userId })
        });

        const result = await response.json();
        const contenedor = document.getElementById("listaPedidos");
        if (!contenedor) return;

        if (!response.ok || !result.pedidos || result.pedidos.length === 0) {
            contenedor.innerHTML = '<div class="text-center p-20 text-gris">📭 No tienes pedidos</div>';
            return;
        }

        let html = '';
        result.pedidos.forEach(p => {
            html += `
                <div class="perfil-item pedido-item">
                    <div style="display: flex; justify-content: space-between;">
                        <div><strong>${p.titulo}</strong><br><small>${p.tipo} • ${p.fecha}</small></div>
                        <div class="${p.estado === 'entregado' ? 'estado-entregado' : 'estado-pendiente'}">
                            ${p.estado === 'entregado' ? '✅' : '⏳'} ${p.estado}
                        </div>
                    </div>
                </div>
            `;
        });
        contenedor.innerHTML = html;

    } catch (error) {
        console.error("Error:", error);
    }
}

async function cargarTendencias() {
    const res = await fetch(`${API_BASE_URL}/api/tendencias`);
    const data = await res.json();

    const container = document.getElementById("tendencias");

    if (!data || data.length === 0) return;

    container.innerHTML = data.map((item, index) => `
        <div class="tendencia-item" onclick='abrirModalContenido(${JSON.stringify(item).replace(/'/g, "\\'")})'>
            <span class="numero">${index + 1}</span>
            <img src="${item.imagen_url}" alt="${item.titulo}">
        </div>
    `).join('');
}

window.aprobarPago = async function(pagoId) {
    const btn = event.target;
    btn.disabled = true;
    btn.innerText = "⏳";
    
    try {
        const response = await fetch(`${API_BASE_URL}/aprobar_pago`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pagoId })
        });

        if (!response.ok) throw new Error("Error");
        
        alert("✅ Pago aprobado");
        // Recargar la pestaña de membresías
        cambiarAdminTab('membresias');
    } catch (error) {
        alert("❌ Error");
    }
};

window.verificarCompra = function() {
    alert("Si ya pagaste, tu membresía se activará en breve.");
};

// ============ SUBIR DE PLAN ============
function subirPlan() {

    const vence = membresiaActiva?.fecha_fin
        ? new Date(membresiaActiva.fecha_fin).toLocaleDateString()
        : 'desconocida';

    mostrarModal(
        "⬆️ Subir de plan",
        `Al mejorar tu plan se mantendrán los días restantes hasta ${vence}.\n\n¿Quieres ver los planes disponibles?`,
        () => cambiarVista('membresias')
    );
}

// ============ BAJAR DE PLAN ============
function bajarPlan() {

    const vence = membresiaActiva?.fecha_fin
        ? new Date(membresiaActiva.fecha_fin).toLocaleDateString()
        : 'desconocida';

    mostrarModal(
        "⬇️ Bajar de plan",
        `Debes esperar a que termine tu plan actual (${vence}).\n\n¿Quieres ver los planes disponibles?`,
        () => cambiarVista('membresias')
    );
}

async function cargarGeneros(){
    // Ahora usa el helper compartido
    cargarGenerosEnContenedor('contenidoGeneros');
}

// ============ CARGAR GÉNEROS EN CONTENEDOR ESPECÍFICO ============
// Reutilizable tanto para inicio como para explorar/buscar
async function cargarGenerosEnContenedor(containerId) {
    try {
        // Obtener TODO el contenido
        const res = await fetch(`${API_BASE_URL}/api/contenido`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ busqueda: "", tipo: "todo", limit: 500, offset: 0 })
        });
        const result = await res.json();
        let data = result.data;
        if (!data) return;

        // Limpiar y procesar los géneros al inicio
        data = data.map(item => ({
            ...item,
            generosArray: item.genero ? item.genero.split(',').map(g => g.trim().toLowerCase()) : []
        }));

        const grupos = {
            misterioTerror: ["misterio", "terror"],
            suspense: ["suspense"],
            comedia: ["comedia"],
            romanceDrama: ["romance", "drama"],
            accionWestern: ["acción", "western"],
            animacionFamilia: ["animación", "familia"]
        };
        
        const titulos = {
            misterioTerror: "Misterio y Terror",
            suspense: "Suspense",
            comedia: "Comedia",
            romanceDrama: "Romance y Drama",
            accionWestern: "Acción y Western",
            animacionFamilia: "Animación y Familia"
        };

        const contenedor = document.getElementById(containerId);
        if (!contenedor) return;

        let html = "";
        for (const [key, generosGrupo] of Object.entries(grupos)) {
            // Filtrar por coincidencia de géneros
            const peliculas = data.filter(item =>
                item.generosArray.some(g => generosGrupo.includes(g))
            );
            
            if (peliculas.length === 0) continue;
            
            html += `
                <section class="genero-section genero-${key}">
                    <h2 class="genero-titulo">${titulos[key]}</h2>
                    <div class="genero-scroll">
                        ${peliculas.slice(0, 20).map(item => `
                            <div class="genero-card" onclick='abrirModalContenido(${JSON.stringify(item).replace(/'/g, "\\'")})'>
                                <img src="${item.imagen_url}" alt="${item.titulo}">
                            </div>
                        `).join("")}
                    </div>
                </section>
            `;
        }
        contenedor.innerHTML = html;
    } catch (e) {
        console.error("Error cargando géneros:", e);
    }
}

// ============ BUSCADOR INTELIGENTE (buscar + explorar) ============
let buscarDebounce = null;
window.onBuscarInput = function() {
    clearTimeout(buscarDebounce);
    buscarDebounce = setTimeout(() => {
        const query = document.getElementById('buscarInput')?.value?.trim() || '';
        const generosEl = document.getElementById('generosExplorar') || document.getElementById('categoriasBuscar');
        const resultadosEl = document.getElementById('resultados');

        if (!query) {
            if (generosEl) generosEl.style.display = '';
            if (resultadosEl) { resultadosEl.style.display = 'none'; resultadosEl.innerHTML = ''; }
            return;
        }
        if (generosEl) generosEl.style.display = 'none';
        if (resultadosEl) { resultadosEl.style.display = ''; resultadosEl.innerHTML = ''; }
        // Reset para nueva búsqueda
        paginaActual = 1; totalPaginas = 1; totalItemsBackend = 0; cargando = false;
        buscarContenido(1);
    }, 350);
};

// Mostrar resultados filtrados por tipo en explorar
async function mostrarResultadosExplorar() {
    const generosEl = document.getElementById('generosExplorar');
    const resultadosEl = document.getElementById('resultados');
    if (generosEl) generosEl.style.display = 'none';
    if (resultadosEl) resultadosEl.style.display = '';
    await buscarContenido(1);
}

// ============ FILTRAR POR CATEGORÍA EN BUSCAR ============
// Mapa de qué columna y qué valor usar para cada categoría para backend
const FILTROS_BUSCAR = {
    'disponible':       { param: 'descarga',  valor: true        },  // descarga != null
    'serie':            { param: 'tipo',      valor: 'serie'     },
    'anime':            { param: 'tipo',      valor: 'anime'     },
    'peliculas anime':  { param: 'tipo',      valor: 'peliculas anime' }, // nuevo tipo
    'accion':           { param: 'genero',    valor: 'acción'    },
    'ciencia ficcion':  { param: 'genero',    valor: 'ciencia'   },
    'comedia':          { param: 'genero',    valor: 'comedia'   },
    'drama':            { param: 'genero',    valor: 'drama'     },
    'terror':           { param: 'genero',    valor: 'terror'    },
    'familia':          { param: 'genero',    valor: 'familia'   },
};

// Estado del filtro rápido activo (para scroll infinito)
let filtroRapidoActivo = null;
let paginaFiltro = 1;
let totalPaginasFiltro = 1;
let cargandoFiltro = false;

// Construye el body del fetch según el filtro
function buildFiltroBody(categoria, offset = 0) {
    const cfg = FILTROS_BUSCAR[categoria];
    if (!cfg) return null;
    const body = { busqueda: '', tipo: 'todo', limit: LIMITE, offset };
    if (cfg.param === 'tipo')     body.tipo     = cfg.valor;
    if (cfg.param === 'genero')   body.genero   = cfg.valor;
    if (cfg.param === 'descarga') body.descarga = true;
    return body;
}

window.filtrarPorTipo = async function(categoria) {
    const generosEl    = document.getElementById('categoriasBuscar');
    const resultadosEl = document.getElementById('resultados');
    const loader       = document.getElementById('scroll-loader');

    if (generosEl) generosEl.style.display = 'none';
    if (resultadosEl) {
        resultadosEl.style.display = '';
        resultadosEl.innerHTML = '<div class="text-center p-20 text-gris">⏳ Cargando...</div>';
    }

    // Resetear estado de scroll
    filtroRapidoActivo  = categoria;
    paginaFiltro        = 1;
    totalPaginasFiltro  = 1;
    cargandoFiltro      = false;

    const body = buildFiltroBody(categoria, 0);
    if (!body) return;

    try {
        const res    = await fetch(`${API_BASE_URL}/api/contenido`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const result = await res.json();
        const data   = result.data || [];
        const total  = result.total || data.length;

        totalPaginasFiltro = Math.ceil(total / LIMITE);

        if (!data.length) {
            resultadosEl.innerHTML = '<div class="text-center p-20 text-gris">😢 No se encontraron resultados</div>';
            return;
        }

        resultadosEl.innerHTML = data.map(item => tarjetaHTML(item)).join('');

        // Activar scroll infinito para este filtro
        activarScrollInfinitoFiltro();

    } catch (e) {
        console.error('Error filtrarPorTipo:', e);
        if (resultadosEl) resultadosEl.innerHTML = '<div class="text-center p-20 text-gris">❌ Error cargando</div>';
    }
};

// ============ MENÚ MÁS (overlay) ============
function abrirMenuMas() {
    document.getElementById('overlayMas')?.classList.add('active');
}
window.cerrarMenuMas = function() {
    document.getElementById('overlayMas')?.classList.remove('active');
};

// Cambiar a explorar con tipo preseleccionado
window.cambiarVistaConFiltro = function(tipo) {
    tipoActual = tipo;
    cerrarMenuMas();
    cambiarVista('explorar');
};



// ============ BUSCADOR tipo actual ============
let tipoActual = 'todo';

// ============ SCROLL INFINITO UNIFICADO  (llama al backend) ============
let scrollActivo = false;

function activarScrollInfinito() {
    // Limpiar filtro rápido al entrar a explorar
    filtroRapidoActivo = null;
    _registrarScrollHandler();
}

function activarScrollInfinitoFiltro() {
    // filtroRapidoActivo ya está seteado antes de llamar esto
    _registrarScrollHandler();
}

function _registrarScrollHandler() {
    window.removeEventListener('scroll', _scrollUnificado);
    window.addEventListener('scroll', _scrollUnificado);
}

async function _scrollUnificado() {
    // Evitar disparos simultáneos con cualquier flag
    if (cargando || cargandoFiltro) return;

    const scrollBottom = window.innerHeight + window.scrollY;
    const docHeight    = document.documentElement.scrollHeight;
    if (scrollBottom < docHeight - 350) return;

    const grid = document.getElementById('resultados');
    if (!grid || grid.style.display === 'none') return;

    if (filtroRapidoActivo) {
        // ── MODO FILTRO RÁPIDO ──
        // Comparar items reales en pantalla vs total real del backend
        const yaHay = grid.querySelectorAll('.tarjeta').length;
        if (yaHay >= totalItemsFiltro) return;  // ya tenemos todo, no pedir más

        cargandoFiltro = true;
        const loader = document.getElementById('scroll-loader');
        if (loader) loader.style.display = 'flex';

        const body = buildFiltroBody(filtroRapidoActivo, yaHay); // offset = yaHay

        try {
            const res    = await fetch(`${API_BASE_URL}/api/contenido`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const result = await res.json();
            const data   = result.data || [];
            data.forEach(item => grid.insertAdjacentHTML('beforeend', tarjetaHTML(item)));
        } catch (e) { console.error('Scroll filtro:', e); }

        if (loader) loader.style.display = 'none';
        cargandoFiltro = false;

    } else {
        // ── MODO EXPLORAR ──
        // Comparar items reales en pantalla vs total real del backend
        const yaHay = grid.querySelectorAll('.tarjeta').length;
        if (yaHay >= totalItemsBackend) return;  // ya tenemos todo, no pedir más

        cargando = true;
        const loader = document.getElementById('scroll-loader');
        if (loader) loader.style.display = 'flex';

        try {
            const response = await fetch(`${API_BASE_URL}/api/contenido`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ busqueda: busquedaActual, tipo: tipoActual, limit: LIMITE_SCROLL, offset: yaHay })
            });
            const result = await response.json();
            const data   = result.data;
            if (data?.length) {
                data.forEach(item => grid.insertAdjacentHTML('beforeend', tarjetaHTML(item)));
            }
        } catch (e) { console.error('Scroll explorar:', e); }

        if (loader) loader.style.display = 'none';
        cargando = false;
    }
}

// cargarMasContenido ya no se usa directamente — el handler unificado lo reemplaza
async function cargarMasContenido() {}

// renderPaginacion no se usa (scroll infinito)
function renderPaginacion() {}

function mostrarModal(titulo, mensaje, callback) {
    const modal = document.getElementById("modal");
    const title = document.getElementById("modal-title");
    const message = document.getElementById("modal-message");
    const btnOk = document.getElementById("modal-ok");
    const btnCancel = document.getElementById("modal-cancel");

    title.innerText = titulo;
    message.innerText = mensaje;

    modal.classList.remove("hidden");

    btnOk.onclick = () => {
        modal.classList.add("hidden");
        if (callback) callback();
    };

    btnCancel.onclick = () => {
        modal.classList.add("hidden");
    };
}

// ============ MODAL DETALLE CONTENIDO — Premium ============
let contenidoSeleccionado = null;

async function abrirModalContenido(item) {
    // Si el item viene del cache (favs/historial), puede no tener todos los campos
    // (descarga, fuente, tmdb_id, protagonistas...). Fetch completo por id.
    // Si el item viene de cache viejo (antes del fix del spread),
    // 'descarga' no existirá como key → fetch completo desde la API
    if (item.id && !('descarga' in item)) {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/contenido`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ busqueda: '', tipo: item.tipo || 'todo', limit: 50, offset: 0 })
            });
            const data = await resp.json();
            const completo = (data.data || []).find(d => d.id === item.id);
            if (completo) item = { ...completo };
        } catch(e) { console.warn('No se pudo fetch item completo:', e); }
    }

    contenidoSeleccionado = item;
    // historial se registra SOLO cuando presiona reproducir

    // Fondo hero
    const bgEl = document.getElementById('detalleHeroBg');
    if (bgEl) bgEl.style.backgroundImage = `url('${item.imagen_url || ''}')`;

    // Poster
    const imgEl = document.getElementById('detalleImagen');
    if (imgEl) { imgEl.src = item.imagen_url || ''; imgEl.onerror = () => { imgEl.style.display='none'; }; }

    // Badges: año · tipo · rating
    const anioTipoEl = document.getElementById('detalleAnioTipo');
    if (anioTipoEl) {
        const ratingVal = item.rating ? parseFloat(item.rating).toFixed(1) : null;
        const rColor = ratingVal >= 7 ? '#2ecc71' : ratingVal >= 5 ? '#f1c40f' : '#e74c3c';
        let html = '';
        if (item.año) html += `<span class="d-badge">${item.año}</span>`;
        if (item.tipo) html += `<span class="d-badge">${item.tipo.charAt(0).toUpperCase()+item.tipo.slice(1)}</span>`;
        if (ratingVal) html += `<span class="d-badge d-badge-rating" style="color:${rColor};border-color:${rColor}22;background:${rColor}18">
            <svg viewBox="0 0 24 24" width="10" height="10" fill="${rColor}"><polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/></svg>
            ${ratingVal}
        </span>`;
        anioTipoEl.innerHTML = html;
    }

    // Título
    const tituloEl = document.getElementById('detalleTitulo');
    if (tituloEl) tituloEl.textContent = item.titulo || 'Sin título';

    // Duración / tagline
    const durEl = document.getElementById('detalleDuracion');
    if (durEl) {
        const parts = [];
        if (item.duracion) parts.push(item.duracion);
        if (item.genero) parts.push(item.genero.split(',')[0].trim());
        durEl.textContent = parts.join(' · ');
    }

    // Sinopsis
    const sinEl = document.getElementById('detalleSinopsis');
    if (sinEl) sinEl.textContent = item.sinopsis || 'Sin sinopsis disponible.';

    // Meta: género, protagonistas, creadores
    const metaEl = document.getElementById('detalleMeta');
    if (metaEl) {
        let metaHtml = '';
        if (item.genero) metaHtml += `<div class="d-meta-row"><span class="d-meta-label">Género</span><span class="d-meta-val">${item.genero}</span></div>`;
        if (item.protagonistas) metaHtml += `<div class="d-meta-row"><span class="d-meta-label">Reparto</span><span class="d-meta-val">${item.protagonistas}</span></div>`;
        if (item.creadores) metaHtml += `<div class="d-meta-row"><span class="d-meta-label">Creadores</span><span class="d-meta-val">${item.creadores}</span></div>`;
        metaEl.innerHTML = metaHtml;
    }

    // Botón GUARDAR (fav)
    const btnFav = document.getElementById('btnFavModal');
    if (btnFav) {
        const isFav = esFavorito(item.id);
        actualizarBtnFav(btnFav, isFav);
        btnFav.onclick = () => {
            const ahora = toggleFavorito(item);
            actualizarBtnFav(btnFav, ahora);
        };
    }

    // Botón ME GUSTA (local toggle visual)
    const btnLike = document.getElementById('btnLikeModal');
    if (btnLike) {
        const likeKey = `like_${item.id}`;
        const liked = localStorage.getItem(likeKey) === '1';
        actualizarBtnLike(btnLike, liked);
        btnLike.onclick = () => {
            const nowLiked = localStorage.getItem(likeKey) !== '1';
            localStorage.setItem(likeKey, nowLiked ? '1' : '0');
            actualizarBtnLike(btnLike, nowLiked);
        };
    }

    // Botón descargar
const btnDesc = document.getElementById('btnDescargar');

if (btnDesc) {

    const linkDescarga = item.descarga || null;

    if (linkDescarga && linkDescarga.trim() !== '') {

        btnDesc.style.display = 'flex';

        const infoDesc = document.getElementById('infoDescarga');

        if (infoDesc) {
            infoDesc.style.display = membresiaActiva ? 'block' : 'none';
        }

        btnDesc.onclick = (e) => {

            e.stopPropagation();

            // Verificar membresía
            if (!membresiaActiva) {
                document
                    .getElementById("modal-vip-bloqueo")
                    .classList.add("active");
                return;
            }

            try {

                // Links de Telegram
                if (linkDescarga.includes('t.me')) {

                    tg.openTelegramLink(linkDescarga);

                } else {

                    // Abrir navegador externo
                    window.open(linkDescarga, '_blank');

                }

            } catch (error) {

                // Fallback
                window.open(linkDescarga, '_blank');

            }

        };

    } else {

        btnDesc.style.display = 'none';

        const infoDesc = document.getElementById('infoDescarga');

        if (infoDesc) {
            infoDesc.style.display = 'none';
        }

    }

}

    // ── TRAILER YouTube ──────────────────────────────────────────────────────
    const trailerZona = document.getElementById('trailerZona');
    const btnTrailer  = document.getElementById('btnTrailer');
    if (trailerZona && btnTrailer) {
        const trailerUrl = item.trailer_url || '';
        if (trailerUrl) {
            trailerZona.style.display = 'block';
            btnTrailer.onclick = () => {
                try { tg.openLink(trailerUrl); }
                catch(e) { window.open(trailerUrl, '_blank'); }
            };
        } else {
            trailerZona.style.display = 'none';
        }
    }

    // ── PROGRESO VISTO ────────────────────────────────────────────────────────
    // Muestra badge "Visto" si ya presionó Reproducir antes (guardado en localStorage)
    const vistoKey  = `visto_${item.id}`;
    const yaVisto   = localStorage.getItem(vistoKey) === '1';
    const badgeVisto = document.getElementById('badgeVisto');
    if (badgeVisto) {
        badgeVisto.style.display = yaVisto ? 'flex' : 'none';
    }
    // El badge se activa cuando presiona Reproducir (ver handler más abajo)

    // Selector de temporadas (solo series/anime con temporadas en BD)
    await cargarTemporadas(item);

    // Cargar relacionados (mismo tipo/género)
    cargarRelacionados(item);

    // Mostrar modal
    const modal = document.getElementById('modalDetalle');
    if (modal) { modal.classList.add('active'); modal.scrollTop = 0; }
}

function actualizarBtnFav(btn, isFav) {
    btn.classList.toggle('d-accion-active', isFav);
    btn.querySelector('svg').setAttribute('fill', isFav ? '#e8b04b' : 'none');
    btn.querySelector('svg').setAttribute('stroke', isFav ? '#e8b04b' : 'currentColor');
    btn.querySelector('span').textContent = isFav ? 'Guardado' : 'Guardar';
}

function actualizarBtnLike(btn, liked) {
    btn.classList.toggle('d-accion-active', liked);
    btn.querySelector('svg').setAttribute('fill', liked ? '#5b9cf6' : 'none');
    btn.querySelector('svg').setAttribute('stroke', liked ? '#5b9cf6' : 'currentColor');
    btn.querySelector('span').textContent = liked ? 'Te gustó' : 'Me gusta';
}

function compartirContenido() {
    const item = contenidoSeleccionado;
    if (!item) return;

    // Texto completo con título, tipo, año, sinopsis corta y link al bot
    const sinCorta = item.sinopsis ? item.sinopsis.slice(0, 120) + (item.sinopsis.length > 120 ? '...' : '') : '';
    const tipoParts = [item.tipo, item.año].filter(Boolean).join(' · ');
    const texto = `🎬 *${item.titulo}*\n${tipoParts}\n\n${sinCorta}\n\n📲 Míralo en QuehayApp:\nhttps://t.me/${TELEGRAM_BOT_USERNAME}?start=miniapp`;

    const textoPlano = texto.replace(/\*/g, '');

    try {
        const isInTelegram = !!(tg?.initDataUnsafe?.user);

        if (isInTelegram) {
            // Dentro de Telegram WebApp — copiar al portapapeles y mostrar popup nativo
            const copyOk = (() => {
                try {
                    const el = document.createElement('textarea');
                    el.value = textoPlano;
                    el.style.position = 'fixed'; el.style.opacity = '0';
                    document.body.appendChild(el);
                    el.select(); el.setSelectionRange(0, 99999);
                    document.execCommand('copy');
                    document.body.removeChild(el);
                    return true;
                } catch { return false; }
            })();

            // Mostrar popup de Telegram con opción de abrir para compartir
            tg.showPopup({
                title: '¡Copiado!',
                message: copyOk
                    ? `El texto de "${item.titulo}" fue copiado. Pégalo en cualquier chat de Telegram.`
                    : `Comparte "${item.titulo}" con tus amigos en Telegram.`,
                buttons: [
                    { id: 'abrir_bot', type: 'default', text: '📲 Abrir bot para compartir' },
                    { id: 'cerrar', type: 'cancel', text: 'Cerrar' }
                ]
            }, (btnId) => {
                if (btnId === 'abrir_bot') {
                    tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/${TELEGRAM_BOT_USERNAME}%3Fstart%3Dminiapp&text=${encodeURIComponent(textoPlano)}`);
                }
            });

        } else if (navigator.share) {
            // Navegador web con soporte nativo de share sheet (incluye imagen si la tienes)
            navigator.share({
                title: item.titulo,
                text: textoPlano,
                url: `https://t.me/${TELEGRAM_BOT_USERNAME}?start=miniapp`
            });
        } else {
            // Fallback: copiar al portapapeles
            navigator.clipboard?.writeText(textoPlano).then(() => {
                alert('¡Copiado! Pega el texto donde quieras compartirlo.');
            });
        }
    } catch(e) {
        // Último recurso silencioso
        try { navigator.clipboard?.writeText(textoPlano); } catch {}
    }
}

// ============ TEMPORADAS ============
let temporadasActuales = [];  // caché de temporadas de la serie abierta
let temporadaSeleccionada = null;

async function cargarTemporadas(item) {
    const wrap = document.getElementById('detalleTemporadasWrap');
    if (!wrap) return;

    // Solo aplica a series y anime
    if (!['serie', 'anime'].includes(item.tipo)) {
        wrap.style.display = 'none';
        temporadasActuales = [];
        temporadaSeleccionada = null;
        return;
    }

    try {
        const resp = await fetch(`${API_BASE_URL}/api/temporadas/${item.id}`);
        const data = await resp.json();
        const temps = data.temporadas || [];

        if (!temps.length) {
            wrap.style.display = 'none';
            temporadasActuales = [];
            temporadaSeleccionada = null;
            return;
        }

        temporadasActuales = temps;
        // Seleccionar la primera temporada por defecto
        seleccionarTemporada(temps[0], item, false);

        // Renderizar selector
        wrap.style.display = 'block';
        const grid = document.getElementById('detalleTemporadasGrid');
        if (grid) {
            // Usar data-idx en lugar de JSON inline en onclick
            // para evitar Unexpected end of input cuando el título tiene comillas
            grid.innerHTML = temps.map((t, i) => `
                <button class="temp-btn ${i === 0 ? 'temp-btn-active' : ''}"
                    id="tempbtn_${t.id}"
                    data-idx="${i}">
                    <span class="temp-num">T${t.numero}</span>
                    <span class="temp-nombre">${t.nombre || 'Temporada ' + t.numero}</span>
                    ${t.episodios ? `<span class="temp-eps">${t.episodios} ep</span>` : ''}
                </button>`).join('');
            // Agregar listeners después de insertar el HTML (seguro con cualquier carácter)
            grid.querySelectorAll('.temp-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.idx);
                    seleccionarTemporada(temporadasActuales[idx], contenidoSeleccionado, true, this);
                });
            });
        }
    } catch(e) {
        console.warn('Error cargando temporadas:', e);
        wrap.style.display = 'none';
    }
}

function seleccionarTemporada(temporada, itemBase, actualizarPoster = true, btnEl = null) {
    temporadaSeleccionada = temporada;

    // Marcar botón activo
    document.querySelectorAll('.temp-btn').forEach(b => b.classList.remove('temp-btn-active'));
    if (btnEl) btnEl.classList.add('temp-btn-active');

    // Cambiar poster si la temporada tiene su propia portada
    if (actualizarPoster && temporada.poster_url) {
        const imgEl = document.getElementById('detalleImagen');
        const bgEl  = document.getElementById('detalleHeroBg');
        if (imgEl) imgEl.src = temporada.poster_url;
        if (bgEl)  bgEl.style.backgroundImage = `url('${temporada.poster_url}')`;
    }

    // El botón Reproducir ahora usará el enlace de la temporada
    // (btnVerAhora listener lo lee de temporadaSeleccionada en tiempo real)
    const btnVer = document.getElementById('btnVerAhora');
    if (btnVer) {
        const tieneEnlace = temporada.enlace && temporada.enlace.trim() !== '';
        btnVer.disabled = !tieneEnlace;
        btnVer.title = tieneEnlace ? '' : 'Esta temporada aún no tiene enlace de reproducción';
        btnVer.style.opacity = tieneEnlace ? '1' : '0.5';
    }
}

async function cargarRelacionados(item) {
    const wrap = document.getElementById('detalleRelacionadosWrap');
    const grid = document.getElementById('detalleRelacionados');
    if (!wrap || !grid) return;
    wrap.style.display = 'none';
    try {
        const genero = item.genero?.split(',')[0]?.trim() || '';
        const resp = await fetch(`${API_BASE_URL}/api/contenido`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tipo: item.tipo, genero, limit: 8, offset: 0 })
        });
        const data = await resp.json();
        const relacionados = (data.data || []).filter(r => r.id !== item.id).slice(0, 6);
        if (!relacionados.length) return;
        grid.innerHTML = relacionados.map(r => {
            const score = r.rating ? parseFloat(r.rating) : 0;
            const rColor = score >= 7 ? '#2ecc71' : score >= 5 ? '#f1c40f' : '#e74c3c';
            const ratingBadge = score > 0
                ? `<span class="d-rel-rating" style="color:${rColor}">★ ${score.toFixed(1)}</span>`
                : '';
            return `
            <div class="d-rel-card" onclick='abrirModalContenido(${JSON.stringify(r).replace(/'/g,"\'")})'  >
                <div class="d-rel-img" style="background-image:url('${r.imagen_url}')">
                    ${ratingBadge}
                </div>
                <div class="d-rel-titulo">${r.titulo}</div>
                <div class="d-rel-sub">${r.año || ''}</div>
            </div>`;
        }).join('');
        wrap.style.display = 'block';
    } catch(e) { console.error('relacionados:', e); }
}


window.cerrarModalDetalle = function() {
    document.getElementById('modalDetalle')?.classList.remove('active');
    contenidoSeleccionado = null;
};

// mantener compatibilidad
function cerrarModalContenido() { cerrarModalDetalle(); }

// Configurar el botón "Ver ahora" del nuevo modal
document.addEventListener('DOMContentLoaded', function() {
    const btnVer = document.getElementById('btnVerAhora');
    if (btnVer) {
        btnVer.addEventListener('click', async function() {
            let item = contenidoSeleccionado;
            if (!item) return;

            if (!membresiaActiva) {
                document.getElementById("modal-vip-bloqueo").classList.add("active");
                return;
            }

            // Si el item viene del cache (favs/historial) puede tener campos incompletos.
            // Intentamos obtener el item completo de la API usando el id.
            if (item.id && !item.fuente && !item.enlace_canal && !item.tmdb_id) {
                try {
                    const resp = await fetch(`${API_BASE_URL}/api/contenido`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ busqueda: '', tipo: 'todo', limit: 1, offset: 0, id: item.id })
                    });
                    const data = await resp.json();
                    // Buscar por id en los resultados
                    const completo = (data.data || []).find(d => d.id === item.id);
                    if (completo) item = completo;
                } catch(e) { console.warn('No se pudo obtener item completo:', e); }
            }

            // ✅ Registrar en historial SOLO cuando presiona reproducir
            agregarAlHistorial(item);
            // Marcar como visto en localStorage
            localStorage.setItem(`visto_${item.id}`, '1');

            cerrarModalDetalle();

            // Si tiene temporada seleccionada con enlace → usar ese enlace
            if (temporadaSeleccionada && temporadaSeleccionada.enlace) {
                const link = temporadaSeleccionada.enlace.trim();
                try {
                    if (link.includes('t.me')) tg.openTelegramLink(link);
                    else tg.openLink(link);
                } catch(e) { window.open(link, '_blank'); }
                return;
            }

            // Modo normal (sin temporadas)
            if ((!item.fuente || item.fuente === 'canal') && item.enlace_canal) {
                if (item.enlace_canal.includes('t.me')) tg.openTelegramLink(item.enlace_canal);
                else tg.openLink(item.enlace_canal);
                return;
            }
            if (item.fuente === 'vimeus' && item.tmdb_id) {
                abrirReproductorVimeus(item);
                return;
            }
            console.warn('Item sin fuente ni enlace:', item);
        });
    }
});

// ============ REPRODUCTOR VIMEUS COMPLETO ============

// Función principal que decide según plataforma
async function abrirReproductorVimeus(item) {
    console.log("🎬 abrirReproductorVimeus llamado con:", item);
    
    if (!item || !item.tmdb_id) {
        console.error("❌ No hay tmdb_id");
        return;
    }
    
    const tg = window.Telegram?.WebApp;
    const platform = tg?.platform || 'unknown';
    
    console.log("📱 Plataforma:", platform);
    
    // ===== SI ES MÓVIL, MOSTRAR POPUP PRIMERO =====
    if (platform === 'ios' || platform === 'android') {
        tg.showPopup({
            title: '📱 Modo móvil',
            message: '🎬 Reproductor Externo\n\n' +
                     '⚠️ Este video puede contener publicidad, nosotros no la controlamos.\n' +
                     '❌ En móvil no hay pantalla completa.\n\n' +
                     '💻 Usa Telegram web o Desktop para mejor experiencia y sin publcidad.\n\n' +
                     '¿Continuar?',
            buttons: [
                { id: 'continuar', type: 'default', text: '▶ Continuar' },
                { id: 'cancelar', type: 'destructive', text: 'Cancelar' }
            ]
        }, async function(buttonId) {
            if (buttonId === 'continuar') {
                await abrirReproductorDirecto(item);
            }
        });
        return;
    }
    
    // ===== SI ES DESKTOP, ABRIR DIRECTO =====
    console.log("💻 Modo desktop, abriendo directo");
    await abrirReproductorDirecto(item);
}

// Función que abre el reproductor (con fullscreen)
let vimeusViewKey = null;

// Función para obtener la view_key (con caché)
async function obtenerVimeusViewKey() {
    // Si ya la tenemos en caché, devolverla
    if (vimeusViewKey) return vimeusViewKey;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/config/vimeus_key`);
        const data = await response.json();
        
        if (data.view_key) {
            vimeusViewKey = data.view_key;
            return vimeusViewKey;
        } else {
            console.error("No se pudo obtener view_key");
            return null;
        }
    } catch (error) {
        console.error("Error obteniendo view_key:", error);
        return null;
    }
}

// Función modificada que ahora es async
async function abrirReproductorDirecto(item) {
    console.log("🎬 abrirReproductorDirecto:", item);
    
    // Obtener la view_key
    const viewKey = await obtenerVimeusViewKey();
    if (!viewKey) {
        alert("Error de configuración. Contacta al soporte.");
        return;
    }
    
    const tipo = item.tipo || 'pelicula';
    let embedUrl = '';
    
    if (tipo === 'pelicula') {
        embedUrl = `https://vimeus.com/e/movie?tmdb=${item.tmdb_id}&view_key=${viewKey}`;
    } else if (tipo === 'serie') {
        embedUrl = `https://vimeus.com/e/serie?tmdb=${item.tmdb_id}&view_key=${viewKey}`;
    } else {
        embedUrl = `https://vimeus.com/e/anime?tmdb=${item.tmdb_id}&view_key=${viewKey}`;
    }
    
    embedUrl += '&title=quehay&theme=blue&loader=v2&font=v3&overlay=v4&selector=v1&playUI=v3&epanel=v1&splash=v2';
    
    console.log("🔗 URL generada:", embedUrl);
    
    const iframe = document.getElementById('iframeReproductor');
    if (!iframe) {
        console.error("❌ No se encontró el iframe");
        return;
    }
    
    iframe.src = embedUrl;
    document.getElementById('modalReproductor').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    iniciarDeteccionFullscreen();
}

// ===== FUNCIONES DE FULLSCREEN PARA DESKTOP =====
function iniciarDeteccionFullscreen() {
    console.log("🖥️ Iniciando detección de fullscreen");
    
    // Escuchar cambios en el fullscreen del navegador
    document.addEventListener('fullscreenchange', manejarFullscreen);
    document.addEventListener('webkitfullscreenchange', manejarFullscreen);
    
    // Escuchar mensajes de Vimeus
    window.addEventListener('message', manejarMensajeVimeus);
}

function manejarFullscreen() {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
        console.log("🖥️ Vimeus activó fullscreen");
        activarFullscreenTelegram();
    } else {
        console.log("🖥️ Vimeus salió de fullscreen");
        desactivarFullscreenTelegram();
    }
}

function manejarMensajeVimeus(e) {
    if (!e.data) return;
    
    const data = typeof e.data === 'string' ? e.data : JSON.stringify(e.data);
    
    if (data.includes('fullscreen') || data.includes('expand')) {
        console.log("📨 Vimeus envió señal de fullscreen");
        activarFullscreenTelegram();
    }
}

function activarFullscreenTelegram() {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;
    
    console.log("📱 Activando fullscreen en Telegram");
    
    if (typeof tg.requestFullscreen === 'function') {
        tg.requestFullscreen();
    }
    
    if (screen.orientation && typeof screen.orientation.lock === 'function') {
        screen.orientation.lock('landscape').catch(() => {});
    }
}

function desactivarFullscreenTelegram() {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;
    
    console.log("📱 Desactivando fullscreen en Telegram");
    
    if (typeof tg.exitFullscreen === 'function') {
        tg.exitFullscreen();
    }
    
    if (screen.orientation && typeof screen.orientation.unlock === 'function') {
        screen.orientation.unlock();
    }
}

// ===== FUNCIÓN PARA CERRAR EL REPRODUCTOR =====
function cerrarReproductor() {
    console.log("🔚 Cerrando reproductor");
    
    const iframe = document.getElementById('iframeReproductor');
    
    if (document.fullscreenElement) {
        document.exitFullscreen();
    }
    
    desactivarFullscreenTelegram();
    
    // Limpiar listeners
    document.removeEventListener('fullscreenchange', manejarFullscreen);
    document.removeEventListener('webkitfullscreenchange', manejarFullscreen);
    window.removeEventListener('message', manejarMensajeVimeus);
    
    if (iframe) iframe.src = '';
    document.getElementById('modalReproductor').style.display = 'none';
    document.body.style.overflow = '';
}

// Cerrar con Escape
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('modalReproductor');
        if (modal && modal.style.display === 'flex') {
            cerrarReproductor();
        }
    }
});

// ============ FUNCIONES PARA EL CONTADOR DE OFERTA ============
function iniciarContadorOferta() {
    const ahora = new Date();
    const finOferta = new Date(ahora);
    finOferta.setHours(23, 59, 59, 0);
 
    // Función para actualizar el contador
    function actualizarContador() {
        const ahoraActual = new Date();
        const diferencia = finOferta - ahoraActual;
        
        const contenedorHoras = document.getElementById('horas');
        const contenedorMinutos = document.getElementById('minutos');
        const contenedorSegundos = document.getElementById('segundos');
        
        // Si los elementos del contador no existen (ej. no estamos en vista membresías), no hacer nada
        if (!contenedorHoras || !contenedorMinutos || !contenedorSegundos) return;
        
        if (diferencia <= 0) {
            // La oferta terminó
            contenedorHoras.innerText = '00';
            contenedorMinutos.innerText = '00';
            contenedorSegundos.innerText = '00';

            return;
        }
        
        // Calcular horas, minutos y segundos
        const horas = Math.floor(diferencia / (1000 * 60 * 60));
        const minutos = Math.floor((diferencia % (1000 * 60 * 60)) / (1000 * 60));
        const segundos = Math.floor((diferencia % (1000 * 60)) / 1000);
        
        // Actualizar el HTML (con dos dígitos siempre)
        contenedorHoras.innerText = horas.toString().padStart(2, '0');
        contenedorMinutos.innerText = minutos.toString().padStart(2, '0');
        contenedorSegundos.innerText = segundos.toString().padStart(2, '0');
    }
    
    // Ejecutar inmediatamente y luego cada segundo
    actualizarContador();
    setInterval(actualizarContador, 1000);
}

// ============ COPIAR CÓDIGO DE DESCUENTO ============
function copiarCodigo(codigo) {
    // Crear un elemento temporal
    const input = document.createElement('input');
    input.value = codigo;
    document.body.appendChild(input);
    
    // Seleccionar y copiar
    input.select();
    document.execCommand('copy');
    
    // Eliminar el elemento temporal
    document.body.removeChild(input);
    
    // Mostrar notificación (puedes usar el popup de Telegram)
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.showPopup({
            title: '✅ Código copiado',
            message: 'El código QH50OFF ha sido copiado. Úsalo al pagar con tarjeta.',
            buttons: [{ type: 'ok' }]
        });
    } else {
        alert('Código copiado: QH50OFF');
    }
}

function verTutorialYape() {
    abrirVideoTutorial("https://player.vimeo.com/video/1180635702?badge=0&amp;autopause=0&amp;player_id=0&amp;app_id=58479");
}

function verTutorialTarjeta() {
    abrirVideoTutorial("https://player.vimeo.com/video/1180635496?badge=0&amp;autopause=0&amp;player_id=0&amp;app_id=58479");
}

function abrirVideoTutorial(url) {
    document.getElementById("modal-video").style.display = "flex";
    document.getElementById("video-frame").src = url + "?autoplay=1";
}

function cerrarVideo() {
    document.getElementById("modal-video").style.display = "none";
    document.getElementById("video-frame").src = "";
}
// iniciarContadorOferta();
// ============ FILTROS COMBINADOS ============

function _poblarSelectGeneros() {
    const sel = document.getElementById('filtroGeneroSel');
    if (!sel) return;
    // Recopilar géneros únicos del contenido cargado
    const generosSet = new Set();
    (window._todoCatalogo || []).forEach(item => {
        if (item.genero) item.genero.split(',').forEach(g => {
            const gtr = g.trim();
            if (gtr) generosSet.add(gtr);
        });
    });
    const sorted = [...generosSet].sort();
    sorted.forEach(g => {
        const opt = document.createElement('option');
        opt.value = g;
        opt.textContent = g;
        if (window.filtroGenero === g) opt.selected = true;
        sel.appendChild(opt);
    });
}

window.aplicarFiltrosExtra = function() {
    const genSel  = document.getElementById('filtroGeneroSel');
    const anioSel = document.getElementById('filtroAnioSel');
    window.filtroGenero = genSel  ? genSel.value  : '';
    window.filtroAnio   = anioSel ? anioSel.value : '';
    const btnLimpiar = document.getElementById('btnLimpiarFiltros');
    if (btnLimpiar) btnLimpiar.style.display = (window.filtroGenero || window.filtroAnio) ? 'block' : 'none';
    paginaActual = 1;
    totalPaginas = 1;
    const resultados = document.getElementById('resultados');
    if (resultados) { resultados.innerHTML = ''; resultados.style.display = 'none'; }
    mostrarResultadosExplorar();
};

window.limpiarFiltrosExtra = function() {
    window.filtroGenero = '';
    window.filtroAnio   = '';
    const genSel  = document.getElementById('filtroGeneroSel');
    const anioSel = document.getElementById('filtroAnioSel');
    if (genSel)  genSel.value  = '';
    if (anioSel) anioSel.value = '';
    const btnLimpiar = document.getElementById('btnLimpiarFiltros');
    if (btnLimpiar) btnLimpiar.style.display = 'none';
    paginaActual = 1;
    const resultados = document.getElementById('resultados');
    if (resultados) { resultados.innerHTML = ''; resultados.style.display = 'none'; }
    // Volver a mostrar géneros
    const generosExplorar = document.getElementById('generosExplorar');
    if (generosExplorar) cargarGenerosEnContenedor('generosExplorar');
};

// ============ INICIAR ============
iniciar();