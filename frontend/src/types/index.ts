export type RequestStatus = 'pending' | 'processing' | 'done' | 'error';

export interface RequestItem {
  id: string;
  question: string;
  status: RequestStatus;
  response: string;
  timestamp: number;
}

export interface ApiResponse {
  response: string;
  catalog_images: string[];
}