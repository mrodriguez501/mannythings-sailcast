function Advisories({ alerts }) {
  if (!alerts) {
    return (
      <section className="card">
        <div className="card-title">Active Advisories</div>
        <p className="not-available">Alert data not available</p>
      </section>
    );
  }

  if (alerts.count === 0) {
    return (
      <section className="card">
        <div className="card-title">Active Advisories</div>
        <p className="no-alerts">No active weather advisories</p>
      </section>
    );
  }

  function getSeverityClass(severity) {
    switch (severity?.toLowerCase()) {
      case "extreme":
      case "severe":
        return "severe";
      case "moderate":
        return "moderate";
      default:
        return "minor";
    }
  }

  return (
    <section className="card">
      <div className="card-title">
        Active Advisories ({alerts.count})
      </div>
      {alerts.alerts.map((alert, i) => (
        <div
          className={`alert-item ${getSeverityClass(alert.severity)}`}
          key={i}
        >
          <div className="alert-event">{alert.event}</div>
          <div className="alert-headline">{alert.headline}</div>
        </div>
      ))}
    </section>
  );
}

export default Advisories;
