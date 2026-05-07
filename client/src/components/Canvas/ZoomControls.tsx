// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Zoom controls component - Matching reference design
 */
import React from 'react';
import { useAppStore } from '@/stores';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

export function ZoomControls() {
  const { transform, setTransform } = useAppStore();

  const handleZoomIn = () => {
    setTransform({
      ...transform,
      k: Math.min(3, transform.k * 1.2),
    });
  };

  const handleZoomOut = () => {
    setTransform({
      ...transform,
      k: Math.max(0.1, transform.k / 1.2),
    });
  };

  const handleReset = () => {
    setTransform({ x: 0, y: 0, k: 1 });
  };

  return (
    <div className="absolute bottom-4 right-4 flex flex-col gap-2 bg-slate-900 border border-slate-800 rounded-2xl p-2 shadow-2xl">
      <button
        onClick={handleZoomIn}
        className="p-2 hover:bg-slate-800 rounded-xl transition-colors text-slate-400 hover:text-white"
        title="Zoom in"
      >
        <ZoomIn size={18} />
      </button>
      <div className="text-[10px] text-center text-slate-500 px-2 py-1 font-mono font-bold">
        {Math.round(transform.k * 100)}%
      </div>
      <button
        onClick={handleZoomOut}
        className="p-2 hover:bg-slate-800 rounded-xl transition-colors text-slate-400 hover:text-white"
        title="Zoom out"
      >
        <ZoomOut size={18} />
      </button>
      <div className="border-t border-slate-800 my-1" />
      <button
        onClick={handleReset}
        className="p-2 hover:bg-slate-800 rounded-xl transition-colors text-slate-400 hover:text-white"
        title="Reset zoom"
      >
        <Maximize2 size={18} />
      </button>
    </div>
  );
}
