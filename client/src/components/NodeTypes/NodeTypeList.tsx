// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * List of all node types (pattern similar to WorkspaceList).
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import type { NodeType } from '@/types';
import { Box, Code, Database, Cpu, History, Workflow } from 'lucide-react';
import { cn } from '@/utils/cn';

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'input': Database,
  'custom-python': Code,
  'condition-python': Code,
  'custom-llm': Cpu,
  'memory': History,
  'workflow_node': Workflow,
  database: Database,
  code: Code,
  cpu: Cpu,
  history: History,
  workflow: Workflow,
  default: Box,
};

function getIcon(type: NodeType) {
  const Icon = iconMap[type.id] || iconMap[type.id?.split('-')[0]] || iconMap[type.icon || ''] || iconMap.default;
  return Icon;
}

function typeKindLabel(typeKind?: string) {
  if (!typeKind) return 'Node type';
  if (typeKind === 'node_template') return 'Node template';
  if (typeKind === 'workflow_template') return 'Workflow template';
  return 'Built-in';
}

interface NodeTypeListProps {
  onSelectType: (nodeTypeId: string) => void;
}

export function NodeTypeList({ onSelectType }: NodeTypeListProps) {
  const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getNodeTypes()
      .then((types) => {
        if (!cancelled) setNodeTypes(types);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load node types');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-12 animate-in fade-in duration-300">
        <div className="max-w-5xl mx-auto w-full flex items-center justify-center py-24">
          <p className="text-slate-500 text-sm">Loading node types...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-12 animate-in fade-in duration-300">
        <div className="max-w-5xl mx-auto w-full">
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
            {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-12 animate-in fade-in duration-300">
      <div className="shrink-0 max-w-5xl mx-auto w-full">
        <header className="mb-12 border-b border-slate-800 pb-8">
          <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">Node Types</h1>
          <p className="text-slate-500 text-sm">
            View and edit component types: built-in nodes, node templates, and workflow templates.
          </p>
        </header>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {nodeTypes.length === 0 ? (
              <div className="col-span-full text-center py-12">
                <p className="text-slate-500 text-sm">No node types found.</p>
              </div>
            ) : (
              nodeTypes.map((type) => {
                const IconComponent = getIcon(type);
                return (
                  <div
                    key={type.id}
                    onClick={() => onSelectType(type.id)}
                    className={cn(
                      'group relative p-8 rounded-[2.5rem] border-2 transition-all cursor-pointer hover:scale-[1.02]',
                      'bg-slate-900 border-slate-800 hover:border-slate-700'
                    )}
                  >
                    <div className="flex justify-between items-start mb-6">
                      <div className="p-3 rounded-2xl bg-slate-800 text-slate-400 group-hover:text-amber-400 transition-colors">
                        <IconComponent size={24} />
                      </div>
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                        {typeKindLabel(type.type_kind)}
                      </span>
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">{type.name}</h3>
                    <p className="text-sm text-slate-500 line-clamp-2">
                      {type.description || 'No description'}
                    </p>
                    {type.usage_count !== undefined && type.usage_count > 0 && (
                      <p className="text-xs text-slate-600 mt-2">Used {type.usage_count} times</p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
