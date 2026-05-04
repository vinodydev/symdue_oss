/**
 * Dialog to add an existing workflow as a node (workflow reference). Double-click opens that workflow.
 */
import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { X, Workflow } from 'lucide-react';
import type { Workflow as WorkflowType } from '@/types';

interface AddWorkflowAsNodeDialogProps {
  open: boolean;
  onClose: () => void;
}

// Backend regex on node names is `^[A-Za-z0-9_-]+$`. Mirror it here so what
// passes the frontend gate also passes the backend gate.
const NODE_NAME_PATTERN = /^[A-Za-z0-9_-]+$/;
const MAX_NODE_NAME_LEN = 60;

/** Convert any string into a node-name-valid identifier. */
function sanitizeNodeName(s: string): string {
  return s
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^A-Za-z0-9_-]/g, '')
    .slice(0, MAX_NODE_NAME_LEN);
}

function isValidNodeName(s: string): boolean {
  return NODE_NAME_PATTERN.test(s) && s.length <= MAX_NODE_NAME_LEN;
}

export function AddWorkflowAsNodeDialog({ open, onClose }: AddWorkflowAsNodeDialogProps) {
  const { currentWorkspaceId, addNode, setNodes, transform } = useAppStore();
  const [workflows, setWorkflows] = useState<WorkflowType[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('');
  const [nodeName, setNodeName] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && currentWorkspaceId) {
      setLoading(true);
      api.getWorkspaces()
        .then((list) => {
          setWorkflows(list.filter((w) => w.id !== currentWorkspaceId));
          setSelectedWorkflowId('');
          setNodeName('');
        })
        .catch(() => setWorkflows([]))
        .finally(() => setLoading(false));
    }
  }, [open, currentWorkspaceId]);

  const handleSubmit = async () => {
    if (!currentWorkspaceId || !selectedWorkflowId || !nodeName.trim()) return;
    setSubmitting(true);
    try {
      const container = document.querySelector('.canvas-container');
      const rect = container?.getBoundingClientRect();
      const centerX = rect ? (rect.width / 2 - transform.x) / transform.k : 0;
      const centerY = rect ? (rect.height / 2 - transform.y) / transform.k : 0;
      const newNode = await api.createWorkflowReferenceNode(currentWorkspaceId, {
        workflow_id: selectedWorkflowId,
        node_name: nodeName.trim(),
        x: centerX - 110,
        y: centerY - 60,
      });
      addNode(newNode);
      const workspace = await api.getWorkspace(currentWorkspaceId);
      setNodes(workspace.nodes || []);
      onClose();
    } catch (err: any) {
      console.error('Failed to add workflow as node:', err);
      const detail = err?.response?.data?.detail || 'Failed to add workflow. Please try again.';
      alert(detail);
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden">
        <div className="p-6 border-b border-slate-800 bg-slate-900/50 flex items-center gap-3">
          <Workflow size={20} className="text-cyan-400" />
          <h3 className="text-lg font-bold text-white">Add existing workflow as node</h3>
          <button
            onClick={onClose}
            className="ml-auto p-1 rounded-lg text-slate-500 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-6 space-y-4">
          {loading ? (
            <div className="text-center py-6 text-slate-500">Loading workspaces...</div>
          ) : (
            <>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Workflow</label>
                <select
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-cyan-500"
                  value={selectedWorkflowId}
                  onChange={(e) => {
                    setSelectedWorkflowId(e.target.value);
                    const w = workflows.find((f) => f.id === e.target.value);
                    if (w && !nodeName) setNodeName(sanitizeNodeName(w.name || ''));
                  }}
                >
                  <option value="">Select a workflow...</option>
                  {workflows.map((w) => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Node name</label>
                <input
                  className={`w-full bg-slate-950 border rounded-xl px-4 py-3 text-sm text-white outline-none focus:border-cyan-500 ${
                    nodeName.trim().length > 0 && !isValidNodeName(nodeName.trim())
                      ? 'border-rose-500'
                      : 'border-slate-800'
                  }`}
                  value={nodeName}
                  onChange={(e) => setNodeName(e.target.value)}
                  placeholder="e.g. data_fetcher"
                  maxLength={MAX_NODE_NAME_LEN}
                />
                {nodeName.trim().length > 0 && !isValidNodeName(nodeName.trim()) ? (
                  <p className="mt-2 text-[11px] text-rose-400">
                    Only letters, numbers, underscores, and hyphens. No spaces.
                  </p>
                ) : (
                  <p className="mt-2 text-[11px] text-slate-600">
                    Letters, numbers, underscores, and hyphens. Max {MAX_NODE_NAME_LEN} chars.
                  </p>
                )}
              </div>
            </>
          )}
        </div>
        <div className="p-6 bg-slate-950/50 flex gap-3 border-t border-slate-800">
          <button
            onClick={onClose}
            className="flex-1 py-3 text-sm font-bold text-slate-500 hover:text-white transition-colors rounded-xl"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={
              loading ||
              submitting ||
              !selectedWorkflowId ||
              !nodeName.trim() ||
              !isValidNodeName(nodeName.trim())
            }
            className="flex-1 py-3 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-sm font-black uppercase tracking-widest transition-all"
          >
            {submitting ? 'Adding…' : 'Add node'}
          </button>
        </div>
      </div>
    </div>
  );
}
