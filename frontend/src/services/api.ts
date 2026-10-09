import type { ApiResponse } from '../types';

export async function sendMessage(message: string): Promise<ApiResponse> {
  const res = await fetch('/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch('/health');
  return res.json();
}