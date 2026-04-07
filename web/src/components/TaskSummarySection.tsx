interface TaskSummarySectionProps {
  summary: string | null;
}

export function TaskSummarySection({ summary }: TaskSummarySectionProps) {
  return (
    <section className="verification-section">
      <h2>작업 요약</h2>
      <p>{summary ?? '요약 정보가 아직 없습니다.'}</p>
    </section>
  );
}
