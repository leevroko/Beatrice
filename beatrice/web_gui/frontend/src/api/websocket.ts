/** WebSocket JSON-RPC клиент. */

import type {
  JsonRpcRequest,
  JsonRpcResponse,
  JsonRpcEvent,
  WsMessage,
} from './types';

type EventHandler = (event: JsonRpcEvent['params']) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private idCounter = 0;
  private pending = new Map<number, {
    resolve: (v: unknown) => void;
    reject: (e: Error) => void;
  }>();
  private eventHandlers = new Map<string, EventHandler[]>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _connected = false;
  private _onStatusChange: ((connected: boolean) => void) | null = null;

  get connected(): boolean {
    return this._connected;
  }

  set onStatusChange(h: ((c: boolean) => void) | null) {
    this._onStatusChange = h;
  }

  connect(url: string): void {
    if (this.ws) {
      this.ws.close();
    }
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this._connected = true;
      this._onStatusChange?.(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        this.handleMessage(msg);
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    this.ws.onclose = () => {
      this._connected = false;
      this._onStatusChange?.(false);
      // Reject all pending
      for (const [, p] of this.pending) {
        p.reject(new Error('WebSocket closed'));
      }
      this.pending.clear();
      // Reconnect after 3s
      this.reconnectTimer = setTimeout(() => {
        this.connect(url);
      }, 3000);
    };

    this.ws.onerror = () => {
      // onclose will fire after this
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this._connected = false;
    this.ws?.close();
    this.ws = null;
  }

  async call<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket не подключён');
    }
    const id = ++this.idCounter;
    const req: JsonRpcRequest = {
      jsonrpc: '2.0',
      method,
      params,
      id,
    };
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      this.ws!.send(JSON.stringify(req));
      // Timeout after 30s
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`Timeout: ${method}`));
        }
      }, 30000);
    });
  }

  on(eventType: string, handler: EventHandler): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);
    return () => {
      const handlers = this.eventHandlers.get(eventType);
      if (handlers) {
        const idx = handlers.indexOf(handler);
        if (idx >= 0) handlers.splice(idx, 1);
      }
    };
  }

  private handleMessage(msg: WsMessage): void {
    // Event
    if ('method' in msg && msg.method === 'event') {
      const ev = msg as JsonRpcEvent;
      const handlers = this.eventHandlers.get(ev.params.type);
      handlers?.forEach((h) => h(ev.params));
      return;
    }

    // Response
    const resp = msg as JsonRpcResponse;
    if (resp.id !== null && resp.id !== undefined) {
      const pending = this.pending.get(resp.id as number);
      if (pending) {
        this.pending.delete(resp.id as number);
        if (resp.error) {
          pending.reject(new Error(resp.error.message));
        } else {
          pending.resolve(resp.result);
        }
      }
    }
  }
}
