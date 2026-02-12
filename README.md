# Autonomous-Drone-Delivery-System
> **An autonomous drone delivery simulation powered by Python, ArduPilot, and OpenAI.**
>
> ## 🌟 Key Features

* **📲 Telegram Command Center:** Control the drone using a chat interface through GPS coordinates (`28.37, 77.54`).
* **🧠 AI Co-Pilot (OpenAI):** Performs real-time risk assessment before flight, analyzing weather, battery, and distance to issue a "Go/No-Go" verdict.
* **📦 Multi-Stop Delivery:** Optimized route planning using a Nearest Neighbor algorithm to visit multiple delivery points efficiently.
* **👀 Computer Vision (QR Code):** Simulates a "Scan & Verify" mechanism. The drone descends to 3m to read a QR code from the user's phone before releasing the payload.
* **🌦️ Real-Time Weather Safety:** Integration with OpenWeatherMap to automatically ground the drone during rain or high winds (>10m/s).
* **🔋 Physics-Based Battery Simulation:** Real-time battery drain monitoring based on distance traveled, with emergency "Return-to-Launch" (RTL) failsafes.

* ## ⚙️ Prerequisites

Before running the project, ensure you have the following installed:

* **Python 3.10+**
* **Mission Planner** (for visualizing the drone in 3D space)
* **ArduPilot SITL** (Software In The Loop simulator) - *Usually comes with Mission Planner*
* **Git** (for version control)

**Install Python Dependencies**
Run the following command to install all required libraries:
````bash pip install dronekit pymavlink opencv-python pyTelegramBotAPI openai requests````

**🤖 Creating the Telegram Bot**
1. Open Telegram and search for @BotFather.
2. Send the command /newbot.
3. Follow the prompts to name your bot (e.g., SkyLink_Drone_Bot).
4. Copy the HTTP API Token provided by BotFather. You will need this for the code.

**🔑 API Configuration**
You need three API keys for the system to function fully.

1. OpenAI API Key: For natural language processing and risk assessment.
2. OpenWeatherMap API Key: For live weather safety checks.
3. Telegram Bot Token: Obtained in the previous step.

**🚁 Running the Simulation**

Step 1: Start the SITL Simulator : Use Mission Planner's Simulation tab. Run the simulator for a Quadcopter.
Step 2: Launch the Python Controller
Open a new terminal window in your project folder and run: ````python drone_control.py````

**📱 How to Use (Demo Flow)**
1. Open Telegram: Start a chat with your bot.

2. Send a Location: (Coordinates): 28.3668, 77.5411

3. The bot checks the Weather and calculates Battery Risk. If safe, the drone takes off in the simulator.

4. Pickup & Scan: The drone flies to the pickup point and descends.

5. Action Required: Show a QR code to your webcam! **QR Format: 28.370,77.540,20; 28.375,77.542,20 (Lat, Lon, Alt separated by semicolon).**

6. Delivery: The drone optimizes the path, flies to each point, descends to 10m, hovers to simulate drop-off, and finally returns home.

**🛡️ Safety Protocols (Built-in)**
1. Emergency Stop: Type STOP in Telegram at any time to instantly abort the mission and force the drone to Return to Launch (RTL).

2. Geofence: Rejects missions if the target is >1km away.

3. Low Battery: Auto-lands if battery <5% or RTL if <10%.
