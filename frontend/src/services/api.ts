import type { ApiResponse, Conversation, ConversationSummary } from '../types';

export async function sendMessage(message: string, session_id?: string): Promise<ApiResponse> {
  const body: { message: string; session_id?: string } = { message };
  if (session_id) body.session_id = session_id;
  
  const res = await fetch('/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch('/health');
  return res.json();
}

export async function getConversations(): Promise<ConversationSummary[]> {
  const res = await fetch('/conversations');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`/conversations/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`/conversations/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}