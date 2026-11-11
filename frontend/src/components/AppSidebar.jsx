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
import { useMediaQuery } from '../hooks/useMediaQuery';
import '../styles/access-control.css';

const MODULE_ICONS = Object.freeze({
  dre: BarChart3,
  fluxo_caixa: WalletCards,
  admin_banco: Database,
  usuarios: Users,
  orcamento: Calculator,
});

// Mesmo limite do CSS (access-control.css): abaixo dele a sidebar vira gaveta.
export const SIDEBAR_DRAWER_QUERY = '(max-width: 900px)';
const DRAWER_OPEN_CLASS = 'access-drawer-open';
const FOCUSABLE_SELECTOR = 'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function AppSidebar({
  modules,
  permissions,
  activeView,
  onSelectView,
  user,
  onLogout,
  open = false,
  onOpenChange,
  onPrefetchView,
}) {
  const [logoutBusy, setLogoutBusy] = useState(false);
  const sidebarRef = useRef(null);
  const triggerRef = useRef(null);
  const closeButtonRef = useRef(null);
  const wasOpenRef = useRef(open);
  const isDrawer = useMediaQuery(SIDEBAR_DRAWER_QUERY);
  const drawerOpen = isDrawer && open;
  const visibleModules = filterAccessibleModules(modules, permissions);

  // Ao voltar para a largura de desktop a gaveta deixa de existir.
  useEffect(() => {
    if (!isDrawer && open) onOpenChange?.(false);
  }, [isDrawer, onOpenChange, open]);

  useEffect(() => {
    if (!drawerOpen) return undefined;
    const root = document.documentElement;
    root.classList.add(DRAWER_OPEN_CLASS);
    closeButtonRef.current?.focus();

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onOpenChange?.(false);
        return;
      }
      if (event.key !== 'Tab' || !sidebarRef.current) return;
      const focusables = [...sidebarRef.current.querySelectorAll(FOCUSABLE_SELECTOR)];
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const inside = sidebarRef.current.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || !inside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !inside)) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      root.classList.remove(DRAWER_OPEN_CLASS);
    };
  }, [drawerOpen, onOpenChange]);

  // Devolve o foco ao botão de menu quando a gaveta fecha sem navegar.
  useEffect(() => {
    if (wasOpenRef.current && !open && isDrawer && sidebarRef.current?.contains(document.activeElement)) {
      triggerRef.current?.focus();
    }
    wasOpenRef.current = open;
  }, [isDrawer, open]);

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
        ref={triggerRef}
        className={`access-sidebar-trigger ${open ? 'is-menu-open' : ''}`}
        type="button"
        aria-label={open ? 'Menu aberto' : 'Abrir menu'}
        aria-expanded={open}
        aria-controls="goflow-sidebar"
        onClick={() => onOpenChange?.(true)}
      >
        <Menu size={21} aria-hidden="true" />
      </button>

      {drawerOpen && (
        <button
          className="access-sidebar-backdrop"
          type="button"
          aria-label="Fechar menu"
          tabIndex={-1}
          onClick={() => onOpenChange?.(false)}
        />
      )}

      <aside
        ref={sidebarRef}
        id="goflow-sidebar"
        className={`access-sidebar ${open ? 'is-open' : ''}`}
        aria-label="Menu principal"
        inert={isDrawer && !open ? true : undefined}
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
            const prefetch = () => onPrefetchView?.(module.id);
            return (
              <button
                key={module.id}
                className={`access-sidebar-item ${selected ? 'is-active' : ''}`}
                type="button"
                aria-current={selected ? 'page' : undefined}
                onClick={() => selectView(module.id)}
                onPointerEnter={prefetch}
                onFocus={prefetch}
                onTouchStart={prefetch}
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
              <strong title={user?.displayName || user?.username || 'Usuario'}>
                {user?.displayName || user?.username || 'Usuario'}
              </strong>
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
