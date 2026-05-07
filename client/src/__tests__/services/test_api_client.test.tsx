// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * API client tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '@/services/api/client';
import axios from 'axios';

// Mock axios
vi.mock('axios');
const mockedAxios = axios as any;

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Workspace Methods', () => {
    it('should get workspaces', async () => {
      const mockWorkspaces = [
        { id: '1', name: 'Test Workspace', transform: { x: 0, y: 0, k: 1 }, created_at: '', updated_at: '', version: 1 }
      ];
      
      mockedAxios.create.mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockWorkspaces })
      });

      const workspaces = await api.getWorkspaces();
      expect(workspaces).toBeDefined();
      expect(Array.isArray(workspaces)).toBe(true);
    });

    it('should create workspace', async () => {
      const mockWorkspace = { 
        id: '1', 
        name: 'New Workspace', 
        transform: { x: 0, y: 0, k: 1 },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      mockedAxios.create.mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: mockWorkspace })
      });

      const workspace = await api.createWorkspace({ name: 'New Workspace' });
      expect(workspace).toBeDefined();
      expect(workspace.name).toBe('New Workspace');
    });

    it('should get workspace by id', async () => {
      const mockWorkspace = {
        id: '1',
        name: 'Test',
        transform: { x: 0, y: 0, k: 1 },
        nodes: [],
        edges: [],
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      mockedAxios.create.mockReturnValue({
        get: vi.fn().mockResolvedValue({ data: mockWorkspace })
      });

      const workspace = await api.getWorkspace('1');
      expect(workspace).toBeDefined();
      expect(workspace.id).toBe('1');
    });

    it('should update workspace', async () => {
      const mockWorkspace = {
        id: '1',
        name: 'Updated',
        transform: { x: 0, y: 0, k: 1 },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      mockedAxios.create.mockReturnValue({
        patch: vi.fn().mockResolvedValue({ data: mockWorkspace })
      });

      const workspace = await api.updateWorkspace('1', { name: 'Updated' });
      expect(workspace.name).toBe('Updated');
    });

    it('should delete workspace', async () => {
      mockedAxios.create.mockReturnValue({
        delete: vi.fn().mockResolvedValue({ status: 204 })
      });

      await api.deleteWorkspace('1');
      // Should not throw
      expect(true).toBe(true);
    });

    it('should restore workspace', async () => {
      const mockWorkspace = {
        id: '1',
        name: 'Restored',
        transform: { x: 0, y: 0, k: 1 },
        created_at: '',
        updated_at: '',
        version: 1
      };
      
      mockedAxios.create.mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: mockWorkspace })
      });

      const workspace = await api.restoreWorkspace('1');
      expect(workspace).toBeDefined();
    });
  });

  describe('Node Methods', () => {
    it('should create node', async () => {
      const mockNode = {
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
      
      mockedAxios.create.mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: mockNode })
      });

      const node = await api.createNode('ws1', {
        node_type_id: 'input',
        x: 100,
        y: 200
      });
      expect(node).toBeDefined();
      expect(node.node_type_id).toBe('input');
    });

    it('should test node', async () => {
      const mockResult = {
        node_id: '1',
        node_type_id: 'input',
        status: 'success',
        output: 'test output',
        error: null,
        execution_time_ms: 10
      };
      
      mockedAxios.create.mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: mockResult })
      });

      const result = await api.testNode('ws1', 'node1');
      expect(result).toBeDefined();
      expect(result.status).toBe('success');
    });
  });

  describe('Edge Methods', () => {
    it('should create edge with weight', async () => {
      const mockEdge = {
        id: '1',
        workflow_id: 'ws1',
        source: 'node1',
        target: 'node2',
        weight: 0.75,
        created_at: ''
      };
      
      mockedAxios.create.mockReturnValue({
        post: vi.fn().mockResolvedValue({ data: mockEdge })
      });

      const edge = await api.createEdge('ws1', {
        source: 'node1',
        target: 'node2',
        weight: 0.75
      });
      expect(edge).toBeDefined();
      expect(edge.weight).toBe(0.75);
    });

    it('should update edge weight', async () => {
      const mockEdge = {
        id: '1',
        workflow_id: 'ws1',
        source: 'node1',
        target: 'node2',
        weight: 0.9,
        created_at: ''
      };
      
      mockedAxios.create.mockReturnValue({
        patch: vi.fn().mockResolvedValue({ data: mockEdge })
      });

      const edge = await api.updateEdge('ws1', 'edge1', { weight: 0.9 });
      expect(edge.weight).toBe(0.9);
    });
  });
});

