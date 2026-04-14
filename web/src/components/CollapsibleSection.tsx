import { useId, useState, type ReactNode } from 'react';

interface CollapsibleSectionProps {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

export function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
  className = '',
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const contentId = useId();
  const sectionClassName = ['verification-section', 'collapsible-section', className]
    .filter(Boolean)
    .join(' ');

  return (
    <section className={sectionClassName}>
      <button
        type="button"
        className="collapsible-section-summary"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span>{title}</span>
      </button>
      {isOpen && (
        <div id={contentId} className="collapsible-section-body">
          {children}
        </div>
      )}
    </section>
  );
}
