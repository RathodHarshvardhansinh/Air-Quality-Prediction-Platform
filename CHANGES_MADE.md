# AirSense – changes in this version

## Why another website shows a different AQI
1. **Different scale** – you showed the Indian NAQI, most global sites show the US AQI
   (PM2.5 45 µg/m³ = NAQI 76 but US AQI 124). There is now an IN / US switch (also in Settings and History).
2. **CO unit bug** – CPCB CO in mg/m³ was divided by 100. Fixed (CO is mg/m³ in the code, µg/m³ in the database).
3. **Averaging** – NAQI now uses 24-h averages (8-h for CO/O3), US AQI uses NowCast, as the official rules say.
4. **Source** – nearest station limit 60 km -> 30 km, stale station data is ignored, and the dashboard shows
   whether the value is a ground station or a model estimate (ⓘ button explains the differences).

## Database (`python backend/fix_database.py`, already applied to the shipped airsense.db)
* 14,715 duplicate rows removed (Visnagar history was imported twice)
* `aqi` = Indian NAQI, new `us_aqi` = US AQI (before, history held US AQI and live rows held NAQI)
* one unit set (CO µg/m³, wind km/h, local time), one timestamp format, city names merged (Mehsana/Mahesāna)
* unique index (city, timestamp) so duplicates cannot come back
* old importers (`import_csv.py`, `import_historical_data.py`, `backfill_history.py`) are retired because they re-created the problem

## Machine learning
* Old model predicted US AQI while the dashboard showed NAQI. New models predict **both**, 1 h and 6 h ahead.
* XGBoost + CatBoost (+ Random Forest and "no change" baselines for comparison), time-ordered split, no leakage.
* One feature module (`backend/ml_features.py`) is shared by training and live prediction.
* Forecast refuses stale data; for a new place it downloads the last 3 days live (needs lat/lon, the dashboard sends it).
* Shipped models were trained on **Visnagar only** (the only city with real history). Run
  `fetch_city_history.py --all` then `ml/train_models.py` to train on many cities.

## Dashboard / API
* `/environment` loads weather, AQI and traffic in parallel and each can fail on its own.
* CPCB server is slow: 15 s max, then skipped for 5 min (searches stay instant).
* Location is detected on every open (GPS -> approximate -> last place); names like "Majura Taluka" are cleaned.
* History page crash fixed; ranges are measured from the newest saved record.
* Security: Flask debug mode off by default (`AIRSENSE_DEBUG=1` to enable), unauthenticated `/firebase-test` removed.

## Known limits
* History AQI for other cities is model-based (Open-Meteo/CAMS), not ground-sensor data.
* The US AQI 6-hour forecast is the least accurate (see `ml/models/training_report.txt`).
* Rows saved before this version have no US AQI when they lack continuous pollutant data.

## Update: wrong location + "Prediction unavailable"
* The dashboard now shows where the position came from (browser / approximate / chosen by you / saved city).
* If the device clock is Indian time but the detected place is abroad (VPN or bad network location),
  a notice explains it and points to the search box.
* A city you search for is **remembered** and no longer overwritten by auto-detection on the next open.
  Press the target button (⌖) to detect your location again.
* If xgboost/catboost are not installed, the server prints the exact install command at start-up and the
  dashboard says so. Install into the SAME Python / virtual environment that starts the server:
  `python -m pip install -r requirements.txt`
