// Trading App - Frontend JavaScript
// Conecta con FastAPI backend integrado (RL + DB + API)

const API_BASE_URL = 'http://localhost:8000';

// Estado global
const state = {
    authenticated: false,
    accountId: null,
    contracts: [],
    currentContract: null,
    positions: [],
    trades: [],
    stats: {},
    wsConnection: null,
    botActive: false
};

// ============================================================================
// AUTENTICACIÓN
// ============================================================================

async function login() {
    const apiKey = document.getElementById('api-key').value.trim();
    const username = document.getElementById('username').value.trim();
    const messageEl = document.getElementById('auth-message');

    if (!apiKey || !username) {
        showMessage(messageEl, '❌ Por favor complete todos los campos', 'error');
        return;
    }

    showMessage(messageEl, '🔄 Conectando...', 'info');

    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({api_key: apiKey, username: username})
        });

        const data = await response.json();

        if (data.success) {
            state.authenticated = true;
            state.accountId = data.account_id;

            showMessage(messageEl, '✅ Conectado exitosamente', 'success');

            setTimeout(() => {
                document.getElementById('auth-modal').classList.add('hidden');
                document.getElementById('main-app').classList.remove('hidden');
                document.getElementById('account-id').textContent = state.accountId;

                initWebSocket();
                loadInitialData();
            }, 1000);
        } else {
            showMessage(messageEl, `❌ ${data.message}`, 'error');
        }

    } catch (error) {
        console.error('Error en login:', error);
        showMessage(messageEl, '❌ Error de conexión', 'error');
    }
}

function showMessage(element, message, type) {
    element.textContent = message;
    element.className = `text-sm text-center ${
        type === 'error' ? 'text-red-500' :
        type === 'success' ? 'text-green-500' :
        'text-yellow-500'
    }`;
    element.classList.remove('hidden');
}

// ============================================================================
// NAVEGACIÓN DE MÓDULOS
// ============================================================================

function showModule(moduleName) {
    // Ocultar todos los módulos
    document.querySelectorAll('[id^="module-"]').forEach(el => {
        el.classList.remove('module-visible');
        el.classList.add('module-hidden');
    });

    // Mostrar módulo seleccionado
    const moduleEl = document.getElementById(`module-${moduleName}`);
    if (moduleEl) {
        moduleEl.classList.remove('module-hidden');
        moduleEl.classList.add('module-visible');
    }

    // Actualizar navegación
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('nav-active', 'bg-accent-cyan', 'text-white');
        tab.classList.add('text-gray-400');
    });

    const activeTab = document.querySelector(`.nav-tab[data-module="${moduleName}"]`);
    if (activeTab) {
        activeTab.classList.remove('text-gray-400');
        activeTab.classList.add('nav-active');
    }
}

// ============================================================================
// WEBSOCKET
// ============================================================================

function initWebSocket() {
    if (state.wsConnection) {
        state.wsConnection.close();
    }

    state.wsConnection = new WebSocket('ws://localhost:8000/ws');

    state.wsConnection.onopen = () => {
        console.log('✅ WebSocket conectado');
    };

    state.wsConnection.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'signal') {
            console.log('📡 Nueva señal recibida:', data.data);
        } else if (data.type === 'bot_status') {
            console.log('🤖 Estado del bot:', data.data);
        }
    };

    state.wsConnection.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
    };

    state.wsConnection.onclose = () => {
        console.log('⚠️ WebSocket cerrado, reconectando...');

        setTimeout(() => {
            if (state.authenticated) {
                initWebSocket();
            }
        }, 5000);
    };
}

// ============================================================================
// CARGA INICIAL DE DATOS
// ============================================================================

async function loadInitialData() {
    try {
        // Cargar configuración del bot
        const configResponse = await fetch(`${API_BASE_URL}/api/bot/config`);
        const config = await configResponse.json();

        // Cargar estadísticas
        await updateStats();

        // Cargar trades
        await loadTradesHistory();

        // Cargar posiciones
        await loadPositions();

        console.log('✅ Datos iniciales cargados');

    } catch (error) {
        console.error('Error cargando datos iniciales:', error);
    }
}

// ============================================================================
// ESTADÍSTICAS Y DASHBOARD
// ============================================================================

async function updateStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats/daily`);
        state.stats = await response.json();

        updateDashboardStats();

    } catch (error) {
        console.error('Error actualizando estadísticas:', error);
    }
}

async function updateDashboardStats() {
    const stats = state.stats;

    // Balance - obtener de TopstepX API
    try {
        const balanceResponse = await fetch(`${API_BASE_URL}/api/account/balance`);
        if (balanceResponse.ok) {
            const balanceData = await balanceResponse.json();
            const balanceEl = document.getElementById('balance');
            if (balanceEl && balanceData.balance !== undefined) {
                balanceEl.textContent = `$${balanceData.balance.toFixed(2)}`;
            }
        }
    } catch (error) {
        console.error('Error obteniendo balance:', error);
        const balanceEl = document.getElementById('balance');
        if (balanceEl) balanceEl.textContent = '$0.00';
    }

    // P&L Diario
    const pnlEl = document.getElementById('daily-pnl');
    if (pnlEl && stats.total_pnl !== undefined) {
        const pnlColor = stats.total_pnl >= 0 ? 'text-green-500' : 'text-red-500';
        const pnlSign = stats.total_pnl >= 0 ? '+' : '';
        pnlEl.className = `text-3xl font-bold ${pnlColor}`;
        pnlEl.textContent = `${pnlSign}$${Math.abs(stats.total_pnl).toFixed(2)}`;
    }

    // Win Rate
    const winRateEl = document.getElementById('win-rate');
    if (winRateEl && stats.win_rate !== undefined) {
        winRateEl.textContent = `${(stats.win_rate * 100).toFixed(0)}%`;
    }

    // Max Drawdown
    const maxDDEl = document.getElementById('max-drawdown');
    if (maxDDEl && stats.max_drawdown !== undefined) {
        maxDDEl.textContent = `-$${Math.abs(stats.max_drawdown).toFixed(2)}`;
    }
}

// ============================================================================
// POSICIONES
// ============================================================================

async function loadPositions() {
    try {
        // Intentar obtener posiciones desde TopstepX primero
        const response = await fetch(`${API_BASE_URL}/api/positions/topstepx`);
        const data = await response.json();

        state.positions = data.positions || [];

        updatePositionsTable();

    } catch (error) {
        console.error('Error cargando posiciones:', error);
        // Fallback a posiciones de BD
        try {
            const response = await fetch(`${API_BASE_URL}/api/positions?status=OPEN`);
            state.positions = await response.json();
            updatePositionsTable();
        } catch (err) {
            console.error('Error cargando posiciones desde BD:', err);
        }
    }
}

function updatePositionsTable() {
    const tableBody = document.getElementById('positions-table');
    if (!tableBody) return;

    if (!state.positions || state.positions.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="py-8 text-center text-gray-400">No hay posiciones activas</td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = state.positions.map(pos => {
        const pnl = pos.pnl || 0;
        const pnlColor = pnl >= 0 ? 'text-green-500' : 'text-red-500';
        const pnlSign = pnl >= 0 ? '+' : '';
        const currentPrice = pos.current_price || pos.entry_price || 0;

        return `
            <tr class="border-b border-dark-border/50">
                <td class="py-4 font-medium">${pos.contract_name || pos.symbol || 'N/A'}</td>
                <td class="py-4">${pos.quantity || 0}</td>
                <td class="py-4">$${(pos.entry_price || 0).toFixed(2)}</td>
                <td class="py-4">$${currentPrice.toFixed(2)}</td>
                <td class="py-4 ${pnlColor} font-semibold">${pnlSign}$${Math.abs(pnl).toFixed(2)}</td>
                <td class="py-4">
                    <button onclick="closePosition('${pos.id}')" class="text-accent-cyan hover:text-cyan-400 font-medium">Close</button>
                </td>
            </tr>
        `;
    }).join('');
}

// ============================================================================
// HISTORIAL DE TRADES
// ============================================================================

async function loadTradesHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/trades?limit=50`);
        state.trades = await response.json();

        updateTradesTable();

    } catch (error) {
        console.error('Error cargando historial:', error);
    }
}

function updateTradesTable() {
    const tableBody = document.getElementById('history-table');
    if (!tableBody) return;

    if (!state.trades || state.trades.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="py-8 text-center text-gray-400">No hay trades realizados</td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = state.trades.map(trade => {
        const pnlColor = trade.pnl >= 0 ? 'text-green-500' : 'text-red-500';
        const pnlSign = trade.pnl >= 0 ? '+' : '';
        const typeClass = trade.side === 'LONG' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500';
        const typeText = trade.side === 'LONG' ? 'BUY' : 'SELL';

        return `
            <tr class="border-b border-dark-border/50">
                <td class="py-4 font-medium">${trade.contract_name}</td>
                <td class="py-4">${typeText}</td>
                <td class="py-4">${trade.quantity}</td>
                <td class="py-4">${trade.entry_price.toFixed(2)}</td>
                <td class="py-4">${trade.exit_price.toFixed(2)}</td>
                <td class="py-4 ${pnlColor} font-semibold">${pnlSign}$${Math.abs(trade.pnl).toFixed(2)}</td>
                <td class="py-4 text-gray-400">${new Date(trade.exit_time).toLocaleString()}</td>
            </tr>
        `;
    }).join('');
}

// ============================================================================
// BOT
// ============================================================================

async function toggleBot() {
    const checkbox = document.getElementById('bot-toggle');
    const isActive = checkbox.checked;

    try {
        const response = await fetch(`${API_BASE_URL}/api/bot/control`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: isActive ? 'start' : 'stop'
            })
        });

        const data = await response.json();

        if (data.success) {
            state.botActive = isActive;
            console.log(isActive ? '🤖 Bot iniciado' : '🛑 Bot detenido');

            // Update UI text if exists
            const statusEl = document.querySelector('.bg-dark-card p.text-gray-300');
            if (statusEl) {
                statusEl.textContent = isActive ? 'El bot está actualmente activo.' : 'El bot está actualmente inactivo.';
            }
        } else {
            checkbox.checked = !isActive;
            alert('Error: ' + (data.message || 'No se pudo cambiar el estado del bot'));
        }

    } catch (error) {
        console.error('Error controlando bot:', error);
        checkbox.checked = !isActive;
        alert('Error de conexión al intentar controlar el bot');
    }
}

async function saveBotConfig() {
    const config = {
        name: "Bot Configuration",
        stop_loss_usd: 150.0,
        take_profit_ratio: 2.5,
        max_positions: 8,
        max_daily_loss: 600.0,
        max_daily_trades: 50,
        use_smi: true,
        use_macd: true,
        use_bb: true,
        use_ma: true,
        timeframe_minutes: 5,
        min_confidence: 0.70,
        cooldown_seconds: 45
    };

    try {
        const response = await fetch(`${API_BASE_URL}/api/bot/config`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Configuración guardada exitosamente');
        } else {
            alert('❌ Error: ' + data.message);
        }

    } catch (error) {
        console.error('Error guardando configuración:', error);
        alert('❌ Error guardando configuración');
    }
}

// ============================================================================
// CONTRATOS
// ============================================================================

async function searchContracts(symbol) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/contracts/search/${symbol}`);
        const contracts = await response.json();

        console.log(`Contratos encontrados para ${symbol}:`, contracts);
        return contracts;

    } catch (error) {
        console.error('Error buscando contratos:', error);
        return [];
    }
}

// ============================================================================
// SEÑALES
// ============================================================================

async function generateSignal(contractId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/signals/generate/${contractId}`, {
            method: 'POST'
        });

        const signal = await response.json();

        console.log('Señal generada:', signal);
        return signal;

    } catch (error) {
        console.error('Error generando señal:', error);
        return null;
    }
}

// ============================================================================
// DATOS HISTÓRICOS
// ============================================================================

async function downloadBars(contractId, daysBack = 30) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/bars/download/${contractId}?days_back=${daysBack}`, {
            method: 'POST'
        });

        const data = await response.json();

        console.log(`Descargadas ${data.bars_downloaded} barras para ${contractId}`);
        return data;

    } catch (error) {
        console.error('Error descargando barras:', error);
        return null;
    }
}

// ============================================================================
// BACKTEST
// ============================================================================

async function runBacktest() {
    alert('⚠️ Módulo de Backtest en desarrollo. Utilice el script train.py para entrenar el modelo RL.');

    // Show example results
    console.log('Ejecutando backtest de ejemplo...');
}

// ============================================================================
// HORARIOS DE TRADING
// ============================================================================

async function saveTradingSchedule() {
    const schedule = {
        day_of_week: 1, // Monday
        start_time: "09:30",
        end_time: "16:00"
    };

    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(schedule)
        });

        const data = await response.json();

        if (data.success) {
            console.log('✅ Horario guardado');
        }

    } catch (error) {
        console.error('Error guardando horario:', error);
    }
}

async function loadTradingSchedule() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule`);
        const schedules = await response.json();

        console.log('Horarios de trading:', schedules);
        return schedules;

    } catch (error) {
        console.error('Error cargando horarios:', error);
        return [];
    }
}

// ============================================================================
// FUNCIONES DE AUTENTICACIÓN DE USUARIOS
// ============================================================================

function switchAuthTab(tab) {
    const tabs = ['login', 'register', 'forgot-password'];
    const forms = ['form-login', 'form-register', 'form-forgot-password'];

    tabs.forEach((t, i) => {
        const tabEl = document.getElementById(`tab-${t}`);
        const formEl = document.getElementById(forms[i]);

        if (t === tab) {
            if (tabEl) {
                tabEl.classList.add('bg-accent-cyan', 'text-white');
                tabEl.classList.remove('text-gray-400');
            }
            if (formEl) formEl.classList.remove('hidden');
        } else {
            if (tabEl) {
                tabEl.classList.remove('bg-accent-cyan', 'text-white');
                tabEl.classList.add('text-gray-400');
            }
            if (formEl) formEl.classList.add('hidden');
        }
    });
}

async function loginUser() {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const messageEl = document.getElementById('login-message');

    if (!username || !password) {
        showMessage(messageEl, '❌ Complete todos los campos', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/users/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username_or_email: username,
                password: password
            })
        });

        const data = await response.json();

        if (data.success) {
            localStorage.setItem('user_id', data.user_id);
            localStorage.setItem('username', data.username);
            localStorage.setItem('email', data.email);

            showMessage(messageEl, '✅ Login exitoso', 'success');

            setTimeout(() => {
                document.getElementById('auth-modal').classList.add('hidden');
                document.getElementById('main-app').classList.remove('hidden');
                loadUserData();
                loadInitialData();
            }, 1000);
        } else {
            showMessage(messageEl, `❌ ${data.detail || 'Error en login'}`, 'error');
        }
    } catch (error) {
        console.error('Error en login:', error);
        showMessage(messageEl, '❌ Error de conexión', 'error');
    }
}

async function registerUser() {
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm-password').value;
    const messageEl = document.getElementById('register-message');

    if (!username || !email || !password || !confirmPassword) {
        showMessage(messageEl, '❌ Complete todos los campos', 'error');
        return;
    }

    if (password !== confirmPassword) {
        showMessage(messageEl, '❌ Las contraseñas no coinciden', 'error');
        return;
    }

    if (password.length < 8) {
        showMessage(messageEl, '❌ La contraseña debe tener al menos 8 caracteres', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/users/register`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: username,
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (data.success) {
            showMessage(messageEl, '✅ Registro exitoso. Código de verificación: ' + (data.verification_code || 'revisar email'), 'success');
            setTimeout(() => switchAuthTab('login'), 2000);
        } else {
            showMessage(messageEl, `❌ ${data.detail || 'Error en registro'}`, 'error');
        }
    } catch (error) {
        console.error('Error en registro:', error);
        showMessage(messageEl, '❌ Error de conexión', 'error');
    }
}

function showForgotPassword() {
    switchAuthTab('forgot-password');
}

async function sendRecoveryCode() {
    const email = document.getElementById('forgot-email').value;
    const messageEl = document.getElementById('forgot-message');

    if (!email) {
        showMessage(messageEl, '❌ Ingresa tu email', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/users/forgot-password`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: email})
        });

        const data = await response.json();

        if (data.success) {
            showMessage(messageEl, '✅ Código enviado a tu email', 'success');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage(messageEl, '❌ Error de conexión', 'error');
    }
}

// ============================================================================
// ESTRATEGIAS
// ============================================================================

state.strategies = [];

async function loadStrategies() {
    const userId = localStorage.getItem('user_id');
    if (!userId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/strategies?user_id=${userId}`);
        const data = await response.json();
        state.strategies = data.strategies || [];
        updateStrategiesSelect();
    } catch (error) {
        console.error('Error cargando estrategias:', error);
    }
}

function updateStrategiesSelect() {
    const selects = document.querySelectorAll('select[id*="strategy"]');
    selects.forEach(select => {
        select.innerHTML = '<option value="">Seleccionar estrategia...</option>';
        state.strategies.forEach(s => {
            const option = document.createElement('option');
            option.value = s.id;
            option.textContent = s.name;
            select.appendChild(option);
        });
    });
}

async function saveStrategy(strategyData) {
    const userId = localStorage.getItem('user_id');

    try {
        const response = await fetch(`${API_BASE_URL}/api/strategies?user_id=${userId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(strategyData)
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Estrategia guardada');
            await loadStrategies();
        }
    } catch (error) {
        console.error('Error guardando estrategia:', error);
        alert('❌ Error guardando estrategia');
    }
}

// ============================================================================
// CONFIGURACIÓN
// ============================================================================

async function loadUserData() {
    const userId = localStorage.getItem('user_id');
    if (!userId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/users/me?user_id=${userId}`);
        const user = await response.json();

        const userDisplay = document.getElementById('current-user-display');
        const emailDisplay = document.getElementById('current-email-display');

        if (userDisplay) userDisplay.value = user.username;
        if (emailDisplay) emailDisplay.value = user.email;
    } catch (error) {
        console.error('Error cargando datos de usuario:', error);
    }
}

function toggleApiKeyVisibility() {
    const input = document.getElementById('config-api-key');
    const icon = document.getElementById('api-key-visibility-icon');

    if (input && icon) {
        if (input.type === 'password') {
            input.type = 'text';
            icon.textContent = 'visibility_off';
        } else {
            input.type = 'password';
            icon.textContent = 'visibility';
        }
    }
}

async function testTopstepConnection() {
    const apiKey = document.getElementById('config-api-key').value;
    const username = document.getElementById('config-topstep-username').value;
    const statusDiv = document.getElementById('topstep-connection-status');
    const messageEl = document.getElementById('topstep-connection-message');

    if (!apiKey || !username) {
        alert('❌ Ingresa API Key y Username');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({api_key: apiKey, username: username})
        });

        const data = await response.json();

        if (statusDiv && messageEl) {
            if (data.success) {
                statusDiv.classList.remove('hidden', 'bg-red-500/20');
                statusDiv.classList.add('bg-green-500/20');
                messageEl.textContent = '✅ Conexión exitosa a TopstepX';
                messageEl.className = 'text-sm text-green-500';
            } else {
                statusDiv.classList.remove('hidden', 'bg-green-500/20');
                statusDiv.classList.add('bg-red-500/20');
                messageEl.textContent = '❌ Error en conexión: ' + (data.message || 'Desconocido');
                messageEl.className = 'text-sm text-red-500';
            }
        }
    } catch (error) {
        if (statusDiv && messageEl) {
            statusDiv.classList.remove('hidden', 'bg-green-500/20');
            statusDiv.classList.add('bg-red-500/20');
            messageEl.textContent = '❌ Error de conexión';
            messageEl.className = 'text-sm text-red-500';
        }
    }
}

async function saveTopstepApiKey() {
    alert('✅ API Key guardada (funcionalidad completa por implementar)');
}

// ============================================================================
// GESTIÓN DE CONTRATOS
// ============================================================================

async function searchContractsInput() {
    const searchInput = document.querySelector('input[placeholder*="Buscar contratos"]');
    if (!searchInput) return;

    const symbol = searchInput.value.trim();

    if (!symbol || symbol.length < 2) return;

    try {
        const contracts = await searchContracts(symbol);
        updateContractsSearchResults(contracts);
    } catch (error) {
        console.error('Error buscando contratos:', error);
    }
}

function updateContractsSearchResults(contracts) {
    console.log('Contratos encontrados:', contracts);
}

async function addContractToBot(contractId, strategyId = null) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/contracts/${contractId}/add`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({contract_id: contractId, strategy_id: strategyId})
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Contrato añadido al bot');
        }
    } catch (error) {
        console.error('Error añadiendo contrato:', error);
    }
}

async function removeContract(contractId) {
    if (!confirm('¿Eliminar este contrato?')) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/contracts/${contractId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Contrato eliminado');
        }
    } catch (error) {
        console.error('Error eliminando contrato:', error);
    }
}

// ============================================================================
// POSICIONES Y P&L
// ============================================================================

async function closePosition(positionId) {
    if (!confirm('¿Cerrar esta posición?')) return;

    alert('⚠️ Funcionalidad de cierre de posiciones por implementar');
}

function testConnection() {
    alert('⚠️ Para probar la conexión, use el modal de inicio de sesión principal o la configuración de TopstepX.');
}

function saveCredentials() {
    alert('✅ Credenciales guardadas localmente (funcionalidad en desarrollo)');
}

// ============================================================================
// INICIALIZACIÓN
// ============================================================================

// Actualizar stats periódicamente
setInterval(async () => {
    if (state.authenticated) {
        await updateStats();
    }
}, 30000); // Cada 30 segundos

// Verificar autenticación al cargar
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/status`);
        const data = await response.json();

        if (data.authenticated) {
            // Ya estaba autenticado
            state.authenticated = true;
            state.accountId = data.account_id;

            document.getElementById('auth-modal').classList.add('hidden');
            document.getElementById('main-app').classList.remove('hidden');
            document.getElementById('account-id').textContent = state.accountId || 'N/A';

            await loadInitialData();
            initWebSocket();
        }
    } catch (error) {
        // No autenticado, mostrar modal
        console.log('No autenticado, mostrando modal de login');
    }
});

console.log('🚀 AI Trading App initialized');
console.log('📡 Backend:', API_BASE_URL);
