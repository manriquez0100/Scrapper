import { useState, useRef, useCallback } from 'react';
import type { RequestItem, RequestStatus } from '../types';
import { sendMessage } from '../services/api';

const MAX_CONCURRENT = 10;

export function useRequestQueue() {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const activeRef = useRef(0);
  const processingRef = useRef<Set<string>>(new Set());

  const updateStatus = useCallback((id: string, status: RequestStatus, response = '') => {
    setRequests(prev => prev.map(r =>
      r.id === id ? { ...r, status, response } : r
    ));
  }, []);

  const processQueue = useCallback(() => {
    if (activeRef.current >= MAX_CONCURRENT) return;

    const pendingRequest = requests.find(
      r => r.status === 'pending' && !processingRef.current.has(r.id)
    );
    if (!pendingRequest) return;

    processingRef.current.add(pendingRequest.id);
    activeRef.current++;
    updateStatus(pendingRequest.id, 'processing');

    sendMessage(pendingRequest.question)
      .then(data => {
        updateStatus(pendingRequest.id, 'done', data.response);
      })
      .catch(err => {
        updateStatus(pendingRequest.id, 'error', err.message);
      })
      .finally(() => {
        activeRef.current--;
        processingRef.current.delete(pendingRequest.id);
        processQueue();
      });
  }, [requests, updateStatus]);

  const enqueue = useCallback((question: string) => {
    const id = crypto.randomUUID();
    const newRequest: RequestItem = {
      id,
      question,
      status: 'pending',
      response: '',
      timestamp: Date.now(),
    };
    setRequests(prev => [...prev, newRequest]);
    processQueue();
  }, [processQueue]);

  const clearAll = useCallback(() => {
    setRequests([]);
    activeRef.current = 0;
    processingRef.current.clear();
  }, []);

  return { requests, enqueue, clearAll };
}