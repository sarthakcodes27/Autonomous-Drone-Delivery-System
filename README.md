# Autonomous Drone Delivery System 

This project implements an autonomous drone delivery workflow using ArduPilot (SITL), Computer Vision, and Telegram.

## Features
- **Telegram Integration:** Users send GPS coordinates via a Telegram Bot.
- **Autonomous Navigation:** Drone flies to the pickup location autonomously.
- **Computer Vision:** Detects QR codes via onboard camera to receive mission updates.
- **Smart Delivery:** Executes a specific flight path based on QR data and returns to base.

## Tech Stack
- **Flight Controller:** ArduPilot (SITL)
- **Communication:** MAVLink Protocol via `dronekit`
- **Vision:** OpenCV (`cv2`) for QR scanning
- **Interface:** Telegram Bot API

## How to Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
2. Start ArduPilot SITL (Mission Planner).
3. Update the TELEGRAM_TOKEN in drone_control.py.

4. Run the script:
    ```bash
    python drone_control.py
