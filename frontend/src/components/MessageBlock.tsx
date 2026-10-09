import { useState } from 'react';
import { copyResponseToClipboard } from '../utils/clipboard';
import type { Message, RequestItem } from '../types';

interface MessageBlockProps {
  message: Message;
  index: number;
  conversationId: string;
}

export function MessageBlock({ message, index, conversationId }: MessageBlockProps) {
  const [copied, setCopied] = useState(false);
  const isAssistant = message.role === 'assistant';
  const hasContent = isAssistant && (message.content || (message.catalog_images && message.catalog_images.length > 0));

  const handleCopy = async () => {
    if (!isAssistant || !hasContent) return;
    try {
      await copyResponseToClipboard(message.content || '', message.catalog_images || []);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  };

  const borderColor = message.role === 'user' ? '#58a6ff' : '#3fb950';
  const roleLabel = message.role === 'user' ? '▶ You' : '◀ Assistant';

  return (
    <div
      key={`${conversationId}-${index}`}
      className={`output-block ${message.role}`}
      style={{
        borderLeft: `3px solid ${borderColor}`,
        paddingLeft: '12px',
        marginBottom: '16px',
      }}
    >
      <div
        className="output-question"
        style={{ color: '#8b949e', fontSize: '13px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
      >
        {roleLabel}
        {message.role === 'assistant' && (
          <span style={{ marginLeft: '8px', fontSize: '11px', color: '#6e7681' }}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        )}
        {hasContent && (
          <button
            onClick={handleCopy}
            style={{
              marginLeft: 'auto',
              padding: '2px 8px',
              fontSize: '11px',
              background: copied ? '#3fb950' : 'var(--border)',
              color: copied ? '#fff' : 'var(--fg)',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            title="Copiar respuesta al portapapeles (texto e imágenes)"
          >
            {copied ? '✅ Copiado' : '📋 Copiar'}
          </button>
        )}
      </div>
      <pre
        className="output-response"
        style={{ margin: 0, fontSize: '13px', lineHeight: '1.6', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
      >
        {message.content}
      </pre>
      {message.catalog_images && message.catalog_images.length > 0 && (
        <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {message.catalog_images.map((img: string, i: number) => (
            <img
              key={i}
              src={img}
              alt={`Catalog ${i + 1}`}
              style={{ maxHeight: '150px', border: '1px solid var(--border)', borderRadius: '4px', cursor: 'pointer' }}
              onClick={() => window.open(img, '_blank')}
            />
          ))}
        </div>
      )}
    </div>
  );
}


interface RequestBlockProps {
  request: RequestItem;
}

export function RequestBlock({ request }: RequestBlockProps) {
  const [copied, setCopied] = useState(false);
  const isDone = request.status === 'done';
  const hasContent = isDone && (request.response || (request.catalog_images && request.catalog_images.length > 0));

  const handleCopy = async () => {
    if (!isDone || !hasContent) return;
    try {
      await copyResponseToClipboard(request.response || '', request.catalog_images || []);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  };

  return (
    <div
      key={request.id}
      className={`output-block ${request.status}`}
      style={{
        borderLeft: `3px solid ${request.status === 'done' ? '#3fb950' : '#f85149'}`,
        paddingLeft: '12px',
      }}
    >
      <div
        className="output-question"
        style={{ color: '#8b949e', fontSize: '13px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
      >
        ▶ {request.question}
        {hasContent && (
          <button
            onClick={handleCopy}
            style={{
              marginLeft: 'auto',
              padding: '2px 8px',
              fontSize: '11px',
              background: copied ? '#3fb950' : 'var(--border)',
              color: copied ? '#fff' : 'var(--fg)',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            title="Copiar respuesta al portapapeles (texto e imágenes)"
          >
            {copied ? '✅ Copiado' : '📋 Copiar'}
          </button>
        )}
      </div>
      <pre
        className="output-response"
        style={{ margin: 0, fontSize: '13px', lineHeight: '1.6', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
      >
        {request.response}
      </pre>
      {request.catalog_images && request.catalog_images.length > 0 && (
        <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {request.catalog_images.map((img: string, i: number) => (
            <img
              key={i}
              src={img}
              alt={`Catalog ${i + 1}`}
              style={{ maxHeight: '150px', border: '1px solid var(--border)', borderRadius: '4px', cursor: 'pointer' }}
              onClick={() => window.open(img, '_blank')}
            />
          ))}
        </div>
      )}
    </div>
  );
}