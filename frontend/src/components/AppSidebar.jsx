import React, { useEffect, useRef, useState } from 'react';
import {
  BarChart3,
  Calculator,
  Database,
  LogOut,
  Menu,
  Users,
  WalletCards,
  X,
} from 'lucide-react';
import { filterAccessibleModules } from './accessControlModel';
import '../styles/access-control.css';

const MODULE_ICONS = Object.freeze({
  dre: BarChart3,
  fluxo_caixa: WalletCards,
  admin_banco: Database,
  usuarios: Users,
  orcamento: Calculator,
});

export default function AppSidebar({
  modules,
  permissions,
  activeView,
  onSelectView,
  user,
  onLogout,
  open = false,
  onOpenChange,
}) {
  const [logoutBusy, setLogoutBusy] = useState(false);
  const closeButtonRef = useRef(null);
  const visibleModules = filterAccessibleModules(modules, permissions);

  useEffect(() => {
    if (!open) return undefined;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onOpenChange?.(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onOpenChange]);

  const selectView = (moduleId) => {
    onSelectView?.(moduleId);
    onOpenChange?.(false);
  };

  const handleLogout = async () => {
    if (!onLogout || logoutBusy) return;
    setLogoutBusy(true);
    try {
      await onLogout();
    } finally {
      setLogoutBusy(false);
    }
  };

  return (
    <>
      <button
        className={`access-sidebar-trigger ${open ? 'is-menu-open' : ''}`}
        type="button"
        aria-label={open ? 'Menu aberto' : 'Abrir menu'}
        aria-expanded={open}
        aria-controls="goflow-sidebar"
        onClick={() => onOpenChange?.(true)}
      >
        <Menu size={21} aria-hidden="true" />
      </button>

      {open && (
        <button
          className="access-sidebar-backdrop"
          type="button"
          aria-label="Fechar menu"
          onClick={() => onOpenChange?.(false)}
        />
      )}

      <aside
        id="goflow-sidebar"
        className={`access-sidebar ${open ? 'is-open' : ''}`}
        aria-label="Menu principal"
      >
        <header className="access-sidebar-header">
          <img src="/logo-aideal-peq-2.png" alt="AIDEAL" />
          <button
            ref={closeButtonRef}
            className="access-sidebar-close"
            type="button"
            aria-label="Fechar menu"
            onClick={() => onOpenChange?.(false)}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        <nav className="access-sidebar-nav" aria-label="Paineis liberados">
          <p className="access-sidebar-eyebrow">Seus acessos</p>
          {visibleModules.length === 0 && (
            <p className="access-sidebar-empty">Nenhum painel liberado.</p>
          )}
          {visibleModules.map((module) => {
            const Icon = MODULE_ICONS[module.id] || BarChart3;
            const selected = activeView === module.id;
            return (
              <button
                key={module.id}
                className={`access-sidebar-item ${selected ? 'is-active' : ''}`}
                type="button"
                aria-current={selected ? 'page' : undefined}
                onClick={() => selectView(module.id)}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{module.label}</span>
              </button>
            );
          })}
        </nav>

        <footer className="access-sidebar-footer">
          <div className="access-sidebar-user">
            <span aria-hidden="true">{(user?.displayName || user?.username || 'U').slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user?.displayName || user?.username || 'Usuario'}</strong>
              <small>{user?.username || ''}</small>
            </div>
          </div>
          <button
            className="access-sidebar-logout"
            type="button"
            onClick={handleLogout}
            disabled={logoutBusy}
          >
            <LogOut size={17} aria-hidden="true" />
            {logoutBusy ? 'Saindo...' : 'Sair'}
          </button>
        </footer>
      </aside>
    </>
  );
}
