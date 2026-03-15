// ============ CONFIGURACION ============
const API_BASE_URL = "https://cineapp-bot.onrender.com";
const TELEGRAM_BOT_USERNAME = "Popcornqh_admin_bot";    
const ADMIN_ID = 5824989040;

const tg = window.Telegram.WebApp;
tg.expand();

const userId = tg.initDataUnsafe?.user?.id;
const userLang = tg.initDataUnsafe?.user?.language_code || 'es';

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

const avatar = document.getElementById("avatarUsuario");
const nombre = document.getElementById("nombreUsuario");

if(tg.initDataUnsafe?.user){

const user = tg.initDataUnsafe.user;

nombre.innerText = user.first_name || "Usuario";

if(user.photo_url){
avatar.src = user.photo_url;
}else{
avatar.src = "https://i.pravatar.cc/100";
}

}

} catch (error) {

console.error("Error cargando datos:", error);

}

actualizarBadge();

configurarFooter();

configurarEventosFooter();

cambiarVista('inicio');

}

function actualizarBadge(){

const badge = document.getElementById('badge');

if(!badge) return;

badge.innerText = membresiaActiva
? ` ${membresiaActiva.membresias_planes?.nombre || 'Activa'}`
: ' Sin membresía';

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
        // reset scroll state
        tipoActual = tipoActual || 'todo';
        const tipoInicial = tipoActual;
        paginaActual = 1;
        totalPaginas = 1;
        cargando = false;

        contenedor.innerHTML = `
            <div class="buscador">
                <input type="text" id="buscarInput" placeholder="Buscar película o serie..." oninput="onBuscarInput()">
                <span>🔍</span>
            </div>

            <div class="tabs">
                <div class="tab ${tipoInicial==='todo'?'activo':''}"     onclick="cambiarTipo('todo', event)">Todo</div>
                <div class="tab ${tipoInicial==='pelicula'?'activo':''}" onclick="cambiarTipo('pelicula', event)">Películas</div>
                <div class="tab ${tipoInicial==='serie'?'activo':''}"    onclick="cambiarTipo('serie', event)">Series</div>
                <div class="tab ${tipoInicial==='biblico'?'activo':''}"  onclick="cambiarTipo('biblico', event)">Bíblico</div>
                <div class="tab ${tipoInicial==='anime'?'activo':''}"    onclick="cambiarTipo('anime', event)">Anime</div>
                <div class="tab ${tipoInicial==='Peliculas anime'?'activo':''}"    onclick="cambiarTipo('Peliculas anime', event)">Peliculas anime</div>
            </div>

            <div id="generosExplorar"></div>
            <div id="resultados" class="grid" style="display:none;"></div>
            <div id="scroll-loader" class="scroll-loader" style="display:none;">
                <div class="spinner"></div>
            </div>
        `;

        cargarGenerosEnContenedor('generosExplorar');

        if (tipoInicial !== 'todo') {
            mostrarResultadosExplorar();
        }

        // Activar scroll infinito
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
    const membresiaNombre = membresiaActiva?.membresias_planes?.nombre?.toUpperCase() || 'Sin membresía';
    const estado = membresiaActiva ? '✅ Activa' : '❌ Inactiva';
    const vence = membresiaActiva?.fecha_fin
        ? new Date(membresiaActiva.fecha_fin).toLocaleDateString('es-PE')
        : '-';

    const user = tg.initDataUnsafe?.user;
    const nombre = user?.first_name || usuarioActual?.nombre || 'Usuario';
    const avatarSrc = user?.photo_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(nombre)}&background=1565C0&color=fff&size=128`;

    let botones = '';
    if (membresiaActiva) {
        botones = `
        <div class="perfil-btns">
            <button class="btn-perfil-accion" onclick="subirPlan()">Subir Plan</button>
            <button class="btn-perfil-accion" onclick="bajarPlan()">Bajar Plan</button>
        </div>`;
    } else {
        botones = `<button class="btn-perfil-comprar" onclick="cambiarVista('membresias')">Comprar Membresía</button>`;
    }

    contenedor.innerHTML = `
    <div class="perfil-wrap">
        <div class="perfil-nueva-card">
            <img class="perfil-nueva-avatar" src="${avatarSrc}" alt="${nombre}"
                onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(nombre)}&background=1565C0&color=fff&size=128'">
            <div class="perfil-nueva-nombre">${nombre}</div>
            <div class="perfil-nueva-badge">${membresiaNombre}</div>

            <div class="perfil-datos">
                <div class="perfil-dato-row"><strong>ID:</strong> <span>${userId || '—'}</span></div>
                <div class="perfil-dato-row"><strong>Membresía:</strong> <span>${membresiaNombre}</span></div>
                <div class="perfil-dato-row"><strong>Estado:</strong> <span>${estado}</span></div>
                <div class="perfil-dato-row"><strong>Vence:</strong> <span>${vence}</span></div>
            </div>

            ${botones}
        </div>
    </div>`;
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
        html += `
            <div class="perfil-item" style="margin-bottom: 10px; border-left: 4px solid ${p.estado === 'pendiente' ? '#f59e0b' : '#10b981'};">
                <div style="display: flex; justify-content: space-between;">
                    <div style="flex: 1;">
                        <strong>🎬 ${p.titulo}</strong><br>
                        <small>${p.tipo} • ${p.fecha}</small><br>
                        <small>👤 ${p.usuario.nombre} (${p.usuario.telegram_id})</small><br>
                        <small>💎 ${p.usuario.membresia}</small><br>
                        <span class="${p.estado === 'pendiente' ? 'estado-pendiente' : 'estado-entregado'}">
                            ${p.estado === 'pendiente' ? '⏳ Pendiente' : '✅ Entregado'}
                        </span>
                    </div>
                    ${p.estado === 'pendiente' ? 
                        `<button class="btn-comprar" onclick="marcarEntregado(${p.id})" style="width: auto; padding: 5px 10px; font-size: 12px; align-self: center;">Marcar entregado</button>` : ''}
                </div>
            </div>
        `;
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
        body: JSON.stringify({ busqueda: busquedaActual, tipo: tipoActual, limit: LIMITE, offset })
    });

    const result        = await response.json();
    const data          = result.data;
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

function tarjetaHTML(item) {
    return `
        <div class="tarjeta" onclick='abrirModalContenido(${JSON.stringify(item).replace(/'/g, "\\'")})'>
            <div class="tarjeta-imagen">
                <img src="${item.imagen_url}" loading="lazy">
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

    const url = `https://t.me/${TELEGRAM_BOT_USERNAME}?start=pago_${plan}_${precio}`;

    try {
        tg.openTelegramLink(url);
    } catch (e) {
        tg.openLink(url);
    }
};

window.copiarNumero = function(num) {
    try { navigator.clipboard.writeText(num); } catch(e) {}
    const inp = document.createElement('input');
    inp.value = num; document.body.appendChild(inp); inp.select();
    document.execCommand('copy'); document.body.removeChild(inp);
    try {
        tg.showPopup({ title: '✅ Copiado', message: `Número ${num} copiado.`, buttons: [{ type: 'ok' }] });
    } catch (e) { alert('Copiado: ' + num); }
};

window.pagarInternacional = async function(plan) {

    const email = prompt("Escribe el correo que usarás en BuyMeACoffee.\nEs obligatorio para activar tu membresía automáticamente.");

    if (!email) {
        alert("Debes ingresar un correo válido.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/crear_pago_tarjeta`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                telegram_id: userId,
                plan: plan.toLowerCase(),
                email: email
            })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Error creando el pago.");
            return;
        }

        tg.openLink(data.url);

    } catch (error) {
        console.error(error);
        alert("Error de conexión.");
    }
};


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
        const res = await fetch(`${API_BASE_URL}/api/contenido`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ busqueda: "", tipo: "todo", limit: 300, offset: 0 })
        });
        const result = await res.json();
        const data = result.data;
        if (!data) return;

        const grupos = {
            misterioTerror: ["misterio", "terror"],
            comedia: ["comedia"],
            romanceDrama: ["romance", "drama"],
            accionWestern: ["acción", "western"],
            animacionFamilia: ["animación", "familia"]
        };
        const titulos = {
            misterioTerror: "Misterio y Terror",
            comedia: "Comedia",
            romanceDrama: "Romance y Drama",
            accionWestern: "Acción y Western",
            animacionFamilia: "Animación y Familia"
        };

        const contenedor = document.getElementById(containerId);
        if (!contenedor) return;

        let html = "";
        Object.keys(grupos).forEach(key => {
            const peliculas = data.filter(item =>
                grupos[key].includes((item.genero || "").toLowerCase())
            );
            if (peliculas.length === 0) return;
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
        });
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

// ============ MODAL DETALLE CONTENIDO (nuevo diseño) ============
let contenidoSeleccionado = null;

function abrirModalContenido(item) {
    contenidoSeleccionado = item;

    // Fondo blureado
    const bgEl = document.getElementById('detalleHeroBg');
    if (bgEl) bgEl.style.backgroundImage = `url('${item.imagen_url || ''}')`;

    // Poster
    const imgEl = document.getElementById('detalleImagen');
    if (imgEl) { imgEl.src = item.imagen_url || ''; imgEl.onerror = () => { imgEl.style.display='none'; }; }

    // Año y tipo
    const anioTipoEl = document.getElementById('detalleAnioTipo');
    if (anioTipoEl) {
        const partes = [item.año, item.tipo].filter(Boolean);
        anioTipoEl.textContent = partes.join(' | ');
    }

    // Título
    const tituloEl = document.getElementById('detalleTitulo');
    if (tituloEl) tituloEl.textContent = item.titulo || 'Sin título';

    // Sinopsis
    const sinEl = document.getElementById('detalleSinopsis');
    if (sinEl) sinEl.textContent = item.sinopsis || 'Sin sinopsis disponible.';

    // Meta
    const metaEl = document.getElementById('detalleMeta');
    if (metaEl) {
        let metaHtml = '';
        if (item.protagonistas) metaHtml += `<div><strong>Protagonizada por:</strong> ${item.protagonistas}</div>`;
        if (item.creadores)     metaHtml += `<div><strong>Creada por:</strong> ${item.creadores}</div>`;
        if (item.genero)        metaHtml += `<div><strong>Género:</strong> ${item.genero}</div>`;
        metaEl.innerHTML = metaHtml;
    }

    // Botón descargar
    const btnDesc = document.getElementById('btnDescargar');

if (btnDesc) {

    const linkDescarga = item.descarga || null;

    if (linkDescarga && linkDescarga.trim() !== '') {

        btnDesc.style.display = 'flex';

        btnDesc.onclick = (e) => {

            e.stopPropagation();

            // misma validación que usar "Ver ahora"
            if (!membresiaActiva) {
                document.getElementById("modal-vip-bloqueo").classList.add("active");
                return;
            }

             // usuario con membresía → aviso TG
            if (typeof tg !== "undefined") {
                tg.showAlert("🗃 Para descomprimir los archivos ZIP usa la clave:\n\nquehay.live");
            }

            try {
                if (linkDescarga.includes('t.me')) {
                    tg.openTelegramLink(linkDescarga);
                } else {
                    tg.openLink(linkDescarga);
                }
            } catch (e) {
                window.open(linkDescarga, '_blank');
            }

        };

    } else {
        btnDesc.style.display = 'none';
    }

}

    // Mostrar modal
    const modal = document.getElementById('modalDetalle');
    if (modal) { modal.classList.add('active'); modal.scrollTop = 0; }
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
        btnVer.addEventListener('click', function() {
            const item = contenidoSeleccionado;
            if (!item) return;
            cerrarModalDetalle();

            if (!membresiaActiva) {
                document.getElementById("modal-vip-bloqueo").classList.add("active");
                return;
            }
            if ((!item.fuente || item.fuente === 'canal') && item.enlace_canal) {
                if (item.enlace_canal.includes('t.me')) tg.openTelegramLink(item.enlace_canal);
                else tg.openLink(item.enlace_canal);
                return;
            }
            if (item.fuente === 'vimeus' && item.tmdb_id) {
                abrirReproductorVimeus(item);
            }
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
    
    embedUrl += '&title=quehay&theme=blue&loader=v2&font=v3&overlay=v4&selector=v2&playUI=v3&epanel=v1&splash=v2';
    
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
// iniciarContadorOferta();
// ============ INICIAR ============
iniciar();