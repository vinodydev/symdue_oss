/**
 * Run history sidebar — matching reference (code.jsx lines 433-451).
 */
import { useAppStore } from '@/stores';
import { X, CheckCircle2, AlertCircle, Loader2, Clock, Pause, Play, Square, RotateCcw, Maximize2, ArrowLeft } from 'lucide-react';
import { cn } from '@/utils/cn';
import { api } from '@/services/api';
import { useState } from 'react';
import { RunOutputsModal } from './RunOutputsModal';
import { SendSignalPanel } from './SendSignalPanel';
import type { Run } from '@/types';

export function RunHistory() {
  const {
    runs,
    selectedRunId,
    setSelectedRunId,
    selectedNodeId,
    setSelectedNode,
    nodes,
    isHistoryOpen,
    setIsHistoryOpen,
    currentWorkspaceId,
    setIsRunning,
    setRuns,
    updateRun,
    setCurrentWorkspace,
    setCurrentView,
  } = useAppStore();

  const [processingRunId, setProcessingRunId] = useState<string | null>(null);
  const [viewOutputsRun, setViewOutputsRun] = useState<Run | null>(null);

  if (!isHistoryOpen) return null;

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 size={12} className="text-emerald-500" />;
      case 'failed':
      case 'error':
        return <AlertCircle size={12} className="text-red-500" />;
      case 'running':
      case 'queued':
        return <Loader2 size={12} className="text-blue-400 animate-spin" />;
      case 'paused':
        return <Pause size={12} className="text-yellow-500" />;
      case 'waiting':
        return <Clock size={12} className="text-amber-400 animate-pulse" />;
      case 'cancelled':
        return <Clock size={12} className="text-yellow-500" />;
      default:
        return <Clock size={12} className="text-slate-500" />;
    }
  };

  const handlePause = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!currentWorkspaceId) return;
    setProcessingRunId(runId);
    try {
      await api.pauseRun(currentWorkspaceId, runId);
      updateRun(runId, { status: 'paused' });
    } catch (err) {
      console.error('Failed to pause run:', err);
      alert('Failed to pause workflow');
    } finally {
      setProcessingRunId(null);
    }
  };

  const handleResume = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!currentWorkspaceId) return;
    setProcessingRunId(runId);
    try {
      await api.resumeRun(currentWorkspaceId, runId);
      updateRun(runId, { status: 'running' });
    } catch (err) {
      console.error('Failed to resume run:', err);
      alert('Failed to resume workflow');
    } finally {
      setProcessingRunId(null);
    }
  };

  const handleStop = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!currentWorkspaceId) return;
    if (!confirm('Are you sure you want to stop this workflow?')) return;
    setProcessingRunId(runId);
    try {
      await api.cancelRun(currentWorkspaceId, runId);
      updateRun(runId, { status: 'cancelled' });
      setIsRunning(false);
    } catch (err) {
      console.error('Failed to stop run:', err);
      alert('Failed to stop workflow');
    } finally {
      setProcessingRunId(null);
    }
  };

  const handleResumeFromCheckpoint = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!currentWorkspaceId) return;
    setProcessingRunId(runId);
    try {
      await api.resumeRunFromCheckpoint(currentWorkspaceId, { from_run_id: runId });
      const updated = await api.getRuns(currentWorkspaceId);
      setRuns(updated);
      setIsRunning(true);
    } catch (err) {
      console.error('Failed to resume from checkpoint:', err);
      alert('Failed to resume from checkpoint. See console for details.');
    } finally {
      setProcessingRunId(null);
    }
  };

  return (
    <aside className="w-64 bg-slate-900/60 border-r border-slate-800 flex flex-col z-40 animate-in slide-in-from-left duration-300 shadow-xl shrink-0">
      <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/40">
        <h2 className="text-[10px] font-black uppercase text-slate-400 tracking-widest">
          History Log
        </h2>
        <button
          onClick={() => setIsHistoryOpen(false)}
          className="text-slate-600 hover:text-slate-400"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
        {runs.length === 0 ? (
          <div className="text-center py-8 text-slate-600 text-xs italic">
            No runs yet. Click "Execute Graph" to start.
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              onClick={() => {
                setSelectedRunId(run.id);
                if (!selectedNodeId && nodes.length > 0) {
                  setSelectedNode(nodes[0].id);
                }
              }}
              className={cn(
                'group p-3 rounded-xl border transition-all cursor-pointer',
                selectedRunId === run.id
                  ? 'bg-indigo-600/10 border-indigo-500 shadow-lg scale-[1.02]'
                  : 'bg-slate-800/20 border-slate-800 hover:border-slate-700',
              )}
            >
              <div className="flex justify-between items-start mb-1">
                <span
                  className={cn(
                    'text-[11px] font-bold',
                    selectedRunId === run.id ? 'text-indigo-400' : 'text-slate-200',
                  )}
                >
                  {run.label || 'Run'}
                </span>
                <div className="flex items-center gap-2">
                  {/* View outputs: open modal with node outputs from snapshot */}
                  {run.snapshot?.node_outputs && Object.keys(run.snapshot.node_outputs).length > 0 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setViewOutputsRun(run);
                      }}
                      className="p-1 hover:bg-slate-700 rounded text-slate-400 hover:text-white"
                      title="View outputs"
                    >
                      <Maximize2 size={10} />
                    </button>
                  )}
                  {statusIcon(run.status)}
                  {/* Resume from checkpoint: for failed/cancelled/partial runs that have partial outputs */}
                  {(run.status === 'failed' || run.status === 'cancelled' || run.status === 'partial') &&
                    run.snapshot?.node_outputs &&
                    Object.keys(run.snapshot.node_outputs).length > 0 && (
                      <button
                        onClick={(e) => handleResumeFromCheckpoint(e, run.id)}
                        disabled={processingRunId === run.id}
                        className="p-1 hover:bg-indigo-600/20 rounded text-indigo-400 hover:text-indigo-300 disabled:opacity-50"
                        title="Resume from here (skip completed nodes)"
                      >
                        <RotateCcw size={10} />
                      </button>
                    )}
                  {/* Control buttons for active runs */}
                  {(run.status === 'running' || run.status === 'paused' || run.status === 'queued' || run.status === 'waiting') && (
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {run.status === 'running' && (
                        <button
                          onClick={(e) => handlePause(e, run.id)}
                          disabled={processingRunId === run.id}
                          className="p-1 hover:bg-yellow-600/20 rounded text-yellow-400 hover:text-yellow-300 disabled:opacity-50"
                          title="Pause"
                        >
                          <Pause size={10} />
                        </button>
                      )}
                      {run.status === 'paused' && (
                        <button
                          onClick={(e) => handleResume(e, run.id)}
                          disabled={processingRunId === run.id}
                          className="p-1 hover:bg-green-600/20 rounded text-green-400 hover:text-green-300 disabled:opacity-50"
                          title="Resume"
                        >
                          <Play size={10} />
                        </button>
                      )}
                      <button
                        onClick={(e) => handleStop(e, run.id)}
                        disabled={processingRunId === run.id}
                        className="p-1 hover:bg-red-600/20 rounded text-red-400 hover:text-red-300 disabled:opacity-50"
                        title="Stop"
                      >
                        <Square size={10} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-between items-center text-[9px] text-slate-500 font-mono mt-1">
                <span>
                  {run.started_at
                    ? new Date(run.started_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '—'}
                </span>
                <span>
                  {run.duration ? `${(run.duration / 1000).toFixed(1)}s` : run.status}
                </span>
              </div>
              {run.parent_run_id && (
                <div
                  className="mt-1.5 text-[9px] text-slate-500 flex items-center gap-1"
                  title="Triggered by parent run"
                >
                  <span className="italic">Triggered by parent</span>
                </div>
              )}
              {selectedRunId === run.id && run.parent_run_id && run.parent_workflow_id && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setCurrentWorkspace(run.parent_workflow_id!);
                    setSelectedRunId(run.parent_run_id!);
                    setCurrentView('editor');
                  }}
                  className="mt-2 flex items-center gap-1 text-[10px] text-indigo-400 hover:text-indigo-300"
                  title="Go to parent run"
                >
                  <ArrowLeft size={10} />
                  Back to parent run
                </button>
              )}
              {/* Send Signal panel for waiting runs */}
              {selectedRunId === run.id && run.status === 'waiting' && currentWorkspaceId && (
                <div className="mt-2">
                  <SendSignalPanel runId={run.id} workspaceId={currentWorkspaceId} />
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <RunOutputsModal
        open={viewOutputsRun !== null}
        run={viewOutputsRun}
        nodes={nodes}
        onClose={() => setViewOutputsRun(null)}
      />
    </aside>
  );
}

