# 🚚 SmartFleet AI • GDG DevFest

> **Autonomous Last-Mile Logistics Dispatch & Exception Management**  
> Built for the Google Developer Groups (GDG) DevFest Hackathon.

SmartFleet AI bridges the gap between urban last-mile delivery and autonomous exception handling. It combines **Google Gemini 2.5 Flash**, **dynamic route optimization**, and **real-time GPS telemetry** to convert unstructured delivery requests into optimized routes, monitor fleet movements in real-time, and proactively draft customer delay notifications before complaints occur.

---

## ✨ Key Capabilities

- 🤖 **Gemini Order Intake**: Ingests raw, unstructured delivery messages (from WhatsApp, SMS, or dispatch emails) and parses them into structured JSON delivery stops with deadlines and priorities.
- 🗺️ **Dynamic Route Sequencing & ETAs**: Calculates shortest-path TSP stop sequencing and computes dynamic per-leg arrival times (compatible with Google Routes API).
- 📍 **Live Telemetry & Geofencing**: Accepts GPS pings from smartphones (HTML5 Geolocation / Traccar Client) or the included automated Python simulator. Automatically marks stops as **DELIVERED** when the vehicle is within 60 meters.
- ⚠️ **Proactive AI Exception Alerts**: Automatically detects when urban traffic or delays breach a customer's delivery window, triggering Gemini to draft empathetic, professional delay notifications with revised ETAs in real time.
- 📱 **Integrated Driver Mobile App**: A dedicated zero-install mobile web console (`/driver`) allowing drivers to broadcast live GPS and mark deliveries with one tap.
- 🖥️ **Minimalist Dispatcher Dashboard**: Clean, light-themed web interface powered by Leaflet & OpenStreetMap (100% free, zero API key required).

---

## 🛠️ Architecture

```
[Raw Order Text]  ──>  [1. Gemini AI Intake]   ──> Structured Stops (Address, Deadline, Items)
                              │
[Optimized Waypoints] <──  [2. Routing Engine]    ──> Shortest Path TSP & Leg ETAs
                              │
[Phone GPS / Sim] ──>  [3. Live Telemetry]    ──> Auto-Geofence (<60m -> DELIVERED)
                              │
[Deadline Breached?] ──>  [4. Gemini Alert]     ──> Auto-Drafts Empathetic Customer SMS
                              │
                      [5. Dispatch Dashboard] (Live Map + Stop Sequence + KPI Cards)
```

---

## 🚀 Quick Start

### 1. Prerequisites & Environment Setup
Clone this repository and create a virtual environment:
```bash
git clone https://github.com/Its-Spooky-Kooky/GDG-Devfest.git
cd GDG-Devfest

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your free Gemini API key from [Google AI Studio](https://aistudio.google.com/):
```env
GEMINI_API_KEY="AIzaSy..."
```
*(Note: If no API key is provided, SmartFleet AI operates in demo mode with intelligent mock parsing and alerts so your presentation never fails!)*

### 3. Launch the Application
```bash
./run_server.sh
# Or manually: python app.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser.

---

## 📱 Mobile Driver App

Open **[http://localhost:8080/driver](http://localhost:8080/driver)** on any smartphone:
1. Tap **"Start GPS"** to broadcast real-time phone location to the dispatch map.
2. View current active destination and customer notes.
3. Tap **"Mark Stop as Delivered"** upon arrival.
4. For indoor demos, use **"Drive Towards Next Stop"** to simulate incremental movement.

---

## 🧪 Terminal Driver Simulator

To run an automated driver that simulates driving along the route:
```bash
./run_simulator.sh
# Or with custom speedup:
python simulate.py --url http://127.0.0.1:8080/location --speedup 4
```

---

## ☁️ Google Cloud Run Deployment

Deploy directly to Google Cloud serverless container infrastructure:
```bash
gcloud run deploy smartfleet-logistics \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY="YOUR_KEY"
```

---

## 📄 License
MIT License. Built for GDG DevFest Hackathon.
