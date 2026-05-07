// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * API client for GraphMind Orchestrator backend
 */
import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  Workflow,
  WorkflowDetail,
  Node,
  Edge,
  NodeType,
  Run,
  LLMConfig,
  StorageConfig,
  CreateStorageConfigRequest,
  UpdateStorageConfigRequest,
  NodeStorageInfo,
  CreateWorkspaceRequest,
  UpdateWorkspaceRequest,
  CreateNodeRequest,
  UpdateNodeRequest,
  UpdateNodePositionRequest,
  CreateEdgeRequest,
  UpdateEdgeRequest,
  CreateRunRequest,
  ResumeRunFromRequest,
  WorkflowExportPayload,
  WorkflowImportPayload,
  WaitStateResponse,
  FlowEvent,
  EventCreate,
  EventUpdate,
  EventInvocation,
  EventInvocationDetail,
} from '@/types';

// Use relative path to leverage Vite proxy, or use env var if set
const API_URL = import.meta.env.VITE_API_URL || '';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL, // Empty string = relative paths, will use Vite proxy
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // ========== Workspace Endpoints ==========
  async getWorkspaces(includeDeleted = false): Promise<Workflow[]> {
    const response = await this.client.get('/api/workspaces', {
      params: { include_deleted: includeDeleted },
    });
    return response.data;
  }

  async getWorkspace(id: string): Promise<WorkflowDetail> {
    const response = await this.client.get(`/api/workspaces/${id}`);
    return response.data;
  }

  /** List nodes with "Use input from parent" (edge nodes). Used for Expected input keys and Run external input UI. */
  async getWorkflowEdgeNodes(workspaceId: string): Promise<{ edge_nodes: import('@/types').EdgeNodeInfo[] }> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/edge-nodes`);
    return response.data;
  }

  async createWorkspace(data: CreateWorkspaceRequest): Promise<Workflow> {
    const response = await this.client.post('/api/workspaces', data);
    return response.data;
  }

  async updateWorkspace(id: string, data: UpdateWorkspaceRequest): Promise<Workflow> {
    const response = await this.client.patch(`/api/workspaces/${id}`, data);
    return response.data;
  }

  async deleteWorkspace(id: string): Promise<void> {
    await this.client.delete(`/api/workspaces/${id}`);
  }

  async restoreWorkspace(id: string): Promise<Workflow> {
    const response = await this.client.post(`/api/workspaces/${id}/restore`);
    return response.data;
  }

  /** Export workflow as JSON (downloadable format). */
  async exportWorkflow(workspaceId: string): Promise<WorkflowExportPayload> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/export`);
    return response.data;
  }

  /** Import workflow from JSON; creates a new workflow and returns it. */
  async importWorkflow(payload: WorkflowImportPayload): Promise<Workflow> {
    const response = await this.client.post('/api/workspaces/import', payload);
    return response.data;
  }

  // ========== Node Endpoints ==========
  async getNodes(workspaceId: string): Promise<Node[]> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/nodes`);
    return response.data;
  }

  async getNode(workspaceId: string, nodeId: string): Promise<Node> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/nodes/${nodeId}`);
    return response.data;
  }

  async createNode(workspaceId: string, data: CreateNodeRequest): Promise<Node> {
    // Map config to config_overrides for API compatibility
    const payload = {
      node_type_id: data.node_type_id,
      name: data.name,
      x: data.x,
      y: data.y,
      config_overrides: data.config_overrides || data.config || {},
    };
    const response = await this.client.post(`/api/workspaces/${workspaceId}/nodes`, payload);
    return response.data;
  }

  async updateNode(workspaceId: string, nodeId: string, data: UpdateNodeRequest): Promise<Node> {
    const response = await this.client.patch(`/api/workspaces/${workspaceId}/nodes/${nodeId}`, data);
    return response.data;
  }

  async updateNodePosition(workspaceId: string, nodeId: string, data: UpdateNodePositionRequest): Promise<Node> {
    const response = await this.client.patch(`/api/workspaces/${workspaceId}/nodes/${nodeId}/position`, data);
    return response.data;
  }

  async deleteNode(workspaceId: string, nodeId: string): Promise<void> {
    await this.client.delete(`/api/workspaces/${workspaceId}/nodes/${nodeId}`);
  }

  async testNode(workspaceId: string, nodeId: string, testInputs?: Record<string, any>): Promise<{
    node_id: string;
    node_type_id: string;
    status: 'success' | 'error' | 'pending';
    output: any;
    error: string | null;
    execution_time_ms: number;
  }> {
    const response = await this.client.post(
      `/api/workspaces/${workspaceId}/nodes/${nodeId}/test`,
      testInputs || {}
    );
    return response.data;
  }

  // ========== Edge Endpoints ==========
  async getEdges(workspaceId: string): Promise<Edge[]> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/edges`);
    return response.data;
  }

  async getEdge(workspaceId: string, edgeId: string): Promise<Edge> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/edges/${edgeId}`);
    return response.data;
  }

  async createEdge(workspaceId: string, data: CreateEdgeRequest): Promise<Edge> {
    const response = await this.client.post(`/api/workspaces/${workspaceId}/edges`, data);
    return response.data;
  }

  async updateEdge(workspaceId: string, edgeId: string, data: UpdateEdgeRequest): Promise<Edge> {
    const response = await this.client.patch(`/api/workspaces/${workspaceId}/edges/${edgeId}`, data);
    return response.data;
  }

  async deleteEdge(workspaceId: string, edgeId: string): Promise<void> {
    await this.client.delete(`/api/workspaces/${workspaceId}/edges/${edgeId}`);
  }

  // ========== Run Endpoints ==========

  /** Normalize backend RunResponse (run_id → id, status names) to frontend Run type */
  private normalizeRun(data: any): Run {
    return {
      ...data,
      id: data.run_id || data.id,
      status: this.mapRunStatus(data.status),
    };
  }

  /** Map backend status names to frontend status names */
  private mapRunStatus(status: string): Run['status'] {
    const map: Record<string, Run['status']> = {
      queued: 'queued',
      running: 'running',
      paused: 'paused',
      waiting: 'waiting',
      success: 'completed',
      completed: 'completed',
      error: 'failed',
      failed: 'failed',
      cancelled: 'cancelled',
      partial: 'partial',
      cancellation_requested: 'cancellation_requested',
    };
    return map[status] || 'running';
  }

  async getRuns(workspaceId: string): Promise<Run[]> {
    const response = await this.client.get(`/api/runs/${workspaceId}`);
    return (response.data || []).map((r: any) => this.normalizeRun(r));
  }

  async getRun(workspaceId: string, runId: string): Promise<Run> {
    const response = await this.client.get(`/api/runs/${workspaceId}/${runId}`);
    return this.normalizeRun(response.data);
  }

  async createRun(workspaceId: string, data: CreateRunRequest): Promise<Run> {
    const response = await this.client.post(`/api/runs/${workspaceId}`, data);
    return this.normalizeRun(response.data);
  }

  async cancelRun(workspaceId: string, runId: string): Promise<Run> {
    const response = await this.client.post(`/api/runs/${workspaceId}/${runId}/cancel`);
    return this.normalizeRun(response.data);
  }

  async pauseRun(workspaceId: string, runId: string): Promise<Run> {
    const response = await this.client.post(`/api/runs/${workspaceId}/${runId}/pause`);
    return this.normalizeRun(response.data);
  }

  async resumeRun(workspaceId: string, runId: string): Promise<Run> {
    const response = await this.client.post(`/api/runs/${workspaceId}/${runId}/resume`);
    return this.normalizeRun(response.data);
  }

  /** Create a new run that resumes from a previous run's checkpoint (skips completed nodes). */
  async resumeRunFromCheckpoint(workspaceId: string, data: ResumeRunFromRequest): Promise<Run> {
    const response = await this.client.post(`/api/runs/${workspaceId}/resume-from`, data);
    return this.normalizeRun(response.data);
  }

  // ========== Node Type Endpoints ==========
  async getNodeTypes(category?: string, isBuiltin?: boolean, typeKind?: string): Promise<NodeType[]> {
    const response = await this.client.get('/api/node-types', {
      params: { category, is_builtin: isBuiltin, type_kind: typeKind },
    });
    return response.data;
  }

  async getNodeType(nodeTypeId: string): Promise<NodeType> {
    const response = await this.client.get(`/api/node-types/${nodeTypeId}`);
    return response.data;
  }

  async updateNodeType(nodeTypeId: string, data: import('@/types').NodeTypeUpdate): Promise<NodeType> {
    const response = await this.client.put(`/api/node-types/${nodeTypeId}`, data);
    return response.data;
  }

  async deleteNodeType(nodeTypeId: string): Promise<void> {
    await this.client.delete(`/api/node-types/${nodeTypeId}`);
  }

  async createTemplateEditCopy(nodeTypeId: string): Promise<{ workflow_id: string }> {
    const response = await this.client.post(`/api/node-types/${nodeTypeId}/create-edit-copy`);
    return response.data;
  }

  async saveTemplateFromWorkflow(nodeTypeId: string, workflowId: string): Promise<NodeType> {
    const response = await this.client.post(`/api/node-types/${nodeTypeId}/save-template-from-workflow`, { workflow_id: workflowId });
    return response.data;
  }

  async syncTemplateFromWorkflow(nodeTypeId: string): Promise<NodeType> {
    const response = await this.client.post(`/api/node-types/${nodeTypeId}/sync-from-workflow`);
    return response.data;
  }

  async createNodeType(data: Partial<NodeType>): Promise<NodeType> {
    const response = await this.client.post('/api/node-types', data);
    return response.data;
  }

  // ========== LLM Config Endpoints ==========
  async getLLMConfigs(includeDeleted = false): Promise<LLMConfig[]> {
    const response = await this.client.get('/api/llm-configs', {
      params: { include_deleted: includeDeleted },
    });
    return response.data;
  }

  async getLLMConfig(id: string): Promise<LLMConfig> {
    const response = await this.client.get(`/api/llm-configs/${id}`);
    return response.data;
  }

  async createLLMConfig(data: Partial<LLMConfig>): Promise<LLMConfig> {
    const response = await this.client.post('/api/llm-configs', data);
    return response.data;
  }

  async updateLLMConfig(id: string, data: Partial<LLMConfig>): Promise<LLMConfig> {
    const response = await this.client.put(`/api/llm-configs/${id}`, data);
    return response.data;
  }

  async deleteLLMConfig(id: string): Promise<void> {
    await this.client.delete(`/api/llm-configs/${id}`);
  }

  async restoreLLMConfig(id: string): Promise<LLMConfig> {
    const response = await this.client.post(`/api/llm-configs/${id}/restore`);
    return response.data;
  }

  // ========== Storage Config Endpoints ==========
  async getStorageConfigs(): Promise<StorageConfig[]> {
    const response = await this.client.get('/api/storage');
    return response.data;
  }

  async getStorageConfig(id: string): Promise<StorageConfig> {
    const response = await this.client.get(`/api/storage/${id}`);
    return response.data;
  }

  async createStorageConfig(data: CreateStorageConfigRequest): Promise<StorageConfig> {
    const response = await this.client.post('/api/storage', data);
    return response.data;
  }

  async updateStorageConfig(id: string, data: UpdateStorageConfigRequest): Promise<StorageConfig> {
    const response = await this.client.put(`/api/storage/${id}`, data);
    return response.data;
  }

  async deleteStorageConfig(id: string): Promise<void> {
    await this.client.delete(`/api/storage/${id}`);
  }

  // ========== Node-Storage Management ==========
  async attachStorageToNode(nodeId: string, storageId: string, alias?: string): Promise<void> {
    const params = new URLSearchParams();
    params.append('storage_id', storageId);
    if (alias) {
      params.append('alias', alias);
    }
    await this.client.post(`/api/storage/nodes/${nodeId}/storages?${params.toString()}`);
  }

  async getNodeStorages(nodeId: string): Promise<NodeStorageInfo[]> {
    const response = await this.client.get(`/api/storage/nodes/${nodeId}/storages`);
    return response.data;
  }

  async detachStorageFromNode(nodeId: string, storageId: string): Promise<void> {
    await this.client.delete(`/api/storage/nodes/${nodeId}/storages/${storageId}`);
  }

  // ========== Template Endpoints ==========
  async saveNodeAsTemplate(nodeId: string, data: import('@/types').SaveNodeAsTemplateRequest): Promise<{
    node_type_id: string;
    workflow_env_vars: string[];
    node_env_vars: string[];
  }> {
    const response = await this.client.post(`/api/node-types/from-node/${nodeId}`, data);
    return response.data;
  }

  async saveWorkflowAsTemplate(workflowId: string, data: import('@/types').SaveWorkflowAsTemplateRequest): Promise<{
    node_type_id: string;
    workflow_env_vars: string[];
    input_ports: any[];
    output_ports: any[];
    storage_requirements?: Record<string, any>;
  }> {
    const response = await this.client.post(`/api/node-types/from-workflow/${workflowId}`, data);
    return response.data;
  }

  async createNodeFromTemplate(workspaceId: string, data: import('@/types').CreateNodeFromTemplateRequest): Promise<Node> {
    const response = await this.client.post(`/api/workspaces/${workspaceId}/nodes/from-template`, data);
    return response.data;
  }

  async createWorkflowFromTemplate(data: import('@/types').CreateWorkflowFromTemplateRequest): Promise<Workflow> {
    const response = await this.client.post('/api/workspaces/from-template', data);
    return response.data;
  }

  async createSubWorkflowNode(workspaceId: string, data: import('@/types').CreateSubWorkflowNodeRequest): Promise<Node> {
    const response = await this.client.post(`/api/workspaces/${workspaceId}/nodes/from-workflow-template`, data);
    return response.data;
  }

  /** Add an existing workflow as a node (reference). Double-click opens that workflow. */
  async createWorkflowReferenceNode(workspaceId: string, data: import('@/types').CreateWorkflowReferenceNodeRequest): Promise<Node> {
    const response = await this.client.post(`/api/workspaces/${workspaceId}/nodes/workflow-reference`, data);
    return response.data;
  }

  // ========== Workflow Config Endpoints ==========
  async getWorkflowConfig(workspaceId: string): Promise<{ workflow_id: string; config: Record<string, string> }> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/config`);
    return response.data;
  }

  async updateWorkflowConfig(workspaceId: string, config: Record<string, string>): Promise<{ workflow_id: string; config: Record<string, string> }> {
    const response = await this.client.put(`/api/workspaces/${workspaceId}/config`, { config });
    return response.data;
  }

  async getExecutionConfig(workspaceId: string): Promise<{ workflow_id: string; execution_config: Record<string, number> }> {
    const response = await this.client.get(`/api/workspaces/${workspaceId}/execution-config`);
    return response.data;
  }

  async updateExecutionConfig(
    workspaceId: string,
    execution_config: Record<string, number>
  ): Promise<{ workflow_id: string; execution_config: Record<string, number> }> {
    const response = await this.client.put(`/api/workspaces/${workspaceId}/execution-config`, {
      execution_config,
    });
    return response.data;
  }

  async updateNodeConfig(workspaceId: string, nodeId: string, nodeConfig: Record<string, string>): Promise<{ node_id: string; node_config: Record<string, string> }> {
    const response = await this.client.put(`/api/workspaces/${workspaceId}/nodes/${nodeId}/config`, { node_config: nodeConfig });
    return response.data;
  }

  // ========== Signal / Wait Endpoints ==========

  async emitToChannel(channel: string, signal: string, data?: any): Promise<{ delivered_to: number; channel: string; message: string }> {
    const response = await this.client.post(`/api/signals/${channel}`, { signal, data });
    return response.data;
  }

  async sendSignalToRun(runId: string, _workspaceId: string, signal: string, data?: any): Promise<{ delivered_to: number; channel: string; message: string }> {
    const response = await this.client.post(`/api/runs/${runId}/signal`, { signal, data });
    return response.data;
  }

  async getRunWaits(_workspaceId: string, runId: string): Promise<WaitStateResponse[]> {
    const response = await this.client.get(`/api/runs/${runId}/waits`);
    return response.data;
  }

  // ========== Event Endpoints ==========

  async getEvents(): Promise<FlowEvent[]> {
    const response = await this.client.get('/api/events');
    return response.data;
  }

  async createEvent(spec: EventCreate): Promise<FlowEvent> {
    const response = await this.client.post('/api/events', spec);
    return response.data;
  }

  async getEvent(id: string): Promise<FlowEvent> {
    const response = await this.client.get(`/api/events/${id}`);
    return response.data;
  }

  async updateEvent(id: string, spec: EventUpdate): Promise<FlowEvent> {
    const response = await this.client.patch(`/api/events/${id}`, spec);
    return response.data;
  }

  async deleteEvent(id: string): Promise<void> {
    await this.client.delete(`/api/events/${id}`);
  }

  async triggerEvent(id: string, input?: any): Promise<EventInvocationDetail> {
    const response = await this.client.post(`/api/events/${id}/trigger`, input ?? {});
    return response.data;
  }

  async enableEvent(id: string): Promise<FlowEvent> {
    const response = await this.client.post(`/api/events/${id}/enable`);
    return response.data;
  }

  async disableEvent(id: string): Promise<FlowEvent> {
    const response = await this.client.post(`/api/events/${id}/disable`);
    return response.data;
  }

  async getEventInvocations(eventId: string, limit = 20, offset = 0): Promise<EventInvocation[]> {
    const response = await this.client.get(`/api/events/${eventId}/invocations`, {
      params: { limit, offset },
    });
    return response.data;
  }

  async getEventInvocation(eventId: string, invocationId: string): Promise<EventInvocationDetail> {
    const response = await this.client.get(`/api/events/${eventId}/invocations/${invocationId}`);
    return response.data;
  }
}

export const api = new ApiClient();
