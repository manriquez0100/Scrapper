import { useRef, useEffect, useState } from 'react';
import { useRequestQueue } from '../hooks/useRequestQueue';
import { RequestList } from './RequestList';
import { InputLine } from './InputLine';
import { getConversation } from '../services/api';
import { MessageBlock, RequestBlock } from './MessageBlock';
import { ConfigPanel } from './ConfigPanel';
import type { Conversation, Message, RequestItem } from '../types';

export function Terminal() {
  const {
    requests,
    currentSessionId,
    enqueue,
    clearAll,
    selectSession,
    startNewConversation,
    lastCompletedSessionId,
    lastCompletedRequestId,
  } = useRequestQueue();
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const outputRef = useRef<HTMLDivElement>(null);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [showConfig, setShowConfig] = useState(false);

  const handleSubmit = (question: string) => {
    if (question === '__CLEAR__') {
      clearAll();
      setActiveConversation(null);
      return;
    }
    setHistory(prev => [...prev, question]);
    setHistoryIndex(-1);
    enqueue(question);
  };

  const newConversation = () => {
    startNewConversation();
    setActiveConversation(null);
  };

  const completedRequests = requests.filter(r => r.status === 'done' || r.status === 'error');
  const activeRequests = requests.filter(
    request => request.session_id === currentSessionId &&
      (request.status === 'pending' || request.status === 'processing'),
  );

  const loadConversation = async (id: string) => {
    setConversationLoading(true);
    try {
      const conv = await getConversation(id);
      setActiveConversation(conv);
      selectSession(conv.id);
    } catch (err) {
      console.error('Failed to load conversation:', err);
    } finally {
      setConversationLoading(false);
    }
  };

  useEffect(() => {
    if (lastCompletedSessionId) loadConversation(lastCompletedSessionId);
  }, [lastCompletedSessionId, lastCompletedRequestId]);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [completedRequests.length, activeConversation, activeRequests.length, requests]);

  const renderLoadingRequest = (request: RequestItem) => {
    const processing = request.status === 'processing';
    return (
      <div key={request.id} className="loading-request" aria-live="polite">
        <div className="output-question loading-request-question">▶ You</div>
        <pre className="output-response loading-request-message">{request.question}</pre>
        <div className="loading-response">
          <span className="loading-spinner" aria-hidden="true" />
          <span>{processing ? 'Buscando libros y preparando catálogo…' : 'Consulta en cola…'}</span>
        </div>
      </div>
    );
  };

  const renderMessages = () => {
    if (activeConversation) {
      return activeConversation.messages.map((msg: Message, index: number) => (
        <MessageBlock key={`${activeConversation.id}-${index}`} message={msg} index={index} conversationId={activeConversation.id} />
      ));
    }

    return completedRequests
      .filter(r => r.status === 'done' || r.status === 'error')
      .map(r => (
        <RequestBlock key={r.id} request={r} />
      ));
  };

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
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="status" style={{ color: '#3fb950', fontSize: '12px' }}>● Connected</span>
          {activeConversation && (
            <span style={{ fontSize: '11px', color: '#8b949e' }}>
              Conversation: {activeConversation.id.slice(0, 8)}...
            </span>
          )}
          <button
            onClick={() => setShowConfig(!showConfig)}
            style={{
              padding: '6px 12px',
              background: showConfig ? 'var(--primary)' : 'transparent',
              color: showConfig ? 'white' : 'var(--fg)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
            title={showConfig ? 'Ocultar configuración' : 'Mostrar configuración'}
          >
            ⚙️ Config
          </button>
        </div>
      </div>

      <RequestList
        requests={requests}
        onLoadConversation={loadConversation}
        activeConversationId={activeConversation?.id || null}
        refreshKey={completedRequests.length}
        onNewConversation={newConversation}
      />

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
        {conversationLoading && (
          <div style={{ color: '#8b949e', textAlign: 'center', marginTop: '40px' }}>
            Loading conversation...
          </div>
        )}
        {!conversationLoading && (
          <>
            {renderMessages()}
            {activeRequests.map(renderLoadingRequest)}
            {(!activeConversation && completedRequests.length === 0) && (
              <div style={{ color: '#8b949e', textAlign: 'center', marginTop: '40px' }}>
                Submit a question to get started...
              </div>
            )}
          </>
        )}
      </div>

      {showConfig && (
        <div
          style={{
            gridArea: 'list',
            borderRight: '1px solid var(--border)',
            background: 'var(--panel-bg)',
            overflow: 'auto',
            zIndex: 10,
          }}
        >
          <ConfigPanel />
        </div>
      )}

      <InputLine
        onSubmit={handleSubmit}
        disabled={activeRequests.length > 0}
        history={history}
        historyIndex={historyIndex}
        setHistoryIndex={setHistoryIndex}
      />
    </div>
  );
}
