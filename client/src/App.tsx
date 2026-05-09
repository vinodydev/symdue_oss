// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Main App component
 */
import { useEffect, useRef } from 'react';
import { AppLayout } from './components/AppLayout';
import { Canvas } from './components/Canvas/Canvas';
import { WorkflowHeader } from './components/Canvas/WorkflowHeader';
import { RunHistory } from './components/Sidebar/RunHistory';
import { SettingsPage } from './components/Settings/SettingsPage';
import { NodeTypesView } from './components/NodeTypes/NodeTypesView';
import { WorkspaceList } from './components/Sidebar/WorkspaceList';
import { EventsPage } from './pages/EventsPage';
import { useAppStore } from './stores';
import { api } from './services/api';
import { useWebSocket } from './hooks/useWebSocket';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

function App() {
  const {
    currentWorkspaceId,
    setCurrentWorkspace,
    setWorkspaces,
    setNodes,
    setEdges,
    setTransform,
    setRuns,
    setLLMConfigs,
    currentView,
    setCurrentView,
    isHistoryOpen,
    workspaces,
    runs,
    currentRunId,
    selectedRunId,
    selectedNodeTypeId,
    setSelectedNodeTypeId,
    nodes,
    updateNodeStatus,
    clearNodeStatuses,
    isRunning,
    seedNonce,
  } = useAppStore();

  // Load workspaces + global data on mount
  useEffect(() => {
    loadWorkspaces();
    loadLLMConfigs();
  }, []);

  // Restore current workspace from localStorage after workspaces are loaded
  useEffect(() => {
    if (workspaces.length === 0 || currentWorkspaceId) return;
    try {
      const stored = typeof window !== 'undefined' && window.localStorage.getItem('graphmind_current_workspace_id');
      if (stored && workspaces.some((w) => w.id === stored)) {
        setCurrentWorkspace(stored);
      }
    } catch (_) { /* ignore */ }
  }, [workspaces, currentWorkspaceId, setCurrentWorkspace]);

  // Load workspace data when workspace changes
  useEffect(() => {
    if (currentWorkspaceId) {
      loadWorkspaceData(currentWorkspaceId);
      loadRuns(currentWorkspaceId);
      setCurrentView('editor');
    } else {
      setNodes([]);
      setEdges([]);
      setRuns([]);
    }
  }, [currentWorkspaceId]);

  // WebSocket connection
  useWebSocket(currentWorkspaceId);

  // When the user clicks a historical run in the history sidebar, the runs list
  // doesn't carry a snapshot for it (summary mode). Fetch it lazily so the failed
  // node highlights and the resume-from-checkpoint button can render.
  useEffect(() => {
    if (!currentWorkspaceId || !selectedRunId) return;
    const target = runs.find((r) => r.id === selectedRunId);
    if (!target || target.snapshot) return;
    let cancelled = false;
    (async () => {
      try {
        const fullRun = await api.getRun(currentWorkspaceId, selectedRunId);
        if (cancelled) return;
        const latest = useAppStore.getState().runs;
        setRuns(latest.map((r) => (r.id === fullRun.id ? fullRun : r)));
      } catch (err) {
        console.error('Failed to hydrate selected run snapshot:', err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedRunId, currentWorkspaceId, runs, setRuns]);

  // Seed node statuses from active run's snapshot.
  //
  // Two scenarios this serves:
  //   1. User views a historical run (isRunning=false) — re-paint the canvas
  //      from snapshot every time `runs`/selection changes.
  //   2. User reloads / reconnects DURING an active run (isRunning=true) —
  //      paint already-completed nodes ONCE from the snapshot, then let the
  //      WebSocket NODE_STATUS stream take over.
  //
  // Without the seed-once guard, scenario 2 leaves the canvas mostly blank:
  // the WS only emits status for nodes that fire AFTER reconnect, so nodes
  // already finished pre-reload would never get their green checkmark.
  // With the guard, we paint once on first mount-with-snapshot, then bail —
  // so loop iterations and mid-flight running indicators from WS aren't
  // overridden by stale snapshot data.
  const lastSeededRunIdRef = useRef<string | null>(null);
  const lastSeededNonceRef = useRef<number>(-1);
  useEffect(() => {
    const activeRun =
      runs.find((r) => r.id === (currentRunId ?? selectedRunId)) ??
      runs.find((r) => r.status === 'running');
    if (!activeRun?.snapshot?.node_outputs || nodes.length === 0) return;
    // During a live run, normally bail after the first seed so WS NODE_STATUS
    // can drive the canvas. EXCEPT when seedNonce changes — that signals
    // something forced a snapshot refetch (e.g. WS reconnect after docker
    // down/up dropped events) and we need to repaint to catch up.
    if (
      isRunning &&
      lastSeededRunIdRef.current === activeRun.id &&
      lastSeededNonceRef.current === seedNonce
    ) {
      return;
    }
    lastSeededRunIdRef.current = activeRun.id;
    lastSeededNonceRef.current = seedNonce;

    // When viewing a historical / finished run, wipe stale statuses first so
    // ghost "running" spinners or greens from a previous selection don't
    // bleed into this run's display. For live runs we rely on the seed-once
    // guard above to avoid overriding mid-flight WS updates, so don't clear.
    if (!isRunning) clearNodeStatuses();

    const outputs = activeRun.snapshot.node_outputs as Record<string, { error?: string } | unknown>;
    nodes.forEach((node) => {
      const entry = outputs[node.id] ?? outputs[node.name ?? ''];
      if (entry && typeof entry === 'object') {
        const obj = entry as Record<string, unknown>;
        if (obj.__suspended__) {
          // Wait node or downstream blocked node
          const isWaitNode = node.node_type_id === 'wait';
          updateNodeStatus(node.id, isWaitNode ? 'waiting' : 'blocked');
        } else if ('error' in obj && obj.error) {
          updateNodeStatus(node.id, 'error');
        } else {
          updateNodeStatus(node.id, 'success');
        }
      } else if (entry !== undefined && entry !== null) {
        updateNodeStatus(node.id, 'success');
      }
    });

    // For failed / cancelled runs, the snapshot's node_outputs only has entries
    // for nodes that completed — the node where execution actually stopped is
    // missing. Mark that node red so users see WHERE the run died, not just
    // greens for the survivors. `next_node_id` (LangGraph's planned next step)
    // is the most accurate cursor; `last_executed_node_id` is the fallback.
    if (activeRun.status === 'failed' || activeRun.status === 'cancelled') {
      const snap = activeRun.snapshot as Record<string, unknown>;
      const failurePointId =
        (snap.next_node_id as string | undefined) ??
        (snap.last_executed_node_id as string | undefined);
      if (failurePointId) {
        const node = nodes.find(
          (n) => n.id === failurePointId || n.name === failurePointId,
        );
        if (node) updateNodeStatus(node.id, 'error');
      }
    }
  }, [runs, currentRunId, selectedRunId, nodes, updateNodeStatus, clearNodeStatuses, isRunning, seedNonce]);

  // Keyboard shortcuts
  useKeyboardShortcuts();

  const loadWorkspaces = async () => {
    try {
      const data = await api.getWorkspaces();
      setWorkspaces(data);
    } catch (error) {
      console.error('Failed to load workspaces:', error);
    }
  };

  const loadWorkspaceData = async (workspaceId: string) => {
    try {
      const workspace = await api.getWorkspace(workspaceId);
      setNodes(workspace.nodes || []);
      setEdges(workspace.edges || []);
      if (workspace.transform) {
        setTransform(workspace.transform);
      }
    } catch (error) {
      console.error('Failed to load workspace data:', error);
    }
  };

  // The `runs` list comes back without `snapshot` payloads (summary mode in
  // api.getRuns) so the canvas mount fetch stays small. The seeding effect
  // above needs `snapshot.node_outputs` for the active run only — pull that
  // single snapshot lazily and merge it into the runs state. Other runs'
  // snapshots load on-demand when the user clicks them in the history panel.
  const loadRuns = async (workspaceId: string) => {
    try {
      const summaryRuns = await api.getRuns(workspaceId);
      setRuns(summaryRuns);

      const activeStatuses = new Set(['running', 'queued', 'paused', 'waiting']);
      const activeRun =
        summaryRuns.find((r) => r.id === (currentRunId ?? selectedRunId)) ??
        summaryRuns.find((r) => activeStatuses.has(r.status));
      if (!activeRun) return;

      try {
        const fullRun = await api.getRun(workspaceId, activeRun.id);
        setRuns(summaryRuns.map((r) => (r.id === fullRun.id ? fullRun : r)));
      } catch (err) {
        console.error('Failed to hydrate active run snapshot:', err);
      }
    } catch (error) {
      console.error('Failed to load runs:', error);
    }
  };

  const loadLLMConfigs = async () => {
    try {
      const configs = await api.getLLMConfigs();
      setLLMConfigs(configs);
    } catch (error) {
      console.error('Failed to load LLM configs:', error);
    }
  };

  const handleCreateWorkspace = async () => {
    try {
      const newWorkspace = await api.createWorkspace({ name: 'Untitled Workflow' });
      setWorkspaces([...workspaces, newWorkspace]);
    } catch (error) {
      console.error('Failed to create workspace:', error);
    }
  };

  return (
    <AppLayout>
      {currentView === 'workspaces' && (
        <WorkspaceList
          workspaces={workspaces}
          currentWorkspaceId={currentWorkspaceId}
          onCreateWorkspace={handleCreateWorkspace}
          onRefresh={loadWorkspaces}
        />
      )}

      {currentView === 'editor' && (
        <div className="flex-1 flex flex-col overflow-hidden h-full">
          {/* Workflow header */}
          <WorkflowHeader />

          {/* Main content area */}
          <div className="flex-1 flex overflow-hidden">
            {/* Run history sidebar (left, conditionally shown) */}
            {isHistoryOpen && <RunHistory />}

            {/* Canvas (fills remaining space) */}
            <div className="flex-1 relative overflow-hidden">
              <Canvas />
            </div>
          </div>
        </div>
      )}

      {currentView === 'settings' && <SettingsPage />}
      {currentView === 'events' && <EventsPage />}
      {currentView === 'node_types' && (
        <NodeTypesView
          selectedNodeTypeId={selectedNodeTypeId}
          setSelectedNodeTypeId={setSelectedNodeTypeId}
          setCurrentView={setCurrentView}
          setCurrentWorkspace={setCurrentWorkspace}
        />
      )}
    </AppLayout>
  );
}

export default App;
