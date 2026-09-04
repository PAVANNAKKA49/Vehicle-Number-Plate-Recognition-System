# INDISCAN — Quick Start Commands

---

## 🌐 Run Web App (Flask)

```bash
cd number_plate_flask_or_fasiapi/web

# First time only — create virtual env and install deps
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run the server
python app.py
```
Open: **http://localhost:5000**

---

## 📱 Run Mobile App (Build APK)

```bash
cd number_plate_flask_or_fasiapi/mobile_app

# First time only — install node packages
npm install
```

**Update your server URL first:**  
Edit `src/api.js` → replace `NGROK_URL` with your ngrok/local IP.

```bash
# Step 1 — Bundle JavaScript into app assets
npx react-native bundle --platform android --dev false --entry-file index.js --bundle-output .\android\app\src\main\assets\index.android.bundle --assets-dest .\android\app\src\main\res

# Step 2 — Build the APK
cd android
.\gradlew.bat assembleDebug
```

APK location:
```
mobile_app\android\app\build\outputs\apk\debug\app-debug.apk
```

> ⚡ Re-run **both steps** every time you change code or update the server URL.

---

## 🔗 ngrok (to expose Flask to phone over internet)

```bash
ngrok http 5000
```
Copy the `https://xxxx.ngrok-free.app` URL → paste into `src/api.js` → rebuild APK.
