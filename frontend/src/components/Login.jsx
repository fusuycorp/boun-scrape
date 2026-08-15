import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../hooks/useToast';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const showToast = useToast();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError('MISSING_FIELDS: PROVIDE_OPERATOR_ID_AND_PASSKEY');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await login(username, password);
      showToast('Authentication sequence completed', 'success');
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'INVALID_CREDENTIALS');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '16px',
      background: 'var(--bg-void)',
    }}>
      {/* Hazard stripe */}
      <div className="hazard-bar" style={{ width: '100%', maxWidth: '440px', marginBottom: '0' }} />

      {/* Login Card */}
      <div className="cyber-card" style={{
        width: '100%',
        maxWidth: '440px',
        border: '2px solid var(--border-hard)',
        padding: '28px',
      }}>
        {/* ASCII Banner */}
        <pre className="glow-green" style={{
          color: 'var(--neon-green)',
          fontSize: '10px',
          lineHeight: '1.3',
          textAlign: 'center',
          margin: '0 0 20px 0',
          fontFamily: 'var(--font-mono)',
          overflow: 'hidden',
        }}>
{`╔══════════════════════════════════════════╗
║  BOGAZICI UNIVERSITY MAINFRAME TERMINAL  ║
║  RESTRICTED // LEVEL-4 CLEARANCE ONLY    ║
╚══════════════════════════════════════════╝`}
        </pre>

        {/* Error */}
        {error && (
          <div style={{
            marginBottom: '16px',
            padding: '10px 12px',
            background: 'rgba(255,0,85,0.06)',
            border: '1px solid var(--neon-pink)',
            color: 'var(--neon-pink)',
            fontSize: '11px',
            fontWeight: 700,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
          }}>
            [!] ACCESS_DENIED: {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '14px' }}>
            <label style={{
              display: 'block',
              color: 'var(--neon-amber)',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginBottom: '6px',
              fontFamily: 'var(--font-mono)',
            }}>
              OPERATOR_ID:
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              required
              className="cyber-input"
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              color: 'var(--neon-amber)',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginBottom: '6px',
              fontFamily: 'var(--font-mono)',
            }}>
              SECURITY_PASSKEY:
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="cyber-input"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-cyber btn-cyber-primary"
            style={{ width: '100%', padding: '10px 16px', fontSize: '12px' }}
          >
            {loading ? '[...AUTHENTICATING]' : '[>> AUTHENTICATE]'}
          </button>
        </form>

        {/* Footer */}
        <div style={{
          marginTop: '20px',
          paddingTop: '12px',
          borderTop: '1px solid var(--border-dim)',
          textAlign: 'center',
        }}>
          <span style={{
            color: 'var(--text-muted)',
            fontSize: '9px',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}>
            BOUN REGISTRATION DATA EXTRACTION ENGINE // v2.0
          </span>
        </div>
      </div>
    </div>
  );
}
