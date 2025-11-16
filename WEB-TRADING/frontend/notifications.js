/**
 * Sistema de Notificaciones de Errores
 * Captura y muestra todos los errores del sistema en tiempo real
 */

class ErrorNotificationSystem {
    constructor() {
        this.notifications = [];
        this.notificationHistory = [];
        this.maxNotifications = 5;
        this.maxHistorySize = 50;
        this.init();
    }

    init() {
        // Crear contenedor de notificaciones
        this.createNotificationContainer();

        // Interceptar errores globales de JavaScript
        window.addEventListener('error', (event) => {
            this.handleJSError(event);
        });

        // Interceptar promesas rechazadas
        window.addEventListener('unhandledrejection', (event) => {
            this.handlePromiseRejection(event);
        });

        // Interceptar errores de fetch
        this.interceptFetch();

        // Interceptar errores de WebSocket
        this.interceptWebSocket();

        console.log('✅ Sistema de Notificaciones de Errores iniciado');
    }

    createNotificationContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
            width: 100%;
        `;
        document.body.appendChild(container);
    }

    showNotification(title, message, type = 'error', details = null) {
        const notification = {
            id: Date.now(),
            title,
            message,
            type,
            details,
            timestamp: new Date()
        };

        this.notifications.unshift(notification);

        // Guardar en historial
        this.notificationHistory.unshift(notification);
        if (this.notificationHistory.length > this.maxHistorySize) {
            this.notificationHistory.pop();
        }

        // Actualizar badge de la campanita
        this.updateNotificationBadge();

        // Limitar número de notificaciones visibles
        if (this.notifications.length > this.maxNotifications) {
            this.notifications.pop();
        }

        this.renderNotification(notification);
        this.logError(notification);

        // Auto-ocultar después de 5 segundos (excepto errores críticos)
        if (type !== 'critical') {
            setTimeout(() => this.hideNotification(notification.id), 5000);
        }
    }

    renderNotification(notification) {
        const container = document.getElementById('notification-container');

        const colors = {
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            critical: 'bg-red-700',
            info: 'bg-blue-500',
            success: 'bg-green-500'
        };

        const icons = {
            error: 'error',
            warning: 'warning',
            critical: 'dangerous',
            info: 'info',
            success: 'check_circle'
        };

        const notificationEl = document.createElement('div');
        notificationEl.id = `notification-${notification.id}`;
        notificationEl.className = `${colors[notification.type]} text-white rounded-lg shadow-2xl mb-3 overflow-hidden animate-slide-in`;
        notificationEl.style.animation = 'slideIn 0.3s ease-out';

        notificationEl.innerHTML = `
            <div class="p-4">
                <div class="flex items-start">
                    <span class="material-symbols-outlined text-2xl mr-3">${icons[notification.type]}</span>
                    <div class="flex-1">
                        <div class="flex items-start justify-between">
                            <h4 class="font-bold text-sm">${notification.title}</h4>
                            <button onclick="errorNotificationSystem.hideNotification(${notification.id})" class="ml-2 hover:bg-white/20 rounded p-1">
                                <span class="material-symbols-outlined text-sm">close</span>
                            </button>
                        </div>
                        <p class="text-sm mt-1 opacity-90">${notification.message}</p>
                        ${notification.details ? `
                            <details class="mt-2">
                                <summary class="cursor-pointer text-xs opacity-75 hover:opacity-100">Ver detalles técnicos</summary>
                                <pre class="text-xs mt-2 bg-black/20 p-2 rounded overflow-x-auto max-h-40">${JSON.stringify(notification.details, null, 2)}</pre>
                            </details>
                        ` : ''}
                        <div class="text-xs mt-2 opacity-75">
                            ${this.formatTime(notification.timestamp)}
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.insertBefore(notificationEl, container.firstChild);
    }

    hideNotification(id) {
        const el = document.getElementById(`notification-${id}`);
        if (el) {
            el.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => el.remove(), 300);
        }
        this.notifications = this.notifications.filter(n => n.id !== id);
    }

    handleJSError(event) {
        this.showNotification(
            '❌ Error de JavaScript',
            event.message,
            'error',
            {
                file: event.filename,
                line: event.lineno,
                column: event.colno,
                stack: event.error?.stack
            }
        );

        // Prevenir que el error se propague a la consola (opcional)
        // event.preventDefault();
    }

    handlePromiseRejection(event) {
        this.showNotification(
            '⚠️ Promise Rechazada',
            event.reason?.message || event.reason || 'Error no especificado',
            'warning',
            {
                reason: event.reason,
                promise: event.promise
            }
        );
    }

    interceptFetch() {
        const originalFetch = window.fetch;

        window.fetch = async (...args) => {
            try {
                const response = await originalFetch(...args);

                // Interceptar errores HTTP
                if (!response.ok) {
                    const errorData = await response.clone().json().catch(() => ({}));

                    this.showNotification(
                        `❌ Error HTTP ${response.status}`,
                        errorData.detail || errorData.message || response.statusText,
                        response.status >= 500 ? 'critical' : 'error',
                        {
                            url: args[0],
                            status: response.status,
                            statusText: response.statusText,
                            error: errorData
                        }
                    );
                }

                return response;
            } catch (error) {
                this.showNotification(
                    '❌ Error de Red',
                    error.message || 'No se pudo conectar al servidor',
                    'critical',
                    {
                        url: args[0],
                        error: error.toString()
                    }
                );
                throw error;
            }
        };
    }

    interceptWebSocket() {
        const OriginalWebSocket = window.WebSocket;

        window.WebSocket = function(...args) {
            const ws = new OriginalWebSocket(...args);

            ws.addEventListener('error', (event) => {
                errorNotificationSystem.showNotification(
                    '❌ Error de WebSocket',
                    'Conexión WebSocket falló',
                    'error',
                    {
                        url: args[0],
                        readyState: ws.readyState
                    }
                );
            });

            ws.addEventListener('close', (event) => {
                if (!event.wasClean) {
                    errorNotificationSystem.showNotification(
                        '⚠️ WebSocket Cerrado',
                        `Conexión cerrada inesperadamente (código: ${event.code})`,
                        'warning',
                        {
                            code: event.code,
                            reason: event.reason,
                            wasClean: event.wasClean
                        }
                    );
                }
            });

            return ws;
        };
    }

    logError(notification) {
        // Enviar error al backend para registro
        const logData = {
            type: 'frontend_error',
            level: notification.type,
            title: notification.title,
            message: notification.message,
            details: notification.details,
            timestamp: notification.timestamp.toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href
        };

        // No usar fetch directo para evitar recursión
        navigator.sendBeacon('/api/logs/error', JSON.stringify(logData));

        // También loguear en consola
        console.error('[Error System]', notification);
    }

    formatTime(date) {
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return 'Hace menos de 1 minuto';
        if (diff < 3600000) return `Hace ${Math.floor(diff / 60000)} minutos`;
        return date.toLocaleTimeString('es-ES');
    }

    // Método público para mostrar notificaciones personalizadas
    notify(title, message, type = 'info') {
        this.showNotification(title, message, type);
    }

    // Limpiar todas las notificaciones
    clearAll() {
        const container = document.getElementById('notification-container');
        if (container) {
            container.innerHTML = '';
        }
        this.notifications = [];
    }

    // Actualizar badge de notificaciones
    updateNotificationBadge() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            const unreadCount = this.notificationHistory.length;
            if (unreadCount > 0) {
                badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    }

    // Toggle panel de notificaciones
    toggleNotificationPanel() {
        const panel = document.getElementById('notification-panel');
        if (!panel) {
            // Si no existe, crearlo y mostrarlo
            this.showNotificationPanel();
        } else {
            // Si existe, alternar visibilidad
            const isHidden = panel.classList.contains('hidden');
            if (isHidden) {
                this.showNotificationPanel();
            } else {
                this.hideNotificationPanel();
            }
        }
    }

    // Mostrar panel de notificaciones
    showNotificationPanel() {
        const panel = document.getElementById('notification-panel');
        if (!panel) {
            this.createNotificationPanel();
        }

        const panelEl = document.getElementById('notification-panel');
        panelEl.classList.remove('hidden');
        this.renderNotificationHistory();
    }

    // Ocultar panel de notificaciones
    hideNotificationPanel() {
        const panel = document.getElementById('notification-panel');
        if (panel) {
            panel.classList.add('hidden');
        }
    }

    // Crear panel de notificaciones
    createNotificationPanel() {
        const panel = document.createElement('div');
        panel.id = 'notification-panel';
        panel.className = 'fixed top-16 right-4 w-96 max-h-[600px] bg-dark-card border border-dark-border rounded-xl shadow-2xl z-[9998] hidden overflow-hidden';
        panel.innerHTML = `
            <div class="flex items-center justify-between p-4 border-b border-dark-border bg-dark-bg">
                <h3 class="text-lg font-bold text-white">Notificaciones</h3>
                <div class="flex items-center gap-2">
                    <button onclick="errorNotificationSystem.clearHistory()" class="text-sm text-gray-400 hover:text-white">
                        Limpiar
                    </button>
                    <button onclick="errorNotificationSystem.hideNotificationPanel()" class="text-gray-400 hover:text-white">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </div>
            </div>
            <div id="notification-history-list" class="overflow-y-auto max-h-[540px] p-2">
                <!-- Historial de notificaciones -->
            </div>
        `;
        document.body.appendChild(panel);
    }

    // Renderizar historial de notificaciones
    renderNotificationHistory() {
        const listEl = document.getElementById('notification-history-list');
        if (!listEl) return;

        if (this.notificationHistory.length === 0) {
            listEl.innerHTML = `
                <div class="text-center py-12 text-gray-400">
                    <span class="material-symbols-outlined text-5xl mb-2">notifications_off</span>
                    <p>No hay notificaciones</p>
                </div>
            `;
            return;
        }

        const colors = {
            error: 'bg-red-500/20 border-red-500',
            warning: 'bg-yellow-500/20 border-yellow-500',
            critical: 'bg-red-700/20 border-red-700',
            info: 'bg-blue-500/20 border-blue-500',
            success: 'bg-green-500/20 border-green-500'
        };

        const icons = {
            error: 'error',
            warning: 'warning',
            critical: 'dangerous',
            info: 'info',
            success: 'check_circle'
        };

        listEl.innerHTML = this.notificationHistory.map(n => `
            <div class="${colors[n.type]} border-l-4 rounded-lg p-3 mb-2">
                <div class="flex items-start gap-2">
                    <span class="material-symbols-outlined text-lg">${icons[n.type]}</span>
                    <div class="flex-1">
                        <h4 class="font-semibold text-sm text-white">${n.title}</h4>
                        <p class="text-xs text-gray-300 mt-1">${n.message}</p>
                        <p class="text-xs text-gray-500 mt-1">${this.formatTime(n.timestamp)}</p>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // Limpiar historial
    clearHistory() {
        this.notificationHistory = [];
        this.updateNotificationBadge();
        this.renderNotificationHistory();
    }
}

// Estilos para animaciones
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }

    .animate-slide-in {
        animation: slideIn 0.3s ease-out;
    }
`;
document.head.appendChild(style);

// Inicializar sistema globalmente
const errorNotificationSystem = new ErrorNotificationSystem();

// Exportar para uso en otros scripts
window.errorNotificationSystem = errorNotificationSystem;
