// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * TypeScript types for GraphMind Orchestrator
 */

export interface Workflow {
  id: string;
  name: string;
  transform: { x: number; y: number; k: number };
  created_at: string;
  updated_at: string;
  version: number;
  deleted_at?: string | null;
}

export interface WorkflowDetail extends Workflow {
  nodes: Node[];
  edges: Edge[];
}

export interface Node {
  id: string;
  workflow_id: string;
  node_type_id: string;
  name: string;
  x: number;
  y: number;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface Edge {
  id: string;
  workflow_id: string;
  source: string;
  target: string;
  weight: number;
  source_handle?: 'true' | 'false';
  created_at: string;
}

export interface NodeType {
  id: string;
  category: string;
  name: string;
  description: string | null;
  icon: string | null;
  default_config?: Record<string, any> | null;
  config_schema: Record<string, any> | null;
  is_builtin: boolean;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  // Template-specific fields
  type_kind?: 'node_type' | 'node_template' | 'workflow_template';
  node_template_data?: Record<string, any>;
  workflow_template_data?: Record<string, any>;
  workflow_env_template?: Record<string, any>;
  node_env_template?: Record<string, any>;
  input_ports?: Array<{ node_id: string; node_name: string; node_type_id: string; description: string }>;
  output_ports?: Array<{ node_id: string; node_name: string; node_type_id: string; description: string }>;
  is_public?: boolean;
  usage_count?: number;
  /** For workflow_template: id of the workflow to open in editor */
  workflow_id?: string;
}

/** Partial update payload for node type (PUT /api/node-types/:id) */
export interface NodeTypeUpdate {
  name?: string;
  description?: string | null;
  icon?: string | null;
  category?: string;
  default_config?: Record<string, any>;
  config_schema?: Record<string, any> | null;
  is_public?: boolean;
}

export interface Run {
  id: string;
  workflow_id: string;
  temporal_workflow_id: string | null;
  parent_run_id?: string | null;
  parent_workflow_id?: string | null;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'cancellation_requested' | 'paused' | 'queued' | 'partial' | 'waiting';
  label: string | null;
  started_at: string;
  completed_at: string | null;
  duration: number | null;
  error_message: string | null;
  snapshot: Record<string, any>;
}

export interface LLMConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url: string | null;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkspaceRequest {
  name?: string;
}

export interface UpdateWorkspaceRequest {
  name?: string;
  transform?: { x: number; y: number; k: number };
}

/** Workflow export/import JSON format (same shape for export response and import request). */
export interface WorkflowExportPayload {
  version: number;
  name: string;
  transform?: { x: number; y: number; k: number };
  workflow_config?: Record<string, string>;
  nodes: Array<{
    id: string;
    name: string;
    node_type_id: string;
    ui_x: number;
    ui_y: number;
    config?: Record<string, any>;
    node_config?: Record<string, any>;
  }>;
  edges: Array<{
    source_node_id: string;
    target_node_id: string;
    weight?: number;
  }>;
}

export type WorkflowImportPayload = WorkflowExportPayload;

export interface CreateNodeRequest {
  node_type_id: string;
  name?: string;
  x: number;
  y: number;
  config_overrides?: Record<string, any>;
}

export interface UpdateNodeRequest {
  node_type_id?: string;
  name?: string;
  x?: number;
  y?: number;
  config?: Record<string, any>;
}

export interface UpdateNodePositionRequest {
  x: number;
  y: number;
}

export interface CreateEdgeRequest {
  source: string;
  target: string;
  weight?: number;
  source_handle?: 'true' | 'false';
}

export interface UpdateEdgeRequest {
  weight?: number;
  source_handle?: 'true' | 'false';
}

export interface CreateRunRequest {
  inputs?: Record<string, any>;
  label?: string;
  /** Optional external input dict for edge nodes (keys = node name or external_input_key). Used when running workflow standalone. */
  external_input?: Record<string, any>;
}

/** Request to create a new run that resumes from a previous run's checkpoint. */
export interface ResumeRunFromRequest {
  from_run_id: string;
  inputs?: Record<string, any>;
  start_from_node_id?: string;
}

export type NodeStatus = 'idle' | 'running' | 'success' | 'error';

export interface WebSocketMessage {
  type: string;
  run_id?: string;
  node_id?: string;
  status?: NodeStatus;
  timestamp?: string;
  data?: Record<string, any>;
}

export interface StorageConfig {
  id: string;
  name: string;
  storage_type: 'postgresql' | 'redis' | 'mongodb' | 'chroma' | 'local_file' | 'minio' | 's3';
  config: Record<string, any>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateStorageConfigRequest {
  name: string;
  storage_type: StorageConfig['storage_type'];
  config: Record<string, any>;
  enabled?: boolean;
}

export interface UpdateStorageConfigRequest {
  name?: string;
  config?: Record<string, any>;
  enabled?: boolean;
}

export interface StorageReference {
  storage_id: string;
  alias?: string;
}

export interface NodeStorageInfo {
  storage_id: string;
  storage_name: string;
  storage_type: string;
  alias?: string;
}

// Template-related types
export interface SaveNodeAsTemplateRequest {
  template_name: string;
  template_description?: string;
  is_public: boolean;
}

export interface SaveWorkflowAsTemplateRequest {
  template_name: string;
  template_description?: string;
  is_public: boolean;
}

export interface CreateNodeFromTemplateRequest {
  template_id: string;
  node_name: string;
  workflow_env?: Record<string, string>;
  node_env?: Record<string, string>;
}

export interface CreateNodeFromTemplateRequest {
  template_id: string;
  node_name: string;
  workflow_env?: Record<string, string>;
  node_env?: Record<string, string>;
  storages?: Array<{ alias: string; storage_id: string }>;
  requirements?: string;
  config_overrides?: Record<string, any>;
}

export interface CreateWorkflowFromTemplateRequest {
  template_id: string;
  workflow_name: string;
  workflow_env?: Record<string, string>;
}

export interface CreateSubWorkflowNodeRequest {
  template_id: string;
  node_name: string;
  workflow_env?: Record<string, string>;
  storage_mapping?: Record<string, string>;
}

/** Add an existing workflow as a node (reference, not copy). Opens that workflow on double-click. */
export interface CreateWorkflowReferenceNodeRequest {
  workflow_id: string;
  node_name: string;
  x?: number;
  y?: number;
}

/** Edge node: has use_input_from_parent; key is used in external_input / parent input dict. */
export interface EdgeNodeInfo {
  node_id: string;
  node_name: string;
  key: string;
}

// ── Wait node / Signal types ──────────────────────────────────────────────
export type { WaitMode, WaitNodeConfig, WaitStateResponse } from './wait';

// ── Event types ───────────────────────────────────────────────────────────
export type {
  EventType,
  Event as FlowEvent,
  EventCreate,
  EventUpdate,
  EventInvocation,
  EventInvocationDetail,
} from './event';

