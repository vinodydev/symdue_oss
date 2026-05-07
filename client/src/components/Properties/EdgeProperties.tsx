// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Edge properties editor - Matching reference design
 */
import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { Edge } from '@/types';
import { Scale, Trash2 } from 'lucide-react';

interface EdgePropertiesProps {
  edge: Edge;
}

export function EdgeProperties({ edge }: EdgePropertiesProps) {
  const { currentWorkspaceId, updateEdge, nodes, setSelectedEdge, setPropertiesPanelOpen } = useAppStore();
  const [weight, setWeight] = useState(edge.weight);

  useEffect(() => {
    setWeight(edge.weight);
  }, [edge.id, edge.weight]);

  const sourceNode = nodes.find((n) => n.id === edge.source);
  const targetNode = nodes.find((n) => n.id === edge.target);

  const handleWeightChange = async (newWeight: number) => {
    if (!currentWorkspaceId) return;

    setWeight(newWeight);
    try {
      await api.updateEdge(currentWorkspaceId, edge.id, { weight: newWeight });
      updateEdge(edge.id, { weight: newWeight });
    } catch (error) {
      console.error('Failed to update edge weight:', error);
      alert('Failed to update edge weight');
      setWeight(edge.weight); // Revert on error
    }
  };

  const handleDelete = async () => {
    if (!currentWorkspaceId) return;
    if (!confirm('Are you sure you want to delete this edge?')) {
      return;
    }

    try {
      await api.deleteEdge(currentWorkspaceId, edge.id);
      const { deleteEdge } = useAppStore.getState();
      deleteEdge(edge.id);
      setSelectedEdge(null);
      setPropertiesPanelOpen(false);
    } catch (error) {
      console.error('Failed to delete edge:', error);
      alert('Failed to delete edge');
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="p-4 bg-indigo-500/5 border border-indigo-500/20 rounded-2xl flex items-center gap-3">
        <Scale size={20} className="text-indigo-400" />
        <p className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Signal Importance</p>
      </div>
      
      <div className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between items-center text-[10px] font-bold uppercase text-slate-500">
            <span>Normalized Weight</span>
            <span className="text-indigo-400 font-mono text-xs">{weight.toFixed(1)}</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.1" 
            className="w-full accent-indigo-500 cursor-pointer h-1.5 bg-slate-800 rounded-full" 
            value={weight} 
            onChange={(e) => handleWeightChange(parseFloat(e.target.value))} 
          />
        </div>
        
        <button 
          onClick={handleDelete} 
          className="w-full py-3 mt-4 bg-red-950/20 text-red-500 border border-red-500/20 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-red-900/30 transition-all flex items-center justify-center gap-2"
        >
          <Trash2 size={14}/> Delete Connection
        </button>
      </div>
    </div>
  );
}
