# Falak Finance Monitor

## Prerequisites
- OCI VPS (Ubuntu 24.04 recommended)
- Tailscale installed and configured
- Docker and Docker Compose installed

## Setup
1. Put the repository on the server:
   ```bash
   cd falak-finance-monitor
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   # Fill in values in .env, including TAILSCALE_IP from `tailscale ip -4`
   ```
3. Create data directory:
   ```bash
   mkdir -p data
   ```
4. Launch the application:
   ```bash
   docker-compose up -d
   ```

## Access
Access the dashboard via the Tailscale IP configured in `.env`:
`http://$TAILSCALE_IP:8765`

## Kite Token Refresh
Zerodha Kite requires a daily access token refresh. Run the following script to generate a new token:

```python
import os
from kiteconnect import KiteConnect

KITE_API_KEY = os.environ["KITE_API_KEY"]
KITE_API_SECRET = os.environ["KITE_API_SECRET"]

def get_kite_token():
    kite = KiteConnect(api_key=KITE_API_KEY)
    print(f"1. Go to this URL: {kite.login_url()}")
    request_token = input("2. Enter the 'request_token' from the redirect URL: ")
    
    try:
        data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
        print(f"\nSUCCESS! Your Access Token is:\n{data['access_token']}")
        print("\nUpdate your .env file with this KITE_ACCESS_TOKEN.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_kite_token()
```

## Binance API Setup
- Create a **read-only** API key on Binance.
- **DO NOT** enable trading or withdrawal permissions.
- Restrict access to your Tailscale IP for maximum security.

## Tailscale Setup
No OCI Security List changes are needed. Tailscale manages the encrypted tunnel, allowing you to access port 8765 securely over the Tailscale network.

## Logs
Monitor the application logs:
```bash
docker-compose logs -f falak-finance-monitor
```

## Update
To update and rebuild the application:
```bash
git pull
docker-compose up -d --build
```
