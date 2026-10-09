import { useRef, useEffect, useState } from 'react';
import { useRequestQueue } from '../hooks/useRequestQueue';
import { RequestList } from './RequestList';
import { InputLine } from './InputLine';

export function Terminal() {
  const { requests, enqueue, clearAll } = useRequestQueue();
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const outputRef = useRef<HTMLDivElement>(null);

  const handleSubmit = (question: string) => {
    if (question === '__CLEAR__') {
      clearAll();
      return;
    }
    setHistory(prev => [...prev, question]);
    setHistoryIndex(-1);
    enqueue(question);
  };

  const completedRequests = requests.filter(r => r.status === 'done' || r.status === 'error');

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [completedRequests.length]);

  return (
    <div className="terminal" style={{
      display: 'grid',
      gridTemplateColumns: '300px 1fr',
      gridTemplateRows: '40px 1fr 48px',
      height: '100vh',
      gridTemplateAreas: `
        "header header"
        "list body"
        "input input"
      `,
    }}>
      <div
        className="terminal-header"
        style={{
          gridArea: 'header',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 16px',
          background: 'var(--panel-bg)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span style={{ fontWeight: 'bold', fontSize: '14px' }}>🖥️  Scrapper Terminal</span>
        <span className="status" style={{ color: '#3fb950', fontSize: '12px' }}>● Connected</span>
      </div>

      <RequestList requests={requests} />

      <div
        className="output-area"
        ref={outputRef}
        style={{
          gridArea: 'body',
          padding: '16px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {completedRequests.map(r => (
          <div
            key={r.id}
            className={`output-block ${r.status}`}
            style={{
              borderLeft: `3px solid ${r.status === 'done' ? '#3fb950' : '#f85149'}`,
              paddingLeft: '12px',
            }}
          >
            <div
              className="output-question"
              style={{ color: '#8b949e', fontSize: '13px', marginBottom: '4px' }}
            >
              ▶ {r.question}
            </div>
            <pre
              className="output-response"
              style={{ margin: 0, fontSize: '13px', lineHeight: '1.6', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            >
              {r.response}
            </pre>
          </div>
        ))}
        {completedRequests.length === 0 && (
          <div style={{ color: '#8b949e', textAlign: 'center', marginTop: '40px' }}>
            Submit a question to get started...
          </div>
        )}
      </div>

      <InputLine
        onSubmit={handleSubmit}
        history={history}
        historyIndex={historyIndex}
        setHistoryIndex={setHistoryIndex}
      />
    </div>
  );
}