// Trading App - Frontend JavaScript
// Conecta con FastAPI backend integrado (RL + DB + API)

// Detectar automáticamente el host del backend
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : `${window.location.protocol}//${window.location.hostname}:8000`;

// Estado global
const state = {
    authenticated: false,
    accountId: null,
    selectedAccountData: null,
    availableAccounts: [],
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
            body: JSON.stringify({
                api_key: apiKey,
                username: username,
                system_username: 'default_user'
            })
        });

        const data = await response.json();

        if (data.success) {
            state.authenticated = true;
            state.availableAccounts = data.accounts || [];

            showMessage(messageEl, '✅ Conectado exitosamente', 'success');

            setTimeout(() => {
                document.getElementById('auth-modal').classList.add('hidden');
                document.getElementById('main-app').classList.remove('hidden');

                populateAccountSelector();
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

function populateAccountSelector() {
    const selector = document.getElementById('account-selector');
    const noCredsMessage = document.getElementById('no-credentials-message');

    if (!state.availableAccounts || state.availableAccounts.length === 0) {
        // Mostrar mensaje de "Ingresa credenciales"
        selector.classList.add('hidden');
        noCredsMessage.classList.remove('hidden');
        return;
    }

    // Ocultar mensaje y mostrar selector
    noCredsMessage.classList.add('hidden');
    selector.classList.remove('hidden');

    // Limpiar opciones existentes
    selector.innerHTML = '<option value="">Selecciona una cuenta</option>';

    // Agregar cuentas
    state.availableAccounts.forEach(account => {
        const option = document.createElement('option');
        option.value = account.id;
        option.textContent = `${account.name} - $${account.balance.toFixed(2)}`;
        option.selected = account.is_selected || false;

        // Guardar datos de la cuenta en el option
        option.dataset.accountData = JSON.stringify(account);

        selector.appendChild(option);

        // Si es la cuenta seleccionada, actualizar estado
        if (account.is_selected) {
            state.accountId = account.id;
            state.selectedAccountData = account;
        }
    });

    // Evento de cambio de cuenta
    selector.addEventListener('change', handleAccountChange);
}

async function handleAccountChange(event) {
    const selector = event.target;
    const selectedOption = selector.options[selector.selectedIndex];

    if (!selectedOption || !selectedOption.value) return;

    const accountId = selectedOption.value;
    const accountData = JSON.parse(selectedOption.dataset.accountData || '{}');

    try {
        // Llamar al backend para marcar la cuenta como seleccionada
        const response = await fetch(`${API_BASE_URL}/api/auth/select-account`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({account_id: accountId})
        });

        const data = await response.json();

        if (data.success) {
            state.accountId = accountId;
            state.selectedAccountData = accountData;

            console.log(`✅ Cuenta cambiada a: ${data.account_name}`);

            // Recargar datos para la nueva cuenta
            await loadAccountData();
        }

    } catch (error) {
        console.error('Error cambiando cuenta:', error);
        alert('Error al cambiar de cuenta');
    }
}

async function loadAccountData() {
    // Recargar todos los datos específicos de la cuenta seleccionada
    await updateStats();
    await loadTradesHistory();
    await loadPositions();
    await updateDashboardBalance();
}

function updateDashboardBalance() {
    const balanceEl = document.getElementById('balance');
    if (balanceEl && state.selectedAccountData) {
        balanceEl.textContent = `$${state.selectedAccountData.balance.toFixed(2)}`;
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

    // Construir URL del WebSocket dinámicamente
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'localhost:8000'
        : `${window.location.hostname}:8000`;
    const wsUrl = `${wsProtocol}//${wsHost}/ws`;

    state.wsConnection = new WebSocket(wsUrl);

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

function updateDashboardStats() {
    const stats = state.stats;

    // Balance (viene de la cuenta seleccionada)
    const balanceEl = document.getElementById('balance');
    if (balanceEl && state.selectedAccountData) {
        balanceEl.textContent = `$${state.selectedAccountData.balance.toFixed(2)}`;
    } else if (balanceEl) {
        balanceEl.textContent = `$0.00`;
    }

    // P&L Diario
    const pnlEl = document.getElementById('daily-pnl');
    if (pnlEl && stats.total_pnl !== undefined) {
        const pnlColor = stats.total_pnl >= 0 ? 'text-green-500' : 'text-red-500';
        const pnlSign = stats.total_pnl >= 0 ? '+' : '';
        pnlEl.className = `text-3xl font-bold ${pnlColor}`;
        pnlEl.textContent = `${pnlSign}$${Math.abs(stats.total_pnl).toFixed(2)}`;
    } else if (pnlEl) {
        pnlEl.textContent = `$0.00`;
    }

    // Win Rate
    const winRateEl = document.getElementById('win-rate');
    if (winRateEl && stats.win_rate !== undefined) {
        winRateEl.textContent = `${(stats.win_rate).toFixed(0)}%`;
    } else if (winRateEl) {
        winRateEl.textContent = `0%`;
    }

    // Max Drawdown
    const maxDDEl = document.getElementById('max-drawdown');
    if (maxDDEl && stats.max_drawdown !== undefined) {
        maxDDEl.textContent = `-$${Math.abs(stats.max_drawdown).toFixed(2)}`;
    } else if (maxDDEl) {
        maxDDEl.textContent = `$0.00`;
    }
}

// ============================================================================
// POSICIONES
// ============================================================================

async function loadPositions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/positions?status=OPEN`);
        state.positions = await response.json();

        // updatePositionsTable(); // Ya tiene datos mock en HTML

    } catch (error) {
        console.error('Error cargando posiciones:', error);
    }
}

// ============================================================================
// HISTORIAL DE TRADES
// ============================================================================

async function loadTradesHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/trades?limit=50`);
        state.trades = await response.json();

        // updateTradesTable(); // Ya tiene datos mock en HTML

    } catch (error) {
        console.error('Error cargando historial:', error);
    }
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
// CONFIGURACIÓN
// ============================================================================

function testConnection() {
    alert('⚠️ Para probar la conexión, use el modal de inicio de sesión principal.');
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

// Verificar autenticación y credenciales guardadas al cargar
window.addEventListener('DOMContentLoaded', async () => {
    try {
        // Verificar si hay credenciales guardadas
        const credsResponse = await fetch(`${API_BASE_URL}/api/auth/credentials?system_username=default_user`);
        const credsData = await credsResponse.json();

        if (credsData.success && credsData.has_credentials) {
            // Hay credenciales guardadas
            state.availableAccounts = credsData.accounts || [];

            // Verificar estado de autenticación
            const statusResponse = await fetch(`${API_BASE_URL}/api/auth/status`);
            const statusData = await statusResponse.json();

            if (statusData.authenticated) {
                // Ya autenticado, mostrar app
                state.authenticated = true;
                state.accountId = statusData.account_id;

                document.getElementById('auth-modal').classList.add('hidden');
                document.getElementById('main-app').classList.remove('hidden');

                populateAccountSelector();
                await loadInitialData();
                initWebSocket();
            } else {
                // Hay credenciales pero no autenticado, mostrar selector
                populateAccountSelector();
            }
        } else {
            // No hay credenciales, mostrar mensaje
            const selector = document.getElementById('account-selector');
            const noCredsMessage = document.getElementById('no-credentials-message');
            selector.classList.add('hidden');
            noCredsMessage.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error verificando credenciales:', error);
        // No autenticado, mostrar modal
        console.log('No autenticado, mostrando modal de login');
    }
});

console.log('🚀 AI Trading App initialized');
console.log('📡 Backend:', API_BASE_URL);
