/**
 * Properties panel - Matching reference design
 */
import React from 'react';
import { useAppStore } from '@/stores';
import { NodeProperties } from './NodeProperties';
import { EdgeProperties } from './EdgeProperties';
import { WorkflowExecutionSettings } from './WorkflowExecutionSettings';
import { X } from 'lucide-react';

export function PropertiesPanel() {
  const { selectedNodeId, selectedEdgeId, nodes, edges, setPropertiesPanelOpen } = useAppStore();

  const selectedNode = selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) : null;
  const selectedEdge = selectedEdgeId ? edges.find((e) => e.id === selectedEdgeId) : null;

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Header */}
      <div className="p-5 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center">
        <div className="flex flex-col">
          <h2 className="text-[10px] font-black uppercase text-slate-400 tracking-widest">
            {selectedEdge ? 'Connection' : selectedNode ? 'Configuration' : 'Properties'}
          </h2>
          {(selectedNode || selectedEdge) && (
            <span className="text-[9px] text-slate-600 font-mono tracking-tighter">
              ID: {(selectedNode || selectedEdge)?.id.slice(-4)}
            </span>
          )}
        </div>
        <button
          onClick={() => setPropertiesPanelOpen(false)}
          className="p-1 hover:bg-slate-800 rounded-lg text-slate-500 transition-colors"
          aria-label="Close properties panel"
        >
          <X size={18} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 custom-scrollbar space-y-6">
        {selectedNode ? (
          <NodeProperties node={selectedNode} />
        ) : selectedEdge ? (
          <EdgeProperties edge={selectedEdge} />
        ) : (
          <WorkflowExecutionSettings />
        )}
      </div>
    </div>
  );
}
