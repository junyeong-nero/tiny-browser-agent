interface RequestSummaryHeaderProps {
  requestText: string | null;
}

export function RequestSummaryHeader({ requestText }: RequestSummaryHeaderProps) {
  return (
    <section className="verification-section">
      <h2>요청 내용</h2>
      <p>{requestText ?? '아직 요청 내용이 없습니다.'}</p>
    </section>
  );
}
