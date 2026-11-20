import type { RequestStatus } from '../types';

const statusColors: Record<RequestStatus, string> = {
  pending: '#d29922',
  processing: '#58a6ff',
  done: '#3fb950',
  error: '#f85149',
};

const statusIcons: Record<RequestStatus, string> = {
  pending: '🟡',
  processing: '🔄',
  done: '✅',
  error: '❌',
};

interface StatusBadgeProps {
  status: RequestStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      style={{
        color: statusColors[status],
        marginRight: 8,
        fontSize: '14px',
      }}
    >
      {statusIcons[status]}
    </span>
  );
}