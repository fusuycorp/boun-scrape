import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [authenticating, setAuthenticating] = useState(true);

  const validateSession = useCallback(async (authToken) => {
    if (!authToken) {
      setUser(null);
      setAuthenticating(false);
      return;
    }

    try {
      const meData = await api.getMe();
      setUser(meData);
    } catch {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
    } finally {
      setAuthenticating(false);
    }
  }, []);

  useEffect(() => {
    validateSession(token);
  }, [token, validateSession]);

  const login = async (username, password) => {
    setAuthenticating(true);
    try {
      const data = await api.login(username, password);
      const newToken = data.access_token;
      localStorage.setItem('token', newToken);
      setToken(newToken);
      await validateSession(newToken);
      return true;
    } catch (error) {
      setAuthenticating(false);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        authenticating,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
