function SevenDayOutlook({ sevenDay }) {
  if (!sevenDay || !sevenDay.periods) {
    return (
      <section className="card">
        <div className="card-title">7-Day Outlook</div>
        <p className="not-available">7-day forecast data not available</p>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-title">7-Day Outlook</div>
      <div className="outlook-grid">
        {sevenDay.periods.map((period, i) => (
          <div className="outlook-card" key={i}>
            <div className="day-name">{period.name}</div>
            <div className="temp">
              {period.temperature}&deg;{period.temperatureUnit}
            </div>
            <div className="wind-info">
              {period.windSpeed} {period.windDirection}
            </div>
            <div className="short-forecast">{period.shortForecast}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default SevenDayOutlook;
