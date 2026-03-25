/**
 * SSE Manager for handling Server-Sent Events.
 *
 * P0: Basic SSE connection with event parsing.
 * Enhanced: Exponential backoff reconnection, event sequence detection, connection state management.
 */

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5;
const DEFAULT_BASE_RECONNECT_DELAY = 100; // ms
const EVENT_TYPES: SSEEventType[] = [
  'trace_event',
  'thought',
  'hil_interrupt',
  'token_update',
  'context_window',
  'slot_details',
  'session_metadata',
  'error',
  'done',
];

// ============================================================================
// Type Definitions
// ============================================================================

export type SSEEventType =
  | 'trace_event'
  | 'thought'
  | 'hil_interrupt'
  | 'token_update'
  | 'context_window'
  | 'slot_details'
  | 'session_metadata'
  | 'error'
  | 'done';

export interface SSEEvent {
  type: SSEEventType;
  data: unknown;
}

export type SSEEventHandler = (event: SSEEvent) => void;

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export type StateChangeHandler = (state: ConnectionState) => void;

export interface ConnectionOptions {
  message: string;
  session_id: string;
  user_id: string;
}

// ============================================================================
// SSE Manager Class
// ============================================================================

export class SSEManager {
  private eventSource: EventSource | null = null;
  private handlers: Map<SSEEventType, SSEEventHandler[]> = new Map();
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts: number;
  private readonly baseReconnectDelay: number;

  // Event sequence detection
  private lastSeq = 0;

  // Connection state management
  private state: ConnectionState = 'disconnected';
  private stateChangeHandlers: StateChangeHandler[] = [];

  // Store connection parameters for reconnection
  private baseUrl: string | null = null;
  private currentOptions: ConnectionOptions | null = null;

  constructor(options?: { maxReconnectAttempts?: number; baseReconnectDelay?: number }) {
    this.maxReconnectAttempts = options?.maxReconnectAttempts ?? DEFAULT_MAX_RECONNECT_ATTEMPTS;
    this.baseReconnectDelay = options?.baseReconnectDelay ?? DEFAULT_BASE_RECONNECT_DELAY;
  }

  /**
   * Connect to SSE endpoint.
   * @param url - The base URL of the SSE endpoint (without query parameters)
   * @param options - Connection options including message, session_id, and user_id
   */
  connect(url: string, options: ConnectionOptions) {
    // Build URL with query parameters
    const params = new URLSearchParams({
      message: options.message,
      session_id: options.session_id,
      user_id: options.user_id,
    });

    const fullUrl = `${url}?${params.toString()}`;

    // Store original URL and options for reconnection
    this.baseUrl = url;
    this.currentOptions = options;

    // Close existing connection
    this.disconnect();

    // Set state to connecting
    this.setState('connecting');

    // Create new EventSource
    this.eventSource = new EventSource(fullUrl);

    // Set up event listeners
    this.setupListeners();

    console.log(`[SSE] Connecting to ${fullUrl}`);
  }

  /**
   * Set up EventSource listeners.
   */
  private setupListeners() {
    if (!this.eventSource) return;

    // Connection events
    this.eventSource.onopen = () => {
      console.log('[SSE] Connected');
      this.reconnectAttempts = 0;
      this.setState('connected');
    };

    this.eventSource.onerror = (error) => {
      const readyState = this.eventSource?.readyState;
      const stateName =
        readyState === EventSource.CONNECTING
          ? 'CONNECTING'
          : readyState === EventSource.OPEN
            ? 'OPEN'
            : readyState === EventSource.CLOSED
              ? 'CLOSED'
              : 'UNKNOWN';

      console.error(`[SSE] Error (readyState: ${stateName}):`, error);

      // Handle based on readyState
      if (readyState === EventSource.OPEN) {
        // Connection is still open - might be a transient error
        // Don't disconnect, just emit error event
        this.emit('error', {
          message: 'SSE 连接出现临时错误，连接保持打开',
        });
        return;
      }

      // For CONNECTING or CLOSED states, trigger reconnection logic
      this.setState('error');
      this.reconnectAttempts++;

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('[SSE] Max reconnect attempts reached');
        this.emit('error', {
          message: 'SSE 连接失败，请确认后端已启动（默认 http://localhost:8000）',
        });
        this.disconnect();
      } else {
        this.scheduleReconnect();
      }
    };

    // Message events (type-specific)
    for (const eventType of EVENT_TYPES) {
      this.eventSource.addEventListener(eventType, (e) => {
        this.handleEventMessage(eventType, e as MessageEvent);
      });
    }
  }

  /**
   * Handle incoming SSE event message.
   * @param eventType - The type of SSE event
   * @param event - The MessageEvent from EventSource
   */
  private handleEventMessage(eventType: SSEEventType, event: MessageEvent) {
    try {
      // Skip empty data (can happen during connection errors)
      if (!event.data || event.data.trim() === '') {
        console.debug(`[SSE] Skipping empty ${eventType} event`);
        return;
      }

      const data = JSON.parse(event.data);
      this.emit(eventType, data);
    } catch (err) {
      console.error(`[SSE] Failed to parse ${eventType}:`, err);
      console.error(`[SSE] Raw data:`, event.data);
      // Emit error event for UI to handle
      this.emit('error', {
        message: `Failed to parse SSE event: ${eventType}`,
        raw_data: event.data,
      });
    }
  }

  /**
   * Register event handler for a specific event type.
   * @param eventType - The type of SSE event to listen for
   * @param handler - The callback function to invoke when the event occurs
   */
  on(eventType: SSEEventType, handler: SSEEventHandler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType)!.push(handler);
  }

  /**
   * Unregister event handler for a specific event type.
   * @param eventType - The type of SSE event
   * @param handler - The callback function to remove
   */
  off(eventType: SSEEventType, handler: SSEEventHandler) {
    const handlers = this.handlers.get(eventType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * Emit event to all registered handlers for the event type.
   * @param eventType - The type of SSE event
   * @param data - The event data to emit
   */
  private emit(eventType: SSEEventType, data: unknown) {
    const handlers = this.handlers.get(eventType);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler({ type: eventType, data });
        } catch (err) {
          console.error(`[SSE] Handler error for ${eventType}:`, err);
        }
      }
    }
  }

  /**
   * Disconnect SSE connection and reset state.
   */
  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      console.log('[SSE] Disconnected');
    }
    // Reset sequence number
    this.lastSeq = 0;
    // Reset state
    this.setState('disconnected');
  }

  /**
   * Check if currently connected to SSE endpoint.
   * @returns true if EventSource exists and is in OPEN state
   */
  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }

  /**
   * Get current connection state.
   * @returns The current connection state
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * Schedule reconnection with exponential backoff.
   */
  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SSE] Max reconnect attempts reached');
      this.emit('error', {
        message: 'SSE 连接失败，请确认后端已启动（默认 http://localhost:8000）',
      });
      this.disconnect();
      return;
    }

    const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
    console.log(
      `[SSE] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`
    );

    setTimeout(() => {
      if (this.baseUrl && this.currentOptions) {
        // Don't increment reconnectAttempts here - already done in onerror
        this.connect(this.baseUrl, this.currentOptions);
      }
    }, delay);
  }

  /**
   * Check event sequence number for ordering.
   * @param seq - The sequence number to check
   * @returns true if sequence is valid, false if out of order
   */
  private checkSeq(seq: number): boolean {
    if (seq < this.lastSeq) {
      console.warn(`[SSE] Out of order event: seq=${seq}, last=${this.lastSeq}`);
      return false;
    }
    this.lastSeq = seq;
    return true;
  }

  /**
   * Register state change handler.
   * @param handler - Callback function to invoke when connection state changes
   */
  onStateChange(handler: StateChangeHandler) {
    this.stateChangeHandlers.push(handler);
  }

  /**
   * Unregister state change handler.
   * @param handler - The callback function to remove
   */
  offStateChange(handler: StateChangeHandler) {
    const index = this.stateChangeHandlers.indexOf(handler);
    if (index > -1) {
      this.stateChangeHandlers.splice(index, 1);
    }
  }

  /**
   * Set connection state and notify all registered handlers.
   * @param newState - The new connection state
   */
  private setState(newState: ConnectionState) {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      console.log(`[SSE] State change: ${oldState} -> ${newState}`);
      this.stateChangeHandlers.forEach((h) => h(newState));
    }
  }
}

// Global SSE manager instance
export const sseManager = new SSEManager();
