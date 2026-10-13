import { useState, useRef, useCallback, useEffect } from 'react';
import type { RequestItem, RequestStatus } from '../types';
import { sendMessage } from '../services/api';

const MAX_CONCURRENT = 1;
const BETWEEN_REQUESTS_MS = 250;

export function useRequestQueue() {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => crypto.randomUUID());
  const [lastCompletedSessionId, setLastCompletedSessionId] = useState<string | null>(null);
  const [queueVersion, setQueueVersion] = useState(0);
  const activeRef = useRef(0);
  const processingRef = useRef<Set<string>>(new Set());
  const requestsRef = useRef(requests);

  requestsRef.current = requests;

  const updateStatus = useCallback((id: string, status: RequestStatus, response = '', catalog_images?: string[]) => {
    setRequests(prev => prev.map(r =>
      r.id === id ? { ...r, status, response, catalog_images } : r
    ));
  }, []);

  const processQueue = useCallback(() => {
    if (activeRef.current >= MAX_CONCURRENT) return;

    const pendingRequest = requestsRef.current.find(
      r => r.status === 'pending' && !processingRef.current.has(r.id)
    );
    if (!pendingRequest) return;

    processingRef.current.add(pendingRequest.id);
    activeRef.current++;
    updateStatus(pendingRequest.id, 'processing');

    sendMessage(pendingRequest.question, pendingRequest.session_id)
      .then(data => {
        updateStatus(pendingRequest.id, 'done', data.response, data.catalog_images);
        setLastCompletedSessionId(data.session_id);
      })
      .catch(err => {
        updateStatus(pendingRequest.id, 'error', err.message);
      })
      .finally(() => {
        window.setTimeout(() => {
          if (!processingRef.current.delete(pendingRequest.id)) return;
          activeRef.current = Math.max(0, activeRef.current - 1);
          // Trigger the next FIFO item only after this one has released the browser and LM Studio.
          setQueueVersion(version => version + 1);
        }, BETWEEN_REQUESTS_MS);
      });
  }, [updateStatus]);

  useEffect(() => {
    processQueue();
  }, [requests, queueVersion, processQueue]);

  const enqueue = useCallback((question: string) => {
    const id = crypto.randomUUID();
    const newRequest: RequestItem = {
      id,
      question,
      status: 'pending',
      response: '',
      timestamp: Date.now(),
      session_id: currentSessionId,
    };
    setRequests(prev => [...prev, newRequest]);
  }, [currentSessionId]);

  const clearAll = useCallback(() => {
    setRequests([]);
    activeRef.current = 0;
    processingRef.current.clear();
    setCurrentSessionId(crypto.randomUUID());
  }, []);

  const selectSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
  }, []);

  const startNewConversation = useCallback(() => {
    setCurrentSessionId(crypto.randomUUID());
    setLastCompletedSessionId(null);
  }, []);

  return { requests, enqueue, clearAll, selectSession, startNewConversation, lastCompletedSessionId };
}
