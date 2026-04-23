# Full Send Systems — iRacing Race Engineering Platform

> **B 1.10** · 8 Modules Live · Real-time voice coaching · IBT telemetry analysis · AI race engineer

![Version](https://img.shields.io/badge/version-B%201.10-c00202)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![iRacing](https://img.shields.io/badge/sim-iRacing%202026%20S2-orange)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What is Full Send Systems?

Full Send Systems is a professional-grade race engineering platform for iRacing. It combines deep IBT telemetry analysis with a real-time AI voice engineer that talks to you like a real crew chief — not a robot. Load your IBT files for post-session analysis, or connect live to iRacing for real-time coaching during a session.

**This is a single HTML file + a Python bridge script. No install required.**

---

## Quick Start

### Option A — Live coaching with iRacing (recommended)

1. Put `fss_b110_complete.html`, `fss_bridge.py` and `FSS_START.bat` in the **same folder**
2. **Double-click `FSS_START.bat`**
3. Chrome opens automatically at `http://localhost:6775`
4. Go to the **Live** tab → click **Connect**
5. Start iRacing — the engineer comes online automatically

### Option B — IBT file analysis (no iRacing needed)

1. Open `fss_b110_complete.html` directly in Chrome
2. Go to **Telemetry** tab → drag and drop your `.ibt` file
3. All 8 modules populate automatically

---

## Requirements

| Requirement | Details |
|------------|---------|
| **Python** | 3.10 or newer — [python.org](https://python.org) (tick "Add to PATH") |
| **Browser** | Google Chrome (required for WebSocket + Web Speech API) |
| **iRacing** | Any current season subscription (for live mode) |
| **OS** | Windows 10 / 11 |

The `FSS_START.bat` launcher installs Python packages automatically on first run:
```
pip install irsdk websockets
```

---

## Modules

| # | Module | Description |
|---|--------|-------------|
| 01 | **Schedule Engine** | Full 2026 S2 schedule — 42 series, live week detection, category/setup filters |
| 02 | **IBT Telemetry** | Direct `.ibt` binary parser — speed, throttle, brake, gear, lap deltas, corner segmentation |
| 03 | **Track Map** | GPS reconstruction from IBT — speed heatmap, brake/throttle overlays, corner labels, car replay |
| 04 | **AI Driver Coach** | Brake consistency, throttle application, corner-by-corner analysis, steering smoothness, AI coaching report |
| 05 | **Setup Engine** | IBT setup YAML extraction, tyre analysis, 3 variant setups (Qualifying/Stable/Aggressive) with STO download |
| 06 | **Strategy Engine** | Fuel calculator, pit windows, tyre strategy, session pit analysis, series matching |
| 07 | **Practice Engine** | Pre-session planner with targets, live session log, telemetry cross-reference after session |
| 08 | **Live AI Voice** | Real-time WebSocket bridge, 5 engineer personas, push-to-talk, voice coaching, post-session summary |

---

## Live Voice Engineer

### 5 Engineer Personas

| Persona | Style |
|---------|-------|
| **Performance** | Calm, data-driven, precise — default race engineer |
| **Qualifying** | Aggressive, high energy, pushes you harder |
| **Endurance** | Strategic, fuel/tyres focused, long-stint management |
| **Driver Coach** | Technical, explains the why, focused on improvement |
| **Minimal Radio** | Critical calls only — pit window, fuel, major errors |

### What the engineer calls out

- **Lap times** — spoken as "one thirty-two point seven" with delta to best
- **Tyre temps** — cold/warming/optimal/hot state transitions (not repeated)
- **Tyre wear** — every 3 laps (all 4 corners)
- **Fuel** — low warning, critical pit call
- **Mistakes** — classified: oversteer, understeer, snap lift, late braking, front lock — with specific correction
- **Track temp** — with rising/falling trend detection + rain threat
- **Pit exit** — gap detection, traffic check
- **Push-to-talk** — hold the radio button, ask questions: fuel, position, gap, tyres, "can I push?"

### Temperature units
Automatically matches your iRacing display settings (°C or °F).

### Voice silenced in demo mode
No audio fires unless iRacing is actually connected — avoids simulated data talking over you.

---

## File Structure

```
your-folder/
├── fss_b110_complete.html    ← Main application (open this in Chrome)
├── fss_bridge.py             ← Python WebSocket bridge for live iRacing
├── FSS_START.bat             ← Windows launcher (double-click to start)
├── README.md                 ← This file
└── LICENSE                   ← MIT License
```

---

## How the Bridge Works

```
iRacing (shared memory) → fss_bridge.py → WebSocket ws://localhost:6776
                                        → HTTP server http://localhost:6775
                                        → Chrome (FSS HTML app)
```

The bridge reads iRacing's shared memory at **20Hz** and streams 40+ telemetry channels to the browser over WebSocket. It also serves the HTML file over HTTP (required — Chrome blocks WebSocket connections from `file://`).

**Why can't I just open the HTML file directly?**
Chrome's security policy blocks WebSocket connections from `file://` pages. The bridge serves the file over `http://localhost:6775` which allows the connection. Always use the URL the bridge prints, not the file path.

---

## Troubleshooting

**"Chrome prevents WebSocket from file://"**
→ Use `FSS_START.bat` or run `python fss_bridge.py` manually. Open the `http://localhost:6775` URL.

**"Python not found"**
→ Install Python from [python.org](https://python.org). During install, tick **"Add Python to PATH"**.

**"irsdk not installed / demo mode"**
→ Run `pip install irsdk` or let `FSS_START.bat` do it automatically.

**Bridge starts but iRacing doesn't connect**
→ Make sure iRacing is running and a session is loaded (not just the launcher). The bridge retries every 2 seconds.

**Tabs are frozen / clock not working**
→ Make sure you opened from `http://localhost:6775` not `file://`. If loading from file, all functionality is still available for IBT analysis but Live tab won't work.

**Track map looks wrong**
→ Select a different reference lap using the lap buttons. The best lap is pre-selected.

---

## IBT File Analysis — No Python Needed

All offline analysis modules (01–07) work by opening `fss_b110_complete.html` directly in Chrome and loading an IBT file. No Python, no bridge, no iRacing needed.

---

## Known Limitations

- **Tyre wear on BMW M LMDh / some GTP cars**: iRacing only updates the wear channel when tyres are changed, not lap-by-lap. The platform detects this and shows a warning. This is an iRacing SDK limitation.
- **Track map corners**: Corner labels are detected from GPS curvature (Menger algorithm). On some tracks the count may differ from official corner numbering.
- **Web Speech API**: Voice output requires Chrome. Firefox and Safari are not supported for the voice engineer.
- **Live mode Windows only**: The Python bridge uses iRacing's Windows shared memory API.

---

## Contributing

Pull requests welcome. Please test against at least one IBT file before submitting.

For bugs or feature requests, open an issue and include:
- Which module
- What you expected vs what happened
- Your iRacing car/track if relevant

---

## Credits

Built by the Full Send Systems team for the iRacing community.

iRacing SDK Python wrapper by [kutu](https://github.com/kutu/pyirsdk).

---

*Full Send Systems is not affiliated with iRacing.com Motorsport Simulations, LLC.*
