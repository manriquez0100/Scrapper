import { useState, useEffect } from 'react';
import { getPricing, updatePricing, getBehavior, updateBehavior } from '../services/api';
import type { PricingConfig, BehaviorConfig } from '../types';

const REQUIRED_BEHAVIOR_KEYS = [
  'query_extraction_instructions',
  'query_enrichment_instructions',
  'name_extraction_instructions',
  'customer_care_instructions',
  'no_book_query_response',
  'no_results_response_template',
  'search_error_response',
  'available_with_price_template',
  'available_without_price_template',
  'availability_unknown_template',
  'catalog_notice_template',
  'greeting_morning',
  'greeting_afternoon',
  'greeting_evening',
  'greeting_morning_no_name',
  'greeting_afternoon_no_name',
  'greeting_evening_no_name',
  'purchase_and_shipping_instructions',
  'payment_intent_instructions',
  'purchase_and_shipping_response',
  'follow_up_greeting_template',
  'smart_followup_instructions',
];

export function ConfigPanel() {
  const [pricing, setPricing] = useState<PricingConfig>({ ganancia_envio: 200 });
  const [behavior, setBehavior] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [activeTab, setActiveTab] = useState<'pricing' | 'behavior'>('pricing');

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const [pricingRes, behaviorRes] = await Promise.all([
        getPricing(),
        getBehavior(),
      ]);
      setPricing(pricingRes);
      setBehavior(behaviorRes.behavior);
    } catch (err) {
      console.error('Failed to load config:', err);
      setMessage({ type: 'error', text: 'Error al cargar la configuración' });
    } finally {
      setLoading(false);
    }
  };

  const handlePricingSave = async () => {
    setSaving(true);
    try {
      await updatePricing(pricing.ganancia_envio);
      setMessage({ type: 'success', text: 'Ganancia de envío actualizada' });
    } catch (err) {
      setMessage({ type: 'error', text: 'Error al guardar la ganancia de envío' });
    } finally {
      setSaving(false);
    }
  };

  const handleBehaviorSave = async () => {
    setSaving(true);
    try {
      const missingKeys = REQUIRED_BEHAVIOR_KEYS.filter(k => !behavior[k]);
      if (missingKeys.length > 0) {
        setMessage({ type: 'error', text: `Faltan claves requeridas: ${missingKeys.join(', ')}` });
        return;
      }
      await updateBehavior(behavior);
      setMessage({ type: 'success', text: 'Comportamiento actualizado' });
    } catch (err) {
      setMessage({ type: 'error', text: 'Error al guardar el comportamiento' });
    } finally {
      setSaving(false);
    }
  };

  const handleBehaviorChange = (key: string, value: string) => {
    setBehavior(prev => ({ ...prev, [key]: value }));
  };

  const resetBehavior = async () => {
    try {
      const res = await getBehavior();
      setBehavior(res.behavior);
      setMessage({ type: 'success', text: 'Comportamiento restablecido a valores por defecto' });
    } catch (err) {
      setMessage({ type: 'error', text: 'Error al restablecer' });
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '16px', color: '#8b949e' }}>
        Cargando configuración...
      </div>
    );
  }

  return (
    <div style={{ padding: '16px', maxHeight: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
        <button
          onClick={() => setActiveTab('pricing')}
          style={{
            padding: '8px 16px',
            background: activeTab === 'pricing' ? 'var(--primary)' : 'transparent',
            color: activeTab === 'pricing' ? 'white' : 'var(--fg)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          💰 Precios
        </button>
        <button
          onClick={() => setActiveTab('behavior')}
          style={{
            padding: '8px 16px',
            background: activeTab === 'behavior' ? 'var(--primary)' : 'transparent',
            color: activeTab === 'behavior' ? 'white' : 'var(--fg)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          🤖 Comportamiento
        </button>
      </div>

      {message && (
        <div
          style={{
            padding: '12px',
            marginBottom: '16px',
            borderRadius: '4px',
            background: message.type === 'success' ? 'rgba(63, 185, 80, 0.1)' : 'rgba(248, 81, 73, 0.1)',
            border: `1px solid ${message.type === 'success' ? '#3fb950' : '#f85149'}`,
            color: message.type === 'success' ? '#3fb950' : '#f85149',
          }}
        >
          {message.text}
        </div>
      )}

      {activeTab === 'pricing' && (
        <div>
          <h3 style={{ marginBottom: '16px', fontSize: '14px' }}>Configuración de Precios</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', fontWeight: '500' }}>
                Ganancia fija por libro (MXN)
              </label>
              <input
                type="number"
                value={pricing.ganancia_envio}
                onChange={(e) => setPricing({ ganancia_envio: parseFloat(e.target.value) || 0 })}
                min="0"
                max="10000"
                step="10"
                style={{
                  width: '100%',
                  maxWidth: '200px',
                  padding: '8px 12px',
                  background: 'var(--input-bg)',
                  border: '1px solid var(--border)',
                  borderRadius: '4px',
                  color: 'var(--fg)',
                  fontSize: '14px',
                }}
              />
              <p style={{ marginTop: '8px', fontSize: '12px', color: '#8b949e' }}>
                Esta cantidad se suma al precio base del libro para calcular el precio final con envío.
              </p>
            </div>
            <button
              onClick={handlePricingSave}
              disabled={saving}
              style={{
                padding: '10px 20px',
                background: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.7 : 1,
                alignSelf: 'flex-start',
              }}
            >
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'behavior' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '14px' }}>Comportamiento del Asistente</h3>
            <button
              onClick={resetBehavior}
              disabled={saving}
              style={{
                padding: '6px 12px',
                background: 'transparent',
                color: 'var(--fg-muted)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontSize: '12px',
              }}
            >
              Restablecer
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '60vh', overflow: 'auto' }}>
            {REQUIRED_BEHAVIOR_KEYS.map((key) => (
              <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '12px', fontWeight: '500', color: '#8b949e' }}>
                  {key}
                </label>
                <textarea
                  value={behavior[key] || ''}
                  onChange={(e) => handleBehaviorChange(key, e.target.value)}
                  rows={3}
                  style={{
                    padding: '8px 12px',
                    background: 'var(--input-bg)',
                    border: '1px solid var(--border)',
                    borderRadius: '4px',
                    color: 'var(--fg)',
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    resize: 'vertical',
                    minHeight: '60px',
                  }}
                />
              </div>
            ))}
            <button
              onClick={handleBehaviorSave}
              disabled={saving}
              style={{
                padding: '10px 20px',
                background: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.7 : 1,
                alignSelf: 'flex-start',
                marginTop: '8px',
              }}
            >
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}