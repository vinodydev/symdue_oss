// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Detail for code-based node types: center = code editor (+ translator tab), right = properties form.
 */
import React, { useState, useCallback } from 'react';
import { ArrowLeft, Code2, Brain, Settings2 } from 'lucide-react';
import { api } from '@/services/api';
import type { NodeType, NodeTypeUpdate } from '@/types';
import { PythonCodeEditor } from '../Properties/PythonCodeEditor';
import { NodeTypePropertiesForm } from './NodeTypePropertiesForm';

function getDefaultCode(type: NodeType): string {
  const fromConfig = type.default_config?.python_code ?? type.default_config?.code;
  if (typeof fromConfig === 'string') return fromConfig;
  const fromTemplate = type.node_template_data?.python_code;
  if (typeof fromTemplate === 'string') return fromTemplate;
  return '# Return value is passed to the next node\nreturn {"output": "Hello"}\n';
}

interface NodeTypeDetailCodeProps {
  nodeType: NodeType;
  onBack: () => void;
  onSaved: () => void;
}

export function NodeTypeDetailCode({
  nodeType,
  onBack,
  onSaved,
}: NodeTypeDetailCodeProps) {
  const [code, setCode] = useState(getDefaultCode(nodeType));
  const [savingCode, setSavingCode] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [activeTab, setActiveTab] = useState<'code' | 'translator' | 'config'>('code');

  const hasTranslator = !!(nodeType.default_config?.translator);
  const [translatorJson, setTranslatorJson] = useState(
    JSON.stringify(nodeType.default_config?.translator || {}, null, 2)
  );
  const [translatorDirty, setTranslatorDirty] = useState(false);

  const handleCodeChange = useCallback((newCode: string) => {
    setCode(newCode);
    setDirty(true);
  }, []);

  const handleSaveCode = async () => {
    if (!dirty) return;
    setSavingCode(true);
    try {
      const payload: NodeTypeUpdate = {
        default_config: {
          ...(nodeType.default_config || {}),
          python_code: code,
          code: code,
        },
      };
      await api.updateNodeType(nodeType.id, payload);
      setDirty(false);
      onSaved();
    } catch (err) {
      console.error('Failed to save code', err);
    } finally {
      setSavingCode(false);
    }
  };

  const handleSaveTranslator = async () => {
    if (!translatorDirty) return;
    setSavingCode(true);
    try {
      const parsed = JSON.parse(translatorJson);
      const payload: NodeTypeUpdate = {
        default_config: {
          ...(nodeType.default_config || {}),
          translator: parsed,
        },
      };
      await api.updateNodeType(nodeType.id, payload);
      setTranslatorDirty(false);
      onSaved();
    } catch (err) {
      console.error('Failed to save translator config', err);
    } finally {
      setSavingCode(false);
    }
  };

  const config = nodeType.default_config || {};

  return (
    <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 animate-in fade-in duration-200">
      <div className="shrink-0 flex items-center justify-between gap-4 px-8 py-4 border-b border-slate-800">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white"
        >
          <ArrowLeft size={18} /> Back to Node Types
        </button>
        <h1 className="text-lg font-bold text-white truncate">{nodeType.name}</h1>
        <div className="flex items-center gap-2">
          {config.stateful && (
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400">STATEFUL</span>
          )}
          {hasTranslator && (
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-indigo-950/40 text-indigo-400">SMART NODE</span>
          )}
        </div>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Center: tabbed content */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-slate-800">
          {/* Tab bar */}
          <div className="shrink-0 flex items-center gap-1 px-6 pt-4 pb-0">
            <button
              onClick={() => setActiveTab('code')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-t-lg border-b-2 transition-colors ${
                activeTab === 'code'
                  ? 'border-indigo-500 text-white bg-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" /> Code
            </button>
            {hasTranslator && (
              <button
                onClick={() => setActiveTab('translator')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-t-lg border-b-2 transition-colors ${
                  activeTab === 'translator'
                    ? 'border-indigo-500 text-white bg-slate-900'
                    : 'border-transparent text-slate-500 hover:text-slate-300'
                }`}
              >
                <Brain className="w-3.5 h-3.5" /> Translator
              </button>
            )}
            <button
              onClick={() => setActiveTab('config')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-t-lg border-b-2 transition-colors ${
                activeTab === 'config'
                  ? 'border-indigo-500 text-white bg-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              <Settings2 className="w-3.5 h-3.5" /> Config
            </button>
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0 p-6 pt-3">
            {activeTab === 'code' && (
              <div className="flex flex-col h-full">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                    {config.stateful ? 'Skill handler code' : 'Default / template code'}
                  </span>
                  <button
                    onClick={handleSaveCode}
                    disabled={!dirty || savingCode}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-colors"
                  >
                    {savingCode ? 'Saving...' : 'Save code'}
                  </button>
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
                  <PythonCodeEditor
                    value={code}
                    onChange={handleCodeChange}
                    minHeight="100%"
                    className="h-full min-h-[320px]"
                  />
                </div>
              </div>
            )}

            {activeTab === 'translator' && hasTranslator && (
              <div className="flex flex-col h-full">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                    Translator config (JSON)
                  </span>
                  <button
                    onClick={handleSaveTranslator}
                    disabled={!translatorDirty || savingCode}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-colors"
                  >
                    {savingCode ? 'Saving...' : 'Save translator'}
                  </button>
                </div>
                {/* Summary cards */}
                <div className="flex flex-wrap gap-2 mb-3">
                  {config.translator?.model && (
                    <span className="text-[10px] px-2 py-1 bg-slate-800 text-cyan-400 rounded">
                      Model: {config.translator.model}
                    </span>
                  )}
                  {config.translator?.functions && (
                    <span className="text-[10px] px-2 py-1 bg-slate-800 text-slate-400 rounded">
                      {config.translator.functions.length} functions
                    </span>
                  )}
                  {config.translator?.skip_llm_patterns && (
                    <span className="text-[10px] px-2 py-1 bg-slate-800 text-slate-400 rounded">
                      {config.translator.skip_llm_patterns.length} skip patterns
                    </span>
                  )}
                  {config.translator?.max_steps && (
                    <span className="text-[10px] px-2 py-1 bg-slate-800 text-slate-400 rounded">
                      Max {config.translator.max_steps} steps
                    </span>
                  )}
                </div>
                {/* JSON editor */}
                <div className="flex-1 min-h-0 overflow-hidden">
                  <textarea
                    value={translatorJson}
                    onChange={(e) => { setTranslatorJson(e.target.value); setTranslatorDirty(true); }}
                    className="w-full h-full bg-slate-900 text-slate-300 font-mono text-xs p-4 rounded-lg border border-slate-800 resize-none focus:outline-none focus:border-indigo-500"
                    spellCheck={false}
                  />
                </div>
              </div>
            )}

            {activeTab === 'config' && (
              <div className="flex flex-col h-full overflow-y-auto space-y-4">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  Node configuration
                </span>
                <div className="space-y-3 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 w-28">Stateful:</span>
                    <span className={config.stateful ? 'text-emerald-400' : 'text-slate-600'}>
                      {config.stateful ? 'Yes (container stays alive)' : 'No'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 w-28">Requirements:</span>
                    <span className="text-slate-300 font-mono">{config.requirements || 'none'}</span>
                  </div>
                  {config.container?.image && (
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 w-28">Docker image:</span>
                      <span className="text-slate-300 font-mono text-[10px]">{config.container.image}</span>
                    </div>
                  )}
                </div>
                {/* Raw JSON fallback */}
                <div className="mt-4">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                    Raw default_config
                  </span>
                  <pre className="mt-2 p-3 bg-slate-900 text-slate-400 font-mono text-[10px] rounded-lg border border-slate-800 overflow-auto max-h-60">
                    {JSON.stringify(config, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: properties panel */}
        <aside className="w-80 shrink-0 p-6 bg-slate-900/50 border-l border-slate-800 overflow-y-auto custom-scrollbar">
          <h2 className="text-[10px] font-black uppercase text-slate-400 tracking-widest mb-4">
            Type properties
          </h2>
          <NodeTypePropertiesForm
            nodeType={nodeType}
            onSaved={onSaved}
            compact
          />
        </aside>
      </div>
    </div>
  );
}
