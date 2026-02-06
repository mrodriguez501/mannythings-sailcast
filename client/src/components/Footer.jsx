function Footer({ lastUpdated }) {
  const formattedTime = lastUpdated
    ? new Date(lastUpdated).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "N/A";

  return (
    <footer className="footer">
      <p>
        Data sourced from the{" "}
        <a
          href="https://www.weather.gov"
          target="_blank"
          rel="noopener noreferrer"
        >
          National Weather Service
        </a>
        . AI summaries powered by OpenAI. Last updated: {formattedTime}
      </p>
      <p>
        SailCast &copy; {new Date().getFullYear()} &middot;{" "}
        <a
          href="https://mannythings.us"
          target="_blank"
          rel="noopener noreferrer"
        >
          mannythings.us
        </a>
      </p>
    </footer>
  );
}

export default Footer;
