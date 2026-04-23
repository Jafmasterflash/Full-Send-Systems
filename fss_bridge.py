#!/usr/bin/env python3
"""
Full Send Systems — Live Bridge v1.3
=====================================
Reads iRacing shared memory and streams live telemetry
to the FSS browser app via WebSocket.

HOW TO USE:
  1. Double-click FSS_START.bat  (Windows — recommended)
  2. OR run:  python fss_bridge.py

REQUIREMENTS:
  pip install irsdk websockets
"""

import asyncio, json, time, math, sys, os, threading
import webbrowser, subprocess, http.server, socketserver
from pathlib import Path

print()
print("╔══════════════════════════════════════════════════════╗")
print("║         FULL SEND SYSTEMS  —  Live Bridge v1.3      ║")
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
HTML_NAME = Path(HTML_FILE).name if HTML_FILE else 'fss_b110_complete.html'
if HTML_FILE:
    print(f"✓ App: {HTML_NAME}")
else:
    print("  ! Put fss_b110_complete.html in the same folder as fss_bridge.py")

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

# ── Channels ──────────────────────────────────────────────────────────────────
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
}

# ── State ─────────────────────────────────────────────────────────────────────
class S:
    clients=set(); ir=None; connected=False; meta_sent=False; lap_times=[]

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
        }

demo = Demo()

def read_ir(ir):
    d={}
    for k,v in CHANNELS.items():
        try:
            val=ir[k]
            if val is not None: d[v]=val
        except: pass
    d['speed_kph']=round(d.get('speed_ms',0)*3.6,1)
    fph=d.get('fuel_per_hour',0); bl=d.get('best_lap',90) or 90
    if fph>0:
        fpl=fph*(bl/3600); d['fuel_per_lap_est']=round(fpl,3)
        fuel=d.get('fuel',0)
        if fuel>0: d['laps_fuel_remain']=round(fuel/fpl,1)
    lf=d.get('lf_tcm',0); rf=d.get('rf_tcm',0)
    lr=d.get('lr_tcm',0); rr=d.get('rr_tcm',0)
    if lf and rf: d['front_temp_avg']=round((lf+rf)/2,1)
    if lr and rr: d['rear_temp_avg']=round((lr+rr)/2,1)
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
        return {'driver':dr.get('UserName','Driver'),'car':dr.get('CarScreenName','Car'),
                'track':wi.get('TrackDisplayName','Track'),
                'track_len':float(str(wi.get('TrackLength','4.5 km')).split()[0]),
                'session_type':sess.get('SessionType','Practice'),
                'max_fuel':float(dr.get('CarFuelMaxLtr',55)),
                'num_cars':len(di.get('Drivers',[])),
                'display_units':int(du),'use_fahrenheit':int(du)==0}
    except Exception as e:
        return {'driver':'Driver','car':'Car','track':'Track',
                'max_fuel':55,'use_fahrenheit':False,'error':str(e)}

async def broadcast(t,d):
    if not S.clients: return
    msg=json.dumps({'type':t,'ts':time.time(),'data':d})
    dead=set()
    for ws in list(S.clients):
        try: await ws.send(msg)
        except: dead.add(ws)
    S.clients-=dead

async def telemetry_loop():
    prev=-1
    while True:
        await asyncio.sleep(TICK_SLEEP)
        if not S.clients: continue
        try:
            if HAS_IRSDK and S.ir and S.connected:
                S.ir.freeze_var_buffer_latest(); data=read_ir(S.ir)
            else:
                data=demo.tick(TICK_SLEEP)
            if not S.meta_sent:
                await broadcast('meta',get_meta(S.ir if S.connected else None))
                S.meta_sent=True
            cur=int(data.get('lap',0))
            if cur!=prev and prev>=0:
                last=data.get('last_lap',0)
                if last and last>5:
                    S.lap_times.append({'lap':prev,'time':round(last,3)})
                    await broadcast('lap_complete',{'lap':prev,'time':round(last,3),
                        'fuel':round(data.get('fuel',0),2),'lap_times':S.lap_times[-10:]})
            prev=cur
            await broadcast('telemetry',data)
        except: pass

async def iracing_monitor():
    if not HAS_IRSDK: return
    while True:
        await asyncio.sleep(2)
        try:
            if not S.ir: S.ir=irsdk.IRSDK()
            was=S.connected
            ok=S.ir.startup(); S.connected=bool(ok and S.ir.is_connected)
            if S.connected and not was:
                print("[FSS] ✓ iRacing LIVE!"); S.meta_sent=False
                await broadcast('status',{'connected':True,'source':'iracing','demo_mode':False})
            elif not S.connected and was:
                print("[FSS] iRacing disconnected")
                await broadcast('status',{'connected':False,'demo_mode':True})
        except: pass

async def handler(ws):
    S.clients.add(ws); S.meta_sent=False
    print(f"[FSS] Browser connected ({len(S.clients)} total)")
    try:
        await broadcast('status',{
            'connected':S.connected,'demo_mode':not HAS_IRSDK or not S.connected,
            'source':'iracing' if S.connected else 'demo'})
        async for msg in ws:
            try:
                cmd=json.loads(msg)
                if cmd.get('type')=='ping':
                    await ws.send(json.dumps({'type':'pong','ts':time.time()}))
                elif cmd.get('type')=='ptt_end':
                    await broadcast('ptt',{'active':False,'transcript':cmd.get('text','')})
            except: pass
    except: pass
    finally:
        S.clients.discard(ws)
        print(f"[FSS] Browser disconnected ({len(S.clients)} remaining)")

async def main():
    threading.Thread(target=run_http,daemon=True).start()
    threading.Thread(target=open_browser,daemon=True).start()
    url=f'http://localhost:{HTTP_PORT}/{HTML_NAME}'
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
        async with websockets.serve(handler,'0.0.0.0',WS_PORT,
                                     origins=None,ping_interval=20,ping_timeout=10):
            await asyncio.gather(telemetry_loop(),iracing_monitor())
    except OSError as e:
        if '10048' in str(e) or 'in use' in str(e).lower():
            print(f"\n✗ Port {WS_PORT} already in use — is another bridge running?")
            print("  Check Task Manager for python.exe and close it.")
        else: raise

if __name__=='__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[FSS] Stopped. Goodbye!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback; traceback.print_exc()
        input("Press Enter to exit...")
