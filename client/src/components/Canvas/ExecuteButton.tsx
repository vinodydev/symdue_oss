// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Execute Graph floating button + pre-flight input modal.
 * Matching reference (code.jsx lines 498-510, 706-726).
 */
import { useState, useMemo } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { Play, Loader2, ListRestart, X, Eye, Pause, Square } from 'lucide-react';

export function ExecuteButton() {
  const {
    currentWorkspaceId,
    nodes,
    isRunning,
    setIsRunning,
    selectedRunId,
    setSelectedRunId,
    addRun,
    updateRun,
    clearNodeStatuses,
    runs,
  } = useAppStore();

  const [isInputModalOpen, setIsInputModalOpen] = useState(false);
  const [inputPrefills, setInputPrefills] = useState<Record<string, string>>({});
  const [externalInput, setExternalInput] = useState<Record<string, string>>({});
  const [edgeNodes, setEdgeNodes] = useState<{ node_id: string; node_name: string; key: string }[]>([]);

  // Identify input nodes for preflight
  const inputNodes = useMemo(
    () => nodes.filter((n) => n.node_type_id === 'input'),
    [nodes],
  );

  const selectedRun = useMemo(
    () => runs.find((r) => r.id === selectedRunId),
    [runs, selectedRunId],
  );

  // Find the current running or paused run
  const currentActiveRun = useMemo(
    () => runs.find((r) => r.status === 'running' || r.status === 'paused' || r.status === 'queued'),
    [runs],
  );

  /** Open the pre-flight modal and prefill input values */
  const triggerRunPreflight = async () => {
    const prefilled: Record<string, string> = {};
    inputNodes.forEach((n) => {
      prefilled[n.id] = (n.config?.value as string) || '';
    });
    setInputPrefills(prefilled);
    setExternalInput({});
    if (currentWorkspaceId) {
      try {
        const { edge_nodes } = await api.getWorkflowEdgeNodes(currentWorkspaceId);
        setEdgeNodes(edge_nodes || []);
      } catch {
        setEdgeNodes([]);
      }
    } else {
      setEdgeNodes([]);
    }
    setIsInputModalOpen(true);
  };

  /** Submit the run to the backend */
  const startGraphExecution = async () => {
    if (!currentWorkspaceId) return;
    setIsInputModalOpen(false);
    setIsRunning(true);
    clearNodeStatuses();

    try {
      const run = await api.createRun(currentWorkspaceId, {
        inputs: inputPrefills,
        label: `Run ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
        external_input: Object.keys(externalInput).length ? externalInput : undefined,
      });
      addRun(run);
      // NOTE: isRunning stays true — the WebSocket handler will set it to false
      // when the workflow completes or fails.
    } catch (err) {
      console.error('Failed to start run:', err);
      setIsRunning(false);
      alert('Failed to start graph execution');
    }
  };

  /** Pause the current running workflow */
  const handlePause = async () => {
    if (!currentWorkspaceId || !currentActiveRun) return;
    try {
      await api.pauseRun(currentWorkspaceId, currentActiveRun.id);
      // Optimistic update — server-side WORKFLOW_STATUS broadcast will reconcile.
      updateRun(currentActiveRun.id, { status: 'paused' });
    } catch (err) {
      console.error('Failed to pause run:', err);
      alert('Failed to pause workflow');
    }
  };

  /** Resume the paused workflow */
  const handleResume = async () => {
    if (!currentWorkspaceId || !currentActiveRun) return;
    try {
      await api.resumeRun(currentWorkspaceId, currentActiveRun.id);
      updateRun(currentActiveRun.id, { status: 'running' });
    } catch (err) {
      console.error('Failed to resume run:', err);
      alert('Failed to resume workflow');
    }
  };

  /** Stop/cancel the current workflow */
  const handleStop = async () => {
    if (!currentWorkspaceId || !currentActiveRun) return;
    if (!confirm('Are you sure you want to stop this workflow?')) return;
    try {
      await api.cancelRun(currentWorkspaceId, currentActiveRun.id);
      updateRun(currentActiveRun.id, { status: 'cancelled' });
      setIsRunning(false);
    } catch (err) {
      console.error('Failed to stop run:', err);
      alert('Failed to stop workflow');
    }
  };

  return (
    <>
      {/* Floating action buttons (top-left of canvas) */}
      <div className="absolute top-6 left-6 flex items-center gap-3 z-40">
        {currentActiveRun && (currentActiveRun.status === 'running' || currentActiveRun.status === 'paused' || currentActiveRun.status === 'queued') ? (
          <>
            {/* Control buttons for active run */}
            {currentActiveRun.status === 'running' && (
              <button
                onClick={handlePause}
                className="flex items-center gap-3 px-6 h-12 rounded-2xl bg-yellow-600 hover:bg-yellow-500 text-white font-bold shadow-2xl transition-all active:scale-95"
                title="Pause workflow"
              >
                <Pause size={18} fill="currentColor" />
                Pause
              </button>
            )}
            {currentActiveRun.status === 'paused' && (
              <button
                onClick={handleResume}
                className="flex items-center gap-3 px-6 h-12 rounded-2xl bg-green-600 hover:bg-green-500 text-white font-bold shadow-2xl transition-all active:scale-95"
                title="Resume workflow"
              >
                <Play size={18} fill="currentColor" />
                Resume
              </button>
            )}
            <button
              onClick={handleStop}
              className="flex items-center gap-3 px-6 h-12 rounded-2xl bg-red-600 hover:bg-red-500 text-white font-bold shadow-2xl transition-all active:scale-95"
              title="Stop workflow"
            >
              <Square size={18} fill="currentColor" />
              Stop
            </button>
          </>
        ) : (
          <button
            onClick={triggerRunPreflight}
            disabled={isRunning || !!selectedRunId}
            className="flex items-center gap-3 px-6 h-12 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold shadow-2xl transition-all active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {isRunning ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Play size={18} fill="currentColor" />
            )}
            Execute Graph
          </button>
        )}

        {/* Snapshot-mode banner (when viewing a past run) */}
        {selectedRunId && selectedRun && (
          <div className="h-12 bg-slate-900/90 backdrop-blur-xl border border-indigo-500/30 rounded-2xl px-4 flex items-center gap-4 shadow-xl animate-in slide-in-from-top-2">
            <Eye size={16} className="text-indigo-400" />
            <span className="text-[10px] font-bold text-slate-200 uppercase tracking-widest">
              Snapshot Mode: {selectedRun.label || 'Run'}
            </span>
            <button
              onClick={() => setSelectedRunId(null)}
              className="p-1 hover:bg-slate-800 rounded-full text-slate-500 hover:text-white transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Pre-flight modal */}
      {isInputModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/90 backdrop-blur-md animate-in fade-in duration-200">
          <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-[2.5rem] shadow-2xl animate-in zoom-in-95 duration-200 overflow-hidden">
            <div className="p-8 border-b border-slate-800 bg-slate-900/50 text-center">
              <h3 className="text-xl font-bold text-white flex justify-center items-center gap-3">
                <ListRestart size={24} className="text-indigo-400" />
                Sequence Pre-flight
              </h3>
            </div>

            <div className="p-8 space-y-6">
              {inputNodes.length > 0 ? (
                inputNodes.map((node) => (
                  <div key={node.id} className="space-y-2">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                      {node.name || 'Input'}
                    </label>
                    <input
                      autoFocus
                      className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500 shadow-inner"
                      value={inputPrefills[node.id] || ''}
                      onChange={(e) =>
                        setInputPrefills((prev) => ({
                          ...prev,
                          [node.id]: e.target.value,
                        }))
                      }
                      placeholder="Enter data value..."
                    />
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-slate-600 italic">
                  No input nodes require data pre-filling.
                </div>
              )}

              {edgeNodes.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                    External input (edge nodes)
                  </label>
                  {edgeNodes.map((en) => (
                    <div key={en.node_id} className="space-y-1">
                      <label className="text-[10px] text-slate-500">{en.node_name} (key: {en.key})</label>
                      <input
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white outline-none focus:border-indigo-500"
                        value={externalInput[en.key] ?? ''}
                        onChange={(e) =>
                          setExternalInput((prev) => ({ ...prev, [en.key]: e.target.value }))
                        }
                        placeholder="Value for this key..."
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="p-8 bg-slate-950/50 flex gap-4 border-t border-slate-800">
              <button
                onClick={() => setIsInputModalOpen(false)}
                className="flex-1 py-4 text-sm font-bold text-slate-500 hover:text-white transition-colors"
              >
                Abort
              </button>
              <button
                onClick={startGraphExecution}
                className="flex-1 py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl text-sm font-black uppercase tracking-widest shadow-xl active:scale-[0.98] transition-all"
              >
                Launch Run
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

