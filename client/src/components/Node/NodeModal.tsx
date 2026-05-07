// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Node Modal - Matching reference design with search
 */
import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { Search, X, Database, Code, Cpu, History } from 'lucide-react';
import type { NodeType } from '@/types';
import { PYTHON_NODE_TEMPLATE } from './pythonNodeTemplate';

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'input': Database,
  'custom-python': Code,
  'custom-llm': Cpu,
  'memory': History,
};

export function NodeModal() {
  const { 
    isNodeModalOpen, 
    setIsNodeModalOpen, 
    nodeSearchQuery, 
    setNodeSearchQuery,
    currentWorkspaceId,
    transform,
    addNode,
    setNodes
  } = useAppStore();

  const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isNodeModalOpen) {
      setLoading(true);
      api.getNodeTypes()
        .then((types) => {
          // API response may not include is_active field
          // Show all nodes if is_active is missing, otherwise filter by is_active
          setNodeTypes(types.filter(t => {
            const nodeType = t as any; // Type assertion to handle missing field
            return nodeType.is_active !== false; // Show if true or undefined
          }));
        })
        .catch((error) => {
          console.error('Failed to load node types:', error);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isNodeModalOpen]);

  const filteredNodes = nodeTypes.filter(n => 
    n.name.toLowerCase().includes(nodeSearchQuery.toLowerCase()) ||
    n.description?.toLowerCase().includes(nodeSearchQuery.toLowerCase())
  );

  const handleAddNode = async (nodeType: NodeType) => {
    if (!currentWorkspaceId) return;
    
    try {
      // Center position accounting for transform
      const container = document.querySelector('.canvas-container');
      const rect = container?.getBoundingClientRect();
      const centerX = rect ? (rect.width / 2 - transform.x) / transform.k : 0;
      const centerY = rect ? (rect.height / 2 - transform.y) / transform.k : 0;
      
      // For a bare custom-python NodeType with no backend-seeded code, inject
      // the starter template (sets the `def main(inputs, storages, files)`
      // shape + comments for files/storages methods). Backend-seeded code
      // wins if present, so this is a frontend fallback only.
      const config_overrides = {
        ...(nodeType.default_config || {}),
        ...(nodeType.id === 'custom-python' && !nodeType.default_config?.code
          ? { code: PYTHON_NODE_TEMPLATE }
          : {}),
      };

      const newNode = await api.createNode(currentWorkspaceId, {
        node_type_id: nodeType.id,
        x: centerX - 110,
        y: centerY - 60,
        config_overrides,
      });
      
      // Add to store
      addNode(newNode);
      
      // Reload workspace to ensure sync
      const workspace = await api.getWorkspace(currentWorkspaceId);
      setNodes(workspace.nodes || []);
      
      setIsNodeModalOpen(false);
      setNodeSearchQuery('');
    } catch (error) {
      console.error('Failed to create node:', error);
      alert('Failed to create node. Please try again.');
    }
  };

  if (!isNodeModalOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl animate-in zoom-in-95 duration-200 overflow-hidden">
        <div className="p-6 border-b border-slate-800 bg-slate-900/50 flex items-center gap-4">
          <Search size={20} className="text-indigo-400" />
          <input 
            autoFocus 
            className="flex-1 bg-transparent text-lg text-white outline-none placeholder:text-slate-700 font-bold" 
            placeholder="Find a component..." 
            value={nodeSearchQuery} 
            onChange={e => setNodeSearchQuery(e.target.value)} 
          />
          <button 
            onClick={() => {
              setIsNodeModalOpen(false);
              setNodeSearchQuery('');
            }} 
            className="text-slate-600 hover:text-white transition-colors"
          >
            <X size={20}/>
          </button>
        </div>
        <div className="max-h-[400px] overflow-y-auto p-4 custom-scrollbar space-y-1 bg-slate-950/20">
          {loading ? (
            <div className="text-center py-8 text-slate-500">Loading node types...</div>
          ) : filteredNodes.length === 0 ? (
            <div className="text-center py-8 text-slate-500">No node types found</div>
          ) : (
            filteredNodes.map(nodeType => {
              const IconComponent = iconMap[nodeType.id] || iconMap[nodeType.id.split('-')[0]] || Database;
              const iconColor = nodeType.id === 'input' ? 'text-emerald-500' : 
                               nodeType.id === 'custom-python' ? 'text-yellow-500' : 
                               nodeType.id === 'custom-llm' ? 'text-purple-500' : 
                               'text-blue-500';
              
              return (
                <button 
                  key={nodeType.id} 
                  onClick={() => handleAddNode(nodeType)} 
                  className="w-full flex items-start gap-4 p-4 rounded-2xl hover:bg-indigo-600/10 transition-all text-left group"
                >
                  <div className="p-3 bg-slate-950 rounded-xl group-hover:scale-110 transition-transform shadow-inner">
                    <IconComponent size={18} className={iconColor} />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-white mb-0.5 group-hover:text-indigo-400 transition-colors">
                      {nodeType.name}
                    </h4>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {nodeType.description || 'No description'}
                    </p>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

