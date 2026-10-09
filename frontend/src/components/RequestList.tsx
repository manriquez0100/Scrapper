import { useState, useEffect } from 'react';
import type { RequestItem, ConversationSummary } from '../types';
import { RequestItem as RequestItemComponent } from './RequestItem';
import { getConversations } from '../services/api';

interface RequestListProps {
  requests: RequestItem[];
  onLoadConversation: (id: string) => void;
  activeConversationId: string | null;
}

export function RequestList({ requests, onLoadConversation, activeConversationId }: RequestListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [showConversations, setShowConversations] = useState(false);

  useEffect(() => {
    getConversations().then(setConversations).catch(console.error);
  }, []);

  const handleLoadConversation = (id: string) => {
    onLoadConversation(id);
    setExpandedId(null);
  };

  return (
    <aside className="request-list" style={{
      background: 'var(--panel-bg)',
      borderRight: '1px solid var(--border)',
      padding: '12px',
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '14px', color: 'var(--fg)' }}>
          📋 Requests ({requests.length})
        </h3>
        <button
          onClick={() => setShowConversations(!showConversations)}
          style={{
            padding: '4px 8px',
            fontSize: '11px',
            background: showConversations ? 'var(--prompt)' : 'var(--border)',
            color: showConversations ? '#000' : 'var(--fg)',
            border: 'none',
            borderRadius: '3px',
            cursor: 'pointer',
          }}
        >
          {showConversations ? '📝 Requests' : '💾 Conversations'}
        </button>
      </div>

      {showConversations ? (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {conversations.length === 0 && (
            <div style={{ color: '#8b949e', fontSize: '13px', textAlign: 'center', padding: '20px' }}>
              No conversations saved yet
            </div>
          )}
          {conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => handleLoadConversation(conv.id)}
              style={{
                padding: '8px',
                marginBottom: '8px',
                background: activeConversationId === conv.id ? 'var(--prompt)' : 'var(--bg)',
                borderRadius: '4px',
                cursor: 'pointer',
                border: '1px solid transparent',
                transition: 'border-color 0.2s',
                color: activeConversationId === conv.id ? '#000' : 'var(--fg)',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}
            >
              <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '4px' }}>
                {new Date(conv.created_at).toLocaleString()}
              </div>
              <div style={{ fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {conv.preview || '(empty)'}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {requests.slice().reverse().map(req => (
            <RequestItemComponent
              key={req.id}
              item={req}
              expanded={expandedId === req.id}
              onToggle={() => setExpandedId(expandedId === req.id ? null : req.id)}
            />
          ))}
          {requests.length === 0 && (
            <div style={{ color: '#8b949e', fontSize: '13px', textAlign: 'center', padding: '20px' }}>
              No requests yet
            </div>
          )}
        </div>
      )}
    </aside>
  );
}