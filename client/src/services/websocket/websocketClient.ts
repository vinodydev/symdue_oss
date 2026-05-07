// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * WebSocket client for real-time updates
 */
import ReconnectingWebSocket from 'reconnecting-websocket';
import type { WebSocketMessage } from '@/types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

class WebSocketClient {
  private ws: ReconnectingWebSocket | null = null;
  private workspaceId: string | null = null;
  private messageHandlers: Set<(message: WebSocketMessage) => void> = new Set();
  private connectionHandlers: Set<(connected: boolean) => void> = new Set();

  connect(workspaceId: string): void {
    if (this.ws && this.workspaceId === workspaceId) {
      // Already connected to this workspace
      return;
    }

    this.disconnect();
    this.workspaceId = workspaceId;

    const url = `${WS_URL}/ws/${workspaceId}`;
    this.ws = new ReconnectingWebSocket(url, [], {
      connectionTimeout: 4000,
      maxRetries: 10,
      maxReconnectionDelay: 10000,
      minReconnectionDelay: 1000,
      reconnectionDelayGrowFactor: 1.3,
    });

    this.ws.addEventListener('open', () => {
      console.log(`✅ WebSocket connected to workspace: ${workspaceId}`);
      this.notifyConnectionHandlers(true);
    });

    this.ws.addEventListener('close', () => {
      console.log(`❌ WebSocket disconnected from workspace: ${workspaceId}`);
      this.notifyConnectionHandlers(false);
    });

    this.ws.addEventListener('error', (error) => {
      console.error('WebSocket error:', error);
    });

    this.ws.addEventListener('message', (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.notifyMessageHandlers(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.workspaceId = null;
  }

  onMessage(handler: (message: WebSocketMessage) => void): () => void {
    this.messageHandlers.add(handler);
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  onConnectionChange(handler: (connected: boolean) => void): () => void {
    this.connectionHandlers.add(handler);
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  private notifyMessageHandlers(message: WebSocketMessage): void {
    this.messageHandlers.forEach((handler) => {
      try {
        handler(message);
      } catch (error) {
        console.error('Error in WebSocket message handler:', error);
      }
    });
  }

  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach((handler) => {
      try {
        handler(connected);
      } catch (error) {
        console.error('Error in WebSocket connection handler:', error);
      }
    });
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  getWorkspaceId(): string | null {
    return this.workspaceId;
  }
}

export const wsClient = new WebSocketClient();

