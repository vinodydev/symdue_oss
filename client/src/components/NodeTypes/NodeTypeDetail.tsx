/**
 * Detail container: fetches node type and renders Code, Workflow, or Properties-only view.
 */
import React, { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import { api } from '@/services/api';
import type { NodeType } from '@/types';
import { NodeTypeDetailCode } from './NodeTypeDetailCode';
import { NodeTypeDetailWorkflow } from './NodeTypeDetailWorkflow';
import { NodeTypeDetailPropertiesOnly } from './NodeTypeDetailPropertiesOnly';

const CODE_BASED_IDS = new Set(['custom-python', 'condition-python']);

function hasCode(type: NodeType): boolean {
  if (CODE_BASED_IDS.has(type.id)) return true;
  if (type.type_kind === 'node_template') {
    const code = type.default_config?.python_code ?? type.node_template_data?.python_code;
    return typeof code === 'string';
  }
  const code = type.default_config?.python_code ?? type.default_config?.code;
  return typeof code === 'string';
}

interface NodeTypeDetailProps {
  nodeTypeId: string;
  onBack: () => void;
  setCurrentView: (view: 'workspaces' | 'editor' | 'settings' | 'node_types') => void;
  setCurrentWorkspace: (id: string | null) => void;
}

export function NodeTypeDetail({
  nodeTypeId,
  onBack,
  setCurrentView,
  setCurrentWorkspace,
}: NodeTypeDetailProps) {
  const [type, setType] = useState<NodeType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getNodeType(nodeTypeId)
      .then((t) => {
        if (!cancelled) setType(t);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Failed to load node type');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [nodeTypeId]);

  const refresh = () => {
    api.getNodeType(nodeTypeId).then(setType).catch(() => {});
  };

  if (loading) {
    return (
      <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-8">
        <p className="text-slate-500 text-sm">Loading...</p>
      </div>
    );
  }

  if (error || !type) {
    return (
      <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-8">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white mb-4"
        >
          <ArrowLeft size={18} /> Back to Node Types
        </button>
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
          {error || 'Node type not found'}
        </div>
      </div>
    );
  }

  if (type.type_kind === 'workflow_template') {
    return (
      <NodeTypeDetailWorkflow
        nodeType={type}
        onBack={onBack}
        onRefresh={refresh}
        setCurrentView={setCurrentView}
        setCurrentWorkspace={setCurrentWorkspace}
      />
    );
  }

  if (hasCode(type)) {
    return (
      <NodeTypeDetailCode
        nodeType={type}
        onBack={onBack}
        onSaved={refresh}
      />
    );
  }

  return (
    <NodeTypeDetailPropertiesOnly
      nodeType={type}
      onBack={onBack}
      onSaved={refresh}
    />
  );
}
