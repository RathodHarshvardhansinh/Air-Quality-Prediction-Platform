import requests
from config import CPCB_API_KEY

url = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"

params = {
    "api-key": CPCB_API_KEY,
    "format": "json",
    "filters[state]": "Gujarat",
    "filters[city]": "Visnagar",
    "limit": 10
}

print("Testing CPCB API...")
print("API key loaded:", bool(CPCB_API_KEY))
print("Requesting Gujarat / Visnagar...")

try:

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    print("\nSTATUS:", response.status_code)

    print("\nRESPONSE:")
    print(response.text[:5000])

except requests.exceptions.Timeout:

    print("\nCPCB API timed out")

except requests.exceptions.RequestException as error:

    print("\nCPCB API ERROR:")
    print(error)