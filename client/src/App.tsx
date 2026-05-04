/**
 * Main App component
 */
import { useEffect } from 'react';
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
    isRunning,
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

  // Seed node statuses from active run's snapshot (fixes completed nodes after refresh/reconnect).
  // Skip while a run is in progress so WebSocket NODE_STATUS is the single source of truth;
  // otherwise loops would never show a node as "running" again after its first completion.
  useEffect(() => {
    if (isRunning) return;
    const activeRun =
      runs.find((r) => r.id === (currentRunId ?? selectedRunId)) ??
      runs.find((r) => r.status === 'running');
    if (!activeRun?.snapshot?.node_outputs || nodes.length === 0) return;
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
  }, [runs, currentRunId, selectedRunId, nodes, updateNodeStatus, isRunning]);

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

  const loadRuns = async (workspaceId: string) => {
    try {
      const runs = await api.getRuns(workspaceId);
      setRuns(runs);
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
