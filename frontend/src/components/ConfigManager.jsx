import React, { useState, useEffect } from 'react';
import { 
  Save, 
  Cookie, 
  FileText, 
  HelpCircle, 
  AlertTriangle,
  CheckCircle2,
  Lock
} from 'lucide-react';

export default function ConfigManager({ token }) {
  const [cookies, setCookies] = useState('');
  const [seedHtml, setSeedHtml] = useState('');
  const [status, setStatus] = useState({
    cookie_loaded: false,
    cookie_masked: '',
    seed_html_loaded: false,
    seed_html_size: 0
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const fetchConfig = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch('/api/config', { headers });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching configurations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, [token]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!cookies && !seedHtml) return;

    setSaving(true);
    setSuccessMsg('');

    try {
      const headers = { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      
      const payload = {};
      if (cookies) payload.cookies = cookies;
      if (seedHtml) payload.seed_html = seedHtml;

      const res = await fetch('/api/config', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error('Failed to update configs.');
      }

      const data = await res.json();
      setSuccessMsg(data.message);
      setCookies('');
      setSeedHtml('');
      
      // Reload configurations
      await fetchConfig();
    } catch (err) {
      alert(err.message || 'Error occurred while saving configurations.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 p-8 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-8 w-8 text-[hsl(var(--accent-primary))]" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-[hsl(var(--text-secondary))] text-sm">Loading Configurations...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-8 animate-fade-in relative">
      <div className="bg-glow-violet bottom-[15%] right-[10%]" />
      
      {/* Title */}
      <div>
        <h1 className="text-3xl font-extrabold text-gradient tracking-tight">System Configurations</h1>
        <p className="text-[hsl(var(--text-secondary))] text-sm mt-1">Configure crawling sessions, bypass reCAPTCHA, and upload mapping seeds</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 z-10 relative">
        {/* Left Form Settings Panel */}
        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-base font-bold mb-4 flex items-center gap-2">
            <Lock size={18} className="text-[hsl(var(--accent-primary))]" />
            Session Credentials Input
          </h2>

          <form onSubmit={handleSave} className="space-y-6">
            {successMsg && (
              <div className="p-3 text-sm text-[hsl(var(--color-success))] bg-[hsla(var(--color-success)/0.1)] border border-[hsla(var(--color-success)/0.2)] rounded-xl flex items-center gap-2">
                <CheckCircle2 size={16} />
                {successMsg}
              </div>
            )}

            {/* Cookies Input */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase tracking-wider flex items-center gap-1.5">
                  <Cookie size={14} className="text-[hsl(var(--text-muted))]" />
                  Browser Session Cookies
                </label>
                {status.cookie_loaded && (
                  <span className="text-[10px] badge badge-success">Loaded: {status.cookie_masked}</span>
                )}
              </div>
              <textarea
                placeholder="Paste the 'Cookie' header value from your browser here (e.g. ASP.NET_SessionId=...; buisSemester=...)"
                value={cookies}
                onChange={(e) => setCookies(e.target.value)}
                rows={4}
                className="glass-input font-mono text-xs w-full resize-y"
              />
              <span className="text-[10px] text-[hsl(var(--text-muted))] leading-relaxed">
                Open Developer Tools (F12) → Network Tab → Search any department schedule page on Bogazici Registration → Copy the value of the <code>Cookie</code> header and paste it above.
              </span>
            </div>

            {/* Seed HTML Input */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-[hsl(var(--text-secondary))] uppercase tracking-wider flex items-center gap-1.5">
                  <FileText size={14} className="text-[hsl(var(--text-muted))]" />
                  Seed response.html Content
                </label>
                {status.seed_html_loaded && (
                  <span className="text-[10px] badge badge-success">Loaded: {(status.seed_html_size / 1024).toFixed(1)} KB</span>
                )}
              </div>
              <textarea
                placeholder="Paste raw HTML content of schedule.aspx index page here..."
                value={seedHtml}
                onChange={(e) => setSeedHtml(e.target.value)}
                rows={6}
                className="glass-input font-mono text-xs w-full resize-y"
              />
              <span className="text-[10px] text-[hsl(var(--text-muted))] leading-relaxed">
                This seed file maps semesters/terms dynamically for Phase 1. You can paste the raw source code of the Bogazici schedule page.
              </span>
            </div>

            <button
              type="submit"
              disabled={saving || (!cookies && !seedHtml)}
              className="btn-primary w-full py-3"
            >
              {saving ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Updating Backend Configuration...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Save size={16} />
                  Save Configurations
                </span>
              )}
            </button>
          </form>
        </div>

        {/* Right Instructions / Help Panel */}
        <div className="lg:col-span-1 space-y-6">
          {/* Warning reCAPTCHA */}
          <div className="glass-panel p-6 border-[hsla(var(--color-warning)/0.25)] bg-gradient-to-tr from-[hsla(var(--color-warning)/0.03)] to-transparent flex flex-col gap-4">
            <h3 className="text-sm font-semibold text-[hsl(var(--color-warning))] flex items-center gap-2">
              <AlertTriangle size={18} />
              reCAPTCHA Security Bypass
            </h3>
            <p className="text-xs text-[hsl(var(--text-secondary))] leading-relaxed">
              Bogazici Registration implements reCAPTCHA v3. To ensure successful scraping in Phase 3 and real-time quota lookups, session cookies are mandatory.
            </p>
            <div className="space-y-2 text-xs text-[hsl(var(--text-secondary))] leading-relaxed list-decimal pl-4">
              <p>1. Open your browser, navigate to Bogazici Registration Schedules page.</p>
              <p>2. Pass the captcha check by searching any department (e.g. CMPE).</p>
              <p>3. Copy the Cookie header string from network logs.</p>
              <p>4. Paste it here. The scraper will automatically inherit these credentials.</p>
            </div>
          </div>

          {/* Help Information Card */}
          <div className="glass-panel p-6 flex flex-col gap-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <HelpCircle size={18} className="text-[hsl(var(--color-info))]" />
              Need Assistance?
            </h3>
            <p className="text-xs text-[hsl(var(--text-secondary))] leading-relaxed">
              If scraping fails with "reCAPTCHA warning", your session cookies have expired. Re-authenticate in your browser, capture a new Cookie string, and update configurations above.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
