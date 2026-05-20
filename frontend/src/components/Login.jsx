import React, { useState } from 'react';
import { User, Lock, Key, Compass } from 'lucide-react';

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Invalid username or password.');
      }

      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      onLoginSuccess(data.access_token);
    } catch (err) {
      setError(err.message || 'Server connection failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-screen flex items-center justify-center overflow-hidden bg-[hsl(var(--bg-primary))]">
      {/* Decorative Blur Spheres */}
      <div className="bg-glow-violet top-[15%] left-[20%]" />
      <div className="bg-glow-pink bottom-[15%] right-[20%]" />
      
      <div className="w-full max-w-md px-6 z-10 animate-fade-in">
        {/* Brand Icon & Title */}
        <div className="flex flex-col items-center mb-8">
          <div className="p-4 rounded-full bg-gradient-to-tr from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] text-white shadow-lg shadow-[hsla(var(--accent-primary)/0.2)] mb-4">
            <Compass size={40} className="animate-spin-slow" />
          </div>
          <h1 className="text-3xl font-extrabold text-gradient-purple tracking-tight">ULTIMATE BOUN</h1>
          <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Registration Scraping & Tracking Suite</p>
        </div>

        {/* Login Form Panel */}
        <div className="glass-panel p-8 glass-panel-hover">
          <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            <Key size={20} className="text-[hsl(var(--accent-primary))]" />
            Administrative Portal
          </h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="p-3 text-sm text-[hsl(var(--color-danger))] bg-[hsla(var(--color-danger)/0.1)] border border-[hsla(var(--color-danger)/0.2)] rounded-lg">
                {error}
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase tracking-wider">
                Username
              </label>
              <div className="relative flex items-center">
                <span className="absolute left-3.5 text-[hsl(var(--text-muted))]">
                  <User size={18} />
                </span>
                <input
                  type="text"
                  placeholder="Enter administrator username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="glass-input w-full pl-11"
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase tracking-wider">
                Password
              </label>
              <div className="relative flex items-center">
                <span className="absolute left-3.5 text-[hsl(var(--text-muted))]">
                  <Lock size={18} />
                </span>
                <input
                  type="password"
                  placeholder="Enter administrator password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="glass-input w-full pl-11"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-4"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Establishing Connection...
                </span>
              ) : (
                'Authenticate Portal'
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-[hsl(var(--text-muted))] mt-8">
          Protected Administrative Session. Unauthorized access prohibited.
        </p>
      </div>
    </div>
  );
}
