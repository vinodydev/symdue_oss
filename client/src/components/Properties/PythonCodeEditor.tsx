/**
 * Python code editor: CodeMirror 6 when deps are installed, else fallback textarea.
 * Used in NodeProperties panel and in ExpandableCodeModal.
 * Optional getValueRef: when provided, getValueRef.current is set to { getValue: () => string }
 * so the parent can read the current editor content at save time (avoids stale state).
 */
import React, { useCallback, useState, useEffect, useRef } from 'react';
import { cn } from '@/utils/cn';

export interface CodeEditorHandle {
  getValue: () => string;
}

interface PythonCodeEditorProps {
  value: string;
  onChange: (code: string) => void;
  disabled?: boolean;
  minHeight?: string;
  className?: string;
  placeholder?: string;
  /** When set, parent can read current value via getValueRef.current.getValue() (e.g. before save) */
  getValueRef?: React.MutableRefObject<CodeEditorHandle | null>;
}

/** Fallback when CodeMirror packages are not installed (e.g. old node_modules in Docker) */
function FallbackCodeEditor({
  value,
  onChange,
  disabled,
  minHeight = '320px',
  className,
  placeholder,
  getValueRef,
}: PythonCodeEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!getValueRef) return;
    getValueRef.current = {
      getValue: () => textareaRef.current?.value ?? '',
    };
    return () => {
      getValueRef.current = null;
    };
  }, [getValueRef]);
  return (
    <textarea
      ref={textareaRef}
      className={cn(
        'w-full bg-slate-950 border-0 rounded-xl p-3 text-xs text-yellow-500/90 font-mono resize-none focus:outline-none focus:ring-0 placeholder:text-slate-500',
        disabled && 'opacity-60 cursor-not-allowed',
        className
      )}
      style={{ minHeight }}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      spellCheck={false}
    />
  );
}

export function PythonCodeEditor(props: PythonCodeEditorProps) {
  const { minHeight = '320px', className, disabled = false } = props;
  const [Editor, setEditor] = useState<React.ComponentType<{
    value: string;
    height: string;
    extensions: unknown[];
    onChange: (v: string) => void;
    editable: boolean;
    placeholder?: string;
    basicSetup: Record<string, boolean>;
    theme: unknown;
  }> | null>(null);
  const [theme, setTheme] = useState<unknown>(null);
  const [pythonExt, setPythonExt] = useState<unknown>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      import('@uiw/react-codemirror').then((m) => m.default),
      import('@codemirror/lang-python').then((m) => m.python()),
      import('@uiw/codemirror-themes').then((m) =>
        m.createTheme({
          theme: 'dark',
          settings: {
            background: '#020617',
            foreground: '#e2e8f0',
            caret: '#94a3b8',
            selection: '#334155',
            gutterBackground: '#0f172a',
            gutterForeground: '#64748b',
          },
          styles: [],
        })
      ),
    ])
      .then(([CodeMirrorComponent, pythonLang, darkTheme]) => {
        if (cancelled) return;
        setEditor(() => CodeMirrorComponent);
        setPythonExt(pythonLang);
        setTheme(darkTheme);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleChange = useCallback(
    (newValue: string) => {
      props.onChange(newValue);
    },
    [props]
  );

  const codemirrorRef = useRef<{ view?: { state: { doc: { toString: () => string } } } } | null>(null);
  useEffect(() => {
    if (!props.getValueRef) return;
    props.getValueRef.current = {
      getValue: () => codemirrorRef.current?.view?.state?.doc?.toString() ?? '',
    };
    return () => {
      props.getValueRef!.current = null;
    };
  }, [props.getValueRef]);

  if (failed || !Editor || theme === null || pythonExt === null) {
    return (
      <div
        className={cn(
          'rounded-xl border border-slate-800 overflow-hidden bg-slate-950',
          disabled && 'opacity-60 pointer-events-none',
          className
        )}
      >
        <FallbackCodeEditor {...props} minHeight={minHeight} />
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-xl border border-slate-800 overflow-hidden bg-slate-950',
        disabled && 'opacity-60 pointer-events-none',
        className
      )}
    >
      <Editor
        ref={codemirrorRef}
        value={props.value}
        height={minHeight}
        extensions={[pythonExt]}
        onChange={handleChange}
        editable={!disabled}
        placeholder={props.placeholder}
        basicSetup={{
          lineNumbers: true,
          highlightActiveLineGutter: !disabled,
          highlightActiveLine: !disabled,
          foldGutter: true,
        }}
        theme={theme}
      />
    </div>
  );
}
