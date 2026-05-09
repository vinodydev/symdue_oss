// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Node properties editor - Matching reference design
 * Includes execution status display during/after graph runs.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { Node, NodeStatus, StorageConfig, NodeStorageInfo, NodeType } from '@/types';
import { Trash2, Database, Code, Cpu, History, Loader2, CheckCircle2, XCircle, Clock, Plus, X, Save, Copy, Check, Maximize2, Workflow, ExternalLink, Eye } from 'lucide-react';
import { WaitNodeProperties } from './WaitNodeProperties';
import { cn } from '@/utils/cn';
import { StorageSelectorModal } from './StorageSelectorModal';
import { OutputModal } from './OutputModal';
import { ExpandableCodeModal } from './ExpandableCodeModal';
import { ExpandableTextModal } from './ExpandableTextModal';
import { HtmlPreviewModal } from './HtmlPreviewModal';
import { PythonCodeEditor, type CodeEditorHandle } from './PythonCodeEditor';
import { IteratorConfig } from './IteratorConfig';
import { supportsIterator } from '@/utils/nodeUtils';
import { SaveNodeAsTemplateDialog } from '../Node/SaveNodeAsTemplateDialog';

interface NodePropertiesProps {
  node: Node;
}

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'input': Database,
  'custom-python': Code,
  'condition-python': Code,
  'custom-llm': Cpu,
  'memory': History,
  'workflow_node': Workflow,
  'html-viewer': Eye,
};

/** Extract HTML content from a raw string for the html-viewer preview (issue17).
 * LLMs commonly wrap output in fenced code blocks (```html ... ```); pull the
 * fenced content if present, otherwise return the raw string. Trim whitespace.
 * Accepts unknown so the modal-mount path doesn't crash for non-html-viewer
 * nodes whose output is an object. */
function extractHtmlForPreview(raw: unknown): string {
  if (typeof raw !== 'string' || !raw) return '';
  const fenceMatch = raw.match(/```(?:html)?\s*\n?([\s\S]*?)\n?```/i);
  return (fenceMatch ? fenceMatch[1] : raw).trim();
}

/** Small badge showing node execution status */
function StatusBadge({ status }: { status: NodeStatus }) {
  if (status === 'idle') return null;

  const statusConfig: Record<NodeStatus, { icon: React.ReactNode; label: string; color: string }> = {
    idle: { icon: null, label: '', color: '' },
    running: {
      icon: <Loader2 size={14} className="animate-spin" />,
      label: 'Executing…',
      color: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    },
    success: {
      icon: <CheckCircle2 size={14} />,
      label: 'Completed',
      color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    },
    error: {
      icon: <XCircle size={14} />,
      label: 'Failed',
      color: 'text-red-400 bg-red-500/10 border-red-500/30',
    },
  };

  const cfg = statusConfig[status];
  if (!cfg) return null;

  return (
    <div className={cn('flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-bold', cfg.color)}>
      {cfg.icon}
      <span>{cfg.label}</span>
    </div>
  );
}

export function NodeProperties({ node }: NodePropertiesProps) {
  const { 
    currentWorkspaceId, 
    updateNode, 
    setSelectedNode, 
    setPropertiesPanelOpen, 
    setCurrentWorkspace,
    setCurrentView,
    setRuns,
    llmConfigs, 
    nodeStatuses, 
    isRunning,
    selectedRunId,
    currentRunId,
    runs,
    nodes,
    edges
  } = useAppStore();
  const [name, setName] = useState(node.name || '');
  const [config, setConfig] = useState(node.config || {});
  const [availableStorages, setAvailableStorages] = useState<StorageConfig[]>([]);
  const [nodeStorages, setNodeStorages] = useState<NodeStorageInfo[]>([]);
  const [showStorageSelector, setShowStorageSelector] = useState(false);
  const [loadingStorages, setLoadingStorages] = useState(false);
  const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
  const [showSaveTemplateDialog, setShowSaveTemplateDialog] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<'inputs' | 'outputs' | 'pythonCode' | 'inputValue' | 'prompt' | 'requirements' | 'htmlPreview' | null>(null);
  const [edgeNodesOfRefWorkflow, setEdgeNodesOfRefWorkflow] = useState<{ node_id: string; node_name: string; key: string }[]>([]);
  const codeEditorGetValueRef = useRef<CodeEditorHandle | null>(null);

  const copyToClipboard = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }).catch(() => {});
  }, []);

  const status: NodeStatus = nodeStatuses[node.id] || 'idle';
  
  // History mode: get historical data from selected run
  const selectedRun = selectedRunId ? runs.find(r => r.id === selectedRunId) : null;
  const isHistoryMode = !!selectedRunId && !!selectedRun;
  const historicalInputs = selectedRun?.snapshot?.node_inputs?.[node.id];
  const historicalOutputs = selectedRun?.snapshot?.node_outputs?.[node.id];
  // Per-iteration history (issue9): list of {step, ts, output} entries — one per node call.
  // Empty/missing for older runs (pre-fix) or non-looping nodes.
  const historicalIterations =
    (selectedRun?.snapshot?.node_iteration_outputs?.[node.id] as
      | Array<{ step?: number; ts?: number; output?: unknown }>
      | undefined) || [];

  // Build a copy/expand-friendly text rendering of all iterations.
  // Used by both the inline copy button and the expand modal so they show
  // identical content. Falls back to a single-output JSON for non-looping nodes.
  const formatIterationsForCopy = (): string => {
    if (historicalIterations.length > 1) {
      return historicalIterations
        .map((entry, i) => {
          const ts =
            entry.ts !== undefined ? new Date(entry.ts * 1000).toLocaleString() : '?';
          const step = entry.step !== undefined ? `step ${entry.step}` : '';
          const header = `=== Call #${i + 1} · ${step}${step ? ' · ' : ''}${ts} ===`;
          return `${header}\n${JSON.stringify(entry.output, null, 2)}`;
        })
        .join('\n\n');
    }
    return historicalOutputs ? JSON.stringify(historicalOutputs, null, 2) : '';
  };

  // Live run mode: show outputs for finished nodes during execution (from refetched current run)
  const activeRun = currentRunId && isRunning ? runs.find(r => r.id === currentRunId) : null;
  const liveInputs = activeRun?.snapshot?.node_inputs?.[node.id];
  const liveOutputs = activeRun?.snapshot?.node_outputs?.[node.id];

  useEffect(() => {
    setName(node.name || '');
    setConfig(node.config || {});
  }, [node.id, node.name, node.config]);

  // Load node types on mount
  useEffect(() => {
    const loadNodeTypes = async () => {
      try {
        const types = await api.getNodeTypes();
        setNodeTypes(types);
      } catch (error) {
        console.error('Failed to load node types:', error);
      }
    };
    loadNodeTypes();
  }, []);

  // Load edge nodes of referenced workflow when this is a workflow_node
  useEffect(() => {
    if (node.node_type_id === 'workflow_node' && node.config?.workflow_id) {
      api.getWorkflowEdgeNodes(node.config.workflow_id)
        .then((r) => setEdgeNodesOfRefWorkflow(r.edge_nodes || []))
        .catch(() => setEdgeNodesOfRefWorkflow([]));
    } else {
      setEdgeNodesOfRefWorkflow([]);
    }
  }, [node.node_type_id, node.config?.workflow_id]);

  // Load storages when node changes
  useEffect(() => {
    if (node.node_type_id === 'custom-python' || node.node_type_id === 'condition-python') {
      loadStorages();
      loadNodeStorages();
    }
  }, [node.id, node.node_type_id]);

  // Check if this node type supports iterator
  // Fallback: if node types haven't loaded yet, check if it's a known iterator-supporting type
  const nodeTypeSupportsIterator = nodeTypes.length > 0 
    ? supportsIterator(node.node_type_id, nodeTypes)
    : (node.node_type_id === 'custom-llm' || node.node_type_id === 'custom-python' || node.node_type_id === 'condition-python');
  
  // Debug logging (remove after verification)
  useEffect(() => {
    console.log('Iterator support check:', {
      nodeTypeId: node.node_type_id,
      nodeTypesCount: nodeTypes.length,
      nodeTypeFound: nodeTypes.find(nt => nt.id === node.node_type_id),
      nodeTypeSchema: nodeTypes.find(nt => nt.id === node.node_type_id)?.config_schema,
      supportsIterator: nodeTypeSupportsIterator,
      fallbackMode: nodeTypes.length === 0
    });
  }, [node.node_type_id, nodeTypes, nodeTypeSupportsIterator]);

  const loadStorages = async () => {
    try {
      setLoadingStorages(true);
      const storages = await api.getStorageConfigs();
      setAvailableStorages(storages.filter((s) => s.enabled));
    } catch (error) {
      console.error('Failed to load storages:', error);
    } finally {
      setLoadingStorages(false);
    }
  };

  const loadNodeStorages = async () => {
    try {
      const storages = await api.getNodeStorages(node.id);
      setNodeStorages(storages);
    } catch (error) {
      console.error('Failed to load node storages:', error);
    }
  };

  const handleAttachStorage = async (storageId: string, alias: string) => {
    console.log('handleAttachStorage called', { storageId, alias, currentWorkspaceId, nodeId: node.id });
    if (!currentWorkspaceId) {
      console.error('No currentWorkspaceId');
      return;
    }

    try {
      console.log('Calling api.attachStorageToNode...');
      await api.attachStorageToNode(node.id, storageId, alias || undefined);
      await loadNodeStorages();
      // Reload node to get updated config
      const updatedNode = await api.getNode(currentWorkspaceId, node.id);
      updateNode(node.id, updatedNode);
      setConfig(updatedNode.config || {});
      setShowStorageSelector(false);
    } catch (error) {
      console.error('Failed to attach storage:', error);
      alert('Failed to attach storage to node');
    }
  };

  const handleDetachStorage = async (storageId: string) => {
    if (!currentWorkspaceId) return;

    try {
      await api.detachStorageFromNode(node.id, storageId);
      await loadNodeStorages();
      // Reload node to get updated config
      const updatedNode = await api.getNode(currentWorkspaceId, node.id);
      updateNode(node.id, updatedNode);
      setConfig(updatedNode.config || {});
    } catch (error) {
      console.error('Failed to detach storage:', error);
      alert('Failed to detach storage from node');
    }
  };

  const handleSave = async () => {
    if (!currentWorkspaceId) return;

    // Use current code from editor ref when available (avoids stale state when CodeMirror hasn't flushed to React state)
    const latestCode = codeEditorGetValueRef.current?.getValue?.();
    const configToSend =
      latestCode !== undefined && (node.node_type_id === 'custom-python' || node.node_type_id === 'condition-python')
        ? { ...config, code: latestCode }
        : config;

    try {
      await api.updateNode(currentWorkspaceId, node.id, { name, config: configToSend });
      updateNode(node.id, { name, config: configToSend });
      setConfig(configToSend);
    } catch (error) {
      console.error('Failed to update node:', error);
      alert('Failed to update node');
    }
  };

  const handleDelete = async () => {
    if (!currentWorkspaceId) return;
    if (!confirm('Are you sure you want to delete this node? This will also delete all connected edges.')) {
      return;
    }

    try {
      await api.deleteNode(currentWorkspaceId, node.id);
      const { deleteNode } = useAppStore.getState();
      deleteNode(node.id);
      setSelectedNode(null);
      setPropertiesPanelOpen(false);
    } catch (error) {
      console.error('Failed to delete node:', error);
      alert('Failed to delete node');
    }
  };

  const IconComponent = iconMap[node.node_type_id] || (node.node_type_id === 'wait' ? Clock : null) || iconMap[node.node_type_id.split('-')[0]] || Database;
  const nodeTypeName = node.node_type_id === 'input' ? 'Input Node' :
                      node.node_type_id === 'custom-python' ? 'Python Script' :
                      node.node_type_id === 'condition-python' ? 'Condition' :
                      node.node_type_id === 'custom-llm' ? 'LLM Node' :
                      node.node_type_id === 'memory' ? 'Memory Node' :
                      node.node_type_id === 'workflow_node' ? 'Workflow' :
                      node.node_type_id === 'wait' ? 'Wait' : node.node_type_id;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* ─── History Mode Banner ─── */}
      {isHistoryMode && selectedRun && (
        <div className="p-4 bg-indigo-950/20 border border-indigo-500/30 rounded-xl">
          <div className="flex items-center gap-2 mb-2">
            <History size={14} className="text-indigo-400" />
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest">
              History Mode: {selectedRun.label || 'Run'}
            </span>
          </div>
          <div className="text-[10px] text-slate-400 space-y-1">
            {selectedRun.started_at && (
              <div>Started: {new Date(selectedRun.started_at).toLocaleString()}</div>
            )}
            {selectedRun.duration && (
              <div>Duration: {selectedRun.duration.toFixed(2)}s</div>
            )}
            {selectedRun.status && (
              <div>Status: <span className="text-slate-300 uppercase">{selectedRun.status}</span></div>
            )}
          </div>
        </div>
      )}

      {/* ─── Historical Inputs Section ─── */}
      {isHistoryMode && historicalInputs && (
        <div>
          <div className="flex items-center justify-between gap-2 mb-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              Execution Inputs (History)
            </label>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setExpandedSection('inputs')}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="Expand"
              >
                <Maximize2 size={14} />
              </button>
              <button
                type="button"
                onClick={() => copyToClipboard(JSON.stringify(historicalInputs, null, 2), 'inputs')}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="Copy to clipboard"
              >
                {copiedId === 'inputs' ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl max-h-48 overflow-y-auto">
            <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap break-words">
              {JSON.stringify(historicalInputs, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* ─── Historical Outputs Section ─── */}
      {isHistoryMode && historicalOutputs && (
        <div>
          <div className="flex items-center justify-between gap-2 mb-1">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              Execution Outputs (History)
              {historicalIterations.length > 1 && (
                <span className="ml-2 text-emerald-400 normal-case tracking-normal">
                  · {historicalIterations.length} iterations
                </span>
              )}
            </label>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setExpandedSection('outputs')}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="Expand"
              >
                <Maximize2 size={14} />
              </button>
              <button
                type="button"
                onClick={() => copyToClipboard(formatIterationsForCopy(), 'outputs')}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title={
                  historicalIterations.length > 1
                    ? `Copy all ${historicalIterations.length} iterations`
                    : 'Copy to clipboard'
                }
              >
                {copiedId === 'outputs' ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>
          </div>
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl max-h-96 overflow-y-auto space-y-3">
            {historicalIterations.length > 1 ? (
              // Per-iteration history (issue9): render newest-first with header per call.
              [...historicalIterations].reverse().map((entry, idx) => {
                const callIndex = historicalIterations.length - 1 - idx;
                return (
                  <div key={`iter-${callIndex}`} className="border-l-2 border-emerald-700/40 pl-2">
                    <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-2">
                      <span className="text-emerald-400 font-bold">Call #{callIndex + 1}</span>
                      {entry.step !== undefined && <span>· step {entry.step}</span>}
                      {entry.ts !== undefined && (
                        <span>· {new Date(entry.ts * 1000).toLocaleTimeString()}</span>
                      )}
                    </div>
                    <pre className="text-xs text-emerald-300 font-mono whitespace-pre-wrap break-words">
                      {JSON.stringify(entry.output, null, 2)}
                    </pre>
                  </div>
                );
              })
            ) : (
              <pre className="text-xs text-emerald-300 font-mono whitespace-pre-wrap break-words">
                {JSON.stringify(historicalOutputs, null, 2)}
              </pre>
            )}
          </div>
          {/* HTML preview pane (issue17): for html-viewer nodes only, sandboxed iframe render */}
          {node.node_type_id === 'html-viewer' && typeof historicalOutputs?.output === 'string' && (
            <div className="mt-3">
              <div className="flex items-center justify-between gap-2 mb-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  HTML Preview
                </label>
                <button
                  type="button"
                  onClick={() => setExpandedSection('htmlPreview')}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                  title="Expand to fullscreen"
                >
                  <Maximize2 size={14} />
                </button>
              </div>
              <iframe
                sandbox=""
                srcDoc={extractHtmlForPreview(historicalOutputs.output as string)}
                className="w-full h-96 bg-white rounded-lg border border-slate-700"
                title="HTML preview"
              />
            </div>
          )}
          {node.node_type_id === 'workflow_node' && historicalOutputs?.child_run_id && historicalOutputs?.child_workflow_id && (
            <div className="mt-2">
              <button
                type="button"
                onClick={async () => {
                  const childWorkflowId = historicalOutputs.child_workflow_id as string;
                  const childRunId = historicalOutputs.child_run_id as string;
                  setCurrentWorkspace(childWorkflowId);
                  setCurrentView('editor');
                  try {
                    const runsList = await api.getRuns(childWorkflowId);
                    setRuns(runsList);
                    setSelectedRunId(childRunId);
                  } catch (e) {
                    console.error('Failed to load child runs:', e);
                    setSelectedRunId(childRunId);
                  }
                }}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 border border-cyan-500/30 rounded-xl text-xs font-bold transition-colors"
              >
                <ExternalLink size={14} />
                View sub-workflow run
              </button>
            </div>
          )}
        </div>
      )}

      {/* ─── Execution Outputs (Live run): show after each node completion during run ─── */}
      {!isHistoryMode && isRunning && activeRun && (liveOutputs || liveInputs) && (
        <div className="space-y-3">
          {liveInputs && (
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  Execution Inputs (Live)
                </label>
                <button
                  type="button"
                  onClick={() => copyToClipboard(JSON.stringify(liveInputs, null, 2), 'liveInputs')}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                  title="Copy to clipboard"
                >
                  {copiedId === 'liveInputs' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl max-h-48 overflow-y-auto">
                <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap break-words">
                  {JSON.stringify(liveInputs, null, 2)}
                </pre>
              </div>
            </div>
          )}
          {liveOutputs && (
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  Execution Outputs (Live)
                </label>
                <button
                  type="button"
                  onClick={() => copyToClipboard(JSON.stringify(liveOutputs, null, 2), 'liveOutputs')}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                  title="Copy to clipboard"
                >
                  {copiedId === 'liveOutputs' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl max-h-64 overflow-y-auto">
                <pre className="text-xs text-emerald-300 font-mono whitespace-pre-wrap break-words">
                  {JSON.stringify(liveOutputs, null, 2)}
                </pre>
              </div>
              {/* HTML preview pane (issue17) — live-mode variant */}
              {node.node_type_id === 'html-viewer' && typeof (liveOutputs as { output?: unknown })?.output === 'string' && (
                <div className="mt-3">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                      HTML Preview
                    </label>
                    <button
                      type="button"
                      onClick={() => setExpandedSection('htmlPreview')}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                      title="Expand to fullscreen"
                    >
                      <Maximize2 size={14} />
                    </button>
                  </div>
                  <iframe
                    sandbox=""
                    srcDoc={extractHtmlForPreview((liveOutputs as { output: string }).output)}
                    className="w-full h-96 bg-white rounded-lg border border-slate-700"
                    title="HTML preview"
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ─── Execution Status Banner (only in live mode) ─── */}
      {!isHistoryMode && (status !== 'idle' || isRunning) && (
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-widest">
            Execution Status
          </label>
          <StatusBadge status={status} />
          {isRunning && status === 'idle' && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-bold text-slate-400 bg-slate-800/30 border-slate-700/30">
              <Clock size={14} />
              <span>Queued — waiting for upstream nodes</span>
            </div>
          )}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Display Name</label>
          <input 
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" 
            value={name} 
            onChange={(e) => !isHistoryMode && setName(e.target.value)}
            onBlur={!isHistoryMode ? handleSave : undefined}
            disabled={isHistoryMode}
          />
        </div>

        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Node Type</label>
          <div className="flex items-center gap-2 p-3 bg-slate-950 border border-slate-800 rounded-lg">
            <IconComponent size={16} className="text-indigo-400" />
            <span className="text-sm text-slate-300">{nodeTypeName}</span>
          </div>
        </div>

        {/* Node ID (useful for debugging) */}
        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Node ID</label>
          <div className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-[10px] text-slate-600 font-mono break-all select-all">
            {node.id}
          </div>
        </div>

        {/* Workflow node: linked workflow + Open + Expected input keys */}
        {node.node_type_id === 'workflow_node' && (
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Linked workflow</label>
              <div className="flex items-center gap-2 p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <Workflow size={16} className="text-cyan-400" />
                <span className="text-sm text-slate-300 flex-1 truncate">{config.workflow_name || config.workflow_id || 'Workflow'}</span>
                {config.workflow_id && !isHistoryMode && (
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentWorkspace(config.workflow_id);
                      setCurrentView('editor');
                    }}
                    className="flex items-center gap-1 px-2 py-1.5 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 border border-cyan-500/30 rounded-lg text-xs font-bold transition-all"
                  >
                    <ExternalLink size={12} /> Open
                  </button>
                )}
              </div>
            </div>
            {edgeNodesOfRefWorkflow.length > 0 && (
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Expected input keys (edge nodes)</label>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-400 font-mono">
                  {edgeNodesOfRefWorkflow.map((en) => en.key).join(', ') || '—'}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Use input from parent (any node) — for sub-workflow edge nodes */}
        {!isHistoryMode && (
          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!!config.use_input_from_parent}
                onChange={(e) => {
                  const newConfig = { ...config, use_input_from_parent: e.target.checked };
                  setConfig(newConfig);
                  updateNode(node.id, { config: newConfig });
                  if (currentWorkspaceId) {
                    api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                  }
                }}
                className="rounded border-slate-600 bg-slate-950 text-indigo-500 focus:ring-indigo-500"
              />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Use input from parent</span>
            </label>
            {config.use_input_from_parent && (
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">External input key</label>
                <input
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
                  value={config.external_input_key ?? ''}
                  onChange={(e) => {
                    const newConfig = { ...config, external_input_key: e.target.value || undefined };
                    setConfig(newConfig);
                    updateNode(node.id, { config: newConfig });
                    if (currentWorkspaceId) {
                      api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                    }
                  }}
                  placeholder={node.name || 'defaults to node name'}
                />
              </div>
            )}
          </div>
        )}

        {/* ─── Wait Node Configuration ─── */}
        {node.node_type_id === 'wait' && !isHistoryMode && (
          <WaitNodeProperties
            config={config}
            onConfigChange={(newConfig) => {
              setConfig(newConfig);
              updateNode(node.id, { config: newConfig });
              if (currentWorkspaceId) {
                api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
              }
            }}
          />
        )}

        {/* ─── HTML Viewer Configuration (issue17) ─── */}
        {node.node_type_id === 'html-viewer' && (
          <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
            <p className="text-[11px] text-indigo-200 leading-relaxed">
              Renders its upstream input as <span className="font-bold">sandboxed HTML</span> in the preview pane below.
              Connect an LLM or any string-producing node upstream. Code fences (<code className="bg-slate-800 px-1 rounded">```html</code>) are stripped automatically.
            </p>
          </div>
        )}

        {node.node_type_id === 'input' && (
          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Input Value</label>
              {!isHistoryMode && (
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setExpandedSection('inputValue')}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    title="Expand"
                  >
                    <Maximize2 size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(config.value || '', 'inputValue')}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    title="Copy"
                  >
                    {copiedId === 'inputValue' ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              )}
            </div>
            <textarea 
              className="w-full h-32 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-300 font-mono focus:border-indigo-500 outline-none disabled:opacity-50 disabled:cursor-not-allowed" 
              value={config.value || ''} 
              onChange={(e) => {
                if (isHistoryMode) return;
                const newConfig = { ...config, value: e.target.value };
                setConfig(newConfig);
                updateNode(node.id, { config: newConfig });
                if (currentWorkspaceId) {
                  api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                }
              }}
              placeholder="Raw data string..."
              disabled={isHistoryMode}
            />
          </div>
        )}

        {(node.node_type_id === 'custom-python' || node.node_type_id === 'condition-python') && (
          <>
            {(node.node_type_id === 'condition-python' || node.config?.condition_mode) && (
              <div className="mb-3 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <p className="text-[10px] font-medium text-amber-200">
                  Condition node: return <code className="bg-slate-800 px-1 rounded">True</code> or <code className="bg-slate-800 px-1 rounded">False</code>, or a dict with <code className="bg-slate-800 px-1 rounded">branch: &quot;true&quot;/&quot;false&quot;</code>. Only the matching branch&apos;s nodes will run.
                </p>
              </div>
            )}
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Python Code</label>
                {!isHistoryMode && (
                  <button
                    type="button"
                    onClick={() => setExpandedSection('pythonCode')}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    title="Expand to edit in modal"
                  >
                    <Maximize2 size={14} />
                  </button>
                )}
              </div>
              <PythonCodeEditor
                value={config.code || ''}
                onChange={(code) => {
                  setConfig((prev) => {
                    const newConfig = { ...prev, code };
                    updateNode(node.id, { config: newConfig });
                    if (currentWorkspaceId) {
                      api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                    }
                    return newConfig;
                  });
                }}
                getValueRef={codeEditorGetValueRef}
                disabled={isHistoryMode}
                minHeight="280px"
                placeholder="def main(data):&#10;  return data"
              />
            </div>
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Requirements</label>
                {!isHistoryMode && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setExpandedSection('requirements')}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                      title="Expand"
                    >
                      <Maximize2 size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(config.requirements || '', 'requirements')}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                      title="Copy"
                    >
                      {copiedId === 'requirements' ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                )}
              </div>
              <textarea 
                className="w-full h-16 bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-400 font-mono outline-none disabled:opacity-50 disabled:cursor-not-allowed" 
                value={config.requirements || ''} 
                onChange={(e) => {
                  if (isHistoryMode) return;
                  const newConfig = { ...config, requirements: e.target.value };
                  setConfig(newConfig);
                  updateNode(node.id, { config: newConfig });
                  if (currentWorkspaceId) {
                    api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                  }
                }}
                placeholder="pip: pandas, requests..."
                disabled={isHistoryMode}
              />
            </div>
          </>
        )}

        {node.node_type_id === 'custom-llm' && (
          <>
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Link Model Backend</label>
              <select 
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed" 
                value={config.configId || ''} 
                onChange={(e) => {
                  if (isHistoryMode) return;
                  const newConfig = { ...config, configId: e.target.value };
                  setConfig(newConfig);
                  updateNode(node.id, { config: newConfig });
                  if (currentWorkspaceId) {
                    api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                  }
                }}
                disabled={isHistoryMode}
              >
                <option value="">Choose Provider...</option>
                {llmConfigs.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Prompt Template</label>
                {!isHistoryMode && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setExpandedSection('prompt')}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                      title="Expand"
                    >
                      <Maximize2 size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(config.prompt || '', 'prompt')}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                      title="Copy"
                    >
                      {copiedId === 'prompt' ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                )}
              </div>
              <textarea 
                className="w-full h-32 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-purple-300 font-mono focus:border-purple-500/30 outline-none shadow-inner disabled:opacity-50 disabled:cursor-not-allowed" 
                value={config.prompt || ''} 
                onChange={(e) => {
                  if (isHistoryMode) return;
                  const newConfig = { ...config, prompt: e.target.value };
                  setConfig(newConfig);
                  updateNode(node.id, { config: newConfig });
                  if (currentWorkspaceId) {
                    api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
                  }
                }}
                placeholder="{text}"
                disabled={isHistoryMode}
              />
            </div>
          </>
        )}

        {/* Storage Section (for Python nodes) */}
        {node.node_type_id === 'custom-python' && !isHistoryMode && (
          <div className="pt-4 border-t border-slate-800">
            <div className="flex items-center justify-between mb-4">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                Attached Storages
              </label>
              <button
                onClick={() => {
                  console.log('Attach Storage button clicked', { showStorageSelector, availableStorages });
                  setShowStorageSelector(true);
                }}
                className="flex items-center gap-2 px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 rounded-lg text-xs font-bold transition-all"
              >
                <Plus size={14} /> Attach Storage
              </button>
            </div>

            {loadingStorages ? (
              <div className="text-xs text-slate-600 italic">Loading storages...</div>
            ) : nodeStorages.length === 0 ? (
              <div className="text-xs text-slate-600 italic py-2">
                No storages attached. Click "Attach Storage" to add one.
              </div>
            ) : (
              <div className="space-y-2">
                {nodeStorages.map((nodeStorage) => (
                  <div
                    key={nodeStorage.storage_id}
                    className="flex items-center justify-between p-3 bg-slate-950 border border-slate-800 rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="text-sm font-bold text-white">{nodeStorage.storage_name}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-slate-500 uppercase">{nodeStorage.storage_type}</span>
                        {nodeStorage.alias && (
                          <>
                            <span className="text-slate-700">•</span>
                            <span className="text-xs text-slate-400 font-mono">
                              alias: {nodeStorage.alias}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDetachStorage(nodeStorage.storage_id)}
                      className="p-2 text-slate-500 hover:text-red-500 transition-colors"
                      title="Detach storage"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {nodeStorages.length > 0 && (
              <div className="mt-4 p-3 bg-indigo-950/10 border border-indigo-500/20 rounded-lg">
                <div className="text-xs text-indigo-400 font-mono">
                  <div className="font-bold text-indigo-500 mb-1">Usage in Python:</div>
                  <div className="text-slate-400">
                    {nodeStorages.map((ns) => {
                      const alias = ns.alias || ns.storage_name.toLowerCase().replace(/\s+/g, '_');
                      return `storages.get("${alias}")`;
                    }).join(', ')}
                  </div>
                </div>
              </div>
            )}

            {showStorageSelector && createPortal(
              <StorageSelectorModal
                availableStorages={availableStorages}
                onSelect={handleAttachStorage}
                onClose={() => {
                  console.log('Closing modal');
                  setShowStorageSelector(false);
                }}
              />,
              document.body
            )}
          </div>
        )}

        {/* Iterator Configuration */}
        {nodeTypeSupportsIterator && !isHistoryMode && (
          <IteratorConfig
            node={node}
            nodes={nodes}
            edges={edges}
            onUpdate={(updates) => {
              updateNode(node.id, updates);
              if (currentWorkspaceId) {
                api.updateNode(currentWorkspaceId, node.id, updates).catch(console.error);
              }
            }}
          />
        )}

        {!isHistoryMode && (
          <>
            <button 
              onClick={() => setShowSaveTemplateDialog(true)} 
              className="w-full py-3 mt-4 bg-blue-950/20 text-blue-400 border border-blue-500/20 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-blue-900/30 transition-all flex items-center justify-center gap-2"
            >
              <Save size={14}/> Save as Template
            </button>
            <button 
              onClick={handleDelete} 
              className="w-full py-3 mt-2 bg-red-950/20 text-red-500 border border-red-500/20 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-red-900/30 transition-all flex items-center justify-center gap-2"
            >
              <Trash2 size={14}/> Remove Node
            </button>
          </>
        )}
      </div>

      {showSaveTemplateDialog && (
        <SaveNodeAsTemplateDialog
          open={showSaveTemplateDialog}
          nodeId={node.id}
          nodeName={node.name}
          onClose={() => setShowSaveTemplateDialog(false)}
          onSuccess={(templateId) => {
            setShowSaveTemplateDialog(false);
            console.log('Template saved:', templateId);
          }}
        />
      )}

      {/* View-only modals for History Inputs/Outputs */}
      <OutputModal
        open={expandedSection === 'inputs'}
        title="Execution Inputs (History)"
        content={historicalInputs ? JSON.stringify(historicalInputs, null, 2) : ''}
        onClose={() => setExpandedSection(null)}
        onCopy={() => copyToClipboard(JSON.stringify(historicalInputs, null, 2), 'inputsModal')}
        copied={copiedId === 'inputsModal'}
        contentClassName="text-slate-300"
      />
      <OutputModal
        open={expandedSection === 'outputs'}
        title={
          historicalIterations.length > 1
            ? `Execution Outputs (History) · ${historicalIterations.length} iterations`
            : 'Execution Outputs (History)'
        }
        content={formatIterationsForCopy()}
        onClose={() => setExpandedSection(null)}
        onCopy={() => copyToClipboard(formatIterationsForCopy(), 'outputsModal')}
        copied={copiedId === 'outputsModal'}
        contentClassName="text-emerald-300"
      />

      {/* Editable modal for Python Code */}
      <ExpandableCodeModal
        open={expandedSection === 'pythonCode'}
        title="Python Code"
        value={config.code || ''}
        onSave={(code) => {
          const newConfig = { ...config, code };
          setConfig(newConfig);
          updateNode(node.id, { config: newConfig });
          if (currentWorkspaceId) {
            api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
          }
        }}
        onClose={() => setExpandedSection(null)}
        onCopy={(code) => copyToClipboard(code, 'pythonCodeModal')}
        copied={copiedId === 'pythonCodeModal'}
      />

      {/* Editable text modals for Input Value, Prompt, Requirements */}
      <ExpandableTextModal
        open={expandedSection === 'inputValue'}
        title="Input Value"
        value={config.value || ''}
        onSave={(text) => {
          const newConfig = { ...config, value: text };
          setConfig(newConfig);
          updateNode(node.id, { config: newConfig });
          if (currentWorkspaceId) {
            api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
          }
        }}
        onClose={() => setExpandedSection(null)}
        onCopy={(text) => copyToClipboard(text, 'inputValueModal')}
        copied={copiedId === 'inputValueModal'}
        placeholder="Raw data string..."
      />
      <ExpandableTextModal
        open={expandedSection === 'prompt'}
        title="Prompt Template"
        value={config.prompt || ''}
        onSave={(text) => {
          const newConfig = { ...config, prompt: text };
          setConfig(newConfig);
          updateNode(node.id, { config: newConfig });
          if (currentWorkspaceId) {
            api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
          }
        }}
        onClose={() => setExpandedSection(null)}
        onCopy={(text) => copyToClipboard(text, 'promptModal')}
        copied={copiedId === 'promptModal'}
        placeholder="{text}"
        textClassName="text-purple-300"
      />
      <ExpandableTextModal
        open={expandedSection === 'requirements'}
        title="Requirements"
        value={config.requirements || ''}
        onSave={(text) => {
          const newConfig = { ...config, requirements: text };
          setConfig(newConfig);
          updateNode(node.id, { config: newConfig });
          if (currentWorkspaceId) {
            api.updateNode(currentWorkspaceId, node.id, { config: newConfig }).catch(console.error);
          }
        }}
        onClose={() => setExpandedSection(null)}
        onCopy={(text) => copyToClipboard(text, 'requirementsModal')}
        copied={copiedId === 'requirementsModal'}
        placeholder="pip: pandas, requests..."
        textClassName="text-slate-400"
      />

      {/* HTML Preview fullscreen modal (issue17) */}
      <HtmlPreviewModal
        open={expandedSection === 'htmlPreview'}
        title="HTML Preview"
        html={extractHtmlForPreview(
          ((isHistoryMode ? historicalOutputs?.output : (liveOutputs as { output?: unknown })?.output) as string) || ''
        )}
        onClose={() => setExpandedSection(null)}
        onCopy={() => {
          const src = ((isHistoryMode ? historicalOutputs?.output : (liveOutputs as { output?: unknown })?.output) as string) || '';
          copyToClipboard(extractHtmlForPreview(src), 'htmlPreviewModal');
        }}
        copied={copiedId === 'htmlPreviewModal'}
      />
    </div>
  );
}
