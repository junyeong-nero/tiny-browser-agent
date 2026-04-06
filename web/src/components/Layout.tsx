import { ReactNode } from 'react';

interface LayoutProps {
  statusBar: ReactNode;
  browserPane: ReactNode;
  chatPanel: ReactNode;
  sidebar: ReactNode;
}

export function Layout({ statusBar, browserPane, chatPanel, sidebar }: LayoutProps) {
  return (
    <div className="layout-container">
      <header className="layout-header">{statusBar}</header>
      <main className="layout-main">
        <div className="layout-left">
          <div className="browser-container">{browserPane}</div>
          <div className="chat-container">{chatPanel}</div>
        </div>
        <aside className="layout-sidebar">{sidebar}</aside>
      </main>
    </div>
  );
}
