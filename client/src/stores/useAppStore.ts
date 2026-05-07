// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Main application store using Zustand
 */
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import type { Node, Edge, Workflow, NodeStatus, LLMConfig, Run } from '@/types';

interface AppState {
  // Workspace state
  workspaces: Workflow[];
  currentWorkspaceId: string | null;

  // Graph state
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;

  // Canvas state
  transform: { x: number; y: number; k: number };

  // UI state
  sidebarOpen: boolean;
  propertiesPanelOpen: boolean;
  activeModal: string | null;
  currentView: 'workspaces' | 'editor' | 'settings' | 'node_types' | 'events';
  isHistoryOpen: boolean;
  activeTool: 'select' | 'pan';
  isNodeModalOpen: boolean;
  nodeSearchQuery: string;
  /** Selected node type id when in node_types view (detail) */
  selectedNodeTypeId: string | null;
  /** True when editor was opened via "Edit workflow" from Node Types */
  openedEditorFromNodeTypes: boolean;
  /** When set, we are editing this workflow template's snapshot; header shows Save template / Discard */
  editingTemplateId: string | null;

  // Execution state
  currentRunId: string | null;
  isRunning: boolean;
  nodeStatuses: Record<string, NodeStatus>;
  runs: Run[];
  selectedRunId: string | null;

  // LLM Config state
  llmConfigs: LLMConfig[];

  // Actions - Workspace
  setCurrentWorkspace: (id: string | null) => void;
  setWorkspaces: (workspaces: Workflow[]) => void;
  addWorkspace: (workspace: Workflow) => void;
  updateWorkspace: (id: string, updates: Partial<Workflow>) => void;
  deleteWorkspace: (id: string) => void;

  // Actions - Graph
  setNodes: (nodes: Node[]) => void;
  addNode: (node: Node) => void;
  updateNode: (id: string, updates: Partial<Node>) => void;
  deleteNode: (id: string) => void;
  setSelectedNode: (id: string | null) => void;

  setEdges: (edges: Edge[]) => void;
  addEdge: (edge: Edge) => void;
  updateEdge: (id: string, updates: Partial<Edge>) => void;
  deleteEdge: (id: string) => void;
  setSelectedEdge: (id: string | null) => void;

  // Actions - Canvas
  setTransform: (transform: { x: number; y: number; k: number }) => void;

  // Actions - UI
  setSidebarOpen: (open: boolean) => void;
  setPropertiesPanelOpen: (open: boolean) => void;
  setActiveModal: (modal: string | null) => void;
  setCurrentView: (view: 'workspaces' | 'editor' | 'settings' | 'node_types' | 'events') => void;
  setIsHistoryOpen: (open: boolean) => void;
  setActiveTool: (tool: 'select' | 'pan') => void;
  setIsNodeModalOpen: (open: boolean) => void;
  setNodeSearchQuery: (query: string) => void;
  setSelectedNodeTypeId: (id: string | null) => void;
  setOpenedEditorFromNodeTypes: (value: boolean) => void;
  setEditingTemplateId: (id: string | null) => void;

  // Actions - Execution
  setCurrentRun: (runId: string | null) => void;
  setIsRunning: (running: boolean) => void;
  updateNodeStatus: (nodeId: string, status: NodeStatus) => void;
  clearNodeStatuses: () => void;
  setRuns: (runs: Run[]) => void;
  addRun: (run: Run) => void;
  updateRun: (runId: string, updates: Partial<Run>) => void;
  setSelectedRunId: (runId: string | null) => void;

  // Actions - LLM Configs
  setLLMConfigs: (configs: LLMConfig[]) => void;
  addLLMConfig: (config: LLMConfig) => void;
  updateLLMConfig: (id: string, updates: Partial<LLMConfig>) => void;
  deleteLLMConfig: (id: string) => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    immer((set) => ({
      // Initial state
      workspaces: [],
      currentWorkspaceId: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      selectedEdgeId: null,
      transform: { x: 0, y: 0, k: 1 },
      sidebarOpen: true,
      propertiesPanelOpen: false,
      activeModal: null,
      currentView: 'workspaces' as const,
      isHistoryOpen: true,
      activeTool: 'select' as const,
      isNodeModalOpen: false,
      nodeSearchQuery: '',
      selectedNodeTypeId: null,
      openedEditorFromNodeTypes: false,
      editingTemplateId: null,
      currentRunId: null,
      isRunning: false,
      nodeStatuses: {},
      runs: [],
      selectedRunId: null,
      llmConfigs: [],

      // Workspace actions
      setCurrentWorkspace: (id) => set((state) => {
        state.currentWorkspaceId = id;
        if (typeof window !== 'undefined') {
          try {
            if (id) window.localStorage.setItem('graphmind_current_workspace_id', id);
            else window.localStorage.removeItem('graphmind_current_workspace_id');
          } catch (_) { /* ignore */ }
        }
      }),
      setWorkspaces: (workspaces) => set((state) => {
        state.workspaces = workspaces;
      }),
      addWorkspace: (workspace) => set((state) => {
        state.workspaces.push(workspace);
      }),
      updateWorkspace: (id, updates) => set((state) => {
        const index = state.workspaces.findIndex((w) => w.id === id);
        if (index !== -1) {
          state.workspaces[index] = { ...state.workspaces[index], ...updates };
        }
      }),
      deleteWorkspace: (id) => set((state) => {
        state.workspaces = state.workspaces.filter((w) => w.id !== id);
        if (state.currentWorkspaceId === id) {
          state.currentWorkspaceId = null;
        }
      }),

      // Graph actions
      setNodes: (nodes) => set((state) => {
        state.nodes = nodes;
      }),
      addNode: (node) => set((state) => {
        state.nodes.push(node);
      }),
      updateNode: (id, updates) => set((state) => {
        const index = state.nodes.findIndex((n) => n.id === id);
        if (index !== -1) {
          state.nodes[index] = { ...state.nodes[index], ...updates };
        }
      }),
      deleteNode: (id) => set((state) => {
        state.nodes = state.nodes.filter((n) => n.id !== id);
        state.edges = state.edges.filter(
          (e) => e.source !== id && e.target !== id
        );
        if (state.selectedNodeId === id) {
          state.selectedNodeId = null;
        }
      }),
      setSelectedNode: (id) => set((state) => {
        state.selectedNodeId = id;
        if (id) {
          state.selectedEdgeId = null;
        }
      }),

      setEdges: (edges) => set((state) => {
        state.edges = edges;
      }),
      addEdge: (edge) => set((state) => {
        state.edges.push(edge);
      }),
      updateEdge: (id, updates) => set((state) => {
        const index = state.edges.findIndex((e) => e.id === id);
        if (index !== -1) {
          state.edges[index] = { ...state.edges[index], ...updates };
        }
      }),
      deleteEdge: (id) => set((state) => {
        state.edges = state.edges.filter((e) => e.id !== id);
        if (state.selectedEdgeId === id) {
          state.selectedEdgeId = null;
        }
      }),
      setSelectedEdge: (id) => set((state) => {
        state.selectedEdgeId = id;
        if (id) {
          state.selectedNodeId = null;
        }
      }),

      // Canvas actions
      setTransform: (transform) => set((state) => {
        state.transform = transform;
      }),

      // UI actions
      setSidebarOpen: (open) => set((state) => {
        state.sidebarOpen = open;
      }),
      setPropertiesPanelOpen: (open) => set((state) => {
        state.propertiesPanelOpen = open;
      }),
      setActiveModal: (modal) => set((state) => {
        state.activeModal = modal;
      }),
      setCurrentView: (view) => set((state) => {
        state.currentView = view;
      }),
      setSelectedNodeTypeId: (id) => set((state) => {
        state.selectedNodeTypeId = id;
      }),
      setOpenedEditorFromNodeTypes: (value) => set((state) => {
        state.openedEditorFromNodeTypes = value;
      }),
      setEditingTemplateId: (id) => set((state) => {
        state.editingTemplateId = id;
      }),
      setIsHistoryOpen: (open) => set((state) => {
        state.isHistoryOpen = open;
      }),
      setActiveTool: (tool) => set((state) => {
        state.activeTool = tool;
      }),
      setIsNodeModalOpen: (open) => set((state) => {
        state.isNodeModalOpen = open;
      }),
      setNodeSearchQuery: (query) => set((state) => {
        state.nodeSearchQuery = query;
      }),

      // Execution actions
      setCurrentRun: (runId) => set((state) => {
        state.currentRunId = runId;
      }),
      setIsRunning: (running) => set((state) => {
        state.isRunning = running;
      }),
      updateNodeStatus: (nodeId, status) => set((state) => {
        state.nodeStatuses[nodeId] = status;
      }),
      clearNodeStatuses: () => set((state) => {
        state.nodeStatuses = {};
      }),
      setRuns: (runs) => set((state) => {
        state.runs = runs;
      }),
      addRun: (run) => set((state) => {
        state.runs.unshift(run);
      }),
      updateRun: (runId, updates) => set((state) => {
        const index = state.runs.findIndex((r) => r.id === runId);
        if (index !== -1) {
          state.runs[index] = { ...state.runs[index], ...updates };
        }
      }),
      setSelectedRunId: (runId) => set((state) => {
        state.selectedRunId = runId;
      }),

      // LLM Config actions
      setLLMConfigs: (configs) => set((state) => {
        state.llmConfigs = configs;
      }),
      addLLMConfig: (config) => set((state) => {
        state.llmConfigs.push(config);
      }),
      updateLLMConfig: (id, updates) => set((state) => {
        const index = state.llmConfigs.findIndex((c) => c.id === id);
        if (index !== -1) {
          state.llmConfigs[index] = { ...state.llmConfigs[index], ...updates };
        }
      }),
      deleteLLMConfig: (id) => set((state) => {
        state.llmConfigs = state.llmConfigs.filter((c) => c.id !== id);
      }),
    })),
    { name: 'GraphMindStore' }
  )
);

// Expose store for Playwright E2E tests (dev only, tree-shaken in prod)
if ((import.meta as any).env?.DEV) {
  (window as any).__appStore = useAppStore;
}
