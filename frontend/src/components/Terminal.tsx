import { useRef, useEffect, useState } from 'react';
import { useRequestQueue } from '../hooks/useRequestQueue';
import { RequestList } from './RequestList';
import { InputLine } from './InputLine';
import { getConversation } from '../services/api';
import { MessageBlock, RequestBlock } from './MessageBlock';
import type { Conversation, Message } from '../types';

export function Terminal() {
  const { requests, enqueue, clearAll, currentSessionId } = useRequestQueue();
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const outputRef = useRef<HTMLDivElement>(null);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [conversationLoading, setConversationLoading] = useState(false);

  const handleSubmit = (question: string) => {
    if (question === '__CLEAR__') {
      clearAll();
      setActiveConversation(null);
      return;
    }
    setHistory(prev => [...prev, question]);
    setHistoryIndex(-1);
    enqueue(question);
    setActiveConversation(null);
  };

  const completedRequests = requests.filter(r => r.status === 'done' || r.status === 'error');

  const loadConversation = async (id: string) => {
    setConversationLoading(true);
    try {
      const conv = await getConversation(id);
      setActiveConversation(conv);
    } catch (err) {
      console.error('Failed to load conversation:', err);
    } finally {
      setConversationLoading(false);
    }
  };

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [completedRequests.length, activeConversation]);

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
        </div>
      </div>

      <RequestList
        requests={requests}
        onLoadConversation={loadConversation}
        activeConversationId={activeConversation?.id || null}
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
            {(!activeConversation && completedRequests.length === 0) && (
              <div style={{ color: '#8b949e', textAlign: 'center', marginTop: '40px' }}>
                Submit a question to get started...
              </div>
            )}
          </>
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