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

function updateDashboardStats() {
    const stats = state.stats;

    // Balance (podría venir del backend)
    const balanceEl = document.getElementById('balance');
    if (balanceEl) {
        balanceEl.textContent = `$150,432.10`; // Mock data from images
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
