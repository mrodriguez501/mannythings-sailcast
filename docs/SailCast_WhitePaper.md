# SailCast: Enhancing Coastal Sailing Safety with AI and NWS Forecast Integration

## 1. Introduction

SailCast is a lightweight, server-hosted application designed to improve coastal sailing decisions through the integration of real-time National Weather Service (NWS) data and artificial intelligence. Hosted on AWS Lightsail and accessible at **mannythings.us/sailcast**, the app aims to provide hourly-updated weather conditions and sailing advisories for specific coastal locations. The initial implementation targets the **Potomac River near KDCA airport**.

This white paper presents the system architecture, design rationale, and implementation approach for incorporating AI-driven insights based on user-defined sailing club safety rules.

## 2. Problem Statement

Recreational sailors often rely on raw weather forecasts that require interpretation. While the NWS provides accurate data, contextualizing it based on boat type, safety rules, and risk thresholds remains a manual and subjective process. SailCast addresses this challenge by automating:

- Hourly retrieval of NWS forecast data
- Parsing and display of critical parameters (wind, gusts, alerts)
- AI-generated weather summaries
- AI-based sailing advisories based on club-defined safety rules

## 3. Architecture Overview

### Frontend
A React application (built with **Vite**) displaying the current 24-hour wind forecast, 7-day weather outlook, and any active advisories. AI-generated summaries are featured in a dedicated section for clarity.

### Backend
- **Python FastAPI** server with scheduled tasks to fetch and parse NWS data
- AI integration using **OpenAI's Python SDK** to interpret forecasts
- **APScheduler** for reliable hourly cron-like job scheduling
- **httpx** as the async HTTP client for NWS API calls
- Club rules document processed as prompt context to ensure recommendations adhere to safety standards

### Hosting
Deployed on an **AWS Lightsail** instance configured for GitHub-based deployments and HTTPS via Let's Encrypt. The FastAPI server runs behind **uvicorn** with nginx as a reverse proxy.

## 4. Key Features

- **Hourly Updates**: Forecast data is refreshed every hour on the hour via APScheduler
- **Compliant Forecast Source**: Only NWS forecast and alert data are used, in accordance with club policy
- **Rules-Aware AI Summaries**: Club safety documents (formatted as Markdown) are used to generate customized, actionable summaries
- **Full Forecast Display**: In addition to the summary, raw wind, gust, and advisory data are shown in clearly labeled sections for transparency

## 5. AI Integration

The AI module reads parsed forecast data and club rules, then uses prompt engineering to generate:

- A human-readable **24-hour weather summary**
- **Sailing advisories** based on boat type, forecasted wind speed, gusts, and alerts
- A **safety level classification** (SAFE / CAUTION / UNSAFE)

### Example Prompt Content

> "You are a sailing safety advisor for a sailing club on the Potomac River near KDCA. Based on the following club rules for Flying Scot boats... [rules here] ... and the following NWS forecast data... [forecast here] ... generate a safety advisory and summary."

### Response Format

The AI returns structured JSON with: `summary`, `advisory`, `safetyLevel`, `keyConcerns`, and `generatedAt` fields, enabling reliable frontend rendering.

## 6. Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | React 19 + Vite 6 |
| Backend | Python 3.11+ / FastAPI |
| AI Engine | OpenAI Python SDK (GPT-4o) |
| HTTP Client | httpx (async) |
| Scheduler | APScheduler |
| Weather Data | NWS API (api.weather.gov) |
| Hosting | AWS Lightsail + nginx + uvicorn |
| Version Control | Git + GitHub |

## 7. Deployment and Maintainability

- **Git-Based Deployment**: Local development is pushed to GitHub and deployed to Lightsail via a deployment shell script
- **Secure Key Management**: OpenAI API keys and configuration variables are stored in environment files (`.env`) and excluded from version control
- **Automated Scheduling**: Uses APScheduler to run data collection and summary generation hourly
- **Virtual Environments**: Python dependencies are isolated in `venv/` and excluded from the repository

## 8. AI Ethics and Future Enhancements

- **Transparent Recommendations**: AI outputs are shown alongside raw data to maintain user trust
- **No Real-Time User Queries**: To prevent misuse and simplify safety assurance, AI only provides summary output, not dynamic Q&A

### Future Features
- Expand to multiple sailing classes
- Support multiple sailing locations
- Add interactive prompts to simulate user engagement and varying weather conditions
- Historical forecast tracking and trend analysis

## 9. Proof of Concept

As a foundational step, a minimal proof of concept (PoC) will be developed to validate the integration of core system components:

1. **OpenAI API Connection**: Successfully call the API with a test prompt and render the response
2. **NWS API Fetch**: Pull a basic forecast (e.g., KDCA metadata) and log/display the response
3. **React Frontend**: Display the AI test response and NWS test data in the browser
4. **Lightsail Hosting**: Confirm communication between deployed backend and frontend

This PoC will establish baseline connectivity and system integrity before implementing full rule-based summaries and data parsing.

## 10. Conclusion

SailCast represents a responsible, rules-driven application of artificial intelligence in the recreational sailing domain. By combining trusted public data from the NWS with a custom-tailored advisory engine, SailCast enhances safety, provides clarity, and offers a blueprint for other safety-focused systems seeking to integrate AI into public service environments.

---

## Appendices

- **Appendix A**: Sample Club Rules — see `server/app/data/club_rules.md`
- **Appendix B**: API Endpoints — see `README.md`
- **Appendix C**: Prompt Engineering — see `server/app/services/openai_service.py`
- **Appendix D**: Deployment Script — see `deploy.sh`
