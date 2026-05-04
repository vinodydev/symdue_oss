/**
 * Settings page — split-view with Model Registry and General tabs.
 * Matching reference (code.jsx lines 602-678).
 */
import { useState } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { Globe, Monitor, Plus, Trash2, Key, Database } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { LLMConfig } from '@/types';
import { StorageSettings } from './StorageSettings';

function SettingsTabItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-5 py-4 rounded-2xl text-sm font-bold transition-all border',
        active
          ? 'bg-indigo-600/10 text-indigo-400 border-indigo-500/20 shadow-sm'
          : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300 border-transparent',
      )}
    >
      {icon} {label}
    </button>
  );
}

export function SettingsPage() {
  const { llmConfigs, addLLMConfig, updateLLMConfig, deleteLLMConfig } = useAppStore();
  const [activeTab, setActiveTab] = useState<'llm' | 'general' | 'storage'>('llm');

  const handleAddConfig = async () => {
    try {
      const config = await api.createLLMConfig({
        name: 'New AI Model',
        provider: 'openai',
        model: 'gpt-4',
        config: {},
      });
      addLLMConfig(config);
    } catch (err) {
      console.error('Failed to create LLM config:', err);
      alert('Failed to create LLM config');
    }
  };

  const handleUpdate = async (id: string, updates: Partial<LLMConfig>) => {
    try {
      const updated = await api.updateLLMConfig(id, updates);
      updateLLMConfig(id, updated);
    } catch (err) {
      console.error('Failed to update LLM config:', err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteLLMConfig(id);
      deleteLLMConfig(id);
    } catch (err) {
      console.error('Failed to delete LLM config:', err);
    }
  };

  return (
    <div className="flex-1 bg-slate-950 flex animate-in fade-in duration-300">
      {/* Left tabs sidebar */}
      <div className="w-72 border-r border-slate-800 bg-slate-900/50 p-8 space-y-2 shrink-0">
        <h1 className="text-2xl font-bold text-white mb-8 tracking-tight">System Settings</h1>
        <SettingsTabItem
          icon={<Globe size={18} />}
          label="Model Registry"
          active={activeTab === 'llm'}
          onClick={() => setActiveTab('llm')}
        />
        <SettingsTabItem
          icon={<Database size={18} />}
          label="Storage"
          active={activeTab === 'storage'}
          onClick={() => setActiveTab('storage')}
        />
        <SettingsTabItem
          icon={<Monitor size={18} />}
          label="General System"
          active={activeTab === 'general'}
          onClick={() => setActiveTab('general')}
        />
      </div>

      {/* Right content panel */}
      <div className="flex-1 p-12">
        {activeTab === 'llm' ? (
          <div className="max-w-3xl">
            {/* Header - fixed */}
            <div className="flex justify-between items-center border-b border-slate-800 pb-6 mb-8">
              <div>
                <h2 className="text-xl font-bold text-white">AI Model Registry</h2>
                <p className="text-slate-500 text-sm mt-1">
                  Configure global AI providers and security tokens.
                </p>
              </div>
              <button
                onClick={handleAddConfig}
                className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-2xl shadow-xl transition-all"
              >
                <Plus size={20} /> Add Provider
              </button>
            </div>

            {/* Scrollable list */}
            <div className="overflow-y-auto custom-scrollbar h-[80vh]">
              <div className="grid gap-6">
                {llmConfigs.length === 0 ? (
                  <div className="text-center py-12 text-slate-600 italic text-sm">
                    No AI providers configured yet.
                  </div>
                ) : (
                  llmConfigs.map((conf) => (
                    <LLMConfigCard
                      key={conf.id}
                      config={conf}
                      onUpdate={(updates) => handleUpdate(conf.id, updates)}
                      onDelete={() => handleDelete(conf.id)}
                    />
                  ))
                )}
              </div>
            </div>
          </div>
        ) : activeTab === 'storage' ? (
          <StorageSettings />
        ) : (
          <div className="space-y-8 max-w-2xl animate-in slide-in-from-right-4">
            <div className="flex justify-between items-center border-b border-slate-800 pb-6">
              <h2 className="text-xl font-bold text-white">General Environment</h2>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-8 shadow-xl">
              <p className="text-sm text-slate-400">
                General settings (auto-save, telemetry, theme) will be available here.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── LLM Config Card ────────────────────────────────────── */

function LLMConfigCard({
  config,
  onUpdate,
  onDelete,
}: {
  config: LLMConfig;
  onUpdate: (updates: Partial<LLMConfig>) => void;
  onDelete: () => void;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-10 relative group shadow-2xl transition-all hover:border-slate-700">
      <button
        onClick={onDelete}
        className="absolute top-8 right-10 text-slate-700 hover:text-red-500 transition-all opacity-0 group-hover:opacity-100 flex items-center gap-2"
      >
        <Trash2 size={18} />
      </button>

      <div className="grid grid-cols-2 gap-12">
        {/* Left column */}
        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
              Provider Label
            </label>
            <input
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white focus:border-indigo-500 outline-none"
              value={config.name}
              onChange={(e) => onUpdate({ name: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
              Service Engine
            </label>
            <select
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500 appearance-none"
              value={config.provider}
              onChange={(e) => onUpdate({ provider: e.target.value })}
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic Claude</option>
              <option value="google">Google Gemini</option>
              <option value="perplexity">Perplexity AI</option>
              <option value="local">Ollama / Local</option>
            </select>
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
              Model Identifier
            </label>
            <input
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
              value={config.model}
              onChange={(e) => onUpdate({ model: e.target.value })}
              placeholder="e.g. gpt-4o"
            />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
              Security Key (API Key)
            </label>
            <div className="relative">
              <Key size={16} className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-600" />
              <input
                type="password"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-12 pr-5 py-4 text-sm text-white focus:border-indigo-500 font-mono outline-none"
                value={config.config?.api_key || ''}
                onChange={(e) =>
                  onUpdate({ config: { ...config.config, api_key: e.target.value } })
                }
                placeholder="sk-••••••••"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
              Base URL (optional)
            </label>
            <input
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white focus:border-indigo-500 font-mono outline-none"
              value={config.base_url || ''}
              onChange={(e) => onUpdate({ base_url: e.target.value || null })}
              placeholder="https://api.openai.com/v1"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

