# AirSense – fixes in this version

## How to run
1. `pip install -r requirements.txt`   (flask-cors was missing before – now included; keep scikit-learn==1.8.0 because the models were saved with it)
2. `python backend/app.py`
3. Open **http://127.0.0.1:5000** in the browser (Flask now serves the website too, which also makes GPS location work reliably).
4. Optional, to keep collecting history: `python backend/collector.py`

## Problems found and fixed

| Problem | Cause | Fix |
|---|---|---|
| "City not found", AQI/weather/traffic empty | The GPS name ("Majura Taluka") was sent to a geocoder that does not know talukas | Backend now works from GPS coordinates; names are cleaned (Taluka/District removed); 2 geocoders as backup |
| Always shows Majura Taluka / Ahmedabad | Old city saved in browser storage + hard-coded fallback | Location is detected on every open (GPS → IP → last place). Old saved value ignored. Added 📍 button to re-detect |
| Traffic button did nothing | Sidebar links were `href="#"` | Air Quality, Weather, Traffic, Settings are now real pages with data |
| Traffic "Unavailable" | One failing API blanked everything; TomTom has no data on small roads | New `/environment` endpoint: weather, AQI and traffic load in parallel and fail independently; traffic falls back to last saved reading; clear "No data" message |
| History chart empty | (1) `loadHistoricalData(range)` stray line crashed the page script, so nothing ever loaded. (2) Backend asked for "last 24h from NOW" but saved data ends in August | Script bug removed; ranges are now measured from the newest saved record; custom date range works; empty state with city suggestions |
| "Good morning" always | Greeting text never updated | Greeting follows your local time (morning/afternoon/evening/night), clock updates live |
| Name | Was derived from e-mail only | Real name from your account profile, e-mail prefix as fallback |
| Weather loading forever | OpenWeather failure left "Loading…" | Automatic fallback to free Open-Meteo weather |
| Slow AQI | CPCB 5000-record file downloaded on every request, via `curl.exe` (Windows only) | Uses `requests`, cached for 10 min |
| History page script/DB path | `airsense.db` was relative to where you launched Python | Absolute path next to the code |
| New places never get history/prediction | Only Visnagar was collected | Each visit saves a reading (max every 30 min) |

## New design
Same green/dark theme, simplified: hero AQI card with animated ring + scale marker, forecast card, 3 equal cards (weather / traffic / advisory), pollutant tiles with sub-index bars, skeleton loading, smooth card animations, mobile bottom navigation, working Analytics popup with a real 24h chart.
