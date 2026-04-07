interface FinalResultSectionProps {
  summary: string | null;
  onSelectCurrentPreview: () => void;
}

export function FinalResultSection({
  summary,
  onSelectCurrentPreview,
}: FinalResultSectionProps) {
  return (
    <section className="verification-section">
      <div className="section-header-with-action">
        <h2>최종 결과</h2>
        <button type="button" className="btn-secondary preview-button" onClick={onSelectCurrentPreview}>
          현재 시점 보기
        </button>
      </div>
      <p>{summary ?? '최종 결과 요약이 아직 없습니다.'}</p>
    </section>
  );
}
