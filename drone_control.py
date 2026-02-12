# --- BATTERY CONFIGURATION ---
BATTERY_LEVEL = 100.0       # Starts at 100%
BATTERY_DRAIN_RATE = 0.05   # Drains 0.05% per meter
last_battery_pos = None     # Drone's position from the previous check

import collections.abc

if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping

from openai import OpenAI
import re
import time
import cv2
import telebot
import requests
from dronekit import connect, VehicleMode, Command, LocationGlobalRelative
from pymavlink import mavutil

# --- CONFIGURATION ---
TELEGRAM_TOKEN = '' # <--- PASTE TELEGRAM BOT API
OWM_API_KEY = "" # <--- PASTE WEATHER API KEY HERE 
client = OpenAI(api_key = "") # <--- PASTE YOUR KEY HERE
CONNECTION_STRING = 'tcp:127.0.0.1:5762' 


# Initialize Bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)
vehicle = None # Global vehicle variable

def connect_drone():
    global vehicle
    print(f"Connecting to drone on {CONNECTION_STRING}...")
    vehicle = connect(CONNECTION_STRING, wait_ready=True)
    print("Drone Connected! Waiting for Telegram Command...")

# --- FLIGHT FUNCTIONS ---
def ai_risk_assessment(weather_summary, battery_level, distance_meters):
    """
    Sends flight data to OpenAI (Updated for Library v1.0+)
    """
    print("🤖 Contacting AI Co-Pilot for Risk Assessment...")
    try:
        # 1. Scenario
        prompt = f"""
        You are a Drone Safety Officer. Analyze the following flight conditions:
        - Weather: {weather_summary}
        - Battery Level: {battery_level}%
        - Pickup Distance: {distance_meters} meters
        
        Rules:
        - Battery drains approx 1% every 20m.
        - Winds over 10m/s are dangerous.
        - Rain is prohibited.
        - If battery is too low for the round trip, reject.
        
        Task:
        Decide if the mission is SAFE or UNSAFE.
        Return your answer in this format EXACTLY:
        "VERDICT: [SAFE/UNSAFE] | REASON: [Short explanation]"
        """
        
        # 2. Ask
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60, 
            temperature=0.2
        )
        
        # 3. Response
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"AI Error: {e}") 
        return "VERDICT: SAFE | REASON: AI Offline (Defaulting to manual protocol)"

def monitor_battery():
    """
    Calculates distance traveled, drains battery, updates terminal HUD,
    and enforces emergency landing if critical.
    """
    global BATTERY_LEVEL, last_battery_pos
    
    # 1. Get Current Location
    current_loc = vehicle.location.global_relative_frame
    
    # Initialize if this is the first check
    if last_battery_pos is None:
        last_battery_pos = current_loc
        return

    # 2. Calculate Distance Traveled since last check
    
    d_lat = (current_loc.lat - last_battery_pos.lat) * 1.113195e5
    d_lon = (current_loc.lon - last_battery_pos.lon) * 1.113195e5
    dist_traveled = (d_lat**2 + d_lon**2) ** 0.5
    
    # 3. Drain Battery
    
    if dist_traveled > 0.1:
        drain_amount = dist_traveled * BATTERY_DRAIN_RATE
        BATTERY_LEVEL -= drain_amount
        
        # Update last known position
        last_battery_pos = current_loc

    # 4. Terminal HUD (Live Output)
    color = "\033[92m" if BATTERY_LEVEL > 50 else "\033[93m" if BATTERY_LEVEL > 20 else "\033[91m"
    reset = "\033[0m"
    print(f"\r{color}🔋 BATT: {BATTERY_LEVEL:.1f}%{reset} | 📏 Last Move: {dist_traveled:.1f}m | ⚠️ System: ONLINE", end="")

    # 5. CRITICAL FAILSAFE
    if BATTERY_LEVEL <= 0:
        print("\n\n❌ BATTERY DEPLETED. SYSTEM FAILURE.")
        vehicle.mode = VehicleMode("LAND")
        
        
    elif BATTERY_LEVEL < 10 and vehicle.mode.name != "RTL":
        print("\n\n⚠️ CRITICAL BATTERY (<10%). FORCING RTL.")
        vehicle.mode = VehicleMode("RTL")

def fly_to_pickup(lat, lon):
    print(f"Received Order. Flying to Pickup Point: {lat}, {lon}")
    
    # 1. Pre-Arm
    while not vehicle.is_armable:
        print("Waiting for drone to initialize...")
        time.sleep(1)
        
    # 2. Takeoff
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.armed = True
    while not vehicle.armed:
        time.sleep(1)
    
    print("Taking Off...")
    vehicle.simple_takeoff(15) # Fly at 15m height
    
    while True:
        if vehicle.location.global_relative_frame.alt >= 14:
            break
        time.sleep(1)

    # 3. Go to Pickup Location
    point = LocationGlobalRelative(lat, lon, 15)
    vehicle.simple_goto(point)
    
    print("En route to Pickup Point...")
    
    # Simple distance check loop
    while True:
        monitor_battery()
        # Calculate distance to target
        current_lat = vehicle.location.global_relative_frame.lat
        current_lon = vehicle.location.global_relative_frame.lon
        dist_lat = (current_lat - lat) * 1.113195e5
        dist_lon = (current_lon - lon) * 1.113195e5
        dist = (dist_lat**2 + dist_lon**2) ** 0.5
        
        print(f"Distance to Pickup: {int(dist)}m")
        if dist < 2: # Within 2 meters
            print("ARRIVED AT PICKUP POINT.")
            break
        time.sleep(2)

def scan_qr_webcam():
    print("Initiating Cargo Scan (Opening Camera)...")
    cap = cv2.VideoCapture(0)
    detector = cv2.QRCodeDetector()
    qr_data = None

    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        data, bbox, _ = detector.detectAndDecode(frame)
        
        if bbox is not None:
            # Draw box
            points = bbox.astype(int)
            n = len(points)
            for i in range(n):
                cv2.line(frame, tuple(points[i][0]), tuple(points[(i+1) % n][0]), (0,255,0), 3)

        if data:
            print(f"QR MISSION RECEIVED: {data}")
            qr_data = data
            cv2.rectangle(frame, (0,0), (frame.shape[1], frame.shape[0]), (0,255,0), 10)
            cv2.imshow("Drone Camera", frame)
            cv2.waitKey(1000)
            break
            
        cv2.imshow("Drone Camera", frame)
        if cv2.waitKey(1) == ord('q'): break
    
    cap.release()
    cv2.destroyAllWindows()
    return qr_data

def execute_qr_mission(data, chat_id):
    print("--- STARTING OPTIMIZED MISSION ---")
    
    
    if data:
        data = re.sub(r'[^0-9,;.-]', '', data)

    if not data: 
        bot.send_message(chat_id, "❌ QR Scan Failed.")
        return

    waypoints = []
    try:
        stops = data.split(';')
        for stop in stops:
            parts = stop.split(',')
            if len(parts) >= 3:
                waypoints.append((float(parts[0]), float(parts[1]), float(parts[2])))
    except Exception as e:
        bot.send_message(chat_id, "❌ Invalid QR Format.")
        return

    # SAFETY CHECK (1km Rule)
    start_lat = vehicle.location.global_relative_frame.lat
    start_lon = vehicle.location.global_relative_frame.lon
    
    
    def get_dist(lat1, lon1, lat2, lon2):
        d_lat = (lat2 - lat1) * 1.113195e5
        d_lon = (lon2 - lon1) * 1.113195e5
        return (d_lat**2 + d_lon**2) ** 0.5

    for i, (lat, lon, alt) in enumerate(waypoints):
        dist = get_dist(start_lat, start_lon, lat, lon)
        if dist > 1000:
            bot.send_message(chat_id, f"❌ Mission REJECTED. Stop #{i+1} is too far ({int(dist)}m).")
            return

    # ROUTE OPTIMIZATION
    print("Optimizing Route for Shortest Path...")
    optimized_waypoints = []
    
    # Start checking from current drone location
    current_sim_lat = start_lat
    current_sim_lon = start_lon
    
    # While there are still stops left to visit...
    while len(waypoints) > 0:
        # Find the closest stop to our current simulated position
        closest_stop = None
        min_dist = 99999999.0
        
        for stop in waypoints:
            lat, lon, alt = stop
            dist = get_dist(current_sim_lat, current_sim_lon, lat, lon)
            if dist < min_dist:
                min_dist = dist
                closest_stop = stop
        
        
        optimized_waypoints.append(closest_stop)
        waypoints.remove(closest_stop)
        
        current_sim_lat = closest_stop[0]
        current_sim_lon = closest_stop[1]
        
    print(f"Route Re-ordered. Stops: {len(optimized_waypoints)}")

    # EXECUTION LOOP
    bot.send_message(chat_id, f"✅ Mission Accepted. Optimized Path for {len(optimized_waypoints)} stops.")
    vehicle.mode = VehicleMode("GUIDED")
    
    for i, (lat, lon, alt) in enumerate(optimized_waypoints):
        stop_num = i + 1
        total_stops = len(optimized_waypoints)
        
        # A. FLY TO TARGET
        print(f"--> Flying to Stop {stop_num}/{total_stops}: {lat}, {lon}")
        bot.send_message(chat_id, f"✈️ En route to Stop {stop_num}...")
        
        target_loc = LocationGlobalRelative(lat, lon, 20)
        vehicle.simple_goto(target_loc)
        
        while True:
            monitor_battery()

            # --- EMERGENCY CHECK ---
            if stop_flag: 
                print("Stopping Flight Loop due to Emergency.")
                return # Exits the function immediately

            curr_lat = vehicle.location.global_relative_frame.lat
            curr_lon = vehicle.location.global_relative_frame.lon
            dist = get_dist(curr_lat, curr_lon, lat, lon)
            
            if dist < 2: 
                break
            time.sleep(1)
            
        # B. DESCEND
        print(f"Arrived at Stop {stop_num}. Descending...")
        descent_loc = LocationGlobalRelative(lat, lon, 10)
        vehicle.simple_goto(descent_loc)
        while vehicle.location.global_relative_frame.alt > 11:
            time.sleep(1)
            
        # C. HOVER
        print("Hovering 15s...")
        time.sleep(15)
        
        # D. CLIMB
        print("Climbing...")
        climb_loc = LocationGlobalRelative(lat, lon, 20)
        vehicle.simple_goto(climb_loc)
        while vehicle.location.global_relative_frame.alt < 19:
            time.sleep(1)

    # --- 5. RETURN HOME ---
    bot.send_message(chat_id, "✅ Deliveries Done. Returning Home.")
    vehicle.mode = VehicleMode("RTL")

    while vehicle.location.global_relative_frame.alt > 1:
        monitor_battery()
        
        time.sleep(2)
        if not vehicle.armed:
            break
            
    print("Drone Landed. System Ready.")

# --- TELEGRAM HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Drone System Online.\nSend coordinates as: 'LAT,LON'\nExample: -35.362, 149.164")

def check_weather_safety(lat, lon):
    """
    Returns (True, Summary) if safe, or (False, Warning) if unsafe.
    """
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OWM_API_KEY}&units=metric"
        response = requests.get(url).json()
        
        if response.get("cod") != 200:
            return False, "⚠️ Weather API Error. Cannot verify safety."

        # 1. Parse Data
        condition = response['weather'][0]['main'] # e.g., "Rain", "Clear", "Clouds"
        description = response['weather'][0]['description'] # e.g., "light rain"
        wind_speed = response['wind']['speed'] # meters per second
        temp = response['main']['temp']
        
        summary = f"{condition} ({description}), {temp}°C, Wind: {wind_speed} m/s"
        
        # 2. Safety Rules
        # Rule A: No Rain/Snow/Storms
        unsafe_conditions = ["Rain", "Thunderstorm", "Drizzle", "Snow", "Tornado", "Squall"]
        if condition in unsafe_conditions:
            return False, f"⛔ Unsafe Condition: {condition} detected. ({summary})"
            
        # Rule B: Wind Limit (e.g., max 10 m/s)
        if wind_speed > 10:
            return False, f"⛔ High Wind Alert: {wind_speed} m/s. Limit is 10 m/s."

        # Rule C: All Good (Clear, Clouds, Mist, Haze are okay)
        return True, f"✅ Weather Safe: {summary}"

    except Exception as e:
        print(f"Weather Check Failed: {e}")
        return True, "⚠️ Weather Check Failed (Offline?). Proceeding with caution."

# --- GLOBAL SAFETY FLAG ---
stop_flag = False

@bot.message_handler(func=lambda message: message.text.lower() == "stop")
def emergency_stop(message):
    global stop_flag
    stop_flag = True #<--- FLIPS THE SWITCH
    
    print("!!! EMERGENCY STOP TRIGGERED !!!")
    bot.reply_to(message, "🚨 EMERGENCY STOP RECEIVED! Aborting Mission & Returning to Launch (RTL).")
    
    # Force RTL Immediately
    vehicle.mode = VehicleMode("RTL")

@bot.message_handler(func=lambda message: True)
@bot.message_handler(func=lambda message: True)
def handle_coordinates(message):
    global stop_flag, BATTERY_LEVEL # <--- Access Global Battery
    stop_flag = False 
    
    try:
        # 1. Parse Coordinates
        text = message.text.replace(" ", "")
        lat_str, lon_str = text.split(',')
        lat = float(lat_str)
        lon = float(lon_str)
        
        bot.reply_to(message, "🌤️ Checking weather...")
        
        # 2. Get Weather Data
        is_weather_safe, weather_msg = check_weather_safety(lat, lon)
        bot.send_message(message.chat.id, weather_msg)
        
        if not is_weather_safe:
            bot.send_message(message.chat.id, "❌ Mission Rejected due to Weather.")
            return 

        # 3. AI RISK ASSESSMENT
        bot.send_message(message.chat.id, "🤖 AI Co-Pilot is analyzing flight risks...")
        
        # Calculate distance to pickup (for the AI)
        curr_loc = vehicle.location.global_relative_frame
        d_lat = (lat - curr_loc.lat) * 1.113195e5
        d_lon = (lon - curr_loc.lon) * 1.113195e5
        dist_to_pickup = int((d_lat**2 + d_lon**2) ** 0.5)
        
        # CALL THE AI
        risk_report = ai_risk_assessment(weather_msg, BATTERY_LEVEL, dist_to_pickup)
        
        # Send AI Verdict to Telegram
        bot.send_message(message.chat.id, risk_report)
        print(f"\nAI REPORT: {risk_report}\n")
        
        # AI Decision Gate
        if "UNSAFE" in risk_report.upper():
            bot.send_message(message.chat.id, "⛔ Mission ABORTED by AI Safety Officer.")
            return # <--- STOPS FLIGHT HERE
            
        bot.send_message(message.chat.id, "✅ AI Clearance Received. Dispatching Drone...")

        # 4. Fly to Pickup (With Battery Monitor active in background)
        fly_to_pickup(lat, lon)
        if stop_flag: return 

        # 5. Descend & Scan
        bot.send_message(message.chat.id, "⬇️ Arrived. Descending to 3m...")
        
        current_lat = vehicle.location.global_relative_frame.lat
        current_lon = vehicle.location.global_relative_frame.lon
        
        vehicle.simple_goto(LocationGlobalRelative(current_lat, current_lon, 3))
        
        while vehicle.location.global_relative_frame.alt > 4:
            if stop_flag: return
            monitor_battery() # Ensure battery is monitored during hover
            time.sleep(1)
            
        bot.send_message(message.chat.id, "📷 Ready. Show QR.")
        qr_data = scan_qr_webcam()
        if stop_flag: return
        
        # 6. Climb
        bot.send_message(message.chat.id, "✅ climbing to 20m...")
        vehicle.simple_goto(LocationGlobalRelative(current_lat, current_lon, 20))
        while vehicle.location.global_relative_frame.alt < 19:
            if stop_flag: return
            monitor_battery()
            time.sleep(1)
            
        # 7. Execute Mission
        execute_qr_mission(qr_data, message.chat.id)
        
    except Exception as e:
        bot.reply_to(message, f"Error: Invalid Format or System Fail.\nDebug: {e}")

# --- MAIN ---
if __name__ == "__main__":
    connect_drone()
    print("Bot is polling... Send a message on Telegram!")
    bot.polling()