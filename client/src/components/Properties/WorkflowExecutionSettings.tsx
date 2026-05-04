/**
 * Workflow execution settings — timeouts for this workflow.
 * Shown in the Properties panel when no node/edge is selected.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { Settings, Save, RotateCcw } from 'lucide-react';

const DEFAULTS = {
  graph_activity_timeout_minutes: 30,
  heartbeat_timeout_minutes: 5,
  default_node_timeout_seconds: 600,
  max_node_timeout_seconds: 3600,
};

type ExecutionConfig = Record<keyof typeof DEFAULTS, number>;

function parseNum(value: string, defaultVal: number): number {
  const n = parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : defaultVal;
}

export function WorkflowExecutionSettings() {
  const { currentWorkspaceId } = useAppStore();
  const [config, setConfig] = useState<ExecutionConfig>({ ...DEFAULTS });
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    if (!currentWorkspaceId) return;
    try {
      const res = await api.getExecutionConfig(currentWorkspaceId);
      const ec = res.execution_config || {};
      setConfig({
        graph_activity_timeout_minutes: Number(ec.graph_activity_timeout_minutes) || DEFAULTS.graph_activity_timeout_minutes,
        heartbeat_timeout_minutes: Number(ec.heartbeat_timeout_minutes) || DEFAULTS.heartbeat_timeout_minutes,
        default_node_timeout_seconds: Number(ec.default_node_timeout_seconds) || DEFAULTS.default_node_timeout_seconds,
        max_node_timeout_seconds: Number(ec.max_node_timeout_seconds) || DEFAULTS.max_node_timeout_seconds,
      });
      setLoaded(true);
      setDirty(false);
    } catch (e) {
      console.error('Failed to load execution config:', e);
      setConfig({ ...DEFAULTS });
      setLoaded(true);
    }
  }, [currentWorkspaceId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleChange = (key: keyof ExecutionConfig, value: string) => {
    const next = { ...config, [key]: parseNum(value, DEFAULTS[key]) };
    setConfig(next);
    setDirty(true);
    setMessage(null);
  };

  const handleSave = async () => {
    if (!currentWorkspaceId || !dirty) return;
    setSaving(true);
    setMessage(null);
    try {
      await api.updateExecutionConfig(currentWorkspaceId, { ...config });
      setDirty(false);
      setMessage({ type: 'success', text: 'Saved.' });
    } catch (e) {
      console.error('Failed to save execution config:', e);
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Save failed' });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setConfig({ ...DEFAULTS });
    setDirty(true);
    setMessage(null);
  };

  if (!currentWorkspaceId) {
    return (
      <div className="text-sm text-slate-500 text-center py-8">
        Open a workflow to edit execution settings.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-slate-400">
        <Settings size={16} />
        <span className="text-[10px] font-black uppercase tracking-widest">Workflow settings</span>
      </div>
      <p className="text-xs text-slate-500">
        Time limits for this workflow run and for each node. Uses defaults when empty.
      </p>

      <div className="space-y-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Execution timeouts</h3>

        <div className="space-y-2">
          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block">
            Graph run timeout (minutes)
          </label>
          <input
            type="number"
            min={1}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            value={config.graph_activity_timeout_minutes}
            onChange={(e) => handleChange('graph_activity_timeout_minutes', e.target.value)}
          />
          <p className="text-[10px] text-slate-600">Max time for the whole run.</p>
        </div>

        <div className="space-y-2">
          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block">
            Heartbeat timeout (minutes)
          </label>
          <input
            type="number"
            min={1}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            value={config.heartbeat_timeout_minutes}
            onChange={(e) => handleChange('heartbeat_timeout_minutes', e.target.value)}
          />
          <p className="text-[10px] text-slate-600">Max time between heartbeats.</p>
        </div>

        <div className="space-y-2">
          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block">
            Node timeout (seconds)
          </label>
          <input
            type="number"
            min={1}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            value={config.default_node_timeout_seconds}
            onChange={(e) => handleChange('default_node_timeout_seconds', e.target.value)}
          />
          <p className="text-[10px] text-slate-600">Max time for one node (e.g. one Python script).</p>
        </div>

        <div className="space-y-2">
          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block">
            Max node timeout (seconds)
          </label>
          <input
            type="number"
            min={1}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            value={config.max_node_timeout_seconds}
            onChange={(e) => handleChange('max_node_timeout_seconds', e.target.value)}
          />
          <p className="text-[10px] text-slate-600">Cap for node timeout (reserved).</p>
        </div>
      </div>

      {message && (
        <p
          className={
            message.type === 'success'
              ? 'text-xs text-emerald-400'
              : 'text-xs text-red-400'
          }
        >
          {message.text}
        </p>
      )}

      <div className="flex flex-wrap gap-2 pt-2">
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors"
        >
          <Save size={14} />
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 text-sm font-medium rounded-xl border border-slate-600 transition-colors"
        >
          <RotateCcw size={14} />
          Reset to defaults
        </button>
      </div>
    </div>
  );
}
