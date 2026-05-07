// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * React hook for WebSocket connection
 */
import { useEffect, useRef } from 'react';
import { wsClient } from '@/services/websocket/websocketClient';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { WebSocketMessage, NodeStatus } from '@/types';

export function useWebSocket(workspaceId: string | null) {
  const {
    updateNodeStatus,
    setCurrentRun,
    setIsRunning,
    clearNodeStatuses,
    setRuns,
    updateRun,
    runs,
  } = useAppStore();
  const handlersRef = useRef<Array<() => void>>([]);

  const refetchRunsIfWorkspace = async () => {
    if (!workspaceId) return;
    try {
      const runsList = await api.getRuns(workspaceId);
      setRuns(runsList);
    } catch (e) {
      console.error('Failed to refetch runs:', e);
    }
  };

  /** Refetch the current run and update it in the runs list (so finished nodes' outputs/logs appear during run). */
  const refetchCurrentRunIfActive = async () => {
    if (!workspaceId) return;
    const currentRunId = useAppStore.getState().currentRunId;
    if (!currentRunId) return;
    try {
      const freshRun = await api.getRun(workspaceId, currentRunId);
      const currentRuns = useAppStore.getState().runs;
      const updated = currentRuns.map((r) => (r.id === currentRunId ? freshRun : r));
      setRuns(updated);
    } catch (e) {
      console.error('Failed to refetch current run:', e);
    }
  };

  useEffect(() => {
    if (!workspaceId) {
      wsClient.disconnect();
      return;
    }

    wsClient.connect(workspaceId);

    const unsubscribeMessage = wsClient.onMessage(
      (message: WebSocketMessage) => {
        const type = message.type?.toUpperCase();

        if (type === 'NODE_STATUS' && message.node_id && message.status) {
          updateNodeStatus(message.node_id, message.status as NodeStatus);
          // Refetch current run so finished nodes' outputs/logs appear in the UI during run
          if (message.status === 'success' || message.status === 'error') {
            refetchCurrentRunIfActive();
          }
        }

        if (type === 'WORKFLOW_STATUS') {
          const status = message.status || (message.data as any)?.status;

          if (status === 'started' || status === 'running') {
            if (message.run_id) {
              setCurrentRun(message.run_id);
            }
            setIsRunning(true);
            clearNodeStatuses();
          }

          if (
            status === 'completed' ||
            status === 'success' ||
            status === 'error' ||
            status === 'failed' ||
            status === 'cancelled'
          ) {
            setIsRunning(false);
            refetchRunsIfWorkspace();
          }
        }

        if (message.type === 'node_status' && message.node_id && message.status) {
          updateNodeStatus(message.node_id, message.status as NodeStatus);
          if (message.status === 'success' || message.status === 'error') {
            refetchCurrentRunIfActive();
          }
        }
        if (message.type === 'run_started' && message.run_id) {
          setCurrentRun(message.run_id);
          setIsRunning(true);
        }
        if (
          message.type === 'run_completed' ||
          message.type === 'run_failed'
        ) {
          setIsRunning(false);
          refetchRunsIfWorkspace();
        }
        // Workflow-level status changes (pause/resume/cancel from the API).
        // Backend emits via publish_node_status with node_id="__workflow__" → type "WORKFLOW_STATUS".
        if (
          (message.type === 'WORKFLOW_STATUS' || message.type === 'workflow_status') &&
          message.run_id &&
          message.status
        ) {
          updateRun(message.run_id, { status: message.status as string });
          if (
            ['cancelled', 'completed', 'error', 'failed'].includes(String(message.status))
          ) {
            setIsRunning(false);
          }
        }
      },
    );

    handlersRef.current.push(unsubscribeMessage);

    const unsubscribeConnection = wsClient.onConnectionChange((connected) => {
      if (connected && workspaceId) {
        refetchRunsIfWorkspace();
      }
    });
    handlersRef.current.push(unsubscribeConnection);

    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return;
      const currentRuns = useAppStore.getState().runs;
      const inFlight = currentRuns.some(
        (r) =>
          r.status === 'running' || r.status === 'queued' || r.status === 'paused',
      );
      if (inFlight && workspaceId) {
        refetchRunsIfWorkspace();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      handlersRef.current.forEach((unsubscribe) => unsubscribe());
      handlersRef.current = [];
      wsClient.disconnect();
    };
  }, [
    workspaceId,
    updateNodeStatus,
    setCurrentRun,
    setIsRunning,
    clearNodeStatuses,
    setRuns,
  ]);

  return {
    isConnected: wsClient.isConnected(),
    workspaceId: wsClient.getWorkspaceId(),
  };
}
