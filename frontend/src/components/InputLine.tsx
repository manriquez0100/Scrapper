import { useRef, useEffect, useState } from 'react';

interface InputLineProps {
  onSubmit: (question: string) => void;
  history: string[];
  historyIndex: number;
  setHistoryIndex: React.Dispatch<React.SetStateAction<number>>;
}

export function InputLine({ onSubmit, history, historyIndex, setHistoryIndex }: InputLineProps) {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      const trimmed = input.trim();
      if (trimmed === ':clear' || trimmed === 'cls') {
        onSubmit('__CLEAR__');
        setInput('');
        return;
      }
      if (trimmed) {
        onSubmit(trimmed);
        setInput('');
      }
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (historyIndex < history.length - 1) {
        const newIndex = historyIndex + 1;
        setHistoryIndex(newIndex);
        setInput(history[newIndex]);
      }
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setInput(history[newIndex]);
      } else {
        setHistoryIndex(-1);
        setInput('');
      }
    }
  };

  return (
    <div
      className="input-line"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '0 16px',
        height: '48px',
        background: 'var(--panel-bg)',
        borderTop: '1px solid var(--border)',
      }}
    >
      <span className="prompt" style={{ color: 'var(--prompt)', whiteSpace: 'nowrap' }}>
        user@scrapper:~$
      </span>
      <input
        ref={inputRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        style={{
          flex: 1,
          background: 'transparent',
          border: 'none',
          color: 'var(--fg)',
          fontSize: '14px',
          fontFamily: 'inherit',
          outline: 'none',
        }}
        placeholder="Type your question... (:clear to clear)"
      />
    </div>
  );
}