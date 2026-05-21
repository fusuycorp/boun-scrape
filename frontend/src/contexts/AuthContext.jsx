import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token') || '');
  const [username, setUsername] = useState('');
  const [authenticating, setAuthenticating] = useState(true);

  const validateToken = useCallback(async (tokenToValidate) => {
    if (!tokenToValidate) {
      setAuthenticating(false);
      return;
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          Authorization: `Bearer ${tokenToValidate}`,
        },
      });

      if (!response.ok) {
        throw new Error('Token validation failed');
      }

      const data = await response.json();
      setUsername(data.username);
    } catch (err) {
      console.warn('Authentication token expired or server offline. Logging out...');
      logout();
    } finally {
      setAuthenticating(false);
    }
  }, []);

  useEffect(() => {
    validateToken(token);
  }, [token, validateToken]);

  const login = (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken('');
    setUsername('');
  };

  const value = {
    token,
    username,
    authenticating,
    isAuthenticated: !!token,
    login,
    logout,
    refreshUser: () => validateToken(token)
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
