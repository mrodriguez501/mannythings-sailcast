function WindForecast({ hourly }) {
  if (!hourly || !hourly.periods) {
    return (
      <section className="card">
        <div className="card-title">24-Hour Wind Forecast</div>
        <p className="not-available">Hourly forecast data not available</p>
      </section>
    );
  }

  function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  }

  return (
    <section className="card">
      <div className="card-title">24-Hour Wind Forecast</div>
      <div style={{ maxHeight: "400px", overflowY: "auto" }}>
        <table className="wind-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Wind</th>
              <th>Direction</th>
              <th>Temp</th>
              <th>Conditions</th>
            </tr>
          </thead>
          <tbody>
            {hourly.periods.map((period, i) => (
              <tr key={i}>
                <td>{formatTime(period.startTime)}</td>
                <td>
                  <strong>{period.windSpeed}</strong>
                </td>
                <td>{period.windDirection}</td>
                <td>
                  {period.temperature}&deg;{period.temperatureUnit}
                </td>
                <td>{period.shortForecast}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default WindForecast;
