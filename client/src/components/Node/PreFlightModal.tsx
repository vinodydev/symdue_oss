/**
 * Pre-flight modal for testing nodes before adding to graph
 */
import React, { useState } from 'react';
import { X, Play, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '@/services/api';
import type { Node } from '@/types';
import { cn } from '@/utils/cn';

interface PreFlightModalProps {
  node: Node;
  workspaceId: string;
  onClose: () => void;
}

interface TestResult {
  node_id: string;
  node_type_id: string;
  status: 'success' | 'error' | 'pending';
  output: any;
  error: string | null;
  execution_time_ms: number;
}

export function PreFlightModal({ node, workspaceId, onClose }: PreFlightModalProps) {
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testInputs, setTestInputs] = useState<Record<string, any>>({});

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const result = await api.testNode(workspaceId, node.id, testInputs);
      setTestResult(result);
    } catch (error: any) {
      setTestResult({
        node_id: node.id,
        node_type_id: node.node_type_id,
        status: 'error',
        output: null,
        error: error.response?.data?.detail || error.message || 'Unknown error',
        execution_time_ms: 0,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const formatOutput = (output: any): string => {
    if (output === null || output === undefined) {
      return 'null';
    }
    if (typeof output === 'string') {
      return output;
    }
    return JSON.stringify(output, null, 2);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/90 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-[2.5rem] shadow-2xl animate-in zoom-in-95 duration-200 overflow-hidden">
        {/* Header */}
        <div className="p-8 border-b border-slate-800 bg-slate-900/50 text-center">
          <h3 className="text-xl font-bold text-white flex justify-center items-center gap-3">
            <span>Pre-flight Test</span>
          </h3>
          <p className="text-sm text-slate-400 mt-2">
            Test node: <span className="font-mono">{node.node_type_id}</span>
          </p>
          <button
            onClick={onClose}
            className="absolute top-8 right-8 p-1 hover:bg-slate-800 rounded-lg transition-colors text-slate-500 hover:text-white"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-8 space-y-6">
          {/* Node Configuration */}
          <div>
            <h3 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Node Configuration</h3>
            <div className="bg-slate-950 rounded-xl p-4 border border-slate-800">
              <pre className="text-[11px] text-slate-300 font-mono overflow-x-auto">
                {JSON.stringify(node.config, null, 2)}
              </pre>
            </div>
          </div>

          {/* Test Inputs (for future use) */}
          {node.node_type_id !== 'input' && (
            <div>
              <h3 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Test Inputs (Optional)</h3>
              <textarea
                value={JSON.stringify(testInputs, null, 2)}
                onChange={(e) => {
                  try {
                    setTestInputs(JSON.parse(e.target.value));
                  } catch {
                    // Invalid JSON, ignore
                  }
                }}
                className="w-full h-24 px-5 py-4 bg-slate-950 border border-slate-800 rounded-2xl text-xs font-mono text-white focus:outline-none focus:border-indigo-500 shadow-inner"
                placeholder='{"key": "value"}'
              />
            </div>
          )}

          {/* Test Result */}
          {testResult && (
            <div>
              <h3 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Test Result</h3>
              <div
                className={cn(
                  'rounded p-3 border',
                  testResult.status === 'success'
                    ? 'bg-green-900/20 border-green-700'
                    : testResult.status === 'error'
                    ? 'bg-red-900/20 border-red-700'
                    : 'bg-yellow-900/20 border-yellow-700'
                )}
              >
                <div className="flex items-center gap-2 mb-2">
                  {testResult.status === 'success' && (
                    <CheckCircle2 size={16} className="text-green-400" />
                  )}
                  {testResult.status === 'error' && (
                    <XCircle size={16} className="text-red-400" />
                  )}
                  {testResult.status === 'pending' && (
                    <Loader2 size={16} className="text-yellow-400 animate-spin" />
                  )}
                  <span
                    className={cn(
                      'text-sm font-medium',
                      testResult.status === 'success'
                        ? 'text-green-400'
                        : testResult.status === 'error'
                        ? 'text-red-400'
                        : 'text-yellow-400'
                    )}
                  >
                    {testResult.status.toUpperCase()}
                  </span>
                  {testResult.execution_time_ms > 0 && (
                    <span className="text-[10px] text-slate-500 ml-auto font-mono">
                      {testResult.execution_time_ms}ms
                    </span>
                  )}
                </div>

                {testResult.error && (
                  <div className="mb-2">
                    <p className="text-[10px] font-black text-red-400 mb-1 uppercase tracking-widest">Error:</p>
                    <p className="text-[11px] text-red-300 font-mono">{testResult.error}</p>
                  </div>
                )}

                {testResult.output !== null && testResult.output !== undefined && (
                  <div>
                    <p className="text-[10px] font-black text-slate-500 mb-1 uppercase tracking-widest">Output:</p>
                    <pre className="text-[11px] text-emerald-400 font-mono bg-slate-950 rounded-xl p-4 border border-slate-800 overflow-x-auto whitespace-pre-wrap">
                      {formatOutput(testResult.output)}
                    </pre>
                  </div>
                )}

                {testResult.status === 'pending' && (
                  <p className="text-[11px] text-yellow-400">
                    Node execution not yet implemented for this node type.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-8 bg-slate-950/50 flex gap-4 border-t border-slate-800">
          <button
            onClick={onClose}
            className="flex-1 py-4 text-sm font-bold text-slate-500 hover:text-white transition-colors"
          >
            Abort
          </button>
          <button
            onClick={handleTest}
            disabled={isTesting}
            className="flex-1 py-4 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:cursor-not-allowed text-white rounded-2xl text-sm font-black uppercase tracking-widest shadow-xl active:scale-[0.98] transition-all flex items-center justify-center gap-2"
          >
            {isTesting ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <Play size={18} fill="currentColor" />
                Launch Test
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

