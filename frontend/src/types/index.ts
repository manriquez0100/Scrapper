export type RequestStatus = 'pending' | 'processing' | 'done' | 'error';

export interface RequestItem {
  id: string;
  question: string;
  status: RequestStatus;
  response: string;
  timestamp: number;
  catalog_images?: string[];
  session_id?: string;
}

export interface ApiResponse {
  response: string;
  catalog_images: string[];
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  catalog_images?: string[];
  timestamp: string;
}

export interface Conversation {
  id: string;
  created_at: string;
  messages: Message[];
}

export interface ConversationSummary {
  id: string;
  created_at: string;
  preview: string;
}