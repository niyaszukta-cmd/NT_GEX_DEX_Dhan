# NYZTrade - Advanced GEX + DEX Analysis Dashboard

Professional-grade Gamma Exposure (GEX) and Delta Exposure (DEX) analysis dashboard for Indian stock markets.

## Features

- ✅ Real-time option chain data via DhanHQ API
- ✅ Gamma & Delta exposure calculations
- ✅ Gamma flip zone detection
- ✅ Flow analysis (GEX/DEX bias)
- ✅ Interactive Plotly charts
- ✅ Trading strategy recommendations
- ✅ Multi-tier authentication
- ✅ Data export functionality

## Setup

### 1. Get DhanHQ API Credentials

1. Open account at [dhan.co](https://www.dhan.co/)
2. Go to API Management
3. Generate API Key and API Secret

### 2. Deploy to Streamlit Cloud

1. Fork this repository
2. Go to [share.streamlit.io](https://share.streamlit.io/)
3. Click "New app"
4. Select your repository
5. Add secrets (Settings → Secrets):
```toml
[passwords]
demo = "demo123"
premium = "premium123"
premium_users = ["premium", "niyas"]

dhan_client_id = "YOUR_CLIENT_ID"
dhan_access_token = "YOUR_API_SECRET"
```

6. Deploy!

## Usage

- **Free Tier**: Login with `demo` / `demo123`
- **Premium**: Login with `premium` / `premium123`

## Tech Stack

- **Frontend**: Streamlit
- **Data**: DhanHQ API v2.1.0
- **Calculations**: Pandas, NumPy, SciPy
- **Visualization**: Plotly
- **Options Pricing**: Black-Scholes model

## License

MIT License - See LICENSE file

## Support

Subscribe to NYZTrade on YouTube for tutorials and updates!

## Disclaimer

This tool is for educational purposes only. Not financial advice.
