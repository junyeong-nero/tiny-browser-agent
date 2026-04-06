interface BrowserPaneProps {
  screenshotB64: string | null | undefined;
  status: string | undefined;
  updatedAt: number | null | undefined;
}

export function BrowserPane({ screenshotB64, status, updatedAt }: BrowserPaneProps) {
  if (!screenshotB64) {
    return (
      <div className="browser-pane empty">
        {status === 'running' ? 'Waiting for browser...' : 'No browser preview available'}
      </div>
    );
  }

  return (
    <div className="browser-pane">
      <div className="browser-pane-content">
        <img
          src={`data:image/png;base64,${screenshotB64}`}
          alt="Browser Preview"
          className="browser-screenshot"
        />
        {updatedAt != null && (
          <div className="browser-updated-at">
            Updated {new Date(updatedAt * 1000).toLocaleTimeString()}
          </div>
        )}
      </div>
    </div>
  );
}
