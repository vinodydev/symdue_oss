/**
 * State management tests
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '@/stores/useAppStore';

describe('App Store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useAppStore.setState({
      workspaces: [],
      currentWorkspaceId: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      selectedEdgeId: null,
      transform: { x: 0, y: 0, k: 1 },
      sidebarOpen: true,
      propertiesPanelOpen: false,
    });
  });

  describe('Initial State', () => {
    it('should initialize with default values', () => {
      const state = useAppStore.getState();
      expect(state.workspaces).toEqual([]);
      expect(state.nodes).toEqual([]);
      expect(state.edges).toEqual([]);
      expect(state.currentWorkspaceId).toBeNull();
      expect(state.selectedNodeId).toBeNull();
      expect(state.selectedEdgeId).toBeNull();
      expect(state.transform).toEqual({ x: 0, y: 0, k: 1 });
    });
  });

  describe('Workspace Actions', () => {
    it('should set workspaces', () => {
      const workspaces = [
        { id: '1', name: 'Test', transform: { x: 0, y: 0, k: 1 }, created_at: '', updated_at: '', version: 1 }
      ];
      
      useAppStore.getState().setWorkspaces(workspaces);
      expect(useAppStore.getState().workspaces).toEqual(workspaces);
    });

    it('should set current workspace', () => {
      useAppStore.getState().setCurrentWorkspace('workspace-1');
      expect(useAppStore.getState().currentWorkspaceId).toBe('workspace-1');
    });

    it('should add workspace', () => {
      const workspace = {
        id: '1',
        name: 'New',
        transform: { x: 0, y: 0, k: 1 },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      useAppStore.getState().addWorkspace(workspace);
      expect(useAppStore.getState().workspaces).toContainEqual(workspace);
    });

    it('should update workspace', () => {
      const workspace = {
        id: '1',
        name: 'Original',
        transform: { x: 0, y: 0, k: 1 },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      useAppStore.getState().addWorkspace(workspace);
      useAppStore.getState().updateWorkspace('1', { name: 'Updated' });
      
      expect(useAppStore.getState().workspaces[0].name).toBe('Updated');
    });

    it('should delete workspace', () => {
      const workspace = {
        id: '1',
        name: 'To Delete',
        transform: { x: 0, y: 0, k: 1 },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      useAppStore.getState().addWorkspace(workspace);
      useAppStore.getState().setCurrentWorkspace('1');
      useAppStore.getState().deleteWorkspace('1');
      
      expect(useAppStore.getState().workspaces).toHaveLength(0);
      expect(useAppStore.getState().currentWorkspaceId).toBeNull();
    });
  });

  describe('Node Actions', () => {
    it('should add node', () => {
      const node = {
        id: '1',
        workflow_id: 'ws1',
        node_type_id: 'input',
        x: 100,
        y: 200,
        config: {},
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      useAppStore.getState().addNode(node);
      expect(useAppStore.getState().nodes).toContainEqual(node);
    });

    it('should update node', () => {
      const node = {
        id: '1',
        workflow_id: 'ws1',
        node_type_id: 'input',
        x: 100,
        y: 200,
        config: { name: 'Original' },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      useAppStore.getState().addNode(node);
      useAppStore.getState().updateNode('1', { config: { name: 'Updated' } });
      
      expect(useAppStore.getState().nodes[0].config.name).toBe('Updated');
    });

    it('should delete node and connected edges', () => {
      const node = {
        id: 'node1',
        workflow_id: 'ws1',
        node_type_id: 'input',
        x: 0,
        y: 0,
        config: {},
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      const edge = {
        id: 'edge1',
        workflow_id: 'ws1',
        source: 'node1',
        target: 'node2',
        weight: 1.0,
        created_at: ''
      };
      
      useAppStore.getState().addNode(node);
      useAppStore.getState().addEdge(edge);
      useAppStore.getState().setSelectedNode('node1');
      
      useAppStore.getState().deleteNode('node1');
      
      expect(useAppStore.getState().nodes).toHaveLength(0);
      expect(useAppStore.getState().edges).toHaveLength(0);
      expect(useAppStore.getState().selectedNodeId).toBeNull();
    });
  });

  describe('Edge Actions', () => {
    it('should add edge', () => {
      const edge = {
        id: '1',
        workflow_id: 'ws1',
        source: 'node1',
        target: 'node2',
        weight: 0.75,
        created_at: ''
      };
      
      useAppStore.getState().addEdge(edge);
      expect(useAppStore.getState().edges).toContainEqual(edge);
    });

    it('should update edge', () => {
      const edge = {
        id: '1',
        workflow_id: 'ws1',
        source: 'node1',
        target: 'node2',
        weight: 0.5,
        created_at: ''
      };
      
      useAppStore.getState().addEdge(edge);
      useAppStore.getState().updateEdge('1', { weight: 0.9 });
      
      expect(useAppStore.getState().edges[0].weight).toBe(0.9);
    });

    it('should delete edge', () => {
      const edge = {
        id: 'edge1',
        workflow_id: 'ws1',
        source: 'node1',
        target: 'node2',
        weight: 1.0,
        created_at: ''
      };
      
      useAppStore.getState().addEdge(edge);
      useAppStore.getState().setSelectedEdge('edge1');
      useAppStore.getState().deleteEdge('edge1');
      
      expect(useAppStore.getState().edges).toHaveLength(0);
      expect(useAppStore.getState().selectedEdgeId).toBeNull();
    });
  });

  describe('Selection Actions', () => {
    it('should select node and deselect edge', () => {
      useAppStore.getState().setSelectedEdge('edge1');
      useAppStore.getState().setSelectedNode('node1');
      
      expect(useAppStore.getState().selectedNodeId).toBe('node1');
      expect(useAppStore.getState().selectedEdgeId).toBeNull();
    });

    it('should select edge and deselect node', () => {
      useAppStore.getState().setSelectedNode('node1');
      useAppStore.getState().setSelectedEdge('edge1');
      
      expect(useAppStore.getState().selectedEdgeId).toBe('edge1');
      expect(useAppStore.getState().selectedNodeId).toBeNull();
    });
  });

  describe('Transform Actions', () => {
    it('should update transform', () => {
      const newTransform = { x: 100, y: 200, k: 1.5 };
      useAppStore.getState().setTransform(newTransform);
      
      expect(useAppStore.getState().transform).toEqual(newTransform);
    });
  });
});

