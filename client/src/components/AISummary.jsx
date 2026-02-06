function AISummary({ summary }) {
  if (!summary) {
    return (
      <section className="card ai-summary">
        <div className="card-title">
          <span>AI Weather Summary</span>
          <span className="ai-label">AI POWERED</span>
        </div>
        <p className="not-available">AI summary is being generated...</p>
      </section>
    );
  }

  const level = (summary.safetyLevel || "").toLowerCase();

  return (
    <section className={`card ai-summary ${level}`}>
      <div className="card-title">
        <span>AI Weather Summary</span>
        <span className="ai-label">AI POWERED</span>
        <span className={`safety-badge ${level}`}>{summary.safetyLevel}</span>
      </div>

      <p className="summary-text">{summary.summary}</p>

      <p className="advisory-text">{summary.advisory}</p>

      {summary.keyConcerns && summary.keyConcerns.length > 0 && (
        <ul className="concerns-list">
          {summary.keyConcerns.map((concern, i) => (
            <li key={i}>{concern}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default AISummary;
