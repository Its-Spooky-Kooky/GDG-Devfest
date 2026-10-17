import os
import time
import math
import json
import logging
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__, static_folder="static", template_folder="templates")

# Configuration
TOKEN = os.environ.get("TRACKER_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

# Try initializing Firestore, fallback to In-Memory store if ADC not found
firestore_client = None
try:
    from google.cloud import firestore
    firestore_client = firestore.Client()
    logging.info("Connected to Google Cloud Firestore successfully.")
except Exception as e:
    logging.warning("Firestore not initialized (%s). Running in-memory cache mode for local demo.", e)

# In-Memory State Cache (used directly or as quick cache alongside Firestore)
STATE = {
    "vehicle": {
        "device": "sim-1",
        "lat": 13.0067,
        "lon": 80.2570,
        "speed_kmh": 0.0,
        "ts": time.time(),
        "source": "standby"
    },
    "stops": [
        {
            "id": "stop-1",
            "customer": "Apollo Specialty Pharmacy",
            "address": "Greams Road, Thousand Lights, Chennai",
            "lat": 13.0569,
            "lon": 80.2525,
            "items": "Urgent Oncology Medicine Box (2x)",
            "deadline": "13:30",
            "priority": "HIGH",
            "status": "PENDING",
            "eta": "13:18",
            "eta_breached": False
        },
        {
            "id": "stop-2",
            "customer": "Adyar Cancer Institute",
            "address": "Sardar Patel Road, Adyar, Chennai",
            "lat": 13.0067,
            "lon": 80.2570,
            "items": "Lab Test Reagents & Cool Pack",
            "deadline": "13:45",
            "priority": "HIGH",
            "status": "PENDING",
            "eta": "13:35",
            "eta_breached": False
        },
        {
            "id": "stop-3",
            "customer": "T. Nagar Retail Hub",
            "address": "Panagal Park, T. Nagar, Chennai",
            "lat": 13.0418,
            "lon": 80.2341,
            "items": "Retail Electronics Package",
            "deadline": "14:15",
            "priority": "NORMAL",
            "status": "PENDING",
            "eta": "14:02",
            "eta_breached": False
        },
        {
            "id": "stop-4",
            "customer": "Anna Nagar Logistics Depot",
            "address": "2nd Avenue, Anna Nagar, Chennai",
            "lat": 13.0850,
            "lon": 80.2101,
            "items": "Express Documents & Parcel",
            "deadline": "14:40",
            "priority": "NORMAL",
            "status": "PENDING",
            "eta": "14:28",
            "eta_breached": False
        }
    ],
    "route_polyline": "",
    "route_points": [
        [13.0067, 80.2570],
        [13.0067, 80.2206],
        [13.0418, 80.2341],
        [13.0569, 80.2425],
        [13.0850, 80.2101]
    ],
    "alerts": [],
    "history": []
}

# --- Gemini Helper Functions ---
def get_gemini_client():
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.error("Failed to initialize Google GenAI client: %s", e)
        return None


def parse_orders_with_gemini(raw_text: str):
    """Parses messy, unstructured order text into structured stop dictionaries."""
    client = get_gemini_client()
    if client:
        prompt = f"""You are a logistics dispatch assistant. Parse the following messy delivery dispatch requests into structured JSON.
Return ONLY valid JSON matching this array structure:
[
  {{
    "id": "stop-1",
    "customer": "Customer or Facility Name",
    "address": "Accurate street address or area (prefer Chennai locations if mentioned)",
    "lat": 13.0827,
    "lon": 80.2707,
    "items": "Items description",
    "deadline": "HH:MM",
    "priority": "HIGH or NORMAL or LOW"
  }}
]

Make sure coordinates (lat, lon) approximate real Chennai locations or the location mentioned.
Orders text:
{raw_text}
"""
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            for idx, stop in enumerate(data):
                stop["id"] = f"stop-{idx+1}"
                stop["status"] = "PENDING"
                stop["eta"] = "--:--"
                stop["eta_breached"] = False
            return data
        except Exception as e:
            logging.error("Gemini API call failed: %s. Using smart fallback parser.", e)

    # Smart Rule-Based Fallback when Gemini API key is not configured
    stops = []
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    coords_pool = [
        (13.0569, 80.2525, "Apollo Hospitals, Greams Rd"),
        (13.0067, 80.2570, "Adyar Cancer Institute, Sardar Patel Rd"),
        (13.0418, 80.2341, "Panagal Park, T. Nagar"),
        (13.0850, 80.2101, "Anna Nagar Roundtana"),
        (13.0827, 80.2707, "Chennai Central Station, Park Town")
    ]
    for idx, line in enumerate(lines):
        ref = coords_pool[idx % len(coords_pool)]
        deadline = "14:00"
        if "before" in line.lower():
            parts = line.lower().split("before")
            if len(parts) > 1:
                deadline = parts[1].strip().split()[0].replace("pm", "").replace("am", "")
                if ":" not in deadline:
                    try:
                        deadline = f"{int(deadline) + 12}:00" if int(deadline) < 12 else f"{deadline}:00"
                    except ValueError:
                        deadline = "14:30"
        stops.append({
            "id": f"stop-{idx+1}",
            "customer": f"Recipient #{idx+1}",
            "address": ref[2],
            "lat": ref[0],
            "lon": ref[1],
            "items": line[:40],
            "deadline": deadline,
            "priority": "HIGH" if "urgent" in line.lower() else "NORMAL",
            "status": "PENDING",
            "eta": "--:--",
            "eta_breached": False
        })
    return stops


def draft_delay_alert_with_gemini(stop, delay_mins, vehicle):
    """Uses Gemini to draft a professional, polite customer delay notification."""
    client = get_gemini_client()
    if client:
        prompt = f"""You are an automated logistics dispatch dispatcher.
A delivery vehicle is delayed due to urban traffic.
Stop Details:
- Customer: {stop.get('customer')}
- Address: {stop.get('address')}
- Items: {stop.get('items')}
- Original Deadline: {stop.get('deadline')}
- Calculated Delay: {delay_mins} minutes
- Revised ETA: {stop.get('eta')}

Draft a short, empathetic, professional SMS / WhatsApp notification to the recipient explaining the delay, providing the revised ETA, and giving reassurance. Max 2-3 sentences.
"""
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            logging.error("Gemini exception generation failed: %s", e)

    return (f"Dear {stop.get('customer')}, your delivery of '{stop.get('items')}' is experiencing "
            f"an unavoidable traffic delay of approx {delay_mins} mins. Revised ETA is {stop.get('eta')}. "
            f"Our dispatch vehicle ({vehicle.get('device')}) is en route.")


# --- Geometry & Routing Helpers ---
def haversine(a, b):
    """Computes distance in meters between two lat/lon pairs."""
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def optimize_stops_order(origin, stops):
    """Optimizes stop sequence to minimize total travel time."""
    if not stops:
        return []
    
    # If Google Maps API key is available, call Google Routes API
    if GOOGLE_MAPS_API_KEY and len(stops) > 1:
        try:
            url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
                "X-Goog-FieldMask": "routes.optimizedIntermediateWaypointIndex,routes.polyline.encodedPolyline"
            }
            body = {
                "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
                "destination": {"location": {"latLng": {"latitude": stops[-1]["lat"], "longitude": stops[-1]["lon"]}}},
                "intermediates": [{"location": {"latLng": {"latitude": s["lat"], "longitude": s["lon"]}}} for s in stops[:-1]],
                "travelMode": "DRIVE",
                "optimizeWaypointOrder": True
            }
            res = requests.post(url, json=body, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if "routes" in data and len(data["routes"]) > 0:
                    route = data["routes"][0]
                    order = route.get("optimizedIntermediateWaypointIndex", list(range(len(stops) - 1)))
                    reordered = [stops[i] for i in order] + [stops[-1]]
                    return reordered
        except Exception as e:
            logging.warning("Google Routes API call failed (%s). Using Nearest Neighbor algorithm.", e)

    # Nearest Neighbor TSP Heuristic Fallback
    unvisited = list(stops)
    current_pos = origin
    ordered = []
    while unvisited:
        nearest = min(unvisited, key=lambda s: haversine(current_pos, (s["lat"], s["lon"])))
        ordered.append(nearest)
        current_pos = (nearest["lat"], nearest["lon"])
        unvisited.remove(nearest)
    return ordered


# --- Location Parsing from Existing Code ---
def to_epoch(v):
    """Accept unix seconds, unix millis, or ISO-8601 string."""
    if v is None:
        return time.time()
    try:
        f = float(v)
        return f / 1000 if f > 1e11 else f
    except (TypeError, ValueError):
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(
            tzinfo=timezone.utc).timestamp() if "+" not in s else datetime.fromisoformat(s).timestamp()


def parse_payload(req):
    """Normalise Traccar (OsmAnd params), OwnTracks (JSON) and simulator (JSON) to one shape.
    Speed is stored in km/h."""
    data = req.get_json(silent=True) if req.is_json else None

    if data:
        if data.get("_type") == "location":  # OwnTracks
            return dict(device=str(data.get("tid") or "owntracks"),
                        lat=float(data["lat"]), lon=float(data["lon"]),
                        ts=to_epoch(data.get("tst")),
                        speed_kmh=float(data.get("vel") or 0),
                        accuracy=data.get("acc"), source="owntracks")
        if "_type" in data:
            return None
        if "lat" in data and "lon" in data:  # simulator
            return dict(device=str(data.get("id", "sim-1")),
                        lat=float(data["lat"]), lon=float(data["lon"]),
                        ts=to_epoch(data.get("timestamp")),
                        speed_kmh=float(data.get("speed") or 0),
                        accuracy=data.get("accuracy"), source="simulator")
        return None

    a = req.values  # Traccar Client: query string or form fields
    if "lat" in a and "lon" in a:
        return dict(device=str(a.get("id", "traccar")),
                    lat=float(a["lat"]), lon=float(a["lon"]),
                    ts=to_epoch(a.get("timestamp")),
                    speed_kmh=float(a.get("speed") or 0) * 1.852,
                    accuracy=a.get("accuracy"), source="traccar")
    return None


def update_etas_and_check_exceptions(vehicle):
    """Recalculates ETA for remaining stops and flags deadlines that will be breached."""
    now = datetime.now()
    cur_pos = (vehicle["lat"], vehicle["lon"])
    avg_speed_mps = max(5.0, (vehicle.get("speed_kmh", 30) / 3.6))  # minimum 18 km/h estimate
    cum_travel_sec = 0

    for stop in STATE["stops"]:
        stop_pos = (stop["lat"], stop["lon"])
        dist_to_stop = haversine(cur_pos, stop_pos)

        # Mark as delivered if vehicle is within 60 meters
        if dist_to_stop < 60 and stop["status"] != "DELIVERED":
            stop["status"] = "DELIVERED"
            stop["delivered_at"] = now.strftime("%H:%M:%S")
            logging.info("Stop %s marked as DELIVERED!", stop["id"])
            continue

        if stop["status"] == "DELIVERED":
            continue

        # Add transit time + 4 mins per stop dwell time
        leg_time_sec = (dist_to_stop / avg_speed_mps) + 240
        cum_travel_sec += leg_time_sec
        est_arrival = now + timedelta(seconds=cum_travel_sec)
        stop["eta"] = est_arrival.strftime("%H:%M")

        # Compare with deadline
        try:
            d_parts = stop["deadline"].split(":")
            deadline_dt = now.replace(hour=int(d_parts[0]), minute=int(d_parts[1]), second=0)
            if est_arrival > deadline_dt:
                delay_mins = int((est_arrival - deadline_dt).total_seconds() / 60)
                if not stop.get("eta_breached"):
                    stop["eta_breached"] = True
                    stop["status"] = "DELAYED"
                    logging.warning("AI EXCEPTION: Stop %s will breach deadline by %d min!", stop["id"], delay_mins)
                    drafted_msg = draft_delay_alert_with_gemini(stop, delay_mins, vehicle)
                    alert_record = {
                        "id": f"alert-{int(time.time())}-{stop['id']}",
                        "timestamp": now.strftime("%H:%M:%S"),
                        "stop_id": stop["id"],
                        "customer": stop["customer"],
                        "delay_mins": delay_mins,
                        "revised_eta": stop["eta"],
                        "drafted_notification": drafted_msg
                    }
                    STATE["alerts"].insert(0, alert_record)
        except Exception as ex:
            logging.debug("Could not parse deadline %s: %s", stop.get("deadline"), ex)


# --- HTTP Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/location", methods=["GET", "POST"])
def location():
    """Receives location pings from Traccar, OwnTracks, or simulate.py."""
    if TOKEN and request.args.get("token") != TOKEN:
        return jsonify(error="unauthorized"), 401
    try:
        p = parse_payload(request)
    except (KeyError, ValueError) as e:
        return jsonify(error=f"bad payload: {e}"), 400
    if p is None:
        return jsonify([]), 200

    # Update in-memory state
    STATE["vehicle"].update(p)
    STATE["history"].append({"lat": p["lat"], "lon": p["lon"], "ts": p["ts"]})
    if len(STATE["history"]) > 200:
        STATE["history"].pop(0)

    # Recalculate dynamic ETAs and trigger Gemini exception handling
    update_etas_and_check_exceptions(STATE["vehicle"])

    # If Firestore is active, save to cloud
    if firestore_client:
        try:
            doc = {**p, "updated": firestore.SERVER_TIMESTAMP}
            vehicle_ref = firestore_client.collection("vehicles").document(p["device"])
            vehicle_ref.set(doc)
            vehicle_ref.collection("track").add(doc)
        except Exception as e:
            logging.error("Firestore write failed: %s", e)

    return jsonify({"status": "ok", "device": p["device"]}), 200


@app.route("/vehicles/<device>")
def vehicle(device):
    if firestore_client:
        try:
            snap = firestore_client.collection("vehicles").document(device).get()
            if snap.exists:
                d = snap.to_dict()
                d.pop("updated", None)
                return jsonify(d)
        except Exception as e:
            logging.error("Firestore read error: %s", e)

    if STATE["vehicle"].get("device") == device or device == "default":
        return jsonify(STATE["vehicle"])
    return jsonify(error="not found"), 404


@app.route("/api/state")
def get_state():
    """Returns complete state: vehicle, stops, route, alerts, and stats for the frontend dashboard."""
    total_stops = len(STATE["stops"])
    delivered_stops = sum(1 for s in STATE["stops"] if s.get("status") == "DELIVERED")
    breached_stops = sum(1 for s in STATE["stops"] if s.get("eta_breached"))
    on_time_pct = int(((total_stops - breached_stops) / total_stops * 100)) if total_stops > 0 else 100

    return jsonify({
        "vehicle": STATE["vehicle"],
        "stops": STATE["stops"],
        "route_points": STATE["route_points"],
        "alerts": STATE["alerts"],
        "stats": {
            "total_stops": total_stops,
            "delivered_stops": delivered_stops,
            "delayed_stops": breached_stops,
            "on_time_pct": on_time_pct
        },
        "flags": {
            "gemini_active": bool(GEMINI_API_KEY),
            "google_maps_active": bool(GOOGLE_MAPS_API_KEY),
            "firestore_active": bool(firestore_client)
        }
    })


@app.route("/api/route")
def get_route():
    """Returns the ordered route waypoints for simulate.py."""
    points = [[STATE["vehicle"]["lat"], STATE["vehicle"]["lon"]]]
    for s in STATE["stops"]:
        if s.get("status") != "DELIVERED":
            points.append([s["lat"], s["lon"]])
    return jsonify({"points": points, "stops": STATE["stops"]})


@app.route("/api/orders/intake", methods=["POST"])
def orders_intake():
    """Gemini-powered order intake: extracts structured deliveries from raw text."""
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text", "")
    if not text.strip():
        return jsonify(error="Text is empty"), 400

    parsed_stops = parse_orders_with_gemini(text)
    if parsed_stops:
        origin = (STATE["vehicle"]["lat"], STATE["vehicle"]["lon"])
        optimized = optimize_stops_order(origin, parsed_stops)
        STATE["stops"] = optimized
        # Re-derive route polyline points
        STATE["route_points"] = [origin] + [[s["lat"], s["lon"]] for s in optimized]
        STATE["alerts"] = []
        update_etas_and_check_exceptions(STATE["vehicle"])
        return jsonify({"status": "success", "count": len(optimized), "stops": optimized})
    return jsonify(error="Could not parse orders"), 422


@app.route("/api/route/optimize", methods=["POST"])
def route_optimize():
    """Re-optimizes stops order and recomputes route path."""
    origin = (STATE["vehicle"]["lat"], STATE["vehicle"]["lon"])
    pending = [s for s in STATE["stops"] if s.get("status") != "DELIVERED"]
    delivered = [s for s in STATE["stops"] if s.get("status") == "DELIVERED"]
    ordered = optimize_stops_order(origin, pending)
    STATE["stops"] = delivered + ordered
    STATE["route_points"] = [origin] + [[s["lat"], s["lon"]] for s in ordered]
    update_etas_and_check_exceptions(STATE["vehicle"])
    return jsonify({"status": "optimized", "stops": STATE["stops"]})


@app.route("/driver")
def driver():
    """Mobile Web App for Delivery Drivers."""
    return render_template("driver.html")


@app.route("/api/stop/deliver", methods=["POST"])
def manual_deliver():
    """Allows driver app to manually mark a stop as delivered."""
    body = request.get_json(force=True, silent=True) or {}
    stop_id = body.get("stop_id")
    for s in STATE["stops"]:
        if not stop_id or s["id"] == stop_id:
            if s["status"] != "DELIVERED":
                s["status"] = "DELIVERED"
                s["delivered_at"] = datetime.now().strftime("%H:%M:%S")
                update_etas_and_check_exceptions(STATE["vehicle"])
                return jsonify({"status": "delivered", "stop": s})
    return jsonify(error="No pending stop found"), 404


@app.route("/api/reset", methods=["POST"])
def reset_state():
    """Resets simulator and stops to starting demo state."""
    STATE["vehicle"]["lat"] = 13.0067
    STATE["vehicle"]["lon"] = 80.2570
    STATE["vehicle"]["speed_kmh"] = 0.0
    STATE["history"] = []
    STATE["alerts"] = []
    for s in STATE["stops"]:
        s["status"] = "PENDING"
        s["eta_breached"] = False
        s.pop("delivered_at", None)
    update_etas_and_check_exceptions(STATE["vehicle"])
    return jsonify({"status": "reset_complete"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logging.info("Starting Logistics Handler server on port %d...", port)
    app.run(host="0.0.0.0", port=port, debug=False)

