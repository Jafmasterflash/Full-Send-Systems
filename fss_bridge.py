#!/usr/bin/env python3
"""
Full Send Systems — Live Bridge v2.0
=====================================
Reads iRacing shared memory via irsdk and streams enriched telemetry
to the FSS browser app via WebSocket.

NEW in v2.0:
  - Sector times S1/S2/S3 (current + best + deltas)
  - Gap ahead/behind + closing rate + intercept prediction
  - Flag state engine (green/yellow/safety_car/red/finish)
  - Incident counter + limit
  - Multiclass awareness
  - all_cars array

HOW TO USE:
  1. Double-click FSS_START.bat  (Windows — recommended)
  2. OR run:  python fss_bridge.py

REQUIREMENTS:
  pip install irsdk websockets
"""

import asyncio, json, time, math, sys, os, threading
import webbrowser, subprocess, http.server, socketserver
from pathlib import Path
from collections import deque

print()
print("╔══════════════════════════════════════════════════════╗")
print("║         FULL SEND SYSTEMS  —  Live Bridge v2.0      ║")
print("╚══════════════════════════════════════════════════════╝")
print()

# ── Python version check ──────────────────────────────────────────────────────
if sys.version_info < (3, 10):
    print("✗ Python 3.10+ required. Download: https://python.org/downloads/")
    input("Press Enter to exit..."); sys.exit(1)
print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}")

# ── Auto-install dependencies ─────────────────────────────────────────────────
def install_pkg(name):
    print(f"  Installing {name}...")
    ret = os.system(f'"{sys.executable}" -m pip install {name} -q')
    return ret == 0

try:
    import websockets
    print("✓ websockets ready")
except ImportError:
    if not install_pkg('websockets'):
        print("✗ Could not install websockets. Try: pip install websockets")
        input("Press Enter to exit..."); sys.exit(1)
    import websockets
    print("✓ websockets installed")

try:
    import irsdk
    HAS_IRSDK = True
    print("✓ irsdk ready — LIVE iRacing mode available")
except ImportError:
    if install_pkg('irsdk'):
        try:
            import irsdk
            HAS_IRSDK = True
            print("✓ irsdk installed — LIVE mode available")
        except Exception:
            HAS_IRSDK = False
            print("  Running in DEMO mode (simulated data)")
    else:
        HAS_IRSDK = False
        print("  DEMO mode (pip install irsdk for live)")

# ── Find HTML file ────────────────────────────────────────────────────────────
def find_html():
    d = Path(__file__).parent
    for f in sorted(d.glob('fss_b1*.html'), reverse=True):
        return str(f)
    return None

HTML_FILE = find_html()
HTML_DIR  = str(Path(HTML_FILE).parent) if HTML_FILE else str(Path(__file__).parent)
HTML_NAME = Path(HTML_FILE).name if HTML_FILE else 'fss_b120_MASTER_9.html'
if HTML_FILE:
    print(f"✓ App: {HTML_NAME}")
else:
    print("  ! Put fss_b120_MASTER_9.html in the same folder as fss_bridge.py")

WS_PORT, HTTP_PORT = 6776, 6775
TICK_SLEEP = 1.0 / 20

# ── HTTP server ───────────────────────────────────────────────────────────────
class FSSHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=HTML_DIR, **kw)
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def log_message(self, *a): pass

def run_http():
    try:
        class ReuseServer(socketserver.TCPServer):
            allow_reuse_address = True
        ReuseServer(('0.0.0.0', HTTP_PORT), FSSHandler).serve_forever()
    except OSError as e:
        print(f"  ! HTTP port {HTTP_PORT} busy: {e}")

def open_browser():
    url = f'http://localhost:{HTTP_PORT}/{HTML_NAME}'
    time.sleep(1.8)
    for path in [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    ]:
        if os.path.exists(path):
            try: subprocess.Popen([path, url]); return
            except Exception: pass
    webbrowser.open(url)

# ── Base channels ─────────────────────────────────────────────────────────────
CHANNELS = {
    'Speed':'speed_ms','Throttle':'throttle','Brake':'brake',
    'SteeringWheelAngle':'steering','Gear':'gear','RPM':'rpm',
    'LapDistPct':'lap_dist','Lap':'lap','LapLastLapTime':'last_lap',
    'LapBestLapTime':'best_lap','LapCurrentLapTime':'current_lap',
    'FuelLevel':'fuel','FuelLevelPct':'fuel_pct','FuelUsePerHour':'fuel_per_hour',
    'LatAccel':'lat_accel','LonAccel':'lon_accel','YawRate':'yaw_rate',
    'PlayerCarPosition':'position','PlayerCarClassPosition':'class_position',
    'SessionTime':'session_time','SessionTimeRemain':'session_time_remain',
    'SessionLapsRemain':'laps_remain','IsOnTrack':'on_track','IsInGarage':'in_garage',
    'IsOnPitRoad':'on_pit_road','WeatherDeclaredWet':'weather_wet',
    'Skies':'skies','AirPressure':'air_pressure',
    'CarIdxEstTime':'car_est_time','CarIdxLapDistPct':'car_pos_arr',
    'LFtempCM':'lf_tcm','RFtempCM':'rf_tcm','LRtempCM':'lr_tcm','RRtempCM':'rr_tcm',
    'LFwearM':'lf_wm','RFwearM':'rf_wm','LRwearM':'lr_wm','RRwearM':'rr_wm',
    'LFpressure':'lf_psi','RFpressure':'rf_psi','LRpressure':'lr_psi','RRpressure':'rr_psi',
    'TrackTemp':'track_temp','AirTemp':'air_temp',
    # v2.0 additions
    'SessionFlags':'session_flags','SessionState':'session_state_int',
    'PlayerCarIdx':'player_car_idx',
    'CarIdxPosition':'car_idx_position','CarIdxClassPosition':'car_idx_class_position',
    'CarIdxLap':'car_idx_lap','CarIdxLastLapTime':'car_idx_last_lap',
    'PlayerCarIdx':'player_car_idx',
    'CarIdxBestLapTime':'car_idx_best_lap','CarIdxOnTrack':'car_idx_on_track',
    'CarIdxOnPitRoad':'car_idx_on_pit','CarIdxClass':'car_idx_class',
    'CarIdxF2Time':'car_idx_f2time',
    'PlayerCarDriverIncidentCount':'incidents',
    'PlayerCarTeamIncidentCount':'team_incidents',
    # Coach-critical additions
    'PlayerTrackSurface':'track_surface_raw',
    'PlayerTrackSurfaceMaterial':'track_surface_material',
    'PlayerCarTowTime':'tow_time',
    'LapDeltaToBestLap':'delta_to_best_live',
    'LapDeltaToBestLap_OK':'delta_to_best_ok',
    'LapDeltaToOptimalLap':'delta_to_optimal',
    'TireLF_RumblePitch':'lf_rumble','TireRF_RumblePitch':'rf_rumble',
    'LapCompleted':'lap_completed_count',
}

SESSION_STATE_MAP = {
    0:'invalid',1:'countdown',2:'warmup',3:'parade_laps',
    4:'racing',5:'checkered',6:'cool_down'
}

# ── Sector tracker ────────────────────────────────────────────────────────────
class SectorTracker:
    BOUNDS = [0.0, 0.333, 0.667, 1.0]

    def __init__(self):
        self.best = [None, None, None]
        self.s1 = None
        self.s2 = None
        self._s1_t = None
        self._s2_t = None
        self._prev_sec = 0
        self._prev_lap = -1

    def sector(self, dist):
        for i in range(2, -1, -1):
            if dist >= self.BOUNDS[i]:
                return i
        return 0

    def update(self, dist, session_time, lap):
        if lap != self._prev_lap:
            self.s1 = self.s2 = None
            self._s1_t = session_time
            self._s2_t = None
            self._prev_sec = 0
            self._prev_lap = lap

        sec = self.sector(dist)

        if sec == 1 and self._prev_sec == 0 and self._s1_t is not None and self.s1 is None:
            self.s1 = session_time - self._s1_t
            self._s2_t = session_time
            if self.best[0] is None or self.s1 < self.best[0]:
                self.best[0] = self.s1

        if sec == 2 and self._prev_sec == 1 and self._s2_t is not None and self.s2 is None:
            self.s2 = session_time - self._s2_t
            if self.best[1] is None or self.s2 < self.best[1]:
                self.best[1] = self.s2

        self._prev_sec = sec
        return sec

    def commit_s3(self, lap_time):
        if self.s1 and self.s2 and lap_time > 0:
            s3 = lap_time - self.s1 - self.s2
            if s3 > 0:
                if self.best[2] is None or s3 < self.best[2]:
                    self.best[2] = s3
                return s3
        return None

    def deltas(self):
        s1d = (self.s1 - self.best[0]) if self.s1 and self.best[0] else None
        s2d = (self.s2 - self.best[1]) if self.s2 and self.best[1] else None
        return s1d, s2d

# ── Gap tracker ───────────────────────────────────────────────────────────────
class GapTracker:
    def __init__(self, n=3):
        self.ahead  = deque(maxlen=n)
        self.behind = deque(maxlen=n)

    def update(self, ahead, behind):
        if ahead  is not None: self.ahead.append(ahead)
        if behind is not None: self.behind.append(behind)

    def _rate(self, hist):
        vals = list(hist)
        n = len(vals)
        if n < 2: return None
        xs = list(range(n))
        xm = sum(xs)/n; ym = sum(vals)/n
        num = sum((x-xm)*(y-ym) for x,y in zip(xs,vals))
        den = sum((x-xm)**2 for x in xs)
        return num/den if den else None

    def rates(self):
        return self._rate(self.ahead), self._rate(self.behind)

    def intercept(self, gap, rate):
        if gap is None or rate is None or rate >= 0: return None
        return abs(gap / rate)

# ── Lap Accumulator — per-zone telemetry for AI coaching ────────────────────
class LapAccumulator:
    ZONES = 50

    def __init__(self):
        self.reset()

    def reset(self):
        self.zones = [{'speed':[],'throttle':[],'brake':[],'lat_accel':[],'yaw':[],'on_track':[]} for _ in range(self.ZONES)]
        self.events = []
        self.tow_active = False
        self.offtrack_active = False

    def zone(self, dist):
        return min(int(dist * self.ZONES), self.ZONES - 1)

    def tick(self, d):
        dist = float(d.get('lap_dist', 0) or 0)
        z = self.zone(dist)
        self.zones[z]['speed'].append(float(d.get('speed_kph', 0) or 0))
        self.zones[z]['throttle'].append(float(d.get('throttle', 0) or 0))
        self.zones[z]['brake'].append(float(d.get('brake', 0) or 0))
        self.zones[z]['lat_accel'].append(abs(float(d.get('lat_accel', 0) or 0)))
        self.zones[z]['yaw'].append(abs(float(d.get('yaw_rate', 0) or 0)))
        self.zones[z]['on_track'].append(bool(d.get('on_track', True)))

    def log_event(self, event_type, d, detail=''):
        dist = float(d.get('lap_dist', 0) or 0)
        self.events.append({
            'type': event_type,
            'dist_pct': round(dist * 100, 1),
            'speed_kph': round(float(d.get('speed_kph', 0) or 0), 1),
            'detail': detail,
        })

    def summarise(self, lap_time, best_lap):
        zone_sums = []
        for i, z in enumerate(self.zones):
            if len(z['speed']) < 2:
                continue
            off_pct = (z['on_track'].count(False) / len(z['on_track']) * 100) if z['on_track'] else 0
            zone_sums.append({
                'zone': i,
                'dist_pct': round(i * 100 / self.ZONES, 0),
                'avg_speed': round(sum(z['speed']) / len(z['speed']), 1),
                'min_speed': round(min(z['speed']), 1),
                'max_brake': round(max(z['brake']), 2) if z['brake'] else 0,
                'avg_throttle': round(sum(z['throttle']) / len(z['throttle']), 2) if z['throttle'] else 0,
                'offtrack_pct': round(off_pct, 1),
            })
        braking_zones = sorted(zone_sums, key=lambda x: x['max_brake'], reverse=True)[:6]
        return {
            'lap_time': round(lap_time, 3),
            'best_lap': round(best_lap, 3) if best_lap else None,
            'delta_to_best': round(lap_time - best_lap, 3) if best_lap else None,
            'events': self.events,
            'braking_zones': braking_zones,
        }


# ── Flag decoder ──────────────────────────────────────────────────────────────
def decode_flags(f):
    if f & 0x10000: return 'black'
    if f & 0x0010:  return 'red'
    if f & 0x0001:  return 'checkered'
    if f & 0x0002:  return 'white'
    if f & 0x8000:  return 'caution_waving'
    if f & 0x4000:  return 'caution'
    if f & 0x0100:  return 'yellow_waving'
    if f & 0x0008:  return 'yellow'
    if f & 0x0040:  return 'debris'
    if f & 0x0004:  return 'green'
    return 'none'

def flag_mode(flag_state, sc_active):
    if flag_state in ('checkered','white'): return 'finish'
    if flag_state == 'red':                 return 'red'
    if sc_active or flag_state in ('caution','caution_waving'): return 'safety_car'
    if flag_state in ('yellow','yellow_waving','debris'):        return 'yellow'
    return 'green'

# ── State ─────────────────────────────────────────────────────────────────────
class S:
    clients   = set()
    ir        = None
    connected = False
    meta_sent = False
    lap_times = []
    sectors   = SectorTracker()
    gaps      = GapTracker()
    accum     = LapAccumulator()   # per-lap zone accumulator for AI coaching
    prev_lap  = -1
    fuel_prev = None
    prev_tow  = 0.0                # for penalty detection
    prev_on_track = True           # for offtrack detection
    pending_event = None           # {type, data, d} waiting for straight

# ── Demo driver ───────────────────────────────────────────────────────────────
class Demo:
    def __init__(self): self.t=0.0; self.lap=1; self.ls=0.0; self.fuel=55.0
    def tick(self,dt):
        self.t+=dt; self.fuel=max(0,self.fuel-dt*0.0009)
        lt=self.t-self.ls
        if lt>90: self.lap+=1; self.ls=self.t; lt=0.0
        d=min(lt/90,1.0)
        spd=120+80*math.sin(d*math.pi*6)
        thr=max(0,min(1,0.5+0.5*math.sin(d*math.pi*6+0.5)))
        brk=max(0,-0.5*math.sin(d*math.pi*6+0.5))
        fph=self.fuel*0.0009*3600; fpl=fph*(90/3600)
        return {
            'speed_ms':spd/3.6,'speed_kph':round(spd,1),
            'throttle':round(thr,3),'brake':round(brk,3),
            'steering':round(math.sin(d*math.pi*8)*0.3,3),
            'gear':max(1,min(6,int(spd/30)+1)),'rpm':round(3000+(spd/200)*5000),
            'lap_dist':round(d,4),'lap':self.lap,'current_lap':round(lt,3),
            'last_lap':89.5+(self.lap%3)*0.3,'best_lap':89.2,
            'fuel':round(self.fuel,2),'fuel_pct':round(self.fuel/55,3),
            'fuel_per_hour':round(fph,2),'fuel_per_lap_est':round(fpl,3),
            'laps_fuel_remain':round(self.fuel/max(fpl,0.001),1),
            'lat_accel':round(math.sin(d*math.pi*8)*15,2),
            'lon_accel':round((thr-brk)*8,2),
            'position':1,'class_position':1,
            'session_time':round(self.t,2),'session_time_remain':round(1800-self.t,1),
            'laps_remain':max(0,30-self.lap),'on_track':True,'in_garage':False,
            'on_pit_road':False,'weather_wet':False,'skies':0,
            'lf_psi':27.5,'rf_psi':27.5,'lr_psi':26.5,'rr_psi':26.5,
            'lf_tcm':85.0,'rf_tcm':87.0,'lr_tcm':82.0,'rr_tcm':84.0,
            'front_temp_avg':86.0,'rear_temp_avg':83.0,
            'lf_wm':99.8,'rf_wm':99.7,'lr_wm':99.6,'rr_wm':99.5,
            'track_temp':32.0,'air_temp':22.0,
            # v2 fields with demo values
            'flag_state':'green','flag_mode':'green','session_state':'racing',
            'safety_car_active':False,'yellow_flag_zones':[],
            'incidents':0,'incidents_limit':0,'incidents_warn_at':0,'team_incidents':0,
            'gap_ahead':None,'gap_behind':None,
            'closing_rate_ahead':None,'closing_rate_behind':None,'intercept_laps':None,
            'sector_current':0,'s1_current':None,'s2_current':None,
            's1_best':None,'s2_best':None,'s3_best':None,
            's1_delta':None,'s2_delta':None,
            'is_multiclass':False,'num_car_classes':1,'all_cars':[],
        }

demo = Demo()

def read_ir(ir):
    d = {}
    for k, v in CHANNELS.items():
        try:
            val = ir[k]
            if val is not None: d[v] = val
        except: pass

    # ── Track surface — offtrack detection ──────────────────────────────────────
    # PlayerTrackSurface: irsdk_TrkLoc enum — int in pyirsdk
    # -1=NotInWorld, 0=OffTrack, 1=InPitStall, 2=AproachingPits, 3=OnTrack
    # NOTE: may return None in Offline Testing sessions — use multi-source detection
    raw_surf = d.get('track_surface_raw')
    surf_val = 3  # default to on-track
    if raw_surf is not None:
        try:
            sv = int(raw_surf)
            surf_val = sv
        except (TypeError, ValueError):
            s = str(raw_surf).lower()
            if 'offtrack' in s or 'off_track' in s:    surf_val = 0
            elif 'pitstall' in s or 'pit_stall' in s:  surf_val = 1
            elif 'aproach' in s or 'approach' in s:    surf_val = 2
            elif 'ontrack' in s or 'on_track' in s:    surf_val = 3

    sdk_is_offtrack = (surf_val == 0)
    sdk_surface_name = {-1:'unknown',0:'offtrack',1:'pit_stall',2:'pit_approach',3:'racing'}.get(surf_val,'racing')

    # Secondary detection: tow_time > 0 always means a track limits violation occurred
    # This works in ALL session types including Offline Testing
    tow_raw = float(d.get('tow_time', 0) or 0)

    # Tertiary detection: IsOnTrack=False but car was previously on track = car left surface
    # Used as final fallback when PlayerTrackSurface is None (Offline Testing)
    sdk_unavailable = (raw_surf is None)

    d['on_track_surface'] = (surf_val == 3)
    d['is_offtrack'] = sdk_is_offtrack
    d['surface_name'] = sdk_surface_name
    d['track_surface_raw_debug'] = str(raw_surf)
    d['sdk_surface_unavailable'] = sdk_unavailable

    # ── Tow/penalty detection ─────────────────────────────────────────────────
    tow = float(d.get('tow_time', 0) or 0)
    d['tow_time'] = round(tow, 1)
    d['penalty_active'] = tow > 0.1

    # ── Live delta sanitise ───────────────────────────────────────────────────
    delta_ok = bool(d.get('delta_to_best_ok', False))
    if not delta_ok:
        d['delta_to_best_live'] = None
    else:
        raw_delta = d.get('delta_to_best_live')
        d['delta_to_best_live'] = round(float(raw_delta), 3) if raw_delta is not None else None

    # Ensure critical driving inputs are always floats (JS mistake detection needs these)
    for fk in ('yaw_rate','throttle','brake','steering','lat_accel','lon_accel','speed_kph'):
        if d.get(fk) is None: d[fk] = 0.0

    # Ensure booleans are real bools not iRacing integers
    d['on_track']  = bool(d.get('on_track', False))
    d['in_garage'] = bool(d.get('in_garage', False))
    d['on_pit_road'] = bool(d.get('on_pit_road', False))

    # Basic derived
    d['speed_kph'] = round(d.get('speed_ms', 0) * 3.6, 1)
    # Fuel per lap — rolling average of actual consumed fuel (reliable from lap 1)
    fph = d.get('fuel_per_hour', 0)
    bl  = d.get('best_lap') or d.get('last_lap') or 90
    if not bl or bl <= 0: bl = 90
    # Primary: use FuelUsePerHour * lap time (works once engine is running)
    if fph > 0 and bl > 0:
        fpl = fph * (bl / 3600)
        d['fuel_per_lap_est'] = round(fpl, 3)
        fuel = d.get('fuel', 0)
        if fuel > 0: d['laps_fuel_remain'] = round(fuel / fpl, 1)
    # Fallback: if fph not available, use lap history from S.lap_times
    elif len(S.lap_times) >= 2 and S.fuel_prev is not None:
        fuel_used_laps = [lt.get('fuel_used', 0) for lt in S.lap_times if lt.get('fuel_used', 0) > 0]
        if fuel_used_laps:
            fpl_est = sum(fuel_used_laps) / len(fuel_used_laps)
            if fpl_est > 0:
                d['fuel_per_lap_est'] = round(fpl_est, 3)
                fuel = d.get('fuel', 0)
                if fuel > 0: d['laps_fuel_remain'] = round(fuel / fpl_est, 1)
    lf=d.get('lf_tcm',0); rf=d.get('rf_tcm',0)
    lr=d.get('lr_tcm',0); rr=d.get('rr_tcm',0)
    if lf and rf: d['front_temp_avg'] = round((lf+rf)/2, 1)
    if lr and rr: d['rear_temp_avg']  = round((lr+rr)/2, 1)

    # iRacing wear values are 0.0–1.0 fractions — convert to percentages for JS
    for wk in ('lf_wm','rf_wm','lr_wm','rr_wm'):
        v = d.get(wk)
        if v is not None:
            d[wk] = round(float(v) * 100, 1)

    # ── Flags ────────────────────────────────────────────────────────────────
    raw_flags   = int(d.get('session_flags', 0) or 0)
    ss_int      = int(d.get('session_state_int', 0) or 0)
    flag_state  = decode_flags(raw_flags)
    sess_state  = SESSION_STATE_MAP.get(ss_int, 'invalid')
    sc_active   = (sess_state == 'parade_laps')
    fmode       = flag_mode(flag_state, sc_active)
    yellow_zones = [{'from':0.0,'to':1.0,'full_course':True}] \
                   if raw_flags & 0xC108 else []

    d['flag_state']        = flag_state
    d['flag_mode']         = fmode
    d['session_state']     = sess_state
    d['safety_car_active'] = sc_active
    d['yellow_flag_zones'] = yellow_zones

    # ── Incidents ────────────────────────────────────────────────────────────
    inc = int(d.get('incidents', 0) or 0)
    d['incidents'] = inc
    d['incidents_limit']   = 0   # populated from session YAML separately
    d['incidents_warn_at'] = 0

    # ── Sectors ──────────────────────────────────────────────────────────────
    lap       = int(d.get('lap', 0) or 0)
    lap_dist  = float(d.get('lap_dist', 0) or 0)
    sess_time = float(d.get('session_time', 0) or 0)
    sec_idx   = S.sectors.update(lap_dist, sess_time, lap)
    s1d, s2d  = S.sectors.deltas()

    d['sector_current'] = sec_idx
    d['s1_current']     = S.sectors.s1
    d['s2_current']     = S.sectors.s2
    d['s1_best']        = S.sectors.best[0]
    d['s2_best']        = S.sectors.best[1]
    d['s3_best']        = S.sectors.best[2]
    d['s1_delta']       = s1d
    d['s2_delta']       = s2d

    # ── Gaps ─────────────────────────────────────────────────────────────────
    f2t  = d.get('car_idx_f2time')
    pos  = d.get('car_idx_position')
    pidx = int(d.get('player_car_idx', 0) or 0)
    gap_ahead = gap_behind = None

    if f2t and pos and pidx < len(f2t):
        my_pos = int(pos[pidx]) if pidx < len(pos) else 0
        ga = f2t[pidx]
        if ga is not None and -60 < ga < 0:
            gap_ahead = abs(ga)
        # find car behind
        for i, p in enumerate(pos):
            if int(p or 0) == my_pos + 1 and i < len(f2t):
                gb = f2t[i]
                if gb is not None and -60 < gb < 0:
                    gap_behind = abs(gb)
                break

    S.gaps.update(gap_ahead, gap_behind)
    cr_ahead, cr_behind = S.gaps.rates()
    intercept = S.gaps.intercept(gap_ahead, cr_ahead)

    d['gap_ahead']           = gap_ahead
    d['gap_behind']          = gap_behind
    d['closing_rate_ahead']  = cr_ahead
    d['closing_rate_behind'] = cr_behind
    d['intercept_laps']      = intercept

    # ── Multiclass ───────────────────────────────────────────────────────────
    car_classes = d.get('car_idx_class')
    num_classes = len(set(c for c in car_classes if c)) if car_classes else 1
    d['is_multiclass']    = num_classes > 1
    d['num_car_classes']  = num_classes

    # ── Traffic detection — closest car ahead within 1.5s ────────────────────
    traffic_close = False
    traffic_close_pos = None
    if gap_ahead is not None and 0 < gap_ahead <= 1.5:
        traffic_close = True
        # Find the position of the car ahead
        my_pos = int((pos[pidx] if pos and pidx < len(pos) else 0) or 0)
        traffic_close_pos = my_pos - 1 if my_pos > 1 else None
    d['traffic_close']     = traffic_close
    d['traffic_close_pos'] = traffic_close_pos

    # ── All cars (lightweight) ────────────────────────────────────────────────
    all_cars = []
    on_track = d.get('car_idx_on_track') or []
    for i, ot in enumerate(on_track):
        if not ot: continue
        all_cars.append({
            'car_idx':       i,
            'is_player':     i == pidx,
            'position':      int((pos[i] if pos and i < len(pos) else 0) or 0),
            'class_position':int(((d.get('car_idx_class_position') or [])[i]
                                  if d.get('car_idx_class_position') and
                                  i < len(d.get('car_idx_class_position',[]))
                                  else 0) or 0),
            'lap':           int(((d.get('car_idx_lap') or [])[i]
                                  if d.get('car_idx_lap') and
                                  i < len(d.get('car_idx_lap',[]))
                                  else 0) or 0),
            'lap_dist':      round(float(((d.get('car_pos_arr') or [])[i]
                                          if d.get('car_pos_arr') and
                                          i < len(d.get('car_pos_arr',[]))
                                          else 0) or 0), 3),
            'last_lap':      float(((d.get('car_idx_last_lap') or [])[i]
                                    if d.get('car_idx_last_lap') and
                                    i < len(d.get('car_idx_last_lap',[]))
                                    else -1) or -1),
            'best_lap':      float(((d.get('car_idx_best_lap') or [])[i]
                                    if d.get('car_idx_best_lap') and
                                    i < len(d.get('car_idx_best_lap',[]))
                                    else -1) or -1),
            'on_pit_road':   bool((d.get('car_idx_on_pit') or [])[i]
                                  if d.get('car_idx_on_pit') and
                                  i < len(d.get('car_idx_on_pit',[]))
                                  else False),
            'gap_to_leader': round(abs(float((f2t[i] if f2t and i < len(f2t)
                                              else 0) or 0)), 2),
        })
    all_cars.sort(key=lambda c: c['position'])
    d['all_cars'] = all_cars

    return d

def get_meta(ir):
    if not ir:
        return {'driver':'Demo Driver','car':'Demo GT3','track':'Demo Circuit',
                'track_len':4.5,'session_type':'Practice','max_fuel':55.0,
                'num_cars':20,'use_fahrenheit':False,'display_units':1}
    try:
        di=ir['DriverInfo'] or {}; wi=ir['WeekendInfo'] or {}
        si=ir['SessionInfo'] or {}
        idx=di.get('DriverCarIdx',0)
        dr=next((d for d in di.get('Drivers',[]) if d.get('CarIdx')==idx),{})
        sn=ir['SessionNum'] or 0
        sess=(si.get('Sessions') or [{}])[min(sn,len(si.get('Sessions',[{}]))-1)]
        du=wi.get('DisplayUnits',1)

        # Incident limit from session info
        inc_limit = 0
        try:
            il_str = str(sess.get('SessionIncidentLimit','unlimited'))
            if il_str.isdigit(): inc_limit = int(il_str)
        except: pass

        # Pit speed limit — convert from m/s to kph
        pit_spd_ms = float(wi.get('TrackPitSpeedLimit', 0) or 0)
        pit_spd_kph = round(pit_spd_ms * 3.6, 0) if pit_spd_ms > 0 else 60.0

        return {'driver':dr.get('UserName','Driver'),'car':dr.get('CarScreenName','Car'),
                'track':wi.get('TrackDisplayName','Track'),
                'track_len':float(str(wi.get('TrackLength','4.5 km')).split()[0]),
                'session_type':sess.get('SessionType','Practice'),
                'max_fuel':float(dr.get('CarFuelMaxLtr',55)),
                'num_cars':len(di.get('Drivers',[])),
                'display_units':int(du),'use_fahrenheit':int(du)==0,
                'incident_limit':inc_limit,
                'pit_speed_limit_kph': int(pit_spd_kph)}
    except Exception as e:
        return {'driver':'Driver','car':'Car','track':'Track',
                'max_fuel':55,'use_fahrenheit':False,'error':str(e)}

async def broadcast(t, d):
    if not S.clients: return
    msg = json.dumps({'type':t,'ts':time.time(),'data':d})
    dead = set()
    for ws in list(S.clients):
        try: await ws.send(msg)
        except: dead.add(ws)
    S.clients -= dead

async def telemetry_loop():
    while True:
        await asyncio.sleep(TICK_SLEEP)
        if not S.clients: continue
        try:
            if HAS_IRSDK and S.ir and S.connected:
                S.ir.freeze_var_buffer_latest()
                data = read_ir(S.ir)
            else:
                data = demo.tick(TICK_SLEEP)

            if not S.meta_sent:
                meta = get_meta(S.ir if S.connected else None)
                S.meta_cache = meta
                await broadcast('meta', meta)
                S.meta_sent = True

            # Lap complete detection
            # Use CarIdxLastLapTime[player_idx] as primary — more reliable than LapLastLapTime
            # Both are read; player index from DriverInfo
            cur = int(data.get('lap', 0))
            if cur != S.prev_lap and S.prev_lap >= 0:
                S._lap_change_pending = S.prev_lap
                S._lap_change_ticks   = 0
                print(f"[FSS] LAP CROSSING: prev={S.prev_lap} cur={cur} at {time.time():.3f}")
                # Capture last lap time immediately at crossing moment
                # Use cached player_car_idx from DriverInfo (more reliable than telemetry field)
                car_idx_laps = data.get('car_idx_last_lap') or []
                pidx_local   = getattr(S, 'player_car_idx', int(data.get('player_car_idx', 0) or 0))
                cidx_last = 0.0
                if car_idx_laps and pidx_local < len(car_idx_laps):
                    try: cidx_last = float(car_idx_laps[pidx_local] or 0)
                    except: cidx_last = 0.0
                direct_last = float(data.get('last_lap', 0) or 0)
                # Use whichever source has a valid time
                S._lap_time_at_crossing = cidx_last if cidx_last > 5 else (direct_last if direct_last > 5 else 0)
                print(f"[FSS] LAP CROSSING captured: cidx={cidx_last:.3f} direct={direct_last:.3f} using={S._lap_time_at_crossing:.3f}")

            if getattr(S, '_lap_change_pending', None) is not None:
                S._lap_change_ticks = getattr(S, '_lap_change_ticks', 0) + 1
                # Use captured time first, then fall back to live field
                last = S._lap_time_at_crossing if getattr(S, '_lap_time_at_crossing', 0) > 5 else data.get('last_lap', 0)
                ready = (last and last > 5)
                timed_out = S._lap_change_ticks > 6
                if ready:
                    fuel_used = round((S.fuel_prev - data.get('fuel', S.fuel_prev)) if S.fuel_prev is not None else 0, 3)
                    completed_lap = S._lap_change_pending
                    s3 = S.sectors.commit_s3(last)
                    S.lap_times.append({'lap': completed_lap, 'time': round(last, 3), 'fuel_used': max(0, fuel_used)})
                    print(f"[FSS] LAP COMPLETE broadcast: lap={completed_lap} time={last:.3f} ticks={S._lap_change_ticks}")
                    await broadcast('lap_complete', {
                        'lap':            completed_lap,
                        'lap_time':       round(last, 3),
                        'time':           round(last, 3),
                        'is_best':        last == data.get('best_lap'),
                        's1':             S.sectors.s1,
                        's2':             S.sectors.s2,
                        's3':             s3,
                        's1_best':        S.sectors.s1 == S.sectors.best[0] if S.sectors.s1 else False,
                        's2_best':        S.sectors.s2 == S.sectors.best[1] if S.sectors.s2 else False,
                        's3_best':        s3 == S.sectors.best[2] if s3 else False,
                        'fuel_used':      max(0, fuel_used),
                        'position':       data.get('position', 0),
                        'class_position': data.get('class_position', 0),
                        'incidents':      data.get('incidents', 0),
                        'incidents_limit':data.get('incidents_limit', 0),
                        'gap_ahead':      data.get('gap_ahead'),
                        'lap_times':      S.lap_times[-10:],
                    })
                    S._lap_change_pending = None
                    S._lap_change_ticks   = 0
                    # ── AI lap debrief — full lap summary for Claude ──────────
                    best = data.get('best_lap') or last
                    lap_summary = S.accum.summarise(last, best)
                    lap_summary['lap'] = completed_lap
                    lap_summary['position'] = data.get('position', 0)
                    lap_summary['fuel_remaining'] = round(data.get('fuel', 0), 1)
                    lap_summary['fuel_per_lap'] = round(data.get('fuel_per_lap_est', 0), 2)
                    lap_summary['laps_fuel_remain'] = round(data.get('laps_fuel_remain', 0), 1)
                    lap_summary['front_temp'] = data.get('front_temp_avg')
                    lap_summary['rear_temp'] = data.get('rear_temp_avg')
                    lap_summary['lf_wear'] = data.get('lf_wm')
                    lap_summary['rf_wear'] = data.get('rf_wm')
                    lap_summary['lr_wear'] = data.get('lr_wm')
                    lap_summary['rr_wear'] = data.get('rr_wm')
                    lap_summary['incidents'] = data.get('incidents', 0)
                    lap_summary['incident_limit'] = data.get('incidents_limit', 0)
                    lap_summary['session_type'] = S.meta_cache.get('session_type', 'Unknown') if hasattr(S, 'meta_cache') else 'Unknown'
                    lap_summary['car'] = S.meta_cache.get('car', 'Car') if hasattr(S, 'meta_cache') else 'Car'
                    lap_summary['track'] = S.meta_cache.get('track', 'Track') if hasattr(S, 'meta_cache') else 'Track'
                    lap_summary['driver'] = S.meta_cache.get('driver', 'Driver') if hasattr(S, 'meta_cache') else 'Driver'
                    lap_summary['lap_history'] = [{'lap': lt['lap'], 'time': lt['time']} for lt in S.lap_times[-5:]]
                    await broadcast('ai_lap_debrief', lap_summary)
                    S.accum.reset()
                elif timed_out:
                    S._lap_change_pending = None
            S.prev_lap  = cur
            S.fuel_prev = data.get('fuel')

            # ── Accumulator tick ─────────────────────────────────────────────
            if data.get('on_track') and not data.get('in_garage'):
                S.accum.tick(data)

            # ── Offtrack + penalty event detection ───────────────────────────
            is_off   = data.get('is_offtrack', False)
            was_off  = not S.prev_on_track
            tow_now  = float(data.get('tow_time', 0) or 0)
            tow_prev = S.prev_tow
            dist_pct = round(data.get('lap_dist', 0) * 100, 1)
            lap_num  = int(data.get('lap', 0))

            # Offtrack via PlayerTrackSurface (works in race sessions)
            if is_off and not was_off:
                S.accum.log_event('offtrack', data)
                print(f"[FSS] OFFTRACK detected via PlayerTrackSurface at {dist_pct}%")
                await broadcast('ai_event', {
                    'event':     'offtrack',
                    'dist_pct':  dist_pct,
                    'speed_kph': data.get('speed_kph', 0),
                    'lap':       lap_num,
                    'surface':   data.get('surface_name', 'offtrack'),
                })
            S.prev_on_track = not is_off

            # Penalty via tow_time — works in ALL sessions including Offline Testing
            # tow_time stays elevated for the full penalty duration — only fire on RISING edge
            # Also debounce: ignore if last penalty was < 3s ago
            tow_cooldown_ok = (time.time() - getattr(S, '_last_penalty_t', 0)) > 3.0
            if tow_now > 0.1 and tow_prev < 0.1 and tow_cooldown_ok:
                S._last_penalty_t = time.time()
                S.accum.log_event('penalty', data, f'tow {tow_now:.1f}s')
                print(f"[FSS] PENALTY detected: {tow_now:.1f}s tow at {dist_pct}%")
                await broadcast('ai_event', {
                    'event':       'penalty',
                    'dist_pct':    dist_pct,
                    'tow_seconds': round(tow_now, 1),
                    'lap':         lap_num,
                    'speed_kph':   data.get('speed_kph', 0),
                })
                # Also fire offtrack if PlayerTrackSurface unavailable (Offline Testing)
                if data.get('sdk_surface_unavailable') and not (is_off and not was_off):
                    S.accum.log_event('offtrack', data, 'inferred from penalty')
                    print(f"[FSS] OFFTRACK inferred from penalty (Offline Testing mode)")
                    await broadcast('ai_event', {
                        'event':     'offtrack',
                        'dist_pct':  dist_pct,
                        'speed_kph': data.get('speed_kph', 0),
                        'lap':       lap_num,
                        'surface':   'offtrack',
                    })
            S.prev_tow = tow_now

            # ── Debug: print key fields every 5s ─────────────────────────────
            if not hasattr(S,'_dbg_t'): S._dbg_t = 0
            if time.time() - S._dbg_t > 5:
                S._dbg_t = time.time()
                raw_s = data.get('track_surface_raw_debug','?')
                print(f"[DBG] on_track={data.get('on_track')} surf={data.get('surface_name','?')} raw_surf={raw_s} is_off={data.get('is_offtrack','?')} "
                      f"fuel={data.get('fuel',0):.1f}L fpl={data.get('fuel_per_lap_est','?')} "
                      f"ft={data.get('front_temp_avg','?')}C lf_wm={data.get('lf_wm','?')}% "
                      f"tow={data.get('tow_time',0)}")

            await broadcast('telemetry', data)
        except Exception as e:
            pass

async def iracing_monitor():
    if not HAS_IRSDK: return
    while True:
        await asyncio.sleep(2)
        try:
            if not S.ir: S.ir = irsdk.IRSDK()
            was = S.connected
            ok  = S.ir.startup()
            S.connected = bool(ok and S.ir.is_connected)
            if S.connected and not was:
                print("[FSS] ✓ iRacing LIVE!")
                S.meta_sent = False
                # Reset sector/gap state for new session
                S.sectors = SectorTracker()
                S.gaps    = GapTracker()
                S.accum   = LapAccumulator()
                S.prev_lap = -1
                S.prev_tow = 0.0
                S.prev_on_track = True
                await broadcast('status', {'connected':True,'source':'iracing','demo_mode':False})
                await broadcast('iracing_connected', {})
                # Resend meta with real iRacing data now that we're connected
                real_meta = get_meta(S.ir)
                S.meta_cache = real_meta
                # Cache player car index for lap time lookup
                try:
                    di = S.ir['DriverInfo'] or {}
                    S.player_car_idx = int(di.get('DriverCarIdx', 0) or 0)
                except:
                    S.player_car_idx = 0
                await broadcast('meta', real_meta)
                S.meta_sent = True
                print(f"[FSS] Meta sent: driver={real_meta.get('driver')} car={real_meta.get('car')} track={real_meta.get('track')} player_idx={S.player_car_idx}")
            elif not S.connected and was:
                print("[FSS] iRacing disconnected")
                await broadcast('status', {'connected':False,'demo_mode':True})
                await broadcast('iracing_disconnected', {})
        except: pass

async def handler(ws):
    S.clients.add(ws)
    S.meta_sent = False
    print(f"[FSS] Browser connected ({len(S.clients)} total)")
    try:
        await broadcast('status', {
            'connected':  S.connected,
            'demo_mode':  not HAS_IRSDK or not S.connected,
            'source':     'iracing' if S.connected else 'demo'})
        async for msg in ws:
            try:
                cmd = json.loads(msg)
                if cmd.get('type') == 'ping':
                    await ws.send(json.dumps({'type':'pong','ts':time.time()}))
                elif cmd.get('type') == 'ptt_end':
                    await broadcast('ptt', {'active':False,'transcript':cmd.get('text','')})
            except: pass
    except: pass
    finally:
        S.clients.discard(ws)
        print(f"[FSS] Browser disconnected ({len(S.clients)} remaining)")

async def main():
    threading.Thread(target=run_http, daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()
    url = f'http://localhost:{HTTP_PORT}/{HTML_NAME}'
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  FSS is ready! Chrome is opening...                  ║")
    print(f"║  URL: {url:<47}║")
    print("║  Go to LIVE tab → CONNECT                            ║")
    print(f"║  Mode: {'LIVE (iRacing)' if HAS_IRSDK else 'DEMO (install irsdk for live)':^46}║")
    print("║  Ctrl+C to stop                                      ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    try:
        async with websockets.serve(handler, '0.0.0.0', WS_PORT,
                                    origins=None, ping_interval=20, ping_timeout=10):
            await asyncio.gather(telemetry_loop(), iracing_monitor())
    except OSError as e:
        if '10048' in str(e) or 'in use' in str(e).lower():
            print(f"\n✗ Port {WS_PORT} already in use — is another bridge running?")
            print("  Check Task Manager for python.exe and close it.")
            input("Press Enter to exit...")
        else: raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[FSS] Stopped. Goodbye!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback; traceback.print_exc()
        input("Press Enter to exit...")
