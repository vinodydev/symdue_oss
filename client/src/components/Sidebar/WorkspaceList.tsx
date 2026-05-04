/**
 * Workspace list component - Matching reference design with grid cards
 */
import React, { useState, useRef } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { Workflow } from '@/types';
import { FolderKanban, Trash2, Plus, Edit2, Upload } from 'lucide-react';
import { cn } from '@/utils/cn';

interface WorkspaceListProps {
  workspaces: Workflow[];
  currentWorkspaceId: string | null;
  onCreateWorkspace: () => void;
  onRefresh: () => void;
}

export function WorkspaceList({
  workspaces,
  currentWorkspaceId,
  onCreateWorkspace,
  onRefresh,
}: WorkspaceListProps) {
  const { setCurrentWorkspace, updateWorkspace, setCurrentView, addWorkspace, setOpenedEditorFromNodeTypes } = useAppStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeWorkspaces = workspaces.filter((w) => !w.deleted_at);

  const handleSelectWorkspace = (workspaceId: string) => {
    setCurrentWorkspace(workspaceId);
    setCurrentView('editor');
    setOpenedEditorFromNodeTypes(false);
  };

  const handleDeleteWorkspace = async (e: React.MouseEvent, workspaceId: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this workspace?')) {
      try {
        await api.deleteWorkspace(workspaceId);
        onRefresh();
      } catch (error) {
        console.error('Failed to delete workspace:', error);
        alert('Failed to delete workspace');
      }
    }
  };

  const handleStartEdit = (e: React.MouseEvent, workspace: Workflow) => {
    e.stopPropagation();
    setEditingId(workspace.id);
    setEditName(workspace.name);
  };

  const handleSaveEdit = async (workspaceId: string) => {
    try {
      await api.updateWorkspace(workspaceId, { name: editName });
      updateWorkspace(workspaceId, { name: editName });
      setEditingId(null);
      onRefresh();
    } catch (error) {
      console.error('Failed to update workspace:', error);
      alert('Failed to update workspace name');
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName('');
  };

  const handleImportJson = () => {
    setImportError(null);
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setImporting(true);
    setImportError(null);
    try {
      const text = await file.text();
      const payload = JSON.parse(text) as import('@/types').WorkflowImportPayload;
      if (!payload.nodes || !Array.isArray(payload.nodes)) {
        throw new Error('Invalid format: missing or invalid "nodes" array');
      }
      if (!payload.edges || !Array.isArray(payload.edges)) {
        throw new Error('Invalid format: missing or invalid "edges" array');
      }
      const workflow = await api.importWorkflow(payload);
      addWorkspace(workflow);
      onRefresh();
      setCurrentWorkspace(workflow.id);
      setCurrentView('editor');
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || 'Import failed';
      setImportError(typeof message === 'string' ? message : JSON.stringify(message));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 h-full min-h-0 bg-slate-950 p-12 animate-in fade-in duration-300">
      <div className="shrink-0 max-w-5xl mx-auto w-full">
        <header className="flex justify-between items-end mb-12 border-b border-slate-800 pb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">Your Pipelines</h1>
            <p className="text-slate-500 text-sm">Switch between independent neural architectures and their history.</p>
          </div>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={handleFileChange}
            />
            <button
              onClick={handleImportJson}
              disabled={importing}
              className="flex items-center gap-2 px-5 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-2xl border border-slate-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              title="Import workflow from JSON file"
            >
              <Upload size={20} />
              {importing ? 'Importing...' : 'Import JSON'}
            </button>
            <button
              onClick={onCreateWorkspace}
              className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-2xl shadow-xl transition-all active:scale-95"
            >
              <Plus size={20}/> New Workflow
            </button>
          </div>
        </header>
        {importError && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
            {importError}
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {activeWorkspaces.length === 0 ? (
            <div className="col-span-full text-center py-12">
              <p className="text-slate-500 text-sm">No workspaces yet. Create one to get started.</p>
            </div>
          ) : (
            activeWorkspaces.map((workspace) => (
              <div 
                key={workspace.id} 
                onClick={() => !editingId && handleSelectWorkspace(workspace.id)}
                className={cn(
                  "group relative p-8 rounded-[2.5rem] border-2 transition-all cursor-pointer hover:scale-[1.02]",
                  currentWorkspaceId === workspace.id
                    ? 'bg-indigo-600/5 border-indigo-500/50 shadow-2xl'
                    : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                )}
              >
                <div className="flex justify-between items-start mb-6">
                  <div className={cn(
                    "p-3 rounded-2xl",
                    currentWorkspaceId === workspace.id
                      ? 'bg-indigo-600 text-white shadow-lg'
                      : 'bg-slate-800 text-slate-500'
                  )}>
                    <FolderKanban size={24} />
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-bold text-slate-500 uppercase block tracking-widest">Logs</span>
                    <span className="text-sm font-mono font-bold text-indigo-400">0</span>
                  </div>
                </div>
                
                {editingId === workspace.id ? (
                  <div className="space-y-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleSaveEdit(workspace.id);
                        } else if (e.key === 'Escape') {
                          handleCancelEdit();
                        }
                      }}
                      className="w-full px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      autoFocus
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSaveEdit(workspace.id);
                        }}
                        className="flex-1 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-colors"
                      >
                        Save
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancelEdit();
                        }}
                        className="flex-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-bold rounded-xl transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <h3 className="text-xl font-bold text-white mb-4">
                      {workspace.name}
                    </h3>
                    <div className="absolute bottom-6 right-8 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={(e) => handleStartEdit(e, workspace)} 
                        className="p-2 text-slate-700 hover:text-indigo-400 transition-colors"
                        title="Rename workflow"
                      >
                        <Edit2 size={16}/>
                      </button>
                      <button 
                        onClick={(e) => handleDeleteWorkspace(e, workspace.id)} 
                        className="p-2 text-slate-700 hover:text-red-500 transition-colors"
                        title="Delete workflow"
                      >
                        <Trash2 size={16}/>
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
