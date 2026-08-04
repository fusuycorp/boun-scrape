import React, { useState, useEffect } from 'react';
import { Sliders, Cookie, FileCode2, Save, RotateCcw, ShieldCheck, AlertCircle } from 'lucide-react';
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
        showToast(err.message || 'Failed to load configuration status', 'error');
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
      showToast(res.message || 'Configuration updated successfully!', 'success');
      setSeedHtml('');
      fetchConfig();
    } catch (err) {
      showToast(err.message || 'Failed to save configuration', 'error');
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
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Session & Credentials Manager
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Manage reCAPTCHA bypass session cookies (`cookies.txt`) and ASP.NET ViewState seed files (`response.html`).
        </p>
      </div>

      {/* Config Status Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="p-6 rounded-2xl glass-panel border border-white/10 flex items-center gap-4">
          <div className="p-3.5 rounded-xl bg-violet-500/20 text-violet-300 border border-violet-500/30">
            <Cookie className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              cookies.txt Status
            </span>
            <div className="flex items-center gap-2 mt-1">
              {status?.cookie_loaded ? (
                <span className="text-sm font-extrabold text-emerald-400">
                  Active ({status.cookie_masked || 'Loaded'})
                </span>
              ) : (
                <span className="text-sm font-extrabold text-amber-400">
                  Not Loaded / Expired
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="p-6 rounded-2xl glass-panel border border-white/10 flex items-center gap-4">
          <div className="p-3.5 rounded-xl bg-pink-500/20 text-pink-300 border border-pink-500/30">
            <FileCode2 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              response.html Seed
            </span>
            <div className="flex items-center gap-2 mt-1">
              {status?.seed_html_loaded ? (
                <span className="text-sm font-extrabold text-emerald-400">
                  Present ({status.seed_html_size?.toLocaleString()} bytes)
                </span>
              ) : (
                <span className="text-sm font-extrabold text-amber-400">
                  Missing Seed File
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSave} className="space-y-6">
        {/* Cookie Input */}
        <div className="p-6 rounded-2xl glass-panel border border-white/10 space-y-3">
          <label className="block text-sm font-bold text-white flex items-center gap-2">
            <Cookie className="w-4 h-4 text-violet-400" />
            Session Cookie String (`ASP.NET_SessionId`)
          </label>
          <p className="text-xs text-slate-400">
            Paste the raw cookie string from your browser inspection tool when logged into registration.bogazici.edu.tr.
          </p>
          <textarea
            rows="3"
            value={cookies}
            onChange={(e) => setCookies(e.target.value)}
            placeholder="ASP.NET_SessionId=abcdef1234567890..."
            className="w-full p-4 rounded-xl glass-input text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-violet-500/50"
          />
        </div>

        {/* Seed HTML Input */}
        <div className="p-6 rounded-2xl glass-panel border border-white/10 space-y-3">
          <label className="block text-sm font-bold text-white flex items-center gap-2">
            <FileCode2 className="w-4 h-4 text-pink-400" />
            Seed Form HTML (`response.html`)
          </label>
          <p className="text-xs text-slate-400">
            Paste full HTML source of schedule.aspx containing ASP.NET `__VIEWSTATE` and `__EVENTVALIDATION` fields.
          </p>
          <textarea
            rows="6"
            value={seedHtml}
            onChange={(e) => setSeedHtml(e.target.value)}
            placeholder="<!DOCTYPE html><html><head>...<input type='hidden' name='__VIEWSTATE'..."
            className="w-full p-4 rounded-xl glass-input text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-violet-500/50"
          />
        </div>

        {/* Save Floating Bar */}
        {isDirty && (
          <div className="fixed bottom-6 right-6 z-40 p-4 rounded-2xl bg-slate-900/90 border border-violet-500/50 shadow-2xl backdrop-blur-xl flex items-center gap-4 animate-slide-up">
            <div className="flex items-center gap-2 text-xs font-bold text-violet-300">
              <AlertCircle className="w-4 h-4 text-violet-400" />
              <span>Unsaved changes</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleReset}
                className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-colors"
              >
                Discard
              </button>
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-pink-600 hover:from-violet-500 hover:to-pink-500 text-white font-bold text-xs shadow-lg transition-all"
              >
                <Save className="w-4 h-4" />
                <span>{saving ? 'Saving...' : 'Save Config'}</span>
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
