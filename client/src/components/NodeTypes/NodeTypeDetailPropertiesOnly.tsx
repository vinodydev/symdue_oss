/**
 * Detail for built-in / default types: properties-only form (settings-like).
 */
import React from 'react';
import { ArrowLeft } from 'lucide-react';
import type { NodeType } from '@/types';
import { NodeTypePropertiesForm } from './NodeTypePropertiesForm';

interface NodeTypeDetailPropertiesOnlyProps {
  nodeType: NodeType;
  onBack: () => void;
  onSaved: () => void;
}

export function NodeTypeDetailPropertiesOnly({
  nodeType,
  onBack,
  onSaved,
}: NodeTypeDetailPropertiesOnlyProps) {
  return (
    <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-8 animate-in fade-in duration-200">
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-slate-400 hover:text-white mb-6 w-fit"
      >
        <ArrowLeft size={18} /> Back to Node Types
      </button>

      <div className="max-w-xl">
        <h1 className="text-2xl font-bold text-white mb-6">{nodeType.name}</h1>
        <NodeTypePropertiesForm
          nodeType={nodeType}
          onSaved={onSaved}
        />
      </div>
    </div>
  );
}
