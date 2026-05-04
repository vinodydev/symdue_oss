/**
 * Properties panel for Wait nodes.
 */
import React, { useState, useEffect } from 'react';
import { Plus, X } from 'lucide-react';
import type { WaitMode } from '@/types';

interface WaitNodePropertiesProps {
  config: Record<string, any>;
  onConfigChange: (config: Record<string, any>) => void;
}

const MODE_LABELS: Record<WaitMode, string> = {
  signal: 'Signal — wait for one specific signal',
  any: 'Any — resume on first of several signals',
  all: 'All — wait for all listed signals',
  time: 'Time — resume after a duration',
  until: 'Until — resume at a specific time',
};

export function WaitNodeProperties({ config, onConfigChange }: WaitNodePropertiesProps) {
  const [channel, setChannel] = useState<string>(config.channel || '');
  const [mode, setMode] = useState<WaitMode>((config.mode as WaitMode) || 'signal');
  const [signals, setSignals] = useState<string[]>(config.signals || []);
  const [timeout, setTimeout_] = useState<string>(config.timeout || '');
  const [timeoutUnit, setTimeoutUnit] = useState<'minutes' | 'hours'>('minutes');
  const [duration, setDuration] = useState<string>(config.duration || '');
  const [until, setUntil] = useState<string>(config.until || '');

  // Sync from parent config when it changes externally
  useEffect(() => {
    setChannel(config.channel || '');
    setMode((config.mode as WaitMode) || 'signal');
    setSignals(config.signals || []);
    setTimeout_(config.timeout || '');
    setDuration(config.duration || '');
    setUntil(config.until || '');
  }, [config]);

  const emit = (patch: Partial<Record<string, any>>) => {
    onConfigChange({
      ...config,
      channel,
      mode,
      signals,
      timeout,
      duration,
      until,
      ...patch,
    });
  };

  const handleChannelChange = (v: string) => {
    setChannel(v);
    emit({ channel: v });
  };

  const handleModeChange = (v: WaitMode) => {
    setMode(v);
    emit({ mode: v });
  };

  const handleAddSignal = () => {
    const updated = [...signals, ''];
    setSignals(updated);
    emit({ signals: updated });
  };

  const handleRemoveSignal = (idx: number) => {
    const updated = signals.filter((_, i) => i !== idx);
    setSignals(updated);
    emit({ signals: updated });
  };

  const handleSignalChange = (idx: number, value: string) => {
    const updated = signals.map((s, i) => (i === idx ? value : s));
    setSignals(updated);
    emit({ signals: updated });
  };

  const handleTimeoutChange = (val: string) => {
    const formatted = val ? `${val}${timeoutUnit === 'minutes' ? 'm' : 'h'}` : '';
    setTimeout_(formatted);
    emit({ timeout: formatted });
  };

  const showSignalsList = mode === 'signal' || mode === 'any' || mode === 'all';
  const showTimeout = mode === 'signal' || mode === 'any' || mode === 'all';
  const showDuration = mode === 'time';
  const showUntil = mode === 'until';

  const timeoutNumericValue = timeout ? timeout.replace(/[mh]$/, '') : '';

  return (
    <div className="space-y-4">
      {/* Channel */}
      <div>
        <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">
          Channel
        </label>
        <input
          type="text"
          className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
          placeholder="e.g. order_approval"
          value={channel}
          onChange={(e) => handleChannelChange(e.target.value)}
        />
        <p className="text-[10px] text-slate-500 mt-1">
          Named channel to subscribe to. Use unique names to scope to a specific instance.
        </p>
      </div>

      {/* Mode */}
      <div>
        <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">
          Mode
        </label>
        <select
          className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500/60"
          value={mode}
          onChange={(e) => handleModeChange(e.target.value as WaitMode)}
        >
          {(Object.keys(MODE_LABELS) as WaitMode[]).map((m) => (
            <option key={m} value={m}>
              {MODE_LABELS[m]}
            </option>
          ))}
        </select>
      </div>

      {/* Signals list */}
      {showSignalsList && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-widest">
              {mode === 'signal' ? 'Signal Name' : 'Signal Names'}
            </label>
            <button
              type="button"
              onClick={handleAddSignal}
              className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              <Plus size={12} />
              Add
            </button>
          </div>
          {signals.length === 0 && (
            <p className="text-[10px] text-slate-500">
              {mode === 'signal'
                ? 'Leave empty to accept any signal.'
                : 'Add signal names to match.'}
            </p>
          )}
          <div className="space-y-1">
            {signals.map((sig, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="text"
                  className="flex-1 bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
                  placeholder="signal_name"
                  value={sig}
                  onChange={(e) => handleSignalChange(idx, e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => handleRemoveSignal(idx)}
                  className="text-slate-500 hover:text-red-400 transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeout (optional, for signal/any/all modes) */}
      {showTimeout && (
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">
            Timeout (optional)
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              min="1"
              className="flex-1 bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
              placeholder="e.g. 30"
              value={timeoutNumericValue}
              onChange={(e) => handleTimeoutChange(e.target.value)}
            />
            <select
              className="bg-slate-800/60 border border-slate-600/40 rounded-lg px-2 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500/60"
              value={timeoutUnit}
              onChange={(e) => {
                const u = e.target.value as 'minutes' | 'hours';
                setTimeoutUnit(u);
                if (timeoutNumericValue) {
                  const formatted = `${timeoutNumericValue}${u === 'minutes' ? 'm' : 'h'}`;
                  setTimeout_(formatted);
                  emit({ timeout: formatted });
                }
              }}
            >
              <option value="minutes">Minutes</option>
              <option value="hours">Hours</option>
            </select>
          </div>
          <p className="text-[10px] text-slate-500 mt-1">
            If set, the wait resolves with a timeout payload after this duration.
          </p>
        </div>
      )}

      {/* Duration (time mode) */}
      {showDuration && (
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">
            Duration
          </label>
          <input
            type="text"
            className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
            placeholder="e.g. 10m, 2h, 30s"
            value={duration}
            onChange={(e) => {
              setDuration(e.target.value);
              emit({ duration: e.target.value });
            }}
          />
        </div>
      )}

      {/* Until (until mode) */}
      {showUntil && (
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">
            Resume At
          </label>
          <input
            type="datetime-local"
            className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500/60"
            value={until}
            onChange={(e) => {
              setUntil(e.target.value);
              emit({ until: e.target.value });
            }}
          />
        </div>
      )}
    </div>
  );
}
