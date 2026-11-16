# AirSense – Air Quality Prediction Platform

## Run
```
pip install -r requirements.txt
python backend/app.py
```
Open **http://127.0.0.1:5000** (Flask serves the website too).

Before the first run copy your own `.env` and `firebase-service-account.json` into this folder
(see `.env.example`). They are deliberately not part of this zip.

## Folders
* `backend/`  Flask API: AQI (Indian NAQI + US AQI), weather, traffic, forecast, history, login
* `frontend/` Dashboard, History, Login/Register
* `ml/`       `train_models.py` (XGBoost + CatBoost), trained models in `ml/models/`, old scripts in `ml/legacy/`

## Add more cities and retrain  (needs internet)
```
python backend/fix_database.py                  # only if you use your OWN old database
python backend/fetch_city_history.py --all      # ~40 cities, about 1 minute each, safe to re-run
python ml/train_models.py                       # writes ml/models/ + training_report.txt
```
`python backend/fetch_city_history.py --list` shows the cities (edit `backend/cities.py` to add more).

## Keep collecting live data
`python backend/collector.py` (cities from the file) or `python backend/collector.py Surat Rajkot`.
Every visit to the dashboard also saves a reading (at most every 30 minutes per place).

See `CHANGES_MADE.md` for what was fixed.
