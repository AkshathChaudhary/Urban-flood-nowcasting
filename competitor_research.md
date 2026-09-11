# SIH26085: Urban Flood Nowcasting - Competitive Landscape Analysis

This document provides a deep dive into the current market of urban flood prediction and routing systems to help build a strong case for your SIH presentation.

## The State of the Market (2024-2025)

The industry is currently transitioning from **reactive, macro-level weather alerts** to **proactive, hyperlocal digital twins**. However, a significant gap remains: bridging the physics of urban drainage with consumer-level dynamic routing. 

Here is a breakdown of the existing solutions, categorized by their primary function.

---

### Category 1: Global Tech Giants (The "Macro" Forecasters)

**1. Google Flood Hub**
*   **What it does:** Uses AI (Hydrologic + Inundation models) to forecast floods up to 7 days (riverine) and 24 hours (urban) in advance across 150+ countries. 
*   **How it routes:** Google Maps relies heavily on *crowdsourced* reports (users tapping "Road Flooded"). It does not currently use real-time depth physics to preemptively close road segments for routing.
*   **The Gap:** It provides high-level warnings but lacks the granular, street-by-street hydraulic drainage simulation required to tell a driver if their specific sedan will clear a specific underpass in 30 minutes.

**2. Waze (Google) & FloodMapp Pilot**
*   **What it does:** FloodMapp (an Australian AI flood mapping company) partnered with Waze for a pilot in Norfolk, Virginia. FloodMapp's "NowCast" generates real-time inundation maps, which are piped into Waze to automatically close roads and reroute drivers.
*   **The Gap:** This is our **closest direct competitor**. However, it is an enterprise integration pilot, not a universal standard. FloodMapp relies heavily on its proprietary data models, leaving a massive gap for an open-source, scalable Indian solution built on localized drainage physics.

---

### Category 2: Government & Academic Systems (The "Institutional" Monitors)

**3. I-FLOWS Mumbai (MoES / MCGM)**
*   **What it does:** The official integrated flood warning system for Mumbai. It uses weather models (IMD) to provide warnings 6 to 72 hours in advance and maps vulnerabilities across 24 wards.
*   **The Gap:** Heavily criticized for acting more as a "forecast delivery" tool than a real-time early warning system for flash floods. It is an institutional dashboard, entirely lacking consumer navigation or vehicle-specific routing features.

**4. mumbaiflood.in (IIT Bombay)**
*   **What it does:** An experimental, highly localized portal offering hourly forecasts, IoT sensor water-level tracking, and crowdsourced waterlogging reports (including local train updates).
*   **The Gap:** It is a monitoring and reporting dashboard. It tells you where the water is, but it does not run A* pathfinding algorithms to actively route you around it.

**5. FloodNet NYC**
*   **What it does:** A massive deployment of solar-powered ultrasonic sensors across New York City to monitor street-level flooding in real-time. 
*   **The Gap:** Purely a hardware/data-collection initiative. It provides an open-data dashboard but does not perform predictive routing. 

---

### Category 3: Enterprise & Utility Solutions (The "B2B" Platforms)

**6. Previsico (FloodMap Live)**
*   **What it does:** Uses hydrodynamic modeling and IoT sensors to provide 48-hour surface water (pluvial) flood forecasts. 
*   **Target Market:** Commercial insurance and property owners (alerting them to move assets or deploy flood gates).
*   **The Gap:** Not designed for traffic or navigation. 

**7. Idrica (GoAigua) / DHI (MIKE+) / StormSensor**
*   **What they do:** These are heavy-duty digital twin and 1D/2D hydraulic modeling platforms (like MIKE+) or IoT networks (StormSensor) used by city planners and water utilities to manage sewer overflows and pump stations.
*   **The Gap:** These are professional engineering tools. They calculate Manning's equation and pipe capacities beautifully, but their output is for engineers in a control room, not an API for a logistics company or a commuter.

**8. Tomorrow.io**
*   **What it does:** A weather intelligence platform offering a "Weather on Routes API" for logistics companies to avoid severe weather.
*   **The Gap:** Uses a "Flood Index" (1-5 risk level) rather than calculating exact water depths in centimeters based on street-level drainage capacities.

---

## The "Killer" Differentiation for Your Slide Deck

When the judges ask, *"Isn't Google Maps already doing this?"*, here is how you position your project (`urbanFlood/backend`):

**"Existing systems are fragmented. You either have Google Maps waiting for someone to get stuck in a flood to report it, or you have heavy engineering software (like MIKE+) sitting in a municipal control room. Our system bridges the two."**

**Our 3 Core USPs:**
1.  **Physics-Informed, Not Just Crowdsourced:** We aren't waiting for users to report a flood. By coupling Rainfall Nowcasting (`provider.py`) with Manning's Hydraulics (`drainage.py`), we *predict* the surcharge before the first car gets stuck.
2.  **Vehicle-Specific Clearance Logic:** A flood depth of 20cm means a truck can pass, but a hatchback will stall. Our `RoutingEngine` dynamically weights the A* graph based on the specific vehicle's clearance threshold—a feature entirely absent in standard navigation apps.
3.  **Closed-Loop Automation:** We take raw meteorological data, simulate the drainage failure, and output actionable, safe paths in a single automated pipeline.

---

## Suggested Narrative for the Presentation

*   **The Problem:** "In 2024, navigation apps still route drivers into flooded underpasses because they rely on reactive, crowdsourced data. Meanwhile, city engineers have predictive hydraulic models that never reach the public."
*   **The Solution:** "We built a predictive routing engine that calculates street-level water depths based on drainage physics, and dynamically severs network graph edges for vehicles that cannot clear the depth."
