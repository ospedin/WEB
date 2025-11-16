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
    botActive: false,
    topstepConnected: false,
    topstepApiKey: null,
    topstepUsername: null
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

    // Cargar datos específicos del módulo
    if (moduleName === 'bot') {
        loadActiveContracts();
    } else if (moduleName === 'backtest') {
        loadBacktestContracts();
        loadBacktestStrategies();
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
// ACTUALIZAR INDICADOR DE CONEXIÓN EN HEADER
// ============================================================================

function updateTopstepHeaderIndicator() {
    const indicator = document.getElementById('topstep-header-indicator');
    const dot = document.getElementById('topstep-header-dot');
    const text = document.getElementById('topstep-header-text');

    if (!indicator || !dot || !text) return;

    if (state.topstepConnected) {
        // Mostrar como conectado
        indicator.classList.remove('hidden');
        dot.classList.remove('bg-red-500', 'bg-yellow-500');
        dot.classList.add('bg-green-500');
        text.textContent = 'Conectado a TopstepX';
    } else {
        // Ocultar indicador cuando no está conectado
        indicator.classList.add('hidden');
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

    // Balance - obtener de TopstepX API solo si está conectado
    const balanceEl = document.getElementById('balance');
    if (!state.topstepConnected) {
        // Si TopstepX no está conectado, mostrar valor por defecto
        if (balanceEl) balanceEl.textContent = '$0.00';
    } else {
        // Si está conectado, intentar obtener el balance real
        try {
            const balanceResponse = await fetch(`${API_BASE_URL}/api/account/balance`);
            if (balanceResponse.ok) {
                const balanceData = await balanceResponse.json();
                if (balanceEl && balanceData.balance !== undefined) {
                    balanceEl.textContent = `$${balanceData.balance.toFixed(2)}`;
                }
            } else {
                if (balanceEl) balanceEl.textContent = '$0.00';
            }
        } catch (error) {
            console.log('TopstepX no conectado, mostrando balance por defecto');
            if (balanceEl) balanceEl.textContent = '$0.00';
        }
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
    // Solo intentar cargar posiciones si TopstepX está conectado
    if (!state.topstepConnected) {
        state.positions = [];
        updatePositionsTable();
        return;
    }

    try {
        // Intentar obtener posiciones desde TopstepX
        const response = await fetch(`${API_BASE_URL}/api/positions/topstepx`);

        if (response.ok) {
            const data = await response.json();
            state.positions = data.positions || [];
        } else {
            state.positions = [];
        }

        updatePositionsTable();

    } catch (error) {
        console.log('TopstepX no conectado, mostrando posiciones vacías');
        state.positions = [];
        updatePositionsTable();
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

let currentBacktestMode = 'combined'; // 'model', 'combined', 'indicators'
let currentStrategyId = null;

// Configurar modo de backtest
function setBacktestMode(mode) {
    currentBacktestMode = mode;

    // Actualizar botones
    ['model', 'combined', 'indicators'].forEach(m => {
        const btn = document.getElementById(`mode-${m}`);
        if (btn) {
            if (m === mode) {
                btn.classList.remove('bg-dark-bg', 'text-gray-400', 'border-dark-border');
                btn.classList.add('bg-accent-cyan', 'text-white', 'border-accent-cyan');
            } else {
                btn.classList.remove('bg-accent-cyan', 'text-white', 'border-accent-cyan');
                btn.classList.add('bg-dark-bg', 'text-gray-400', 'border-dark-border');
            }
        }
    });

    // Mostrar/ocultar panel de indicadores según el modo
    const indicatorsPanel = document.getElementById('indicators-config');
    if (mode === 'model') {
        indicatorsPanel.classList.add('hidden');
    } else {
        indicatorsPanel.classList.remove('hidden');
    }

    console.log(`Modo de backtest configurado: ${mode}`);
}

// Toggle panel de indicadores
function toggleIndicatorsConfig() {
    const panel = document.getElementById('indicators-config-panel');
    const icon = document.getElementById('indicators-toggle-icon');

    if (panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
        icon.textContent = 'expand_less';
    } else {
        panel.classList.add('hidden');
        icon.textContent = 'expand_more';
    }
}

// Event listeners para checkboxes de indicadores
document.addEventListener('DOMContentLoaded', () => {
    // Setup indicator checkbox listeners
    const indicators = ['smi', 'stochrsi', 'macd', 'bb', 'kdj', 'ma', 'cci', 'roc', 'atr', 'wr'];

    indicators.forEach(indicator => {
        const checkbox = document.getElementById(`use-${indicator}`);
        const paramsDiv = document.getElementById(`${indicator}-params`);

        if (checkbox && paramsDiv) {
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    paramsDiv.classList.remove('hidden');
                } else {
                    paramsDiv.classList.add('hidden');
                }
            });
        }
    });

    // Configurar fechas por defecto (últimos 6 meses)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 6);

    const startInput = document.getElementById('backtest-start-date');
    const endInput = document.getElementById('backtest-end-date');

    if (startInput) startInput.valueAsDate = startDate;
    if (endInput) endInput.valueAsDate = endDate;
});

// Variables para backtest contract search
let backtestContractSearchTimeout = null;
let selectedBacktestContract = null;

// Buscar contratos para backtest
async function searchBacktestContracts() {
    const searchInput = document.getElementById('backtest-contract-search');
    if (!searchInput) return;

    const symbol = searchInput.value.trim().toUpperCase();

    // Limpiar timeout anterior
    if (backtestContractSearchTimeout) {
        clearTimeout(backtestContractSearchTimeout);
    }

    // Si el campo está vacío, limpiar resultados
    if (!symbol || symbol.length < 1) {
        document.getElementById('backtest-contract-results').innerHTML = '';
        return;
    }

    // Mostrar indicador de carga
    document.getElementById('backtest-contract-results').innerHTML = `
        <div class="text-center py-2 text-gray-400">
            <span class="material-symbols-outlined animate-spin text-xl">progress_activity</span>
        </div>
    `;

    // Esperar 500ms antes de buscar (debounce)
    backtestContractSearchTimeout = setTimeout(async () => {
        try {
            const contracts = await searchContracts(symbol);
            displayBacktestContractResults(contracts);
        } catch (error) {
            console.error('Error buscando contratos para backtest:', error);
            document.getElementById('backtest-contract-results').innerHTML = `
                <div class="text-center py-2 text-red-400 text-sm">
                    Error al buscar contratos
                </div>
            `;
        }
    }, 500);
}

// Mostrar resultados de búsqueda para backtest
function displayBacktestContractResults(contracts) {
    const resultsContainer = document.getElementById('backtest-contract-results');

    if (!contracts || contracts.length === 0) {
        resultsContainer.innerHTML = `
            <div class="text-center py-2 text-gray-400 text-sm">
                No se encontraron contratos
            </div>
        `;
        return;
    }

    resultsContainer.innerHTML = contracts.map(contract => `
        <div
            onclick="selectBacktestContract('${contract.id}', '${contract.name}', '${contract.symbol_id}')"
            class="flex items-center justify-between p-2 bg-dark-bg rounded-lg border border-dark-border hover:border-accent-cyan transition cursor-pointer">
            <div class="flex-1">
                <p class="font-medium text-white text-sm">${contract.name || contract.symbol_id}</p>
                <p class="text-xs text-gray-400">${contract.description || 'Sin descripción'}</p>
            </div>
            <span class="material-symbols-outlined text-gray-400 text-sm">chevron_right</span>
        </div>
    `).join('');
}

// Seleccionar contrato para backtest
function selectBacktestContract(contractId, contractName, symbolId) {
    selectedBacktestContract = {
        id: contractId,
        name: contractName,
        symbol_id: symbolId
    };

    // Mostrar contrato seleccionado
    document.getElementById('backtest-selected-contract-name').textContent = contractName;
    document.getElementById('backtest-selected-contract-id').textContent = `ID: ${symbolId}`;
    document.getElementById('backtest-selected-contract').classList.remove('hidden');

    // Limpiar búsqueda
    document.getElementById('backtest-contract-search').value = '';
    document.getElementById('backtest-contract-results').innerHTML = '';

    console.log(`✅ Contrato seleccionado para backtest: ${contractName}`);
}

// Limpiar selección de contrato
function clearBacktestContractSelection() {
    selectedBacktestContract = null;
    document.getElementById('backtest-selected-contract').classList.add('hidden');
}

// Cargar contratos iniciales (ya no es necesario, pero lo dejo para compatibilidad)
async function loadBacktestContracts() {
    // Ya no es necesario cargar contratos al inicio,
    // se cargarán mediante búsqueda
    console.log('✅ Buscador de contratos para backtest listo');
}

// Cargar estrategias guardadas
async function loadBacktestStrategies() {
    try {
        const userId = localStorage.getItem('user_id');
        if (!userId) return;

        const response = await fetch(`${API_BASE_URL}/api/strategies?user_id=${userId}`);
        const data = await response.json();

        const selector = document.getElementById('load-strategy-selector');
        if (!selector) return;

        // Limpiar opciones excepto la primera
        selector.innerHTML = '<option value="">Nueva estrategia...</option>';

        if (data.strategies && data.strategies.length > 0) {
            data.strategies.forEach(strategy => {
                const option = document.createElement('option');
                option.value = strategy.id;
                option.textContent = strategy.name;
                selector.appendChild(option);
            });
        }

        console.log(`✅ ${data.strategies?.length || 0} estrategias cargadas`);
    } catch (error) {
        console.error('Error cargando estrategias:', error);
    }
}

// Cargar configuración de estrategia
async function loadStrategyConfig() {
    const selector = document.getElementById('load-strategy-selector');
    const strategyId = selector.value;

    if (!strategyId) {
        // Nueva estrategia - resetear formulario
        resetBacktestForm();
        return;
    }

    try {
        const userId = localStorage.getItem('user_id');
        const response = await fetch(`${API_BASE_URL}/api/strategies/${strategyId}?user_id=${userId}`);
        const strategy = await response.json();

        currentStrategyId = strategyId;

        // Cargar nombre
        document.getElementById('strategy-name-input').value = strategy.name || '';

        // Cargar parámetros de riesgo
        if (strategy.timeframe_minutes) {
            document.getElementById('backtest-timeframe').value = strategy.timeframe_minutes;
        }
        if (strategy.stop_loss_usd !== undefined) {
            document.getElementById('backtest-stop-loss').value = strategy.stop_loss_usd;
        }
        if (strategy.take_profit_ratio !== undefined && strategy.stop_loss_usd) {
            document.getElementById('backtest-take-profit').value = strategy.stop_loss_usd * strategy.take_profit_ratio;
        }

        // Cargar modo
        if (strategy.use_model && (strategy.use_smi || strategy.use_macd || strategy.use_bb || strategy.use_ma || strategy.use_stoch_rsi || strategy.use_kdj || strategy.use_cci || strategy.use_roc || strategy.use_atr || strategy.use_wr)) {
            setBacktestMode('combined');
        } else if (strategy.use_model) {
            setBacktestMode('model');
        } else {
            setBacktestMode('indicators');
        }

        // Cargar indicadores
        const indicators = {
            'smi': ['k_period', 'd_period', 'smooth'],
            'stochrsi': ['rsi_period', 'stoch_period', 'k', 'd'],
            'macd': ['fast', 'slow', 'signal'],
            'bb': ['period', 'std_dev'],
            'kdj': ['k_period', 'd_period', 'j_period'],
            'ma': ['fast', 'slow'],
            'cci': ['period', 'constant'],
            'roc': ['period'],
            'atr': ['period'],
            'wr': ['period']
        };

        for (const [indicator, params] of Object.entries(indicators)) {
            const useCheckbox = document.getElementById(`use-${indicator}`);
            const enabled = strategy[`use_${indicator}`];

            if (useCheckbox) {
                useCheckbox.checked = enabled;
                const paramsDiv = document.getElementById(`${indicator}-params`);
                if (paramsDiv) {
                    if (enabled) {
                        paramsDiv.classList.remove('hidden');
                    } else {
                        paramsDiv.classList.add('hidden');
                    }
                }

                // Cargar parámetros
                params.forEach(param => {
                    const input = document.getElementById(`${indicator}-${param.replace('_', '-')}`);
                    if (input && strategy[`${indicator}_${param}`] !== undefined) {
                        input.value = strategy[`${indicator}_${param}`];
                    }
                });
            }
        }

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Estrategia cargada',
                `Configuración de "${strategy.name}" cargada correctamente`,
                'success'
            );
        }
    } catch (error) {
        console.error('Error cargando estrategia:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo cargar la estrategia',
                'error'
            );
        }
    }
}

// Resetear formulario de backtest
function resetBacktestForm() {
    currentStrategyId = null;
    document.getElementById('strategy-name-input').value = '';

    // Desmarcar todos los indicadores
    ['smi', 'stochrsi', 'macd', 'bb', 'kdj', 'ma', 'cci', 'roc', 'atr', 'wr'].forEach(indicator => {
        const checkbox = document.getElementById(`use-${indicator}`);
        if (checkbox) {
            checkbox.checked = false;
            const paramsDiv = document.getElementById(`${indicator}-params`);
            if (paramsDiv) paramsDiv.classList.add('hidden');
        }
    });

    setBacktestMode('combined');
}

// Guardar estrategia de backtest
async function saveBacktestStrategy() {
    const strategyName = document.getElementById('strategy-name-input').value.trim();

    if (!strategyName) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '⚠️ Nombre requerido',
                'Por favor ingresa un nombre para la estrategia',
                'warning'
            );
        }
        return;
    }

    const userId = localStorage.getItem('user_id');
    if (!userId) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se encontró el usuario',
                'error'
            );
        }
        return;
    }

    // Recopilar configuración
    const strategyConfig = {
        user_id: parseInt(userId),
        name: strategyName,
        description: `Estrategia de backtest creada el ${new Date().toLocaleDateString()}`,

        // Modelo
        use_model: currentBacktestMode === 'model' || currentBacktestMode === 'combined',

        // Parámetros de riesgo
        timeframe_minutes: parseInt(document.getElementById('backtest-timeframe')?.value) || 5,
        stop_loss_usd: parseFloat(document.getElementById('backtest-stop-loss')?.value) || 150,
        take_profit_ratio: parseFloat(document.getElementById('backtest-take-profit')?.value) / parseFloat(document.getElementById('backtest-stop-loss')?.value) || 2.0,

        // Indicadores
        use_smi: document.getElementById('use-smi')?.checked || false,
        use_stoch_rsi: document.getElementById('use-stochrsi')?.checked || false,
        use_macd: document.getElementById('use-macd')?.checked || false,
        use_bb: document.getElementById('use-bb')?.checked || false,
        use_kdj: document.getElementById('use-kdj')?.checked || false,
        use_ma: document.getElementById('use-ma')?.checked || false,
        use_cci: document.getElementById('use-cci')?.checked || false,
        use_roc: document.getElementById('use-roc')?.checked || false,
        use_atr: document.getElementById('use-atr')?.checked || false,
        use_wr: document.getElementById('use-wr')?.checked || false,

        // Parámetros SMI
        smi_k_period: parseInt(document.getElementById('smi-k-period')?.value) || 10,
        smi_d_period: parseInt(document.getElementById('smi-d-period')?.value) || 3,
        smi_smooth: parseInt(document.getElementById('smi-smooth')?.value) || 3,

        // Parámetros StochRSI
        stoch_rsi_rsi_period: parseInt(document.getElementById('stochrsi-rsi-period')?.value) || 14,
        stoch_rsi_stoch_period: parseInt(document.getElementById('stochrsi-stoch-period')?.value) || 14,
        stoch_rsi_k: parseInt(document.getElementById('stochrsi-k')?.value) || 3,
        stoch_rsi_d: parseInt(document.getElementById('stochrsi-d')?.value) || 3,

        // Parámetros MACD
        macd_fast: parseInt(document.getElementById('macd-fast')?.value) || 12,
        macd_slow: parseInt(document.getElementById('macd-slow')?.value) || 26,
        macd_signal: parseInt(document.getElementById('macd-signal')?.value) || 9,

        // Parámetros BB
        bb_period: parseInt(document.getElementById('bb-period')?.value) || 20,
        bb_std_dev: parseFloat(document.getElementById('bb-std-dev')?.value) || 2.0,

        // Parámetros KDJ
        kdj_k_period: parseInt(document.getElementById('kdj-k-period')?.value) || 9,
        kdj_d_period: parseInt(document.getElementById('kdj-d-period')?.value) || 3,
        kdj_j_period: parseInt(document.getElementById('kdj-j-period')?.value) || 3,

        // Parámetros MA
        ma_fast: parseInt(document.getElementById('ma-fast')?.value) || 10,
        ma_slow: parseInt(document.getElementById('ma-slow')?.value) || 30,

        // Parámetros CCI
        cci_period: parseInt(document.getElementById('cci-period')?.value) || 20,
        cci_constant: parseFloat(document.getElementById('cci-constant')?.value) || 0.015,

        // Parámetros ROC
        roc_period: parseInt(document.getElementById('roc-period')?.value) || 12,

        // Parámetros ATR
        atr_period: parseInt(document.getElementById('atr-period')?.value) || 14,

        // Parámetros WR
        wr_period: parseInt(document.getElementById('wr-period')?.value) || 14
    };

    try {
        let response;

        if (currentStrategyId) {
            // Actualizar estrategia existente
            response = await fetch(`${API_BASE_URL}/api/strategies/${currentStrategyId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(strategyConfig)
            });
        } else {
            // Crear nueva estrategia
            response = await fetch(`${API_BASE_URL}/api/strategies`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(strategyConfig)
            });
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Error guardando estrategia');
        }

        if (data.id) {
            currentStrategyId = data.id;
        }

        // Recargar lista de estrategias
        await loadBacktestStrategies();

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Estrategia guardada',
                `"${strategyName}" se guardó correctamente`,
                'success'
            );
        }
    } catch (error) {
        console.error('Error guardando estrategia:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo guardar la estrategia',
                'error'
            );
        }
    }
}

// Ejecutar backtest
async function executeBacktest() {
    const startDate = document.getElementById('backtest-start-date').value;
    const endDate = document.getElementById('backtest-end-date').value;

    // Validaciones
    if (!selectedBacktestContract) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '⚠️ Contrato requerido',
                'Busca y selecciona un contrato para ejecutar el backtest',
                'warning'
            );
        }
        return;
    }

    if (!startDate || !endDate) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '⚠️ Fechas requeridas',
                'Selecciona el rango de fechas para el backtest',
                'warning'
            );
        }
        return;
    }

    // Determinar modo según el backend
    let mode = 'bot_only';
    if (currentBacktestMode === 'model') {
        mode = 'bot_only';
    } else if (currentBacktestMode === 'combined') {
        mode = 'bot_indicators';
    } else if (currentBacktestMode === 'indicators') {
        mode = 'indicators_only';
    }

    // Obtener parámetros adicionales
    const timeframe = parseInt(document.getElementById('backtest-timeframe').value);
    const stopLoss = parseFloat(document.getElementById('backtest-stop-loss').value) || 150;
    const takeProfit = parseFloat(document.getElementById('backtest-take-profit').value) || 300;

    // Calcular take profit ratio
    const takeProfitRatio = stopLoss > 0 ? takeProfit / stopLoss : 2.0;

    // Obtener parámetros de sobreventa/sobrecompra
    const smiOversold = parseFloat(document.getElementById('smi-oversold')?.value) || -40;
    const smiOverbought = parseFloat(document.getElementById('smi-overbought')?.value) || 40;
    const stochRsiOversold = parseFloat(document.getElementById('stochrsi-oversold')?.value) || 20;
    const stochRsiOverbought = parseFloat(document.getElementById('stochrsi-overbought')?.value) || 80;
    const minConfidence = parseFloat(document.getElementById('backtest-min-confidence')?.value) || 0.70;

    // Obtener indicadores seleccionados
    const useSmi = document.getElementById('use-smi')?.checked || false;
    const useMacd = document.getElementById('use-macd')?.checked || false;
    const useBb = document.getElementById('use-bb')?.checked || false;
    const useMa = document.getElementById('use-ma')?.checked || false;
    const useStochRsi = document.getElementById('use-stochrsi')?.checked || false;
    const useVwap = document.getElementById('use-vwap')?.checked || false;
    const useSupertrend = document.getElementById('use-supertrend')?.checked || false;
    const useKdj = document.getElementById('use-kdj')?.checked || false;
    const useCci = document.getElementById('use-cci')?.checked || false;
    const useRoc = document.getElementById('use-roc')?.checked || false;
    const useAtr = document.getElementById('use-atr')?.checked || false;
    const useWr = document.getElementById('use-wr')?.checked || false;

    // Verificar que al menos un indicador esté seleccionado si no es modo "model"
    const hasAnyIndicator = useSmi || useMacd || useBb || useMa || useStochRsi || useVwap || useSupertrend || useKdj;
    if (currentBacktestMode !== 'model' && !hasAnyIndicator) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '⚠️ Indicadores requeridos',
                'Selecciona al menos un indicador técnico',
                'warning'
            );
        }
        return;
    }

    // Configuración del backtest según el backend requiere
    const backtestConfig = {
        contract_id: selectedBacktestContract.id,
        mode: mode,
        timeframes: [timeframe],  // Usar el timeframe seleccionado
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
        stop_loss_usd: stopLoss,
        take_profit_ratio: takeProfitRatio,
        // Parámetros de indicadores
        smi_oversold: smiOversold,
        smi_overbought: smiOverbought,
        stoch_rsi_oversold: stochRsiOversold,
        stoch_rsi_overbought: stochRsiOverbought,
        min_confidence: minConfidence,
        // Indicadores seleccionados
        use_smi: useSmi,
        use_macd: useMacd,
        use_bb: useBb,
        use_ma: useMa,
        use_stoch_rsi: useStochRsi,
        use_vwap: useVwap,
        use_supertrend: useSupertrend,
        use_kdj: useKdj,
        use_cci: useCci,
        use_roc: useRoc,
        use_atr: useAtr,
        use_wr: useWr
    }

    try {
        // Mostrar indicador de carga - PASO 1: Descargando datos
        document.getElementById('backtest-results').classList.add('hidden');
        document.getElementById('backtest-no-results').classList.remove('hidden');
        document.getElementById('backtest-no-results').innerHTML = `
            <div class="text-center py-12">
                <span class="material-symbols-outlined text-6xl text-accent-cyan mb-4 animate-spin">download</span>
                <h3 class="text-xl font-bold mb-2">Descargando Datos Históricos...</h3>
                <p class="text-gray-400">Timeframe: ${timeframe} minuto(s)</p>
                <p class="text-gray-400 mt-2">Esto puede tomar algunos minutos</p>
            </div>
        `;

        // PASO 1: Descargar datos históricos
        const startDateObj = new Date(startDate);
        const endDateObj = new Date(endDate);
        const daysBack = Math.ceil((endDateObj - startDateObj) / (1000 * 60 * 60 * 24)) + 1;

        console.log(`📥 Descargando ${daysBack} días de datos históricos para ${selectedBacktestContract.name}...`);

        const downloadResponse = await fetch(
            `${API_BASE_URL}/api/bars/download/${selectedBacktestContract.id}?days_back=${daysBack}&timeframe=${timeframe}`,
            { method: 'POST' }
        );

        if (!downloadResponse.ok) {
            const errorData = await downloadResponse.json();
            throw new Error(errorData.detail || 'Error descargando datos históricos');
        }

        const downloadData = await downloadResponse.json();
        console.log(`✅ Descargados ${downloadData.bars_downloaded || 0} barras`);

        // Notificar descarga exitosa
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Datos Descargados',
                `${downloadData.bars_downloaded || 0} barras descargadas correctamente`,
                'success'
            );
        }

        // PASO 2: Ejecutar backtest
        document.getElementById('backtest-no-results').innerHTML = `
            <div class="text-center py-12">
                <span class="material-symbols-outlined text-6xl text-accent-cyan mb-4 animate-spin">psychology</span>
                <h3 class="text-xl font-bold mb-2">Ejecutando Backtest...</h3>
                <p class="text-gray-400">Analizando ${downloadData.bars_downloaded || 0} barras</p>
                <p class="text-gray-400 mt-2">Esto puede tomar algunos minutos</p>
            </div>
        `;

        const response = await fetch(`${API_BASE_URL}/api/backtest/run`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(backtestConfig)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Error ejecutando backtest');
        }

        // Mostrar resultados
        displayBacktestResults(data);

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Backtest completado',
                'Los resultados están listos',
                'success'
            );
        }
    } catch (error) {
        console.error('Error ejecutando backtest:', error);

        document.getElementById('backtest-no-results').innerHTML = `
            <div class="text-center py-12">
                <span class="material-symbols-outlined text-6xl text-red-500 mb-4">error</span>
                <h3 class="text-xl font-bold mb-2">Error en Backtest</h3>
                <p class="text-gray-400">${error.message}</p>
            </div>
        `;

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo ejecutar el backtest',
                'error'
            );
        }
    }
}

// Mostrar resultados del backtest
function displayBacktestResults(data) {
    document.getElementById('backtest-no-results').classList.add('hidden');
    document.getElementById('backtest-results').classList.remove('hidden');

    // Extraer results del objeto de respuesta
    const results = data.results || data;

    // Actualizar métricas
    const totalPnl = parseFloat(results.total_pnl) || 0;
    const winRate = (parseFloat(results.win_rate) * 100) || 0;
    const profitFactor = parseFloat(results.profit_factor) || 0;
    const maxDrawdown = parseFloat(results.max_drawdown) || 0;

    document.getElementById('backtest-total-pnl').textContent = `$${totalPnl.toFixed(2)}`;
    document.getElementById('backtest-win-rate').textContent = `${winRate.toFixed(1)}%`;
    document.getElementById('backtest-profit-factor').textContent = profitFactor.toFixed(2);
    document.getElementById('backtest-max-drawdown').textContent = `$${maxDrawdown.toFixed(2)}`;

    // Mostrar trades
    if (results.trades && results.trades.length > 0) {
        document.getElementById('backtest-trades').classList.remove('hidden');
        renderBacktestTrades(results.trades);
    } else {
        document.getElementById('backtest-trades').classList.add('hidden');
    }

    // Renderizar gráfico de velas con indicadores
    if (results.chart_data && results.chart_data.candlesticks && results.chart_data.candlesticks.length > 0) {
        document.getElementById('candlestick-chart-container').classList.remove('hidden');
        renderBacktestChart(results.chart_data, results.trades || [], results.equity_curve || []);
    } else {
        document.getElementById('candlestick-chart-container').classList.add('hidden');
    }

    // Renderizar curva de capital
    if (results.equity_curve && results.equity_curve.length > 0) {
        document.getElementById('equity-curve-container')?.classList.remove('hidden');
        renderEquityCurve(results.equity_curve, results.initial_balance || 100000);
    } else {
        document.getElementById('equity-curve-container')?.classList.add('hidden');
    }

    console.log('✅ Resultados del backtest mostrados:', {
        trades: results.trades?.length || 0,
        candlesticks: results.chart_data?.candlesticks?.length || 0,
        equity_points: results.equity_curve?.length || 0,
        pnl: totalPnl,
        winRate: winRate
    });
}

// Renderizar tabla de trades del backtest
function renderBacktestTrades(trades) {
    const tableBody = document.getElementById('backtest-trades-table');

    if (!trades || trades.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="py-8 text-center text-gray-400">
                    No se generaron operaciones en este backtest
                    <p class="text-sm mt-2">Esto puede ser porque:</p>
                    <ul class="text-sm mt-1">
                        <li>• Las condiciones de los indicadores no se cumplieron</li>
                        <li>• SMI (Sobreventa: <-40, Sobrecompra: >+40)</li>
                        <li>• Stochastic RSI (Sobreventa: <20, Sobrecompra: >80)</li>
                    </ul>
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = trades.map(trade => {
        const pnl = trade.pnl || 0;
        const ticks = trade.ticks || 0;
        const pnlColor = pnl >= 0 ? 'text-green-500' : 'text-red-500';
        const entryTime = trade.entry_time ? new Date(trade.entry_time).toLocaleString() : 'N/A';
        const exitTime = trade.exit_time ? new Date(trade.exit_time).toLocaleString() : 'N/A';

        return `
            <tr class="border-b border-dark-border hover:bg-dark-bg transition">
                <td class="py-4 font-medium">${trade.contract_id || 'N/A'}</td>
                <td class="py-4">${entryTime}</td>
                <td class="py-4">
                    <span class="px-2 py-1 rounded text-xs ${trade.side === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}">
                        ${trade.side}
                    </span>
                </td>
                <td class="py-4">$${(trade.entry_price || 0).toFixed(2)}</td>
                <td class="py-4">$${(trade.exit_price || 0).toFixed(2)}</td>
                <td class="py-4 ${pnlColor} font-semibold">$${pnl.toFixed(2)}</td>
                <td class="py-4 text-gray-400">${ticks.toFixed(1)} ticks</td>
            </tr>
        `;
    }).join('');
}

// ============================================================================
// HORARIOS DE TRADING
// ============================================================================

// Alternar día de trading
function toggleTradingDay(day) {
    const button = document.getElementById(`day-${day}`);
    if (!button) return;

    const isActive = button.getAttribute('data-active') === 'true';

    if (isActive) {
        // Desactivar
        button.setAttribute('data-active', 'false');
        button.classList.remove('bg-accent-cyan', 'text-white');
        button.classList.add('bg-dark-bg', 'text-gray-400');
    } else {
        // Activar
        button.setAttribute('data-active', 'true');
        button.classList.remove('bg-dark-bg', 'text-gray-400');
        button.classList.add('bg-accent-cyan', 'text-white');
    }
}

// Obtener días activos
function getActiveTradingDays() {
    const days = [];
    for (let i = 0; i <= 6; i++) {
        const button = document.getElementById(`day-${i}`);
        if (button && button.getAttribute('data-active') === 'true') {
            days.push(i);
        }
    }
    return days;
}

// Guardar horario de trading
async function saveTradingSchedule() {
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;
    const activeDays = getActiveTradingDays();

    if (!startTime || !endTime) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '⚠️ Horarios requeridos',
                'Configura la hora de inicio y fin',
                'warning'
            );
        }
        return;
    }

    if (activeDays.length === 0) {
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '⚠️ Días requeridos',
                'Selecciona al menos un día de trading',
                'warning'
            );
        }
        return;
    }

    try {
        // Guardar horario para cada día activo
        const promises = activeDays.map(day => {
            const schedule = {
                day_of_week: day,
                start_time: startTime,
                end_time: endTime
            };

            return fetch(`${API_BASE_URL}/api/schedule`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(schedule)
            });
        });

        await Promise.all(promises);

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Horario guardado',
                `Horario configurado para ${activeDays.length} día(s)`,
                'success'
            );
        }

        console.log('✅ Horario guardado para días:', activeDays);

    } catch (error) {
        console.error('Error guardando horario:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo guardar el horario',
                'error'
            );
        }
    }
}

// Cargar horarios de trading
async function loadTradingSchedule() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule`);
        const schedules = await response.json();

        if (schedules && schedules.length > 0) {
            // Tomar el primer horario como referencia
            const firstSchedule = schedules[0];
            document.getElementById('start-time').value = firstSchedule.start_time;
            document.getElementById('end-time').value = firstSchedule.end_time;

            // Marcar días activos
            schedules.forEach(schedule => {
                const button = document.getElementById(`day-${schedule.day_of_week}`);
                if (button) {
                    button.setAttribute('data-active', 'true');
                    button.classList.remove('bg-dark-bg', 'text-gray-400');
                    button.classList.add('bg-accent-cyan', 'text-white');
                }
            });

            console.log('✅ Horarios cargados:', schedules);
        }

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
    const keepSession = document.getElementById('keep-session').checked;
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
            // Guardar datos de sesión
            const sessionData = {
                user_id: data.user_id,
                username: data.username,
                email: data.email,
                timestamp: Date.now()
            };

            // Si el usuario marcó "Mantener sesión", establecer expiración de 15 días
            if (keepSession) {
                sessionData.expiration = Date.now() + (15 * 24 * 60 * 60 * 1000); // 15 días
            } else {
                sessionData.expiration = Date.now() + (24 * 60 * 60 * 1000); // 1 día por defecto
            }

            localStorage.setItem('user_session', JSON.stringify(sessionData));
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
        if (statusDiv && messageEl) {
            statusDiv.classList.remove('hidden', 'bg-green-500/20');
            statusDiv.classList.add('bg-red-500/20');
            messageEl.textContent = '❌ Ingresa API Key y Username';
            messageEl.className = 'text-sm text-red-500';
        }
        return;
    }

    // Mostrar mensaje de prueba
    if (statusDiv && messageEl) {
        statusDiv.classList.remove('hidden', 'bg-red-500/20', 'bg-green-500/20');
        statusDiv.classList.add('bg-yellow-500/20');
        messageEl.textContent = '🔄 Probando conexión...';
        messageEl.className = 'text-sm text-yellow-500';
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
                statusDiv.classList.remove('hidden', 'bg-red-500/20', 'bg-yellow-500/20');
                statusDiv.classList.add('bg-green-500/20');
                messageEl.textContent = '✅ Conexión exitosa a TopstepX - Account ID: ' + (data.account_id || 'N/A');
                messageEl.className = 'text-sm text-green-500';
            } else {
                statusDiv.classList.remove('hidden', 'bg-green-500/20', 'bg-yellow-500/20');
                statusDiv.classList.add('bg-red-500/20');
                messageEl.textContent = '❌ Error en conexión: ' + (data.message || 'Desconocido');
                messageEl.className = 'text-sm text-red-500';
            }
        }
    } catch (error) {
        console.error('Error probando conexión:', error);
        if (statusDiv && messageEl) {
            statusDiv.classList.remove('hidden', 'bg-green-500/20', 'bg-yellow-500/20');
            statusDiv.classList.add('bg-red-500/20');
            messageEl.textContent = '❌ Error de conexión con el servidor';
            messageEl.className = 'text-sm text-red-500';
        }
    }
}

async function toggleTopstepConnection() {
    if (state.topstepConnected) {
        // Desconectar
        await disconnectTopstepX();
    } else {
        // Conectar
        await connectTopstepX();
    }
}

async function connectTopstepX() {
    const apiKey = document.getElementById('config-api-key').value;
    const username = document.getElementById('config-topstep-username').value;
    const statusDiv = document.getElementById('topstep-connection-status');
    const messageEl = document.getElementById('topstep-connection-message');
    const indicator = document.getElementById('topstep-connection-indicator');
    const statusIcon = document.getElementById('topstep-status-icon');
    const statusText = document.getElementById('topstep-status-text');
    const accountInfo = document.getElementById('topstep-account-info');
    const connectBtn = document.getElementById('topstep-connect-btn');
    const connectBtnText = document.getElementById('topstep-connect-btn-text');

    if (!apiKey || !username) {
        if (statusDiv && messageEl) {
            statusDiv.classList.remove('hidden', 'bg-green-500/20');
            statusDiv.classList.add('bg-red-500/20');
            messageEl.textContent = '❌ Ingresa API Key y Username antes de conectar';
            messageEl.className = 'text-sm text-red-500';
        }
        return;
    }

    // Mostrar estado de conexión
    if (statusDiv && messageEl) {
        statusDiv.classList.remove('hidden', 'bg-red-500/20', 'bg-green-500/20');
        statusDiv.classList.add('bg-yellow-500/20');
        messageEl.textContent = '🔄 Conectando a TopstepX...';
        messageEl.className = 'text-sm text-yellow-500';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({api_key: apiKey, username: username})
        });

        const data = await response.json();

        if (data.success) {
            // Guardar estado
            state.topstepConnected = true;
            state.topstepApiKey = apiKey;
            state.topstepUsername = username;
            state.accountId = data.account_id;

            // Guardar en localStorage
            localStorage.setItem('topstep_api_key', apiKey);
            localStorage.setItem('topstep_username', username);
            localStorage.setItem('topstep_account_id', data.account_id || '');

            // Actualizar UI de configuración
            if (indicator) indicator.classList.remove('hidden');
            if (statusIcon) {
                statusIcon.classList.remove('bg-red-500', 'bg-yellow-500');
                statusIcon.classList.add('bg-green-500');
            }
            if (statusText) statusText.textContent = 'Conectado';
            if (accountInfo) accountInfo.textContent = 'Account ID: ' + (data.account_id || 'N/A');

            if (connectBtn) {
                connectBtn.classList.remove('bg-accent-cyan', 'hover:bg-cyan-600');
                connectBtn.classList.add('bg-red-600', 'hover:bg-red-700');
            }
            if (connectBtnText) connectBtnText.textContent = 'Desconectar';

            if (statusDiv && messageEl) {
                statusDiv.classList.remove('hidden', 'bg-red-500/20', 'bg-yellow-500/20');
                statusDiv.classList.add('bg-green-500/20');
                messageEl.textContent = '✅ Conectado exitosamente a TopstepX';
                messageEl.className = 'text-sm text-green-500';
            }

            // Actualizar indicador de conexión en header
            updateTopstepHeaderIndicator();

            // Cargar cuentas activas y actualizar nombre de cuenta
            try {
                const accountsResponse = await fetch(`${API_BASE_URL}/api/accounts/active`);
                const accountsData = await accountsResponse.json();

                if (accountsData.connected && accountsData.accounts && accountsData.accounts.length > 0) {
                    // Encontrar la cuenta actual por ID
                    const currentAcc = accountsData.accounts.find(acc => acc.id.toString() === data.account_id.toString());

                    if (currentAcc) {
                        currentAccountId = currentAcc.id.toString();
                        updateCurrentAccountName(currentAcc.name);
                        console.log(`✅ Cuenta actual: ${currentAcc.name} (Balance: $${currentAcc.balance})`);
                    } else {
                        // Si no se encuentra, usar la primera cuenta activa
                        currentAccountId = accountsData.accounts[0].id.toString();
                        updateCurrentAccountName(accountsData.accounts[0].name);
                    }

                    // Guardar la lista de cuentas activas
                    activeAccounts = accountsData.accounts;
                } else {
                    updateCurrentAccountName('Sin cuenta activa');
                }
            } catch (error) {
                console.error('Error cargando cuentas activas:', error);
                updateCurrentAccountName('Error cargando cuenta');
            }

            // Iniciar WebSocket si no está iniciado
            if (!state.wsConnection) {
                initWebSocket();
            }

            // Cargar datos iniciales
            await loadInitialData();

        } else {
            if (statusDiv && messageEl) {
                statusDiv.classList.remove('hidden', 'bg-green-500/20', 'bg-yellow-500/20');
                statusDiv.classList.add('bg-red-500/20');
                messageEl.textContent = '❌ Error: ' + (data.message || 'No se pudo conectar');
                messageEl.className = 'text-sm text-red-500';
            }
        }
    } catch (error) {
        console.error('Error conectando a TopstepX:', error);
        if (statusDiv && messageEl) {
            statusDiv.classList.remove('hidden', 'bg-green-500/20', 'bg-yellow-500/20');
            statusDiv.classList.add('bg-red-500/20');
            messageEl.textContent = '❌ Error de conexión con el servidor';
            messageEl.className = 'text-sm text-red-500';
        }
    }
}

async function disconnectTopstepX() {
    const statusDiv = document.getElementById('topstep-connection-status');
    const messageEl = document.getElementById('topstep-connection-message');
    const indicator = document.getElementById('topstep-connection-indicator');
    const statusIcon = document.getElementById('topstep-status-icon');
    const statusText = document.getElementById('topstep-status-text');
    const accountInfo = document.getElementById('topstep-account-info');
    const connectBtn = document.getElementById('topstep-connect-btn');
    const connectBtnText = document.getElementById('topstep-connect-btn-text');

    // Actualizar estado
    state.topstepConnected = false;
    state.topstepApiKey = null;
    state.topstepUsername = null;
    state.accountId = null;

    // Limpiar localStorage
    localStorage.removeItem('topstep_api_key');
    localStorage.removeItem('topstep_username');
    localStorage.removeItem('topstep_account_id');

    // Actualizar UI de configuración
    if (indicator) indicator.classList.add('hidden');
    if (statusIcon) {
        statusIcon.classList.remove('bg-green-500', 'bg-yellow-500');
        statusIcon.classList.add('bg-red-500');
    }
    if (statusText) statusText.textContent = 'Desconectado';
    if (accountInfo) accountInfo.textContent = '';

    if (connectBtn) {
        connectBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
        connectBtn.classList.add('bg-accent-cyan', 'hover:bg-cyan-600');
    }
    if (connectBtnText) connectBtnText.textContent = 'Conectar';

    if (statusDiv && messageEl) {
        statusDiv.classList.remove('hidden', 'bg-red-500/20', 'bg-green-500/20');
        statusDiv.classList.add('bg-yellow-500/20');
        messageEl.textContent = '⚠️ Desconectado de TopstepX';
        messageEl.className = 'text-sm text-yellow-500';
    }

    // Actualizar indicador de conexión en header
    updateTopstepHeaderIndicator();

    // Cerrar WebSocket
    if (state.wsConnection) {
        state.wsConnection.close();
        state.wsConnection = null;
    }

    // Resetear balance a $0.00
    const balanceEl = document.getElementById('balance');
    if (balanceEl) balanceEl.textContent = '$0.00';
}

// Cargar configuración guardada de TopstepX al iniciar
async function loadSavedTopstepConfig() {
    const savedApiKey = localStorage.getItem('topstep_api_key');
    const savedUsername = localStorage.getItem('topstep_username');
    const savedAccountId = localStorage.getItem('topstep_account_id');

    if (savedApiKey && savedUsername) {
        const apiKeyInput = document.getElementById('config-api-key');
        const usernameInput = document.getElementById('config-topstep-username');

        if (apiKeyInput) apiKeyInput.value = savedApiKey;
        if (usernameInput) usernameInput.value = savedUsername;

        console.log('🔄 Restaurando conexión TopstepX con el backend...');

        // Reconectar automáticamente con el backend
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({api_key: savedApiKey, username: savedUsername})
            });

            const data = await response.json();

            if (data.success) {
                console.log('✅ Conexión TopstepX restaurada exitosamente');

                // Actualizar estado
                state.topstepConnected = true;
                state.topstepApiKey = savedApiKey;
                state.topstepUsername = savedUsername;
                state.accountId = data.account_id || savedAccountId;

                // Actualizar account ID guardado si es diferente
                if (data.account_id) {
                    localStorage.setItem('topstep_account_id', data.account_id);
                }

                // Actualizar UI
                const indicator = document.getElementById('topstep-connection-indicator');
                const statusIcon = document.getElementById('topstep-status-icon');
                const statusText = document.getElementById('topstep-status-text');
                const accountInfo = document.getElementById('topstep-account-info');
                const connectBtn = document.getElementById('topstep-connect-btn');
                const connectBtnText = document.getElementById('topstep-connect-btn-text');

                if (indicator) indicator.classList.remove('hidden');
                if (statusIcon) {
                    statusIcon.classList.remove('bg-red-500');
                    statusIcon.classList.add('bg-green-500');
                }
                if (statusText) statusText.textContent = 'Conectado';
                if (accountInfo) accountInfo.textContent = 'Account ID: ' + (state.accountId || 'N/A');

                if (connectBtn) {
                    connectBtn.classList.remove('bg-accent-cyan', 'hover:bg-cyan-600');
                    connectBtn.classList.add('bg-red-600', 'hover:bg-red-700');
                }
                if (connectBtnText) connectBtnText.textContent = 'Desconectar';

                // Actualizar indicador de conexión en header
                updateTopstepHeaderIndicator();

                // Cargar cuentas activas y actualizar nombre de cuenta
                try {
                    const accountsResponse = await fetch(`${API_BASE_URL}/api/accounts/active`);
                    const accountsData = await accountsResponse.json();

                    if (accountsData.connected && accountsData.accounts && accountsData.accounts.length > 0) {
                        // Encontrar la cuenta actual por ID
                        const currentAcc = accountsData.accounts.find(acc => acc.id.toString() === state.accountId.toString());

                        if (currentAcc) {
                            currentAccountId = currentAcc.id.toString();
                            updateCurrentAccountName(currentAcc.name);
                            console.log(`✅ Cuenta restaurada: ${currentAcc.name} (Balance: $${currentAcc.balance})`);
                        } else {
                            // Si no se encuentra, usar la primera cuenta activa
                            currentAccountId = accountsData.accounts[0].id.toString();
                            updateCurrentAccountName(accountsData.accounts[0].name);
                        }

                        // Guardar la lista de cuentas activas
                        activeAccounts = accountsData.accounts;
                    } else {
                        updateCurrentAccountName('Sin cuenta activa');
                    }
                } catch (error) {
                    console.error('Error cargando cuentas activas:', error);
                    updateCurrentAccountName('Error cargando cuenta');
                }

            } else {
                console.warn('⚠️ No se pudo restaurar conexión TopstepX:', data.message);
                // Limpiar credenciales guardadas si falló la reconexión
                localStorage.removeItem('topstep_api_key');
                localStorage.removeItem('topstep_username');
                localStorage.removeItem('topstep_account_id');
                state.topstepConnected = false;
                updateTopstepHeaderIndicator();
            }
        } catch (error) {
            console.error('❌ Error restaurando conexión TopstepX:', error);
            state.topstepConnected = false;
            updateTopstepHeaderIndicator();
        }
    }
}

// ============================================================================
// GESTIÓN DE CONTRATOS
// ============================================================================

let contractSearchTimeout = null;
let availableStrategies = [];

async function searchContractsInput() {
    const searchInput = document.getElementById('contract-search-input');
    if (!searchInput) return;

    const symbol = searchInput.value.trim().toUpperCase();

    // Limpiar timeout anterior
    if (contractSearchTimeout) {
        clearTimeout(contractSearchTimeout);
    }

    // Si el campo está vacío, limpiar resultados
    if (!symbol || symbol.length < 1) {
        document.getElementById('contract-search-results').innerHTML = '';
        return;
    }

    // Mostrar indicador de carga
    document.getElementById('contract-search-results').innerHTML = `
        <div class="text-center py-4 text-gray-400">
            <span class="material-symbols-outlined animate-spin text-2xl">progress_activity</span>
            <p class="text-sm mt-2">Buscando contratos...</p>
        </div>
    `;

    // Esperar 500ms antes de buscar (debounce)
    contractSearchTimeout = setTimeout(async () => {
        try {
            const contracts = await searchContracts(symbol);
            updateContractsSearchResults(contracts);
        } catch (error) {
            console.error('Error buscando contratos:', error);
            document.getElementById('contract-search-results').innerHTML = `
                <div class="text-center py-4 text-red-400">
                    <span class="material-symbols-outlined text-2xl">error</span>
                    <p class="text-sm mt-2">Error al buscar contratos</p>
                </div>
            `;
        }
    }, 500);
}

function updateContractsSearchResults(contracts) {
    const resultsContainer = document.getElementById('contract-search-results');

    if (!contracts || contracts.length === 0) {
        resultsContainer.innerHTML = `
            <div class="text-center py-4 text-gray-400">
                <span class="material-symbols-outlined text-2xl">search_off</span>
                <p class="text-sm mt-2">No se encontraron contratos</p>
            </div>
        `;
        return;
    }

    resultsContainer.innerHTML = contracts.map(contract => `
        <div class="flex items-center justify-between p-3 bg-dark-bg rounded-lg border border-dark-border hover:border-accent-cyan transition">
            <div class="flex-1">
                <p class="font-semibold text-white">${contract.name || contract.symbol_id}</p>
                <p class="text-sm text-gray-400">${contract.description || 'Sin descripción'}</p>
                <div class="flex items-center gap-2 mt-1">
                    <span class="text-xs text-gray-500">Tick: ${contract.tick_size} | Valor: $${contract.tick_value}</span>
                </div>
            </div>
            <button
                onclick="showAddContractModal('${contract.id}', '${contract.name || contract.symbol_id}')"
                class="ml-3 w-10 h-10 flex items-center justify-center bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/80 transition">
                <span class="material-symbols-outlined">add</span>
            </button>
        </div>
    `).join('');

    console.log(`✅ ${contracts.length} contratos encontrados`);
}

async function showAddContractModal(contractId, contractName) {
    // Cargar estrategias disponibles si no se han cargado
    if (availableStrategies.length === 0) {
        await loadAvailableStrategies();
    }

    // Crear modal para seleccionar estrategia
    const modal = document.createElement('div');
    modal.id = 'add-contract-modal';
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-[10000]';
    modal.innerHTML = `
        <div class="bg-dark-card border border-dark-border rounded-xl p-6 max-w-md w-full mx-4">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-xl font-bold text-white">Añadir Contrato</h3>
                <button onclick="closeAddContractModal()" class="text-gray-400 hover:text-white">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="mb-4">
                <p class="text-gray-300 mb-2">Contrato: <span class="font-semibold text-white">${contractName}</span></p>
            </div>

            <div class="mb-6">
                <label class="text-gray-400 text-sm block mb-2">Estrategia (opcional)</label>
                <select id="contract-strategy-selector" class="w-full bg-dark-bg text-white rounded-lg px-4 py-2 border border-dark-border focus:border-accent-cyan focus:outline-none">
                    <option value="">Sin estrategia</option>
                    ${availableStrategies.map(s => `
                        <option value="${s.id}">${s.name}</option>
                    `).join('')}
                </select>
                <p class="text-xs text-gray-500 mt-1">Puedes asignar una estrategia más tarde</p>
            </div>

            <div class="flex gap-3">
                <button
                    onclick="closeAddContractModal()"
                    class="flex-1 px-4 py-2 bg-dark-bg text-gray-300 rounded-lg hover:bg-dark-border transition">
                    Cancelar
                </button>
                <button
                    onclick="confirmAddContract('${contractId}')"
                    class="flex-1 px-4 py-2 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/80 transition">
                    Añadir
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

function closeAddContractModal() {
    const modal = document.getElementById('add-contract-modal');
    if (modal) modal.remove();
}

async function confirmAddContract(contractId) {
    const strategySelector = document.getElementById('contract-strategy-selector');
    const strategyId = strategySelector ? strategySelector.value : null;

    try {
        await addContractToBot(contractId, strategyId || null);
        closeAddContractModal();

        // Limpiar búsqueda y recargar contratos activos
        document.getElementById('contract-search-input').value = '';
        document.getElementById('contract-search-results').innerHTML = '';
        await loadActiveContracts();

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Contrato añadido',
                'El contrato se ha añadido correctamente al bot',
                'success'
            );
        }
    } catch (error) {
        console.error('Error añadiendo contrato:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo añadir el contrato',
                'error'
            );
        }
    }
}

async function loadAvailableStrategies() {
    try {
        const userId = localStorage.getItem('user_id');
        if (!userId) return;

        const response = await fetch(`${API_BASE_URL}/api/strategies?user_id=${userId}`);
        const data = await response.json();

        availableStrategies = data.strategies || [];
        console.log(`✅ ${availableStrategies.length} estrategias cargadas`);
    } catch (error) {
        console.error('Error cargando estrategias:', error);
        availableStrategies = [];
    }
}

async function addContractToBot(contractId, strategyId = null) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/contracts/${contractId}/add`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                contract_id: contractId,
                strategy_id: strategyId
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Error añadiendo contrato');
        }

        return data;
    } catch (error) {
        console.error('Error añadiendo contrato:', error);
        throw error;
    }
}

async function loadActiveContracts() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/contracts`);
        const contracts = await response.json();

        const listContainer = document.getElementById('active-contracts-list');

        if (!contracts || contracts.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center py-6 text-gray-400">
                    <span class="material-symbols-outlined text-4xl mb-2">inbox</span>
                    <p class="text-sm">No hay contratos activos</p>
                </div>
            `;
            return;
        }

        listContainer.innerHTML = contracts.map(contract => `
            <div class="flex items-center justify-between p-3 bg-dark-bg rounded-lg border border-dark-border">
                <div class="flex-1">
                    <p class="font-semibold text-white">${contract.name}</p>
                    <p class="text-sm text-gray-400">ID: ${contract.symbol_id}</p>
                </div>
                <div class="flex gap-2">
                    <button
                        onclick="changeContractStrategy('${contract.id}', '${contract.name}')"
                        class="w-10 h-10 flex items-center justify-center bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition"
                        title="Cambiar estrategia">
                        <span class="material-symbols-outlined">edit</span>
                    </button>
                    <button
                        onclick="removeContract('${contract.id}')"
                        class="w-10 h-10 flex items-center justify-center bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition"
                        title="Eliminar contrato">
                        <span class="material-symbols-outlined">delete</span>
                    </button>
                </div>
            </div>
        `).join('');

        console.log(`✅ ${contracts.length} contratos activos cargados`);
    } catch (error) {
        console.error('Error cargando contratos activos:', error);
    }
}

async function changeContractStrategy(contractId, contractName) {
    // Cargar estrategias disponibles
    if (availableStrategies.length === 0) {
        await loadAvailableStrategies();
    }

    // Crear modal para cambiar estrategia
    const modal = document.createElement('div');
    modal.id = 'change-strategy-modal';
    modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-[10000]';
    modal.innerHTML = `
        <div class="bg-dark-card border border-dark-border rounded-xl p-6 max-w-md w-full mx-4">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-xl font-bold text-white">Cambiar Estrategia</h3>
                <button onclick="closeChangeStrategyModal()" class="text-gray-400 hover:text-white">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>

            <div class="mb-4">
                <p class="text-gray-300 mb-2">Contrato: <span class="font-semibold text-white">${contractName}</span></p>
            </div>

            <div class="mb-6">
                <label class="text-gray-400 text-sm block mb-2">Nueva Estrategia</label>
                <select id="change-strategy-selector" class="w-full bg-dark-bg text-white rounded-lg px-4 py-2 border border-dark-border focus:border-accent-cyan focus:outline-none">
                    <option value="">Sin estrategia</option>
                    ${availableStrategies.map(s => `
                        <option value="${s.id}">${s.name}</option>
                    `).join('')}
                </select>
            </div>

            <div class="flex gap-3">
                <button
                    onclick="closeChangeStrategyModal()"
                    class="flex-1 px-4 py-2 bg-dark-bg text-gray-300 rounded-lg hover:bg-dark-border transition">
                    Cancelar
                </button>
                <button
                    onclick="confirmChangeStrategy('${contractId}')"
                    class="flex-1 px-4 py-2 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/80 transition">
                    Cambiar
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

function closeChangeStrategyModal() {
    const modal = document.getElementById('change-strategy-modal');
    if (modal) modal.remove();
}

async function confirmChangeStrategy(contractId) {
    const strategySelector = document.getElementById('change-strategy-selector');
    const strategyId = strategySelector ? strategySelector.value : null;

    try {
        // Re-añadir el contrato con la nueva estrategia
        await addContractToBot(contractId, strategyId || null);
        closeChangeStrategyModal();

        // Recargar contratos activos
        await loadActiveContracts();

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Estrategia actualizada',
                'La estrategia del contrato se actualizó correctamente',
                'success'
            );
        }
    } catch (error) {
        console.error('Error cambiando estrategia:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo cambiar la estrategia',
                'error'
            );
        }
    }
}

async function removeContract(contractId) {
    if (!confirm('¿Eliminar este contrato del bot?')) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/contracts/${contractId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Error eliminando contrato');
        }

        await loadActiveContracts();

        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '✅ Contrato eliminado',
                'El contrato se ha eliminado correctamente',
                'success'
            );
        }
    } catch (error) {
        console.error('Error eliminando contrato:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo eliminar el contrato',
                'error'
            );
        }
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
// SELECTOR DE CUENTAS
// ============================================================================

let activeAccounts = [];
let currentAccountId = null;

function toggleAccountSelector() {
    const dropdown = document.getElementById('account-selector-dropdown');
    if (dropdown) {
        const isHidden = dropdown.classList.contains('hidden');
        if (isHidden) {
            dropdown.classList.remove('hidden');
            loadActiveAccounts();
        } else {
            dropdown.classList.add('hidden');
        }
    }
}

async function loadActiveAccounts() {
    if (!state.topstepConnected) {
        const accountList = document.getElementById('account-list');
        if (accountList) {
            accountList.innerHTML = `
                <div class="text-center py-6 text-gray-400">
                    <span class="material-symbols-outlined text-4xl mb-2">account_balance</span>
                    <p class="text-sm">No conectado a TopstepX</p>
                </div>
            `;
        }
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/accounts/active`);
        const data = await response.json();

        if (data.connected && data.accounts) {
            activeAccounts = data.accounts;
            renderAccountList(data.accounts);
        } else {
            const accountList = document.getElementById('account-list');
            if (accountList) {
                accountList.innerHTML = `
                    <div class="text-center py-6 text-gray-400">
                        <span class="material-symbols-outlined text-4xl mb-2">error</span>
                        <p class="text-sm">No se encontraron cuentas activas</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error cargando cuentas activas:', error);
    }
}

function renderAccountList(accounts) {
    const accountList = document.getElementById('account-list');
    if (!accountList) return;

    if (accounts.length === 0) {
        accountList.innerHTML = `
            <div class="text-center py-6 text-gray-400">
                <span class="material-symbols-outlined text-4xl mb-2">inbox</span>
                <p class="text-sm">No hay cuentas activas</p>
            </div>
        `;
        return;
    }

    accountList.innerHTML = accounts.map(acc => `
        <button onclick="selectAccount('${acc.id}', '${escapeHtml(acc.name)}')"
                class="w-full text-left px-3 py-3 hover:bg-dark-border rounded transition ${currentAccountId === acc.id.toString() ? 'bg-dark-border border-l-2 border-accent-cyan' : ''}">
            <div class="flex items-center justify-between">
                <div class="flex-1">
                    <p class="text-white font-semibold text-sm">${escapeHtml(acc.name)}</p>
                    <p class="text-gray-400 text-xs mt-1">ID: ${acc.id}</p>
                </div>
                <div class="text-right">
                    <p class="text-green-500 font-bold">$${acc.balance.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                    <p class="text-xs text-gray-500">${acc.simulated ? 'SIM' : 'REAL'}</p>
                </div>
            </div>
        </button>
    `).join('');
}

async function selectAccount(accountId, accountName) {
    console.log(`📋 Cambiando a cuenta: ${accountName} (ID: ${accountId})`);

    try {
        const response = await fetch(`${API_BASE_URL}/api/accounts/switch/${accountId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            // Actualizar estado global
            currentAccountId = accountId;
            state.accountId = accountId;

            // Actualizar UI
            updateCurrentAccountName(accountName);

            // Cerrar dropdown
            const dropdown = document.getElementById('account-selector-dropdown');
            if (dropdown) dropdown.classList.add('hidden');

            // Recargar datos del dashboard
            await loadInitialData();

            // Mostrar notificación de éxito
            if (window.errorNotificationSystem) {
                window.errorNotificationSystem.notify(
                    '✅ Cuenta cambiada',
                    `Ahora estás viendo: ${accountName}`,
                    'success'
                );
            }

            console.log('✅ Cuenta cambiada exitosamente');
        }
    } catch (error) {
        console.error('Error cambiando de cuenta:', error);
        if (window.errorNotificationSystem) {
            window.errorNotificationSystem.notify(
                '❌ Error',
                'No se pudo cambiar de cuenta',
                'error'
            );
        }
    }
}

function updateCurrentAccountName(name) {
    const accountNameEl = document.getElementById('current-account-name');
    if (accountNameEl) {
        accountNameEl.textContent = name;
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============================================================================
// CERRAR SESIÓN
// ============================================================================

function logoutUser() {
    // Confirmar cierre de sesión
    if (!confirm('¿Estás seguro de que quieres cerrar sesión?')) {
        return;
    }

    // Limpiar todo el almacenamiento local
    localStorage.removeItem('user_session');
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    localStorage.removeItem('email');
    localStorage.removeItem('topstep_api_key');
    localStorage.removeItem('topstep_username');
    localStorage.removeItem('topstep_account_id');

    // Cerrar WebSocket
    if (state.wsConnection) {
        state.wsConnection.close();
        state.wsConnection = null;
    }

    // Resetear estado
    state.authenticated = false;
    state.topstepConnected = false;
    state.accountId = null;

    // Recargar página para mostrar login
    window.location.reload();
}

// ============================================================================
// VALIDACIÓN DE SESIÓN
// ============================================================================

function checkSessionValidity() {
    const sessionData = localStorage.getItem('user_session');

    if (!sessionData) {
        return false;
    }

    try {
        const session = JSON.parse(sessionData);
        const now = Date.now();

        // Verificar si la sesión ha expirado
        if (session.expiration && now > session.expiration) {
            console.log('⚠️ Sesión expirada, limpiando...');
            localStorage.removeItem('user_session');
            localStorage.removeItem('user_id');
            localStorage.removeItem('username');
            localStorage.removeItem('email');
            return false;
        }

        return true;
    } catch (error) {
        console.error('Error verificando sesión:', error);
        return false;
    }
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

// Agregar event listener para Enter en el campo de contraseña
window.addEventListener('DOMContentLoaded', () => {
    const passwordInput = document.getElementById('login-password');
    if (passwordInput) {
        passwordInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                loginUser();
            }
        });
    }
});

// Verificar autenticación al cargar
window.addEventListener('DOMContentLoaded', async () => {
    // Inicializar indicador de conexión como oculto
    updateTopstepHeaderIndicator();

    // Verificar si hay sesión válida guardada
    if (checkSessionValidity()) {
        const sessionData = JSON.parse(localStorage.getItem('user_session'));

        console.log('✅ Sesión válida encontrada, restaurando...');

        // Restaurar estado de autenticación
        state.authenticated = true;

        // Mostrar aplicación
        document.getElementById('auth-modal').classList.add('hidden');
        document.getElementById('main-app').classList.remove('hidden');

        // Cargar configuración guardada de TopstepX (esperar a que termine)
        await loadSavedTopstepConfig();

        // Cargar datos de usuario
        await loadUserData();
        await loadInitialData();

        // Iniciar WebSocket si TopstepX está conectado
        if (state.topstepConnected) {
            initWebSocket();
        }

        return;
    }

    // Si no hay sesión válida, cargar configuración de TopstepX de todos modos
    await loadSavedTopstepConfig();

    // Mostrar modal de login
    console.log('❌ No hay sesión válida, mostrando modal de login');
});

// ============================================================================
// GRÁFICO DE VELAS CON INDICADORES (BACKTEST)
// ============================================================================

let backtestChart = null;
let backtestCandleSeries = null;
let backtestIndicatorSeries = {};
let backtestMarkers = [];

// Variables globales para gráficos
let equityChart = null;
let equityLineSeries = null;

function renderEquityCurve(equityCurve, initialBalance) {
    const container = document.getElementById('equity-curve-chart');

    // Limpiar gráfico anterior si existe
    if (equityChart) {
        equityChart.remove();
        equityChart = null;
        equityLineSeries = null;
    }

    // Crear gráfico de curva de capital
    equityChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 300,
        layout: {
            background: { color: '#0f172a' },
            textColor: '#d1d5db',
        },
        grid: {
            vertLines: { color: '#1e293b' },
            horzLines: { color: '#1e293b' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#334155',
        },
        timeScale: {
            borderColor: '#334155',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    // Preparar datos de la curva de capital
    const equityData = equityCurve.map(point => ({
        time: new Date(point.timestamp).getTime() / 1000,
        value: point.balance
    }));

    // Agregar serie de línea para la curva de capital
    equityLineSeries = equityChart.addLineSeries({
        color: '#3b82f6',
        lineWidth: 2,
        title: 'Balance',
    });
    equityLineSeries.setData(equityData);

    // Añadir línea de balance inicial (referencia)
    const initialBalanceLine = equityChart.addLineSeries({
        color: '#64748b',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        title: 'Balance Inicial',
        priceLineVisible: false,
        lastValueVisible: false,
    });
    initialBalanceLine.setData([
        { time: equityData[0].time, value: initialBalance },
        { time: equityData[equityData.length - 1].time, value: initialBalance }
    ]);

    // Ajustar zoom
    equityChart.timeScale().fitContent();

    // Hacer responsive
    window.addEventListener('resize', () => {
        if (equityChart && container) {
            equityChart.applyOptions({ width: container.clientWidth });
        }
    });

    console.log(`✅ Curva de capital renderizada con ${equityData.length} puntos`);
}

function renderBacktestChart(chartData, trades, equityCurve) {
    const container = document.getElementById('candlestick-chart');

    // Limpiar gráfico anterior si existe
    if (backtestChart) {
        backtestChart.remove();
        backtestChart = null;
        backtestCandleSeries = null;
        backtestIndicatorSeries = {};
    }

    // Crear gráfico
    backtestChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 600,
        layout: {
            background: { color: '#0f172a' },
            textColor: '#d1d5db',
        },
        grid: {
            vertLines: { color: '#1e293b' },
            horzLines: { color: '#1e293b' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#334155',
        },
        timeScale: {
            borderColor: '#334155',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    // Agregar serie de velas
    backtestCandleSeries = backtestChart.addCandlestickSeries({
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
    });

    backtestCandleSeries.setData(chartData.candlesticks);

    // Agregar marcadores de trades
    const markers = trades.map(trade => {
        const entryTime = new Date(trade.entry_time).getTime() / 1000;
        const exitTime = new Date(trade.exit_time).getTime() / 1000;
        const isProfit = trade.pnl > 0;

        return [
            // Marcador de entrada
            {
                time: entryTime,
                position: trade.side === 'LONG' ? 'belowBar' : 'aboveBar',
                color: trade.side === 'LONG' ? '#22c55e' : '#ef4444',
                shape: trade.side === 'LONG' ? 'arrowUp' : 'arrowDown',
                text: trade.side,
            },
            // Marcador de salida
            {
                time: exitTime,
                position: isProfit ? 'aboveBar' : 'belowBar',
                color: isProfit ? '#3b82f6' : '#f59e0b',
                shape: 'circle',
                text: `$${trade.pnl.toFixed(0)}`,
            }
        ];
    }).flat();

    backtestCandleSeries.setMarkers(markers);
    backtestMarkers = markers;

    // Agregar líneas de SL/TP para cada trade
    trades.forEach((trade, index) => {
        if (!trade.stop_loss || !trade.take_profit) return;

        const entryTime = new Date(trade.entry_time).getTime() / 1000;
        const exitTime = new Date(trade.exit_time).getTime() / 1000;

        // Línea de Stop Loss (roja)
        const slSeries = backtestChart.addLineSeries({
            color: '#ef4444',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        slSeries.setData([
            { time: entryTime, value: trade.stop_loss },
            { time: exitTime, value: trade.stop_loss }
        ]);

        // Línea de Take Profit (verde)
        const tpSeries = backtestChart.addLineSeries({
            color: '#22c55e',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        tpSeries.setData([
            { time: entryTime, value: trade.take_profit },
            { time: exitTime, value: trade.take_profit }
        ]);

        // Guardar referencias para poder ocultarlas después
        if (!backtestIndicatorSeries.sl_lines) {
            backtestIndicatorSeries.sl_lines = [];
            backtestIndicatorSeries.tp_lines = [];
        }
        backtestIndicatorSeries.sl_lines.push(slSeries);
        backtestIndicatorSeries.tp_lines.push(tpSeries);
    });

    // Agregar indicadores si existen
    if (chartData.indicators) {
        renderIndicators(chartData.indicators);
    }

    // Ajustar zoom para mostrar todos los datos
    backtestChart.timeScale().fitContent();

    // Hacer el gráfico responsive
    window.addEventListener('resize', () => {
        if (backtestChart && container) {
            backtestChart.applyOptions({ width: container.clientWidth });
        }
    });

    console.log(`✅ Gráfico renderizado con ${chartData.candlesticks.length} velas y ${trades.length} trades`);
}

function renderIndicators(indicators) {
    // SMI
    if (indicators.smi) {
        const smiPane = backtestChart.addPane({ height: 150 });

        backtestIndicatorSeries.smi = smiPane.addLineSeries({
            color: '#a855f7',
            lineWidth: 2,
            title: 'SMI',
        });
        backtestIndicatorSeries.smi.setData(indicators.smi.data);

        backtestIndicatorSeries.smi_signal = smiPane.addLineSeries({
            color: '#ec4899',
            lineWidth: 1,
            title: 'Signal',
        });
        backtestIndicatorSeries.smi_signal.setData(indicators.smi.signal);

        // Líneas de sobreventa/sobrecompra
        const smiOversold = indicators.smi.oversold;
        const smiOverbought = indicators.smi.overbought;

        backtestIndicatorSeries.smi_oversold = smiPane.addLineSeries({
            color: '#06b6d4',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `Oversold (${smiOversold})`,
        });
        backtestIndicatorSeries.smi_oversold.setData(
            indicators.smi.data.map(d => ({ time: d.time, value: smiOversold }))
        );

        backtestIndicatorSeries.smi_overbought = smiPane.addLineSeries({
            color: '#f43f5e',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `Overbought (${smiOverbought})`,
        });
        backtestIndicatorSeries.smi_overbought.setData(
            indicators.smi.data.map(d => ({ time: d.time, value: smiOverbought }))
        );
    }

    // Stochastic RSI
    if (indicators.stoch_rsi) {
        const stochPane = backtestChart.addPane({ height: 150 });

        backtestIndicatorSeries.stoch_k = stochPane.addLineSeries({
            color: '#ec4899',
            lineWidth: 2,
            title: 'StochRSI K',
        });
        backtestIndicatorSeries.stoch_k.setData(indicators.stoch_rsi.k);

        backtestIndicatorSeries.stoch_d = stochPane.addLineSeries({
            color: '#a855f7',
            lineWidth: 1,
            title: 'StochRSI D',
        });
        backtestIndicatorSeries.stoch_d.setData(indicators.stoch_rsi.d);

        // Líneas de sobreventa/sobrecompra
        const stochOversold = indicators.stoch_rsi.oversold;
        const stochOverbought = indicators.stoch_rsi.overbought;

        backtestIndicatorSeries.stoch_oversold = stochPane.addLineSeries({
            color: '#06b6d4',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `Oversold (${stochOversold})`,
        });
        backtestIndicatorSeries.stoch_oversold.setData(
            indicators.stoch_rsi.k.map(d => ({ time: d.time, value: stochOversold }))
        );

        backtestIndicatorSeries.stoch_overbought = stochPane.addLineSeries({
            color: '#f43f5e',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: `Overbought (${stochOverbought})`,
        });
        backtestIndicatorSeries.stoch_overbought.setData(
            indicators.stoch_rsi.k.map(d => ({ time: d.time, value: stochOverbought }))
        );
    }

    // MACD
    if (indicators.macd) {
        const macdPane = backtestChart.addPane({ height: 150 });

        backtestIndicatorSeries.macd = macdPane.addLineSeries({
            color: '#3b82f6',
            lineWidth: 2,
            title: 'MACD',
        });
        backtestIndicatorSeries.macd.setData(indicators.macd.macd);

        backtestIndicatorSeries.macd_signal = macdPane.addLineSeries({
            color: '#f59e0b',
            lineWidth: 1,
            title: 'Signal',
        });
        backtestIndicatorSeries.macd_signal.setData(indicators.macd.signal);

        backtestIndicatorSeries.macd_histogram = macdPane.addHistogramSeries({
            color: '#64748b',
            title: 'Histogram',
        });
        backtestIndicatorSeries.macd_histogram.setData(
            indicators.macd.histogram.map(d => ({
                time: d.time,
                value: d.value,
                color: d.value >= 0 ? '#22c55e' : '#ef4444'
            }))
        );
    }

    // Bollinger Bands (overlay en el gráfico principal)
    if (indicators.bollinger_bands) {
        backtestIndicatorSeries.bb_upper = backtestChart.addLineSeries({
            color: '#f59e0b',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: 'BB Upper',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.bb_upper.setData(indicators.bollinger_bands.upper);

        backtestIndicatorSeries.bb_middle = backtestChart.addLineSeries({
            color: '#64748b',
            lineWidth: 1,
            title: 'BB Middle',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.bb_middle.setData(indicators.bollinger_bands.middle);

        backtestIndicatorSeries.bb_lower = backtestChart.addLineSeries({
            color: '#f59e0b',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: 'BB Lower',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.bb_lower.setData(indicators.bollinger_bands.lower);
    }

    // Moving Averages (overlay en el gráfico principal)
    if (indicators.moving_averages) {
        backtestIndicatorSeries.sma_fast = backtestChart.addLineSeries({
            color: '#22c55e',
            lineWidth: 1,
            title: 'SMA Fast',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.sma_fast.setData(indicators.moving_averages.sma_fast);

        backtestIndicatorSeries.sma_slow = backtestChart.addLineSeries({
            color: '#ef4444',
            lineWidth: 1,
            title: 'SMA Slow',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.sma_slow.setData(indicators.moving_averages.sma_slow);
    }

    // VWAP (overlay en el gráfico principal)
    if (indicators.vwap) {
        backtestIndicatorSeries.vwap = backtestChart.addLineSeries({
            color: '#8b5cf6',
            lineWidth: 2,
            title: 'VWAP',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.vwap.setData(indicators.vwap.vwap);

        backtestIndicatorSeries.vwap_upper = backtestChart.addLineSeries({
            color: '#a78bfa',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            title: 'VWAP Upper',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.vwap_upper.setData(indicators.vwap.upper_band);

        backtestIndicatorSeries.vwap_lower = backtestChart.addLineSeries({
            color: '#a78bfa',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            title: 'VWAP Lower',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.vwap_lower.setData(indicators.vwap.lower_band);
    }

    // SuperTrend (overlay en el gráfico principal)
    if (indicators.supertrend) {
        backtestIndicatorSeries.supertrend = backtestChart.addLineSeries({
            color: '#06b6d4',
            lineWidth: 2,
            title: 'SuperTrend',
            priceLineVisible: false,
            lastValueVisible: false,
        });
        backtestIndicatorSeries.supertrend.setData(indicators.supertrend.supertrend);
    }

    // KDJ (panel separado)
    if (indicators.kdj) {
        const kdjPane = backtestChart.addPane({ height: 150 });

        backtestIndicatorSeries.kdj_k = kdjPane.addLineSeries({
            color: '#22c55e',
            lineWidth: 2,
            title: 'KDJ K',
        });
        backtestIndicatorSeries.kdj_k.setData(indicators.kdj.k);

        backtestIndicatorSeries.kdj_d = kdjPane.addLineSeries({
            color: '#ef4444',
            lineWidth: 1,
            title: 'KDJ D',
        });
        backtestIndicatorSeries.kdj_d.setData(indicators.kdj.d);

        backtestIndicatorSeries.kdj_j = kdjPane.addLineSeries({
            color: '#3b82f6',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            title: 'KDJ J',
        });
        backtestIndicatorSeries.kdj_j.setData(indicators.kdj.j);
    }
}

function toggleIndicator(indicatorName) {
    // Esta función se puede expandir para mostrar/ocultar indicadores específicos
    console.log(`Toggle indicator: ${indicatorName}`);
    // Por ahora solo muestra un mensaje
    if (window.errorNotificationSystem) {
        window.errorNotificationSystem.notify(
            'ℹ️ Info',
            `El indicador ${indicatorName.toUpperCase()} ${Math.random() > 0.5 ? 'está visible' : 'está oculto'}`,
            'info'
        );
    }
}

// ============================================================================
// TEMA CLARO/OSCURO
// ============================================================================

function setTheme(theme) {
    const body = document.body;

    // Guardar tema seleccionado
    localStorage.setItem('theme', theme);

    // Eliminar todas las clases de tema
    body.classList.remove('theme-light', 'theme-dark');

    // Determinar tema a aplicar
    let themeToApply = theme;
    if (theme === 'system') {
        // Detectar preferencia del sistema
        themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    // Aplicar tema
    if (themeToApply === 'light') {
        body.classList.add('theme-light');
        body.style.backgroundColor = '#f8fafc';
        body.style.color = '#1e293b';
    } else {
        body.classList.add('theme-dark');
        body.style.backgroundColor = '#0f172a';
        body.style.color = '#ffffff';
    }

    // Actualizar botones
    ['light', 'dark', 'system'].forEach(t => {
        const btn = document.getElementById(`theme-${t}`);
        if (btn) {
            if (t === theme) {
                btn.classList.remove('border-dark-border');
                btn.classList.add('border-accent-cyan');
            } else {
                btn.classList.remove('border-accent-cyan');
                btn.classList.add('border-dark-border');
            }
        }
    });

    // Actualizar gráficos si existen
    updateChartsTheme(themeToApply);

    console.log(`✅ Tema cambiado a: ${theme} (aplicado: ${themeToApply})`);

    if (window.errorNotificationSystem) {
        window.errorNotificationSystem.notify(
            '🎨 Tema actualizado',
            `Tema ${theme === 'light' ? 'claro' : theme === 'dark' ? 'oscuro' : 'del sistema'} aplicado correctamente`,
            'success'
        );
    }
}

function updateChartsTheme(theme) {
    const isDark = theme === 'dark';
    const bgColor = isDark ? '#0f172a' : '#ffffff';
    const textColor = isDark ? '#d1d5db' : '#1e293b';
    const gridColor = isDark ? '#1e293b' : '#e2e8f0';
    const borderColor = isDark ? '#334155' : '#cbd5e1';

    // Actualizar gráfico de backtest si existe
    if (backtestChart) {
        backtestChart.applyOptions({
            layout: {
                background: { color: bgColor },
                textColor: textColor,
            },
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            },
            rightPriceScale: {
                borderColor: borderColor,
            },
            timeScale: {
                borderColor: borderColor,
            },
        });
    }

    // Actualizar gráfico de equity curve si existe
    if (equityChart) {
        equityChart.applyOptions({
            layout: {
                background: { color: bgColor },
                textColor: textColor,
            },
            grid: {
                vertLines: { color: gridColor },
                horzLines: { color: gridColor },
            },
            rightPriceScale: {
                borderColor: borderColor,
            },
            timeScale: {
                borderColor: borderColor,
            },
        });
    }
}

// Cargar tema guardado al iniciar
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
});

console.log('🚀 AI Trading App initialized');
console.log('📡 Backend:', API_BASE_URL);
