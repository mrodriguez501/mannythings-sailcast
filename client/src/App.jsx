import { useState, useEffect } from "react";
import Header from "./components/Header";
import AISummary from "./components/AISummary";
import WindForecast from "./components/WindForecast";
import SevenDayOutlook from "./components/SevenDayOutlook";
import Advisories from "./components/Advisories";
import Footer from "./components/Footer";
import { fetchForecastData } from "./services/api";

function App() {
  const [data, setData] = useState({
    hourly: null,
    sevenDay: null,
    alerts: null,
    summary: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
    // Refresh every 15 minutes
    const interval = setInterval(loadData, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  async function loadData() {
    try {
      setError(null);
      const result = await fetchForecastData();
      setData(result);
    } catch (err) {
      setError("Unable to load forecast data. Please try again later.");
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="app">
        <Header />
        <main className="main-content">
          <div className="loading">
            <div className="loading-spinner"></div>
            <p>Loading forecast data...</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <Header />
      <main className="main-content">
        {error && <div className="error-banner">{error}</div>}
        <AISummary summary={data.summary} />
        <div className="forecast-grid">
          <WindForecast hourly={data.hourly} />
          <Advisories alerts={data.alerts} />
        </div>
        <SevenDayOutlook sevenDay={data.sevenDay} />
      </main>
      <Footer lastUpdated={data.hourly?.fetchedAt} />
    </div>
  );
}

export default App;
