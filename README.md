# VoIP Platform

FreeSWITCH-based residential VoIP platform with REST API.

## Features

- Customer management via REST API
- SIP registration and authentication
- Call forwarding
- CDR (Call Detail Records) tracking
- PostgreSQL backend
- Automatic deployment via Git

## Deployment

Push to the `main` branch to automatically deploy to production.

## API Documentation

See `/docs/API.md` for endpoint documentation.

## Local Development

1. Create virtual environment: `python3 -m venv venv`
2. Activate: `source venv/bin/activate`
3. Install deps: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and configure
5. Run: `python app.py`