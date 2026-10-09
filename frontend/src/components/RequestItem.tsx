import type { RequestItem } from '../types';
import { StatusBadge } from './StatusBadge';

interface RequestItemProps {
  item: RequestItem;
  expanded: boolean;
  onToggle: () => void;
}

export function RequestItem({ item, expanded, onToggle }: RequestItemProps) {
  return (
    <div
      className="request-item"
      onClick={onToggle}
      style={{
        padding: '8px',
        marginBottom: '8px',
        background: 'var(--bg)',
        borderRadius: '4px',
        cursor: 'pointer',
        border: '1px solid transparent',
        transition: 'border-color 0.2s',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'transparent'}
    >
      <div className="request-header" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <StatusBadge status={item.status} />
        <span
          className="question"
          style={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            flex: 1,
            fontSize: '13px',
          }}
        >
          {item.question.slice(0, 60)}{item.question.length > 60 ? '...' : ''}
        </span>
      </div>
      {expanded && (
        <pre
          className="response"
          style={{
            marginTop: '8px',
            padding: '8px',
            background: 'var(--bg)',
            borderRadius: '4px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontSize: '12px',
            lineHeight: '1.5',
            color: item.status === 'error' ? '#f85149' : 'var(--fg)',
          }}
        >
          {item.response || '(processing...)'}
        </pre>
      )}
    </div>
  );
}