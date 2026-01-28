// D3 modules for MCP Apps visualizations
// Selective imports to minimize bundle size

// DOM manipulation
export { select, selectAll, create } from 'd3-selection';

// Force-directed layout (graph viewer)
export {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceX,
  forceY
} from 'd3-force';

// Scales and color schemes
export {
  scaleLinear,
  scaleOrdinal,
  scaleBand,
  scaleTime
} from 'd3-scale';
export { schemeCategory10, schemeTableau10 } from 'd3-scale-chromatic';

// Zoom/pan interaction
export { zoom, zoomIdentity, zoomTransform } from 'd3-zoom';

// Hierarchy (treemap for communities)
export {
  hierarchy,
  treemap,
  treemapBinary,
  treemapSquarify
} from 'd3-hierarchy';

// Shapes (arcs for pie charts, paths)
export { arc, pie, line, area } from 'd3-shape';

// Transitions and animation
export { transition } from 'd3-transition';
export { interpolate, interpolateRgb } from 'd3-interpolate';
export { easeCubicOut, easeElasticOut, easeQuadOut } from 'd3-ease';

// ============================================================================
// SecureMessenger - Secure postMessage handler for MCP Apps
// ============================================================================
// Inlined here for single-bundle convenience (no Node.js module resolution)

/**
 * SecureMessenger - Secure postMessage handler for MCP Apps
 *
 * Validates message origins and enforces JSON-RPC 2.0 format.
 * Used by all Daem0n MCP Apps UIs for host communication.
 */
class SecureMessenger {
    /**
     * Create a SecureMessenger instance.
     * @param {string[]} allowedOrigins - Additional origins to trust (beyond defaults)
     */
    constructor(allowedOrigins = []) {
        this.allowedOrigins = new Set([
            'https://claude.ai',
            'https://desktop.claude.ai',
            'null',
            ...allowedOrigins
        ]);
        this.handlers = new Map();
        this.pendingRequests = new Map();
        this.nextId = 1;
        this.initialized = false;
    }

    init() {
        if (this.initialized) {
            console.warn('[SecureMessenger] Already initialized');
            return;
        }
        window.addEventListener('message', (event) => this._handleMessage(event));
        this.initialized = true;
    }

    _handleMessage(event) {
        if (!this.allowedOrigins.has(event.origin)) {
            console.warn(`[SecureMessenger] Blocked message from untrusted origin: ${event.origin}`);
            return;
        }
        const message = event.data;
        if (!message || typeof message !== 'object' || message.jsonrpc !== '2.0') return;

        if (message.id !== undefined && (message.result !== undefined || message.error !== undefined)) {
            this._handleResponse(message);
            return;
        }
        if (message.method) {
            this._handleRequest(message, event.source);
        }
    }

    _handleResponse(message) {
        const pending = this.pendingRequests.get(message.id);
        if (!pending) return;
        this.pendingRequests.delete(message.id);
        if (message.error) {
            const error = new Error(message.error.message || 'Unknown error');
            error.code = message.error.code;
            pending.reject(error);
        } else {
            pending.resolve(message.result);
        }
    }

    _handleRequest(message, source) {
        const handler = this.handlers.get(message.method);
        if (!handler) {
            if (message.id !== undefined) {
                this._sendResponse(source, message.id, null, {
                    code: -32601,
                    message: `Method not found: ${message.method}`
                });
            }
            return;
        }
        try {
            const result = handler(message.params || {});
            if (result && typeof result.then === 'function') {
                result.then(
                    (res) => message.id !== undefined && this._sendResponse(source, message.id, res),
                    (err) => message.id !== undefined && this._sendResponse(source, message.id, null, {
                        code: -32603, message: err.message
                    })
                );
            } else if (message.id !== undefined) {
                this._sendResponse(source, message.id, result);
            }
        } catch (err) {
            if (message.id !== undefined) {
                this._sendResponse(source, message.id, null, { code: -32603, message: err.message });
            }
        }
    }

    _sendResponse(target, id, result, error = null) {
        if (id === undefined) return;
        const response = { jsonrpc: '2.0', id };
        if (error) response.error = error;
        else response.result = result;
        target.postMessage(response, '*');
    }

    on(method, handler) { this.handlers.set(method, handler); }
    off(method) { this.handlers.delete(method); }

    request(method, params = {}, timeout = 30000) {
        return new Promise((resolve, reject) => {
            const id = this.nextId++;
            const timeoutId = setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error(`Request timeout: ${method}`));
                }
            }, timeout);
            this.pendingRequests.set(id, {
                resolve: (v) => { clearTimeout(timeoutId); resolve(v); },
                reject: (e) => { clearTimeout(timeoutId); reject(e); }
            });
            window.parent.postMessage({ jsonrpc: '2.0', id, method, params }, '*');
        });
    }

    notify(method, params = {}) {
        window.parent.postMessage({ jsonrpc: '2.0', method, params }, '*');
    }

    addOrigin(origin) { this.allowedOrigins.add(origin); }
    isOriginAllowed(origin) { return this.allowedOrigins.has(origin); }
    getMethods() { return Array.from(this.handlers.keys()); }
    destroy() {
        for (const pending of this.pendingRequests.values()) {
            pending.reject(new Error('Messenger destroyed'));
        }
        this.pendingRequests.clear();
        this.handlers.clear();
        this.initialized = false;
    }
}

export { SecureMessenger };

// Auto-initialize SecureMessenger as global instance for template compatibility
if (typeof window !== 'undefined') {
    window.SecureMessenger = new SecureMessenger();
    window.SecureMessenger.init();
}
