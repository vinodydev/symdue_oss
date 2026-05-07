// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Main application layout - Matching reference design
 */
import React from 'react';
import { useAppStore } from '@/stores';
import { PropertiesPanel } from './Properties/PropertiesPanel';
import { NodeModal } from './Node/NodeModal';
import { AddWorkflowAsNodeDialog } from './Node/AddWorkflowAsNodeDialog';
import {
  Layers,
  FolderKanban,
  LayoutDashboard,
  History as HistoryIcon,
  Plus,
  MousePointer2,
  Hand,
  Settings,
  Workflow,
  Box,
  Zap
} from 'lucide-react';
import { cn } from '@/utils/cn';

interface AppLayoutProps {
  children: React.ReactNode;
}

// Nav Icon Button Component (matching reference)
function NavIconButton({
  icon,
  active,
  onClick,
  label,
  color = "text-slate-500",
  disabled = false,
  testId
}: {
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
  label: string;
  color?: string;
  disabled?: boolean;
  testId?: string;
}) {
  return (
    <button
      data-testid={testId}
      onClick={disabled ? undefined : onClick}
      className={cn(
        "group relative w-12 h-12 flex items-center justify-center rounded-xl transition-all",
        disabled ? 'opacity-20 cursor-not-allowed' : '',
        active 
          ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' 
          : `${color} hover:bg-slate-800`
      )}
    >
      {icon}
      <span className="absolute left-16 bg-slate-800 text-white text-[10px] font-black px-3 py-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap shadow-2xl border border-slate-700 z-[100] uppercase tracking-widest">
        {label}
      </span>
    </button>
  );
}

export function AppLayout({ children }: AppLayoutProps) {
  const {
    propertiesPanelOpen,
    currentView,
    setCurrentView,
    isHistoryOpen,
    setIsHistoryOpen,
    activeTool,
    setActiveTool,
    isNodeModalOpen,
    setIsNodeModalOpen
  } = useAppStore();

  const [isAddWorkflowDialogOpen, setIsAddWorkflowDialogOpen] = React.useState(false);

  return (
    <div className="flex h-screen w-screen bg-slate-950 font-sans text-slate-200 overflow-hidden select-none">
      {/* PRIMARY SIDEBAR - Vertical Icon Navigation (w-16) */}
      <aside className="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-6 gap-6 z-50 shrink-0 shadow-2xl">
        <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg mb-4">
          <Layers size={20} className="text-white" />
        </div>
        <nav className="flex flex-col gap-3">
          <NavIconButton 
            icon={<FolderKanban size={20} />} 
            active={currentView === 'workspaces'} 
            onClick={() => setCurrentView('workspaces')} 
            label="Workspaces" 
          />
          <NavIconButton 
            icon={<LayoutDashboard size={20} />} 
            active={currentView === 'editor'} 
            onClick={() => setCurrentView('editor')} 
            label="Editor" 
          />
          <NavIconButton 
            icon={<HistoryIcon size={20} />} 
            active={isHistoryOpen && currentView === 'editor'} 
            onClick={() => setIsHistoryOpen(!isHistoryOpen)} 
            label="Run History" 
          />
          
          <div className="h-px w-6 bg-slate-800 my-1 mx-auto" />
          
          <NavIconButton 
            icon={<Plus size={22} />} 
            active={isNodeModalOpen} 
            onClick={() => {
              if (currentView === 'editor') {
                setIsNodeModalOpen(true);
              }
            }} 
            label="Add Node" 
            color="text-emerald-400"
            disabled={currentView !== 'editor'}
          />
          <NavIconButton 
            icon={<Workflow size={20} />} 
            active={isAddWorkflowDialogOpen} 
            onClick={() => {
              if (currentView === 'editor') {
                setIsAddWorkflowDialogOpen(true);
              }
            }} 
            label="Add workflow as node" 
            color="text-cyan-400"
            disabled={currentView !== 'editor'}
          />
          <NavIconButton 
            icon={<MousePointer2 size={20} />} 
            active={activeTool === 'select'} 
            onClick={() => setActiveTool('select')} 
            label="Select" 
          />
          <NavIconButton 
            icon={<Hand size={20} />} 
            active={activeTool === 'pan'} 
            onClick={() => setActiveTool('pan')} 
            label="Pan Canvas" 
          />
          
          <div className="h-px w-6 bg-slate-800 my-1 mx-auto" />
          
          <NavIconButton
            icon={<Box size={20} />}
            active={currentView === 'node_types'}
            onClick={() => setCurrentView('node_types')}
            label="Node Types"
            color="text-amber-400"
          />
          <NavIconButton
            icon={<Zap size={20} />}
            active={currentView === 'events'}
            onClick={() => setCurrentView('events')}
            label="Events"
            color="text-purple-400"
          />
          <NavIconButton
            icon={<Settings size={20} />}
            active={currentView === 'settings'}
            onClick={() => setCurrentView('settings')}
            label="Settings"
          />
        </nav>
      </aside>

      {/* DYNAMIC VIEW CONTAINER */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar removed - use modal instead for node selection */}

        {/* Main Content Area */}
        <main className="flex-1 relative overflow-hidden">
          {children}
        </main>
      </div>
      
      {/* Global styles matching reference */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
        body { background-color: #020617; }
        @keyframes dash { to { stroke-dashoffset: -12; } }
      `}</style>

      {/* PROPERTIES PANEL (Right) */}
      {propertiesPanelOpen && (
        <aside className="absolute right-0 top-0 bottom-0 w-80 bg-slate-900 border-l border-slate-800 flex flex-col z-50 animate-in slide-in-from-right duration-300 shadow-2xl">
          <PropertiesPanel />
        </aside>
      )}

      {/* NODE MODAL */}
      {isNodeModalOpen && <NodeModal />}
      {isAddWorkflowDialogOpen && (
        <AddWorkflowAsNodeDialog onClose={() => setIsAddWorkflowDialogOpen(false)} open={isAddWorkflowDialogOpen} />
      )}
    </div>
  );
}
