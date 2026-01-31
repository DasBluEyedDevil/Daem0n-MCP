/**
 * SecureMessenger - Secure postMessage handler for MCP Apps
 *
 * Validates message origins and enforces JSON-RPC 2.0 format.
 * Used by all Daem0n MCP Apps UIs for host communication.
 *
 * Security features:
 * - Origin validation using Set.has() for O(1) lookup
 * - Exact origin matching (not startsWith or includes)
 * - JSON-RPC 2.0 message structure validation
 * - Request/response tracking with message IDs
 *
 * @example
 * const messenger = new SecureMessenger();
 * messenger.init();
 *
 * // Register a handler
 * messenger.on('updateData', (params) => {
 *   console.log('Received:', params);
 *   return { status: 'ok' };
 * });
 *
 * // Send a request to host
 * const result = await messenger.request('getData', { id: 123 });
 *
 * // Send a notification (no response expected)
 * messenger.notify('logEvent', { event: 'click' });
 */
class SecureMessenger {
    /**
     * Create a SecureMessenger instance.
     * @param {string[]} allowedOrigins - Additional origins to trust (beyond defaults)
     */
    constructor(allowedOrigins = []) {
        // Default allowed origins for MCP Apps hosts
        this.allowedOrigins = new Set([
            'https://claude.ai',
            'https://desktop.claude.ai',
            'null',  // Sandboxed iframe origin
            ...allowedOrigins
        ]);

        this.handlers = new Map();
        this.pendingRequests = new Map();
        this.nextId = 1;
        this.initialized = false;
    }

    /**
     * Initialize the message listener.
     * Call once when the UI is ready.
     */
    init() {
        if (this.initialized) {
            console.warn('[SecureMessenger] Already initialized');
            return;
        }

        window.addEventListener('message', (event) => {
            this._handleMessage(event);
        });

        this.initialized = true;
    }

    /**
     * Internal message handler with security checks.
     * @private
     */
    _handleMessage(event) {
        // SECURITY: Validate origin first - exact match only
        if (!this.allowedOrigins.has(event.origin)) {
            console.warn(`[SecureMessenger] Blocked message from untrusted origin: ${event.origin}`);
            return;
        }

        const message = event.data;

        // Validate message structure
        if (!message || typeof message !== 'object') {
            return;
        }

        // Must be JSON-RPC 2.0
        if (message.jsonrpc !== '2.0') {
            return;
        }

        // Handle response to our request
        if (message.id !== undefined && (message.result !== undefined || message.error !== undefined)) {
            this._handleResponse(message);
            return;
        }

        // Handle incoming request/notification
        if (message.method) {
            this._handleRequest(message, event.source, event.origin);
        }
    }

    /**
     * Handle response to a request we sent.
     * @private
     */
    _handleResponse(message) {
        const pending = this.pendingRequests.get(message.id);
        if (!pending) {
            console.warn(`[SecureMessenger] No pending request for id: ${message.id}`);
            return;
        }

        this.pendingRequests.delete(message.id);

        if (message.error) {
            const error = new Error(message.error.message || 'Unknown error');
            error.code = message.error.code;
            pending.reject(error);
        } else {
            pending.resolve(message.result);
        }
    }

    /**
     * Handle incoming request from host.
     * @private
     */
    _handleRequest(message, source, origin) {
        const handler = this.handlers.get(message.method);

        if (!handler) {
            // Send error response for requests (not notifications)
            if (message.id !== undefined) {
                this._sendResponse(source, message.id, null, {
                    code: -32601,
                    message: `Method not found: ${message.method}`
                }, origin);
            }
            return;
        }

        try {
            const result = handler(message.params || {});

            // If method returns a Promise, wait for it
            if (result && typeof result.then === 'function') {
                result.then(
                    (res) => {
                        if (message.id !== undefined) {
                            this._sendResponse(source, message.id, res, null, origin);
                        }
                    },
                    (err) => {
                        if (message.id !== undefined) {
                            this._sendResponse(source, message.id, null, {
                                code: -32603,
                                message: err.message
                            }, origin);
                        }
                    }
                );
            } else if (message.id !== undefined) {
                // Synchronous result
                this._sendResponse(source, message.id, result, null, origin);
            }
        } catch (err) {
            if (message.id !== undefined) {
                this._sendResponse(source, message.id, null, {
                    code: -32603,
                    message: err.message
                }, origin);
            }
        }
    }

    /**
     * Send a JSON-RPC 2.0 response.
     * @private
     * @param {Window} target - The target window to send to
     * @param {number|string} id - The JSON-RPC request ID
     * @param {*} result - The result value (if success)
     * @param {object|null} error - The error object (if error)
     * @param {string} targetOrigin - The validated origin to send to
     */
    _sendResponse(target, id, result, error = null, targetOrigin = '*') {
        if (id === undefined) return;  // Notification, no response needed

        const response = {
            jsonrpc: '2.0',
            id: id
        };

        if (error) {
            response.error = error;
        } else {
            response.result = result;
        }

        target.postMessage(response, targetOrigin);
    }

    /**
     * Register a handler for a method.
     * @param {string} method - Method name
     * @param {function} handler - Handler function (receives params, returns result)
     */
    on(method, handler) {
        if (typeof handler !== 'function') {
            throw new Error(`Handler for '${method}' must be a function`);
        }
        this.handlers.set(method, handler);
    }

    /**
     * Remove a handler.
     * @param {string} method - Method name
     */
    off(method) {
        this.handlers.delete(method);
    }

    /**
     * Send a request to the host and wait for response.
     * @param {string} method - Method name
     * @param {object} params - Method parameters
     * @param {number} timeout - Timeout in milliseconds (default: 30000)
     * @returns {Promise} - Resolves with result or rejects with error
     */
    request(method, params = {}, timeout = 30000) {
        return new Promise((resolve, reject) => {
            const id = this.nextId++;

            this.pendingRequests.set(id, { resolve, reject });

            // Timeout handling
            const timeoutId = setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    const error = new Error(`Request timeout: ${method}`);
                    error.code = -32000;
                    reject(error);
                }
            }, timeout);

            // Store timeout ID for cleanup
            const pending = this.pendingRequests.get(id);
            pending.timeoutId = timeoutId;

            // Override resolve/reject to clear timeout
            const originalResolve = pending.resolve;
            const originalReject = pending.reject;
            pending.resolve = (value) => {
                clearTimeout(timeoutId);
                originalResolve(value);
            };
            pending.reject = (error) => {
                clearTimeout(timeoutId);
                originalReject(error);
            };

            const message = {
                jsonrpc: '2.0',
                id: id,
                method: method,
                params: params
            };

            window.parent.postMessage(message, '*');
        });
    }

    /**
     * Send a notification (no response expected).
     * Alias: send() — used by UI templates.
     * @param {string} method - Method name
     * @param {object} params - Method parameters
     */
    send(method, params = {}) {
        return this.notify(method, params);
    }

    /**
     * Send a notification (no response expected).
     * @param {string} method - Method name
     * @param {object} params - Method parameters
     */
    notify(method, params = {}) {
        const message = {
            jsonrpc: '2.0',
            method: method,
            params: params
        };

        window.parent.postMessage(message, '*');
    }

    /**
     * Add an allowed origin dynamically.
     * @param {string} origin - Origin to add (e.g., 'https://example.com')
     */
    addOrigin(origin) {
        this.allowedOrigins.add(origin);
    }

    /**
     * Remove an allowed origin.
     * @param {string} origin - Origin to remove
     */
    removeOrigin(origin) {
        // Don't allow removing default security origins
        const defaults = ['https://claude.ai', 'https://desktop.claude.ai', 'null'];
        if (defaults.includes(origin)) {
            console.warn(`[SecureMessenger] Cannot remove default origin: ${origin}`);
            return;
        }
        this.allowedOrigins.delete(origin);
    }

    /**
     * Check if an origin is allowed.
     * @param {string} origin - Origin to check
     * @returns {boolean}
     */
    isOriginAllowed(origin) {
        return this.allowedOrigins.has(origin);
    }

    /**
     * Get all registered method names.
     * @returns {string[]}
     */
    getMethods() {
        return Array.from(this.handlers.keys());
    }

    /**
     * Destroy the messenger instance.
     * Removes event listener and clears all pending requests.
     */
    destroy() {
        // Clear all pending requests with rejection
        for (const [id, pending] of this.pendingRequests) {
            pending.reject(new Error('Messenger destroyed'));
        }
        this.pendingRequests.clear();
        this.handlers.clear();
        this.initialized = false;
    }
}

// Export for bundling
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SecureMessenger };
}
