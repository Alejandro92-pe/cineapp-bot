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
let planesMembresias = [];

// ============ INICIALIZACIÓN ============
async function iniciar() {
    console.log("🎬 Iniciando app...");

    // Cargar planes desde el backend
    const planesRes = await fetch(`${API_BASE_URL}/api/planes`);
    planesMembresias = await planesRes.json();

    // Cargar usuario y membresía
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

    // Actualizar badge
    const badge = document.getElementById('badge');
    if (badge) {
        badge.innerText = membresiaActiva
            ? `⭐ ${membresiaActiva.membresias_planes?.nombre || 'Activa'}`
            : '👤 Sin membresía';
    }

    configurarFooter();
    cambiarVista('inicio');
}

// ============ CONFIGURAR FOOTER ============
function configurarFooter() {
    const footer = document.querySelector('.footer');
    if (!footer) return;

    const items = footer.querySelectorAll('.footer-item');
    
    if (userId == ADMIN_ID) {
        // Admin: reemplazar "Pedidos" por "ADMIN"
        if (items.length >= 4) {
            items[2].innerHTML = '👑 ADMIN';
            items[2].setAttribute('onclick', "cambiarVista('admin')");
        }
    } else {
        // Usuario normal: aseguramos que "Pedidos" esté correcto
        if (items.length >= 4) {
            items[2].innerHTML = '📦 Pedidos';
            items[2].setAttribute('onclick', "cambiarVista('pedidos')");
        }
    }
}

// ============ CAMBIAR VISTA ============
window.cambiarVista = async function(vista) {
    console.log("📱 Vista:", vista);
    
    // Actualizar clase activa en footer
    document.querySelectorAll('.footer-item').forEach(el => {
        el.classList.remove('activo');
        let texto = el.innerText.trim();
        if ((vista === 'inicio' && texto.includes('Inicio')) ||
            (vista === 'membresias' && texto.includes('Membresías')) ||
            (vista === 'pedidos' && texto.includes('Pedidos')) ||
            (vista === 'admin' && texto.includes('ADMIN')) ||
            (vista === 'perfil' && texto.includes('Perfil'))) {
            el.classList.add('activo');
        }
    });
    
    const contenedor = document.getElementById('contenido');
    
    if (vista === 'inicio') {
        contenedor.innerHTML = `
            <div class="buscador">
                <input type="text" id="buscarInput" placeholder="Buscar película o serie..." onkeyup="buscarContenido()">
                <span>🔍</span>
            </div>
            <div class="tabs">
                <div class="tab activo" onclick="cambiarTipo('todo', event)">Todo</div>
                <div class="tab" onclick="cambiarTipo('pelicula', event)">Películas</div>
                <div class="tab" onclick="cambiarTipo('serie', event)">Series</div>
            </div>
            <div id="resultados" class="grid"></div>
        `;
        buscarContenido();
    }
    
    else if (vista === 'membresias') {
        let html = '<div class="planes">';
        planesMembresias.forEach(p => {
            html += `
                <div class="plan">
                    <div class="plan-info">
                        <div class="plan-nombre">${p.nombre.toUpperCase()}</div>
                        <div class="plan-duracion">${p.duracion_dias} días • ${p.pedidos_por_mes} pedidos</div>
                        <div class="plan-precio">
                            $${p.precio_dolares}
                            <span class="precio-pen">S/${p.precio_soles}</span>
                        </div>
                    </div>
                    <div class="botones-plan">
                        <button class="btn-comprar" onclick="pagarPeru('${p.nombre}', ${p.precio_soles})">
                            🇵🇪 Yape / Plin
                        </button>
                        <button class="btn-comprar tarjeta" onclick="pagarInternacional('${p.nombre}')">
                            💳 Tarjeta Gpay ApplePay y mas
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div><button class="btn-verificar" onclick="verificarCompra()">🔎 Verificar compra</button>';
        contenedor.innerHTML = html;
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

        const usados = pedidosPeriodo.length;
        const restantes = limiteTotal - usados;

        // Si ya no quedan pedidos
        if (restantes <= 0) {
            contenedor.innerHTML = `
                <div class="perfil-card">
                    <p>📊 Usados: ${usados}/${limiteTotal}</p>
                    <p class="text-gris">⚠️ Alcanzaste el límite de tu plan</p>
                </div>
            `;
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
    const membresiaNombre = membresiaActiva?.membresias_planes?.nombre?.toUpperCase() || 'Ninguna';
    const estado = membresiaActiva ? '✅ Activa' : '❌ Inactiva';
    const vence = membresiaActiva?.fecha_fin 
        ? new Date(membresiaActiva.fecha_fin).toLocaleDateString() 
        : '-';

    let botones = '';
    if (membresiaActiva) {
        // Tiene membresía activa, mostrar botones de subir/bajar
        botones = `
            <div style="display: flex; gap: 10px; margin-top: 20px;">
                <button class="btn-comprar" onclick="subirPlan()" style="flex:1;">⬆️ Subir de plan</button>
                <button class="btn-comprar" onclick="bajarPlan()" style="flex:1;">⬇️ Bajar de plan</button>
            </div>
        `;
    } else {
        // No tiene membresía, mostrar botón para comprar
        botones = `
            <button class="btn-comprar" onclick="cambiarVista('membresias')" style="margin-top:20px;">💎 Comprar membresía</button>
        `;
    }

    contenedor.innerHTML = `
        <div class="perfil-card">
            <h3>👤 Mi Perfil</h3>
            <div class="perfil-item"><strong>ID:</strong> ${userId || 'No disponible'}</div>
            <div class="perfil-item"><strong>Nombre:</strong> ${usuarioActual?.nombre || 'No disponible'}</div>
            <div class="perfil-item"><strong>Membresía:</strong> ${membresiaNombre}</div>
            <div class="perfil-item"><strong>Estado:</strong> ${estado}</div>
            <div class="perfil-item"><strong>Vence:</strong> ${vence}</div>
            ${botones}
        </div>
    `;
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

// ============ BUSCADOR ============
let tipoActual = 'todo';

window.buscarContenido = async function() {
    const busqueda = document.getElementById('buscarInput')?.value || '';
    
    const response = await fetch(`${API_BASE_URL}/api/contenido`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ busqueda, tipo: tipoActual })
    });
    const data = await response.json();
    
    const grid = document.getElementById('resultados');
    if (!data || data.length === 0) {
        grid.innerHTML = '<div class="text-center p-20 text-gris">😢 No se encontraron resultados</div>';
        return;
    }
    
    grid.innerHTML = data.map(item => `
        <div class="tarjeta" onclick="abrirVideo('${item.enlace_canal}')">
            <div class="tarjeta-imagen">
                <img src="${item.imagen_url}" alt="${item.titulo}" />
            </div>
            <div class="tarjeta-info">
                <div class="tarjeta-titulo">${item.titulo}</div>
                <div class="tarjeta-detalle">${item.tipo} • ${item.año || ''}</div>
            </div>
        </div>
    `).join('');
};

window.cambiarTipo = function(tipo, e) {
    tipoActual = tipo;
    document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('activo'));
    if (e) e.target.classList.add('activo');
    buscarContenido();
};

window.abrirVideo = function(enlace) {
    if (enlace) tg.openLink(enlace);
};

// ============ PAGOS ============
window.pagarPeru = function(plan, precio) {
    tg.openTelegramLink(`https://t.me/${TELEGRAM_BOT_USERNAME}?start=pago_${plan}_${precio}`);
    tg.showPopup({
        title: '🟣 Pago por Yape/Plin',
        message: 'Serás redirigido al bot.\n\nSigue las instrucciones.',
        buttons: [{type: 'ok'}]
    });
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
    const vence = membresiaActiva?.fecha_fin ? new Date(membresiaActiva.fecha_fin).toLocaleDateString() : 'desconocida';
    tg.showPopup({
        title: '⬆️ Subir de plan',
        message: `Al mejorar a un plan superior, se te sumarán los días restantes de tu membresía actual (hasta el ${vence}) y los pedidos no usados a tu nuevo plan.\n\n¿Quieres continuar?`,
        buttons: [
            { id: 'ok', type: 'default', text: 'Ver planes' },
            { id: 'cancel', type: 'destructive', text: 'Cancelar' }
        ]
    }, (buttonId) => {
        if (buttonId === 'ok') {
            cambiarVista('membresias');
        }
    });
}

// ============ BAJAR DE PLAN ============
function bajarPlan() {
    const vence = membresiaActiva?.fecha_fin ? new Date(membresiaActiva.fecha_fin).toLocaleDateString() : 'desconocida';
    tg.showPopup({
        title: '⬇️ Bajar de plan',
        message: `Para cambiar a un plan inferior, espera a que tu membresía actual termine (${vence}). Serás expulsado de los canales y luego podrás contratar el nuevo plan desde la sección de membresías.\n\n¿Quieres ver los planes disponibles?`,
        buttons: [
            { id: 'ok', type: 'default', text: 'Ver planes' },
            { id: 'cancel', type: 'destructive', text: 'Cancelar' }
        ]
    }, (buttonId) => {
        if (buttonId === 'ok') {
            cambiarVista('membresias');
        }
    });
}

// ============ INICIAR ============
iniciar();