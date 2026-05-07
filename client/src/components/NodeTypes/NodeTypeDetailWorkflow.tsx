// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Detail for workflow template: metadata + "Edit template" and "Sync with latest" actions.
 */
import React, { useState } from 'react';
import { ArrowLeft, Workflow, ExternalLink, RefreshCw } from 'lucide-react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { NodeType } from '@/types';

interface NodeTypeDetailWorkflowProps {
  nodeType: NodeType;
  onBack: () => void;
  onRefresh?: () => void;
  setCurrentView: (view: 'workspaces' | 'editor' | 'settings' | 'node_types') => void;
  setCurrentWorkspace: (id: string | null) => void;
}

export function NodeTypeDetailWorkflow({
  nodeType,
  onBack,
  onRefresh,
  setCurrentView,
  setCurrentWorkspace,
}: NodeTypeDetailWorkflowProps) {
  const setOpenedEditorFromNodeTypes = useAppStore((s) => s.setOpenedEditorFromNodeTypes);
  const setEditingTemplateId = useAppStore((s) => s.setEditingTemplateId);
  const [syncing, setSyncing] = useState(false);
  const [editLoading, setEditLoading] = useState(false);

  const hasOriginalWorkflow =
    !!nodeType.workflow_id || !!nodeType.workflow_template_data?.original_workflow_id;

  const handleEditTemplate = async () => {
    setEditLoading(true);
    try {
      const { workflow_id } = await api.createTemplateEditCopy(nodeType.id);
      setCurrentWorkspace(workflow_id);
      setCurrentView('editor');
      setOpenedEditorFromNodeTypes(true);
      setEditingTemplateId(nodeType.id);
    } catch (e) {
      console.error(e);
    } finally {
      setEditLoading(false);
    }
  };

  const handleSyncFromLatest = async () => {
    if (!hasOriginalWorkflow) return;
    setSyncing(true);
    try {
      await api.syncTemplateFromWorkflow(nodeType.id);
      onRefresh?.();
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-8 animate-in fade-in duration-200">
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-slate-400 hover:text-white mb-6 w-fit"
      >
        <ArrowLeft size={18} /> Back to Node Types
      </button>

      <div className="max-w-2xl space-y-8">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-2xl bg-slate-800 text-cyan-400">
            <Workflow size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">{nodeType.name}</h1>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              Workflow template
            </p>
          </div>
        </div>

        {nodeType.description && (
          <p className="text-slate-400 text-sm">{nodeType.description}</p>
        )}

        {(nodeType.input_ports?.length || nodeType.output_ports?.length) ? (
          <div className="grid grid-cols-2 gap-6">
            {nodeType.input_ports && nodeType.input_ports.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-slate-500 uppercase mb-2">Input ports</h3>
                <ul className="space-y-1 text-sm text-slate-300">
                  {nodeType.input_ports.map((p: any, i: number) => (
                    <li key={i}>{p.node_name || p.node_id}</li>
                  ))}
                </ul>
              </div>
            )}
            {nodeType.output_ports && nodeType.output_ports.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-slate-500 uppercase mb-2">Output ports</h3>
                <ul className="space-y-1 text-sm text-slate-300">
                  {nodeType.output_ports.map((p: any, i: number) => (
                    <li key={i}>{p.node_name || p.node_id}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : null}

        <div className="pt-4 border-t border-slate-800 flex flex-wrap gap-3">
          <button
            onClick={handleEditTemplate}
            disabled={editLoading || !nodeType.workflow_template_data?.nodes?.length}
            className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold rounded-2xl shadow-xl transition-colors"
          >
            <ExternalLink size={18} />
            {editLoading ? 'Creating…' : 'Edit template'}
          </button>
          {hasOriginalWorkflow && (
            <button
              onClick={handleSyncFromLatest}
              disabled={syncing}
              className="flex items-center gap-2 px-6 py-3 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white font-bold rounded-2xl transition-colors"
            >
              <RefreshCw size={18} className={syncing ? 'animate-spin' : ''} />
              {syncing ? 'Syncing…' : 'Sync with latest'}
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500">
          Edit template opens a copy of the saved snapshot to edit; save to update the template. Sync with latest overwrites the snapshot from the original workflow.
        </p>

        {!nodeType.workflow_template_data?.nodes?.length && (
          <p className="text-amber-500/90 text-sm">
            This template has no workflow data to edit.
          </p>
        )}
      </div>
    </div>
  );
}
