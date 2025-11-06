// Simple raw WebSocket service (compatible with FastAPI WebSocket)
// Use relative URL since Nginx proxies /ws/ to backend
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host;

export interface WebSocketMessage {
  type?: string;
  message?: string;
  data?: any;
  timestamp: string;
}

class WebSocketService {
  private connections: Map<string, WebSocket> = new Map();
  private callbacks: Map<string, Set<(data: any) => void>> = new Map();

  // Connect to a ticket's WebSocket
  connectToTicket(ticketId: number | string, callback: (message: WebSocketMessage) => void) {
    const key = `ticket_${ticketId}`;

    // If already connected, just add callback
    if (this.connections.has(key)) {
      if (!this.callbacks.has(key)) {
        this.callbacks.set(key, new Set());
      }
      this.callbacks.get(key)?.add(callback);
      return;
    }

    // Create new WebSocket connection
    const ws = new WebSocket(`${WS_BASE_URL}/ws/ticket/${ticketId}`);

    ws.onopen = () => {
      console.log(`WebSocket connected to ticket ${ticketId}`);
    };

    ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        let payload: WebSocketMessage = {
          ...raw,
          timestamp: raw.timestamp || new Date().toISOString(),
        };

        if (typeof raw?.message === 'string') {
          try {
            const embedded = JSON.parse(raw.message);
            payload = {
              ...payload,
              ...embedded,
              data: embedded.data ?? embedded,
            };
          } catch {
            payload = {
              ...payload,
              message: raw.message,
            };
          }
        }

        this.callbacks.get(key)?.forEach(cb => cb(payload));
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for ticket ${ticketId}:`, error);
    };

    ws.onclose = () => {
      console.log(`WebSocket closed for ticket ${ticketId}`);
      this.connections.delete(key);
      this.callbacks.delete(key);
    };

    this.connections.set(key, ws);

    // Add initial callback
    if (!this.callbacks.has(key)) {
      this.callbacks.set(key, new Set());
    }
    this.callbacks.get(key)?.add(callback);
  }

  disconnectFromTicket(ticketId: number | string) {
    const key = `ticket_${ticketId}`;
    const ws = this.connections.get(key);

    if (ws) {
      ws.close();
      this.connections.delete(key);
      this.callbacks.delete(key);
    }
  }

  disconnectAll() {
    this.connections.forEach((ws) => ws.close());
    this.connections.clear();
    this.callbacks.clear();
  }

  // Legacy methods for backward compatibility (simplified)
  connect() {
    console.debug('WebSocket service initialized');
  }

  disconnect() {
    this.disconnectAll();
  }

  subscribeToTicket(ticketId: number, callback: (message: any) => void) {
    this.connectToTicket(ticketId, callback);
  }

  unsubscribeFromTicket(ticketId: number) {
    this.disconnectFromTicket(ticketId);
  }

  // Stub methods for other subscriptions (not implemented in backend yet)
  subscribeToSLA(_callback?: (message: any) => void) {
    console.debug('SLA WebSocket not implemented yet');
  }

  unsubscribeFromSLA() {}

  subscribeToWorkload(_callback?: (message: any) => void) {
    console.debug('Workload WebSocket not implemented yet');
  }

  unsubscribeFromWorkload() {}

  subscribeToCollaboration(ticketId: number, callback: (message: WebSocketMessage) => void) {
    this.connectToTicket(ticketId, callback);
  }

  unsubscribeFromCollaboration(ticketId: number) {
    this.disconnectFromTicket(ticketId);
  }

  sendCollaborationMessage(ticketId: number, message: string) {
    const key = `ticket_${ticketId}`;
    const ws = this.connections.get(key);

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn(`WebSocket not ready for ticket ${ticketId}; message not sent.`);
      return;
    }

    const sender = localStorage.getItem('collab_user_name') || 'Automation Agent';
    const payload = {
      type: 'collaboration_message',
      data: {
        message,
        member_name: sender,
      },
      timestamp: new Date().toISOString(),
    };

    ws.send(JSON.stringify(payload));
  }

  subscribeToNotifications(_callback?: (message: any) => void) {
    console.debug('Notifications WebSocket not implemented yet');
  }

  unsubscribeFromNotifications() {}

  isConnected(): boolean {
    return this.connections.size > 0;
  }
}

export const wsService = new WebSocketService();
export default wsService;
