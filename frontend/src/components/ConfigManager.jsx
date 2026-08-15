import React, { useState, useEffect } from 'react';
import { Cookie, FileCode2, Save, RotateCcw, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import { useMountedRef } from '../hooks/useSafeAsync';
import { useToast } from '../hooks/useToast';

export default function ConfigManager() {
  const showToast = useToast();
  const isMountedRef = useMountedRef();

  const [cookies, setCookies] = useState('');
  const [seedHtml, setSeedHtml] = useState('');
  const [initialState, setInitialState] = useState({ cookies: '', seedHtml: '' });

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const res = await api.getScraperConfig();
      if (isMountedRef.current) {
        setStatus(res);
        const cookieVal = res.cookie_masked ? `ASP.NET_SessionId=${res.cookie_masked}` : '';
        setCookies(cookieVal);
        setInitialState({ cookies: cookieVal, seedHtml: '' });
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
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const isDirty = cookies !== initialState.cookies || seedHtml !== '';

  const handleSave = async (e) => {
    e.preventDefault();
    if (!isDirty) return;

    setSaving(true);
    try {
      const payload = {};
      if (cookies !== initialState.cookies) payload.cookies = cookies;
      if (seedHtml !== '') payload.seed_html = seedHtml;

      const res = await api.updateScraperConfig(payload);
      showToast(res.message || 'CONFIGURATION_UPDATED_SUCCESSFULLY', 'success');
      setSeedHtml('');
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
    setCookies(initialState.cookies);
    setSeedHtml('');
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
          Mount reCAPTCHA session tokens (`cookies.txt`) and ASP.NET ViewState form payloads (`response.html`).
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
            {status?.cookie_loaded ? (
              <span className="cyber-badge cyber-badge-green">
                [● ACTIVE: {status.cookie_masked || 'MOUNTED'}]
              </span>
            ) : (
              <span className="cyber-badge cyber-badge-amber">
                [! NOT_LOADED / EXPIRED]
              </span>
            )}
          </div>
        </div>

        {/* Seed HTML Status */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <FileCode2 size={16} style={{ color: 'var(--neon-pink)' }} />
            <span style={{ color: 'var(--neon-pink)', fontSize: '11px', fontWeight: 700 }}>
              KEYRING_02: response.html
            </span>
          </div>
          <div>
            {status?.seed_html_loaded ? (
              <span className="cyber-badge cyber-badge-green">
                [● PRESENT: {status.seed_html_size?.toLocaleString()} BYTES]
              </span>
            ) : (
              <span className="cyber-badge cyber-badge-amber">
                [! MISSING_SEED_FILE]
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
            <Cookie size={14} />
            RAW_COOKIE_STRING: (ASP.NET_SessionId)
          </label>
          <p style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '12px' }}>
            Paste the raw cookie string from browser devtools while authenticated on registration.bogazici.edu.tr.
          </p>
          <textarea
            rows="3"
            value={cookies}
            onChange={(e) => setCookies(e.target.value)}
            placeholder="ASP.NET_SessionId=abcdef1234567890..."
            className="cyber-input"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', lineHeight: '1.5' }}
          />
        </div>

        {/* Seed HTML Input */}
        <div className="cyber-card" style={{ border: '1px solid var(--border-hard)', padding: '20px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--neon-pink)', fontSize: '11px', fontWeight: 700, marginBottom: '6px' }}>
            <FileCode2 size={14} />
            SEED_FORM_HTML_BUFFER: (response.html)
          </label>
          <p style={{ color: 'var(--text-secondary)', fontSize: '11px', marginBottom: '12px' }}>
            Paste full HTML source of schedule.aspx containing ASP.NET `__VIEWSTATE` and `__EVENTVALIDATION` fields.
          </p>
          <textarea
            rows="6"
            value={seedHtml}
            onChange={(e) => setSeedHtml(e.target.value)}
            placeholder="<!DOCTYPE html><html><head>...<input type='hidden' name='__VIEWSTATE'..."
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
