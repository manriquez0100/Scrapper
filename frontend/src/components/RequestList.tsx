import { useState } from 'react';
import type { RequestItem } from '../types';
import { RequestItem as RequestItemComponent } from './RequestItem';

interface RequestListProps {
  requests: RequestItem[];
}

export function RequestList({ requests }: RequestListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <aside className="request-list" style={{
      background: 'var(--panel-bg)',
      borderRight: '1px solid var(--border)',
      padding: '12px',
      overflowY: 'auto',
    }}>
      <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', color: 'var(--fg)' }}>
        📋 Requests ({requests.length})
      </h3>
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
    </aside>
  );
}