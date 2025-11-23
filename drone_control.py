import collections.abc
# Monkey patch for Python 3.10+
if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping

import time
import cv2
import telebot # The new library
from dronekit import connect, VehicleMode, Command, LocationGlobalRelative
from pymavlink import mavutil

# --- CONFIGURATION ---
TELEGRAM_TOKEN = '8336184060:AAGfYSMaQzVrKjRjRVrp4FBjN_toBV252GI' # <--- PASTE TOKEN HERE
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

def fly_to_pickup(lat, lon):
    print(f"Received Order. Flying to Pickup Point: {lat}, {lon}")
    
    # 1. Check Pre-Arm
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
        # Calculate distance to target (basic Pythagorean approximation for simulation)
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

def execute_qr_mission(data):
    print("Uploading Final Mission...")
    cmds = vehicle.commands
    cmds.clear()
    
    # Parse QR data
    # Failsafe data if QR is empty
    if not data: 
        print("Scan failed. Using Backup Mission.")
        data = "-35.3610,149.1610,30;-35.3610,149.1650,30;-35.3650,149.1650,30;-35.3650,149.1610,30"

    waypoints = []
    try:
        points = data.split(';')
        for p in points:
            lat, lon, alt = map(float, p.split(','))
            waypoints.append((lat, lon, alt))
    except:
        print("Data error.")
        return

    # Add Waypoints
    for (lat, lon, alt) in waypoints:
        cmds.add(Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, 
                         mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, lat, lon, alt))

    # RTL
    cmds.add(Command(0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, 
                     mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    
    cmds.upload()
    
    print("Executing Final Mission via AUTO mode...")
    vehicle.mode = VehicleMode("AUTO")

# --- TELEGRAM HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Drone System Online.\nSend coordinates as: 'LAT,LON'\nExample: -35.362, 149.164")

@bot.message_handler(func=lambda message: True)
def handle_coordinates(message):
    try:
        # Parse "Lat, Lon" from message
        text = message.text.replace(" ", "")
        lat_str, lon_str = text.split(',')
        lat = float(lat_str)
        lon = float(lon_str)
        
        bot.reply_to(message, f"Coordinates received. Drone dispatching to {lat}, {lon}")
        
        # EXECUTE WORKFLOW
        fly_to_pickup(lat, lon)
        
        bot.send_message(message.chat.id, "Arrived at Pickup. Scanning QR Code...")
        qr_data = scan_qr_webcam()
        
        bot.send_message(message.chat.id, "QR Scanned. Executing Final Mission.")
        execute_qr_mission(qr_data)
        
    except Exception as e:
        bot.reply_to(message, f"Error: Invalid Format. Send 'LAT,LON'.\nDebug: {e}")

# --- MAIN ---
if __name__ == "__main__":
    connect_drone()
    print("Bot is polling... Send a message on Telegram!")
    bot.polling()