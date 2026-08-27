import React, { useState, useEffect, useCallback } from 'react';
import { Cookie, Save, AlertCircle, KeyRound, Terminal } from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';

export default function ConfigManager() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();

  const [cookies, setCookies] = useState('');

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getScraperConfig();
      if (isMountedRef.current) {
        setStatus(res);
      }
    } catch (err) {
      if (isMountedRef.current) {
        showToast(err.message || 'FAILED_TO_LOAD_CONFIG_STATUS', 'error');
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [isMountedRef, showToast]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const isDirty = cookies.trim() !== '';

  const handleSave = async (e) => {
    e.preventDefault();
    if (!isDirty) return;

    setSaving(true);
    try {
      const res = await api.updateScraperConfig({ cookies });
      showToast(res.message || 'CONFIGURATION_UPDATED_SUCCESSFULLY', 'success');
      setCookies('');
      fetchConfig();
    } catch (err) {
      showToast(err.message || 'FAILED_TO_COMMIT_CONFIG', 'error');
    } finally {
      if (isMountedRef.current) {
        setSaving(false);
      }
    }
  };

  const handleReset = () => {
    setCookies('');
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span className="led-indicator led-green" />
          <span style={{ color: 'var(--neon-green)', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em' }}>
            SYS://CREDENTIALS_VAULT
          </span>
        </div>
        <h1 className="glow-green" style={{ color: 'var(--neon-green)', fontSize: '20px', margin: 0 }}>
          /// SESSION_AND_KEYRING_MANAGER
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '4px' }}>
          Mount session tokens (`cookies.txt` / `recaptcha_token.txt`) or paste raw DevTools cURL commands for the scraper client.
        </p>
      </div>

      {/* Config Status Info Deck */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {/* Cookie Status */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <Cookie size={16} style={{ color: 'var(--neon-amber)' }} />
            <span style={{ color: 'var(--neon-amber)', fontSize: '11px', fontWeight: 700 }}>
              KEYRING_01: cookies.txt
            </span>
          </div>
          <div>
            {loading ? (
              <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>[...]</span>
            ) : status?.cookie_loaded ? (
              <span className="cyber-badge cyber-badge-green">[● ACTIVE: MOUNTED]</span>
            ) : (
              <span className="cyber-badge cyber-badge-amber">
                [! NOT_LOADED / EXPIRED]
              </span>
            )}
          </div>
        </div>

        {/* reCAPTCHA Token Status */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <KeyRound size={16} style={{ color: 'var(--neon-cyan)' }} />
            <span style={{ color: 'var(--neon-cyan)', fontSize: '11px', fontWeight: 700 }}>
              KEYRING_02: recaptcha_token.txt
            </span>
          </div>
          <div>
            {loading ? (
              <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>[...]</span>
            ) : status?.recaptcha_loaded ? (
              <span className="cyber-badge cyber-badge-green">[● ACTIVE: MOUNTED]</span>
            ) : (
              <span className="cyber-badge cyber-badge-amber">
                [- OPTIONAL / UNSET]
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Cookie Input */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '20px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--neon-amber)', fontSize: '11px', fontWeight: 700, marginBottom: '6px' }}>
            <Terminal size={14} />
            PASTE RAW COOKIES OR BROWSER DEVTOOLS cURL COMMAND:
          </label>
          <p style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '12px' }}>
            Paste a cookie string (e.g. <code>ASP.NET_SessionId=...</code>) or paste the entire multi-line command directly from Chrome DevTools (<strong>Network → Copy as cURL</strong>). Cookies and reCAPTCHA tokens (<code>gRecResp</code>) are parsed and extracted automatically.
          </p>
          <textarea
            rows="5"
            value={cookies}
            onChange={(e) => setCookies(e.target.value)}
            placeholder="curl 'https://registration.bogazici.edu.tr/BUIS/General/schedule.aspx?p=semester' \
  -H '...' \
  -b 'ASP.NET_SessionId=...; ASPSESSIONIDAQQCCDAD=...' \
  --data-raw '...&ctl00$cphMainContent$gRecResp=...'"
            className="cyber-input"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', lineHeight: '1.5' }}
          />
        </div>

        {/* Save Floating Bar */}
        {isDirty && (
          <div
            className="cyber-card animate-fade-in"
            style={{
              position: 'fixed',
              bottom: '36px',
              right: '24px',
              zIndex: 80,
              padding: '14px 20px',
              border: '2px solid var(--neon-amber)',
              background: 'var(--bg-secondary)',
              boxShadow: '6px 6px 0 rgba(0, 0, 0, 0.9)',
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--neon-amber)', fontSize: '11px', fontWeight: 700 }}>
              <AlertCircle size={14} />
              <span>UNCOMMITTED_CHANGES</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                type="button"
                onClick={handleReset}
                className="btn-cyber"
                style={{ fontSize: '10px', padding: '6px 12px' }}
              >
                [DISCARD]
              </button>
              <button
                type="submit"
                disabled={saving}
                className="btn-cyber btn-cyber-primary"
                style={{ fontSize: '10px', padding: '6px 14px' }}
              >
                <Save size={12} />
                <span>{saving ? '[...COMMITTING]' : '[>> COMMIT_CHANGES]'}</span>
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
