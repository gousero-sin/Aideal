import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { ANONYMOUS_SESSION, createAuthClient } from './authClient';

const AuthContext = createContext(null);

export function AuthProvider({ children, apiBase = '/api' }) {
  const client = useMemo(() => createAuthClient({ apiBase }), [apiBase]);
  const [session, setSession] = useState({ ...ANONYMOUS_SESSION });
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  const refreshSession = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      const nextSession = await client.getSession();
      setSession(nextSession);
      setStatus(nextSession.authenticated ? 'authenticated' : 'anonymous');
      return nextSession;
    } catch (requestError) {
      setSession({ ...ANONYMOUS_SESSION });
      setStatus('anonymous');
      setError(requestError.message);
      return { ...ANONYMOUS_SESSION };
    }
  }, [client]);

  useEffect(() => {
    let active = true;
    setStatus('loading');
    client.getSession()
      .then((nextSession) => {
        if (!active) return;
        setSession(nextSession);
        setStatus(nextSession.authenticated ? 'authenticated' : 'anonymous');
      })
      .catch((requestError) => {
        if (!active) return;
        setSession({ ...ANONYMOUS_SESSION });
        setStatus('anonymous');
        setError(requestError.message);
      });
    return () => {
      active = false;
    };
  }, [client]);

  const login = useCallback(async (credentials) => {
    setStatus('loading');
    setError(null);
    try {
      const nextSession = await client.login(credentials);
      if (!nextSession.authenticated) throw new Error('Credenciais invalidas.');
      setSession(nextSession);
      setStatus('authenticated');
      return nextSession;
    } catch (requestError) {
      setStatus('anonymous');
      setError(requestError.message);
      throw requestError;
    }
  }, [client]);

  const logout = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      await client.logout(session.csrfToken);
      setSession({ ...ANONYMOUS_SESSION });
      setStatus('anonymous');
    } catch (requestError) {
      setStatus('authenticated');
      setError(requestError.message);
      throw requestError;
    }
  }, [client, session.csrfToken]);

  const changePassword = useCallback(async (passwords) => {
    setStatus('loading');
    setError(null);
    try {
      const nextSession = await client.changePassword(passwords, session.csrfToken);
      if (!nextSession.authenticated) {
        throw new Error('Nao foi possivel atualizar a sessao. Entre novamente.');
      }
      setSession(nextSession);
      setStatus('authenticated');
      return nextSession;
    } catch (requestError) {
      setStatus(session.authenticated ? 'authenticated' : 'anonymous');
      setError(requestError.message);
      throw requestError;
    }
  }, [client, session.authenticated, session.csrfToken]);

  const hasPermission = useCallback(
    (permission) => session.permissions.includes(permission),
    [session.permissions],
  );

  const value = useMemo(() => ({
    ...session,
    status,
    error,
    login,
    logout,
    changePassword,
    refreshSession,
    hasPermission,
  }), [changePassword, error, hasPermission, login, logout, refreshSession, session, status]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth deve ser usado dentro de AuthProvider.');
  return context;
}
