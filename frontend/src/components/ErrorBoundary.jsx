import React, { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary intercepted fatal fault:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          className="animate-fade-in"
          style={{
            minHeight: this.props.fullScreen ? '100vh' : '260px',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
            background: 'var(--bg-void)',
          }}
        >
          <div
            className="cyber-card"
            style={{
              maxWidth: '540px',
              width: '100%',
              border: '2px solid var(--neon-pink)',
              padding: '24px',
              boxShadow: '0 0 20px rgba(255, 0, 85, 0.2)',
            }}
          >
            <div className="hazard-bar" style={{ marginBottom: '16px' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <AlertTriangle size={20} style={{ color: 'var(--neon-pink)' }} />
              <h2
                className="glow-pink"
                style={{
                  color: 'var(--neon-pink)',
                  fontSize: '14px',
                  margin: 0,
                  fontWeight: 800,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                }}
              >
                [SYS_CRITICAL] RUNTIME_FAULT_INTERCEPTED
              </h2>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '11px', lineHeight: '1.5', margin: '0 0 16px 0' }}>
              An unhandled rendering exception occurred inside this component tree. Subsystem isolated to prevent mainframe crash.
            </p>

            {this.state.error && (
              <div
                style={{
                  background: 'rgba(255, 0, 85, 0.06)',
                  border: '1px solid var(--neon-pink)',
                  padding: '10px 12px',
                  fontSize: '11px',
                  color: 'var(--neon-pink)',
                  fontFamily: 'var(--font-mono)',
                  marginBottom: '16px',
                  wordBreak: 'break-all',
                  maxHeight: '120px',
                  overflowY: 'auto',
                }}
              >
                [EXCEPTION]: {this.state.error.toString()}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={this.handleReset}
                className="btn-cyber btn-cyber-danger"
                style={{ fontSize: '11px', padding: '8px 16px' }}
              >
                <RefreshCw size={13} />
                <span>[&gt;&gt; REINITIALIZE_SUBSYSTEM]</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
