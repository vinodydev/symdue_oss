// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * React hook for WebSocket connection
 */
import { useEffect, useRef } from 'react';
import { wsClient } from '@/services/websocket/websocketClient';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { WebSocketMessage, NodeStatus, Run } from '@/types';

export function useWebSocket(workspaceId: string | null) {
  const {
    updateNodeStatus,
    setCurrentRun,
    setIsRunning,
    clearNodeStatuses,
    setRuns,
    updateRun,
    markActivity,
    bumpSeedNonce,
  } = useAppStore();
  const handlersRef = useRef<Array<() => void>>([]);
  // Trailing-edge debounce for refetchCurrentRunIfActive. NODE_STATUS events
  // arrive in bursts during fan-out (parallel WEB_SEARCH/PAPER_SEARCH/PDF_READ
  // completing within tens of ms). Each fetch returns ~778 KB; 150 events ×
  // 778 KB = ~116 MB redundant transfer per run. Coalescing to one fetch per
  // ~400 ms quiet window cuts that to a handful of fetches.
  const refetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const REFETCH_DEBOUNCE_MS = 400;

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
  const refetchCurrentRunIfActive = () => {
    if (!workspaceId) return;
    if (refetchTimerRef.current) {
      clearTimeout(refetchTimerRef.current);
    }
    refetchTimerRef.current = setTimeout(async () => {
      refetchTimerRef.current = null;
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
    }, REFETCH_DEBOUNCE_MS);
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

        // Any WS frame counts as evidence the run is alive — feeds the
        // "no progress detected" banner timer.
        markActivity();

        // Heartbeat from worker's astream loop: status='heartbeat' on
        // node_id='__workflow__'. Activity already marked above; nothing else to do.
        if (type === 'WORKFLOW_STATUS' && (message.status as string) === 'heartbeat') {
          return;
        }

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
            // Only wipe node statuses for a genuinely new run. WORKFLOW_STATUS
            // running fires on resume-after-pause too, where we want to keep
            // the canvas state for already-completed nodes.
            const previousRunId = useAppStore.getState().currentRunId;
            if (message.run_id) {
              setCurrentRun(message.run_id);
            }
            setIsRunning(true);
            if (!message.run_id || message.run_id !== previousRunId) {
              clearNodeStatuses();
            }
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
          updateRun(message.run_id, { status: message.status as Run['status'] });
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
        // Catch up after a WS gap (e.g. docker down/up). Redis pub/sub doesn't
        // buffer, so any NODE_STATUS events emitted while we were disconnected
        // are gone. Refresh the runs list AND the active run's full snapshot,
        // then bump seedNonce so the App.tsx seed effect re-paints the canvas
        // even during a live run (its seed-once guard otherwise bails).
        refetchRunsIfWorkspace();
        refetchCurrentRunIfActive();
        bumpSeedNonce();
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
        // Same catch-up dance when the tab was backgrounded long enough that
        // we may have missed events.
        refetchRunsIfWorkspace();
        refetchCurrentRunIfActive();
        bumpSeedNonce();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      handlersRef.current.forEach((unsubscribe) => unsubscribe());
      handlersRef.current = [];
      if (refetchTimerRef.current) {
        clearTimeout(refetchTimerRef.current);
        refetchTimerRef.current = null;
      }
      wsClient.disconnect();
    };
  }, [
    workspaceId,
    updateNodeStatus,
    setCurrentRun,
    setIsRunning,
    clearNodeStatuses,
    setRuns,
    markActivity,
    updateRun,
    bumpSeedNonce,
  ]);

  return {
    isConnected: wsClient.isConnected(),
    workspaceId: wsClient.getWorkspaceId(),
  };
}
