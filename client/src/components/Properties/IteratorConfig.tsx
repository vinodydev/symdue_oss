// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
import React from 'react';
import type { Node, Edge } from '@/types';
import { getUpstreamNodes } from '@/utils/nodeUtils';

interface IteratorConfigProps {
  node: Node;
  nodes: Node[];
  edges: Edge[];
  onUpdate: (updates: Partial<Node>) => void;
}

export function IteratorConfig({ node, nodes, edges, onUpdate }: IteratorConfigProps) {
  const upstreamNodes = getUpstreamNodes(node.id, nodes, edges);
  const iteratorConfig = node.config?.iterator || {};
  
  const handleIteratorToggle = (enabled: boolean) => {
    const updatedConfig = {
      ...node.config,
      iterator: {
        ...iteratorConfig,
        enabled,
      },
    };
    onUpdate({ config: updatedConfig });
  };
  
  const handleSourceNodeChange = (sourceNodeName: string) => {
    const updatedConfig = {
      ...node.config,
      iterator: {
        ...iteratorConfig,
        source_node_name: sourceNodeName || undefined,
      },
    };
    onUpdate({ config: updatedConfig });
  };
  
  const handleArrayKeyChange = (arrayKey: string) => {
    const updatedConfig = {
      ...node.config,
      iterator: {
        ...iteratorConfig,
        array_key: arrayKey || undefined,
      },
    };
    onUpdate({ config: updatedConfig });
  };
  
  const handleErrorStrategyChange = (errorStrategy: string) => {
    const updatedConfig = {
      ...node.config,
      iterator: {
        ...iteratorConfig,
        error_strategy: errorStrategy,
      },
    };
    onUpdate({ config: updatedConfig });
  };
  
  return (
    <div className="space-y-4 pt-4 border-t border-slate-800">
      <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-widest">
        Iterator Mode
      </label>
      
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="iterator-enabled"
          checked={iteratorConfig.enabled || false}
          onChange={(e) => handleIteratorToggle(e.target.checked)}
          className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
        />
        <label htmlFor="iterator-enabled" className="text-sm text-slate-300 cursor-pointer">
          Enable Iterator Mode
        </label>
      </div>
      
      {iteratorConfig.enabled && (
        <div className="space-y-3 pl-6 border-l-2 border-indigo-500/30">
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">
              Source Node (provides array)
            </label>
            <select
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
              value={iteratorConfig.source_node_name || ""}
              onChange={(e) => handleSourceNodeChange(e.target.value)}
            >
              <option value="">Select source node...</option>
              {upstreamNodes.map((upstream) => (
                <option key={upstream.id} value={upstream.name}>
                  {upstream.name}
                </option>
              ))}
            </select>
            {upstreamNodes.length === 0 && (
              <p className="text-xs text-slate-500 mt-1">
                No upstream nodes available. Connect a node first.
              </p>
            )}
          </div>
          
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">
              Array Key (optional, dot notation supported)
            </label>
            <input
              type="text"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
              placeholder="output (default) or items or data.results"
              value={iteratorConfig.array_key || ""}
              onChange={(e) => handleArrayKeyChange(e.target.value)}
            />
            <p className="text-xs text-slate-500 mt-1">
              Leave empty to use default "output" key
            </p>
          </div>
          
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">
              Error Strategy
            </label>
            <select
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
              value={iteratorConfig.error_strategy || "continue"}
              onChange={(e) => handleErrorStrategyChange(e.target.value)}
            >
              <option value="continue">Continue on Error (collect errors)</option>
              <option value="stop">Stop on First Error</option>
            </select>
          </div>
          
          <div className="p-3 bg-indigo-950/10 border border-indigo-500/20 rounded-lg">
            <p className="text-xs font-bold text-indigo-400 mb-2">How it works:</p>
            <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
              <li>Select the upstream node that provides the array</li>
              <li>Specify the key path to the array (default: "output")</li>
              <li>Each item in the array will be processed separately</li>
              <li>Results will be collected into an output array</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

