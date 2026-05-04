/**
 * Python script editor component for Event scripts.
 */
import React, { useState } from 'react';
import { Maximize2, Minimize2, ChevronDown, ChevronRight } from 'lucide-react';

interface ScriptEditorProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  minHeight?: string;
}

const RUNTIME_API_REF = [
  { method: 'runtime.emit_to_channel(channel, data)', description: 'Broadcast to all runs waiting on channel' },
  { method: 'runtime.run_workflow(name_or_id, input)', description: 'Start a new workflow run, returns run_id' },
  { method: 'runtime.get_workflow(run_id)', description: 'Get run status and output snapshot' },
  { method: 'runtime.get_state()', description: "Read this event's persistent JSON state" },
  { method: 'runtime.set_state(data)', description: "Write back to the event's persistent state" },
  { method: 'runtime.create_event(spec)', description: 'Dynamically create a new event, returns event_id' },
  { method: 'runtime.stop_event(event_id)', description: 'Disable an event (self or other)' },
  { method: 'runtime.send_signal(run_id, signal, data)', description: 'Point-to-point signal to a specific run' },
];

export function ScriptEditor({ value, onChange, disabled, minHeight = '200px' }: ScriptEditorProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showRef, setShowRef] = useState(false);

  const textareaClass = [
    'w-full font-mono text-xs text-slate-200 bg-slate-950 border border-slate-700/50 rounded-lg p-3',
    'focus:outline-none focus:border-blue-500/60 resize-none',
    'placeholder-slate-600',
    disabled ? 'opacity-50 cursor-not-allowed' : '',
  ].join(' ');

  const content = (
    <div className={isFullscreen ? 'fixed inset-0 z-50 bg-slate-950 flex flex-col p-6' : 'space-y-2'}>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
          Python Script
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowRef(!showRef)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            {showRef ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            API Reference
          </button>
          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>

      {showRef && (
        <div className="mb-2 p-3 bg-slate-900 border border-slate-700/50 rounded-lg">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Runtime API</p>
          <div className="space-y-1">
            {RUNTIME_API_REF.map(({ method, description }) => (
              <div key={method} className="text-[10px]">
                <code className="text-purple-300">{method}</code>
                <span className="text-slate-500 ml-2">— {description}</span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-slate-500 mt-2">
            Also available: <code className="text-slate-400">state</code>, <code className="text-slate-400">input</code>, <code className="text-slate-400">event</code>, <code className="text-slate-400">logger</code>
          </p>
        </div>
      )}

      <textarea
        className={textareaClass}
        style={{ minHeight: isFullscreen ? 'calc(100vh - 200px)' : minHeight }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={`# Available: runtime, state, input, event, logger\n\ndef on_tick():\n    state = runtime.get_state()\n    # ... your logic here ...\n    runtime.emit_to_channel("my_channel", {"data": "value"})\n    runtime.set_state({**state, "last_tick": "done"})`}
        spellCheck={false}
      />
    </div>
  );

  return content;
}
