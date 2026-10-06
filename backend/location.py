import re
import requests

HEADERS = {"User-Agent": "AirSense-AirQualityPlatform/1.0"}


def _clean(name):
    """'Majura Taluka' -> 'Majura', 'Surat District' -> 'Surat'."""
    if not name:
        return None
    name = re.sub(
        r"\s+(Taluka|Taluk|Tehsil|Tahsil|District|Division|Municipal Corporation)$",
        "",
        name.strip(),
        flags=re.I,
    )
    return name or None


def get_city_coordinates(city):
    """City name -> {name, latitude, longitude, ...}.  Tries 2 free services."""
    query = _clean(city) or city

    # 1) Open-Meteo geocoder
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        if r.status_code == 200:
            results = r.json().get("results")
            if results:
                x = results[0]
                return {
                    "name": x.get("name"),
                    "latitude": x.get("latitude"),
                    "longitude": x.get("longitude"),
                    "country": x.get("country"),
                    "state": x.get("admin1"),
                }
    except requests.RequestException as error:
        print("Open-Meteo geocoding error:", error)

    # 2) OpenStreetMap Nominatim (understands villages / talukas too)
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1, "addressdetails": 1},
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200 and r.json():
            x = r.json()[0]
            addr = x.get("address", {})
            return {
                "name": _clean(
                    addr.get("city") or addr.get("town") or addr.get("village")
                    or addr.get("county") or x.get("name") or city
                ),
                "latitude": float(x["lat"]),
                "longitude": float(x["lon"]),
                "country": addr.get("country"),
                "state": addr.get("state"),
            }
    except (requests.RequestException, ValueError, KeyError) as error:
        print("Nominatim search error:", error)

    return None


def reverse_geocode(latitude, longitude):
    """
    GPS -> readable place name.

    Prefers a real city/town.  Talukas and counties (e.g. 'Majura Taluka')
    are only used as a last resort, and the district (e.g. 'Surat') is
    preferred over them because that is what people expect to see.
    """
    r = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "zoom": 12,
            "addressdetails": 1,
        },
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    addr = r.json().get("address", {})

    raw = (
        addr.get("city")
        or addr.get("town")
        or addr.get("municipality")
        or addr.get("city_district")
        or addr.get("suburb")
        or addr.get("village")
        or addr.get("state_district")
        or addr.get("county")
    )
    name = _clean(raw)
    # "Surat" district beats a tiny sub-division of it
    district = _clean(addr.get("state_district"))
    if raw and re.search(r"(taluka|taluk|tehsil|tahsil)$", raw.strip(), re.I) and district:
        name = district

    return {
        "city": name,
        "district": district,
        "state": addr.get("state"),
        "country": addr.get("country"),
    }
