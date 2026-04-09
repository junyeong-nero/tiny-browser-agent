import { useId, useState } from 'react';

interface AccessibilityTreeViewProps {
  artifactUrl: string | null;
  label: string;
}

export function AccessibilityTreeView({ artifactUrl, label }: AccessibilityTreeViewProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const contentId = useId();

  const loadArtifact = async () => {
    if (!artifactUrl || content != null || isLoading) {
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(artifactUrl);
      if (!response.ok) {
        throw new Error('Failed to load accessibility tree');
      }
      const text = await response.text();
      setContent(text);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load accessibility tree');
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggle = () => {
    const nextOpen = !isOpen;
    setIsOpen(nextOpen);
    if (nextOpen) {
      void loadArtifact();
    }
  };

  if (!artifactUrl) {
    return null;
  }

  return (
    <div className="a11y-tree-view">
      <button
        type="button"
        className="btn-secondary preview-button"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={handleToggle}
      >
        {isOpen ? 'A11y 숨기기' : 'A11y 보기'}
      </button>
      {isOpen && (
        <section id={contentId} className="a11y-tree-panel" aria-label={`${label} accessibility tree`}>
          {isLoading && <div className="a11y-tree-status">불러오는 중...</div>}
          {error && <div className="a11y-tree-status error">{error}</div>}
          {content && <pre className="a11y-tree-content">{content}</pre>}
        </section>
      )}
    </div>
  );
}
