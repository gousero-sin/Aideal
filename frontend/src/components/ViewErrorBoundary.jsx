import React from 'react';

// Segura falhas ao baixar ou renderizar um painel (ex.: chunk antigo após deploy)
// e oferece recarregar sem derrubar a sidebar e o restante da aplicação.
export default class ViewErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidUpdate(previousProps) {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error) {
    console.error('Falha ao abrir o painel.', error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="aideal-panel aideal-panel-error aideal-view-error" role="alert">
        <strong>Não foi possível abrir este painel.</strong>
        <div>Verifique a conexão e recarregue a página. Se acabou de sair uma nova versão, a recarga resolve.</div>
        <button
          className="aideal-action aideal-action-primary"
          type="button"
          onClick={() => window.location.reload()}
        >
          Recarregar página
        </button>
      </section>
    );
  }
}
