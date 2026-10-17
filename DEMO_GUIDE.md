# 🚚 Google AI Smart Logistics & Fleet Dispatch Handler

An on-the-spot prototype built for the Google Developer Group (GDG) hackathon using:
- **Google Gemini 2.5 Flash (`google-genai`)**: Unstructured order intake & real-time empathetic customer delay notifications.
- **Google Routes API / TSP Optimizer**: Multi-stop shortest-path route sequencing and dynamic ETA prediction.
- **Google Cloud Firestore**: Real-time vehicle document updates and append-only breadcrumb history (with graceful local in-memory fallback).
- **Traccar / OwnTracks / Python GPS Simulator**: Real phone GPS tracking or automated route simulator.
- **Interactive Dispatch Dashboard**: Live Leaflet map, geofenced deliveries, on-time KPI tiles, and AI exception center.

---

## 🚀 Quick Start (Running Locally)

### 1. Start the Flask Dispatch Server
From the project root:
```bash
./gdg/bin/python logistics/app.py
```
Or from inside the `logistics/` directory:
```bash
./run_server.sh
```
The server will start on **`http://localhost:8080`**.
Open your browser and navigate to: **[http://localhost:8080](http://localhost:8080)**

---

## 🎯 60-Second Hackathon Demo Script for Judges

1. **Order Intake with Gemini**:
   - In the dashboard, click **"Load Sample"** in the Gemini Order Intake card.
   - Notice the messy dispatch text (e.g. *"Deliver 2 emergency oncology kits to Apollo Hospital before 13:30, urgent..."*).
   - Click **"Parse with Gemini"**. The backend invokes Gemini to extract structured stops, addresses, deadlines, and priorities.
2. **Route Optimization**:
   - Click **"Optimize"** to sequence the stops using shortest-path TSP and compute planned arrival times.
   - The map plots the route polyline and numbered delivery stops in Chennai.
3. **Live GPS Tracking**:
   - In a second terminal window, run the driver simulator:
     ```bash
     # From root:
     ./gdg/bin/python logistics/simulate.py --url http://127.0.0.1:8080/location --speedup 4

     # Or from logistics folder:
     ./run_simulator.sh
     ```
   - Watch the blue delivery truck marker smoothly move along the route on the live map!
   - Telemetry speed, coordinates, and distance are updated in real time.
4. **Automated Geofencing**:
   - When the truck approaches within 60m of a stop, the stop badge changes to **DELIVERED** (green) and on-time statistics update automatically.
5. **AI Exception Handling & Customer Notification**:
   - If travel time causes an ETA to breach the customer's deadline, Gemini flags the incident.
   - An alert appears in the **Gemini AI Exception & Delay Dispatch** feed with an auto-drafted SMS/WhatsApp apology and revised ETA ready to be sent to the recipient!

---

## 📱 Driver Mobile App (2 Options)

### Option 1: Built-in Mobile Web App (Zero Install - Recommended)
1. On any smartphone or browser tab, open:
   ```
   http://<YOUR_IP>:8080/driver
   ```
   *(Or click "Driver App" in the top-right of the dashboard)*
2. Tap **"Start GPS"** to broadcast real phone geolocation directly to the dispatch map via `navigator.geolocation`.
3. The driver can view their active destination, address, dynamic ETA, and tap **"Mark Stop as Delivered"**.
4. Includes an indoor **"Drive Towards Next Stop"** button to simulate moving without walking outside.

### Option 2: Native Tracking App (Traccar Client)
1. Install **Traccar Client** (Free on Google Play Store or iOS App Store).
2. Set **Server URL** to:
   ```
   http://<YOUR_IP>:8080/location
   ```
3. Set **Device Identifier** to `phone-1` and toggle **Status** to ON.
4. The live map will track the phone in real time.

---

## 🔑 Optional API Keys Configuration

Copy `.env.example` to `.env`:
```bash
# Set your free Gemini API key from https://aistudio.google.com/
export GEMINI_API_KEY="AIzaSy..."

# Optional: Google Maps Routes API key
export GOOGLE_MAPS_API_KEY="AIzaSy..."

# Optional: Secret token for tracker auth
export TRACKER_TOKEN="my-secret"
```
*(Note: If no API keys are provided, the system seamlessly runs in demo fallback mode with built-in realistic mock intelligence, so your demo never fails!)*

---

## ☁️ Deploying to Google Cloud Run

From inside the `logistics/` directory:
```bash
gcloud run deploy logistics \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY="YOUR_KEY",TRACKER_TOKEN="my-secret"
```
