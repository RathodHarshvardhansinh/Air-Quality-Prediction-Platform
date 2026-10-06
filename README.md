# AirSense – Air Quality Prediction Platform

```
pip install -r requirements.txt
python backend/app.py
```
Then open http://127.0.0.1:5000

* `backend/`  Flask API (AQI, weather, traffic, predictions, history, login)
* `frontend/` Dashboard, History, Login/Register pages
* `ml/`       Trained models + training scripts
* `.env`      API keys (never share this file or `firebase-service-account.json`)

See `CHANGES_MADE.md` for what changed.
