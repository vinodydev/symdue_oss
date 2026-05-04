/**
 * Workflow header component - displays and allows renaming of the current workflow
 */
import React, { useState } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { Edit2, Check, X, Save, Download, ArrowLeft, Settings, Clock } from 'lucide-react';
import { SaveWorkflowAsTemplateDialog } from '../Workflow/SaveWorkflowAsTemplateDialog';

export function WorkflowHeader() {
  const {
    currentWorkspaceId,
    workspaces,
    updateWorkspace,
    setCurrentView,
    openedEditorFromNodeTypes,
    setOpenedEditorFromNodeTypes,
    editingTemplateId,
    setEditingTemplateId,
    setPropertiesPanelOpen,
    setSelectedNode,
    setSelectedEdge,
    runs,
    selectedRunId,
    currentRunId,
  } = useAppStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [showSaveTemplateDialog, setShowSaveTemplateDialog] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);

  // Find current workspace
  const currentWorkspace = currentWorkspaceId
    ? workspaces.find((w) => w.id === currentWorkspaceId)
    : null;

  if (!currentWorkspace) return null;

  const handleStartEdit = () => {
    setEditName(currentWorkspace.name);
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    if (!currentWorkspaceId || !editName.trim()) {
      setIsEditing(false);
      return;
    }

    try {
      await api.updateWorkspace(currentWorkspaceId, { name: editName.trim() });
      updateWorkspace(currentWorkspaceId, { name: editName.trim() });
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update workspace name:', error);
      alert('Failed to update workflow name');
      setIsEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditName('');
  };

  const handleExportJson = async () => {
    if (!currentWorkspaceId) return;
    try {
      const data = await api.exportWorkflow(currentWorkspaceId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow-${(currentWorkspace.name || 'export').replace(/[^a-z0-9-_]/gi, '-')}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export workflow');
    }
  };

  const handleSaveTemplate = async () => {
    if (!editingTemplateId || !currentWorkspaceId) return;
    setSavingTemplate(true);
    try {
      await api.saveTemplateFromWorkflow(editingTemplateId, currentWorkspaceId);
      setEditingTemplateId(null);
    } catch (e) {
      console.error(e);
      alert('Failed to save template');
    } finally {
      setSavingTemplate(false);
    }
  };

  const handleDiscardTemplateEdit = () => {
    setEditingTemplateId(null);
  };

  return (
    <div className="h-16 bg-slate-900/50 border-b border-slate-800 flex items-center px-6 shrink-0">
      {openedEditorFromNodeTypes && (
        <button
          onClick={() => {
            setCurrentView('node_types');
            setOpenedEditorFromNodeTypes(false);
            setEditingTemplateId(null);
          }}
          className="flex items-center gap-2 mr-4 px-3 py-1.5 bg-amber-600/20 text-amber-400 border border-amber-500/30 rounded-lg text-xs font-medium hover:bg-amber-600/30 transition-colors"
          title="Back to Node Types"
        >
          <ArrowLeft size={14} />
          Back to Node Types
        </button>
      )}
      {editingTemplateId && currentWorkspaceId && (
        <>
          <button
            onClick={handleSaveTemplate}
            disabled={savingTemplate}
            className="flex items-center gap-2 mr-2 px-3 py-1.5 bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-medium hover:bg-emerald-600/30 disabled:opacity-50 transition-colors"
            title="Save template snapshot"
          >
            <Save size={14} />
            {savingTemplate ? 'Saving…' : 'Save template'}
          </button>
          <button
            onClick={handleDiscardTemplateEdit}
            className="flex items-center gap-2 mr-4 px-3 py-1.5 bg-slate-600/20 text-slate-400 border border-slate-500/30 rounded-lg text-xs font-medium hover:bg-slate-600/30 transition-colors"
            title="Discard changes and leave template edit mode"
          >
            <X size={14} />
            Discard
          </button>
        </>
      )}
      {isEditing ? (
        <div className="flex items-center gap-3 flex-1 max-w-md">
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSaveEdit();
              } else if (e.key === 'Escape') {
                handleCancelEdit();
              }
            }}
            className="flex-1 px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            autoFocus
          />
          <button
            onClick={handleSaveEdit}
            className="p-2 text-emerald-400 hover:text-emerald-300 transition-colors"
            title="Save"
          >
            <Check size={18} />
          </button>
          <button
            onClick={handleCancelEdit}
            className="p-2 text-slate-500 hover:text-slate-300 transition-colors"
            title="Cancel"
          >
            <X size={18} />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 flex-1">
          <div className="flex items-center gap-3 group">
            <h1 className="text-lg font-bold text-white">{currentWorkspace.name}</h1>
            <button
              onClick={handleStartEdit}
              className="p-1.5 text-slate-500 hover:text-indigo-400 opacity-0 group-hover:opacity-100 transition-all"
              title="Rename workflow"
            >
              <Edit2 size={16} />
            </button>
          </div>
          <div className="ml-auto flex flex-row items-center flex-wrap gap-2">
            <button
              onClick={() => {
                setSelectedNode(null);
                setSelectedEdge(null);
                setPropertiesPanelOpen(true);
              }}
              className="px-3 py-1.5 bg-slate-700/50 text-slate-300 border border-slate-600 rounded-lg text-xs font-medium hover:bg-slate-600/50 transition-colors flex items-center gap-2 mr-2"
              title="Workflow execution settings"
            >
              <Settings size={14} />
              Settings
            </button>
            <button
              onClick={handleExportJson}
              className="px-3 py-1.5 bg-slate-700/50 text-slate-300 border border-slate-600 rounded-lg text-xs font-medium hover:bg-slate-600/50 transition-colors flex items-center gap-2 mr-2"
              title="Export workflow as JSON"
            >
              <Download size={14} />
              Export JSON
            </button>
            <button
              onClick={() => setShowSaveTemplateDialog(true)}
              className="px-3 py-1.5 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-medium hover:bg-blue-600/30 transition-colors flex items-center gap-2"
              title="Save workflow as template"
            >
              <Save size={14} />
              Save as Template
            </button>
          </div>
        </div>
      )}

      {/* Waiting status banner */}
      {(() => {
        const activeRun = runs.find((r) => r.id === (selectedRunId ?? currentRunId));
        if (activeRun?.status === 'waiting') {
          return (
            <div className="ml-4 flex items-center gap-2 px-3 py-1.5 bg-amber-600/20 text-amber-400 border border-amber-500/30 rounded-lg text-xs shrink-0">
              <Clock size={14} className="animate-pulse" />
              Waiting on signal...
            </div>
          );
        }
        return null;
      })()}

      {showSaveTemplateDialog && currentWorkspace && (
        <SaveWorkflowAsTemplateDialog
          open={showSaveTemplateDialog}
          workflowId={currentWorkspace.id}
          workflowName={currentWorkspace.name}
          onClose={() => setShowSaveTemplateDialog(false)}
          onSuccess={(templateId) => {
            setShowSaveTemplateDialog(false);
            console.log('Workflow template saved:', templateId);
          }}
        />
      )}
    </div>
  );
}

