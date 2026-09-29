import React, { useEffect, useRef, useState } from 'react';
import { Demo, LocalEngine, Packet, XY, Road, roadsFromGeoJSON, matchRoad, forestPredict } from './engine';
import './style.css';
const API = (import.meta as any).env.VITE_API_URL || 'http://127.0.0.1:8000';
const fmt = (n: any, d = 1) => typeof n === 'number' && Number.isFinite(n) ? n.toFixed(d) : '—';
const save = (name: string, data: any) => { data = { ...data, project: 'KinematiX', team: { name: 'ORIGIN X', id: '134028' } }; if ((window as any).KinematiX?.saveReport) {
    (window as any).KinematiX.saveReport(name, JSON.stringify(data, null, 2));
    return;
} const u = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = u; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(u), 1000); };
type Point = {
    reference?: XY;
    estimated: XY;
    baseline?: XY;
    uncertainty?: number;
    error?: number;
    t?: number;
};
function Plot({ points, roads = [], matched = null }: {
    points: Point[];
    roads?: Road[];
    matched?: XY | null;
}) {
    const all = points.flatMap(p => [p.estimated, ...(p.reference ? [p.reference] : []), ...(p.baseline ? [p.baseline] : [])]);
    if (!all.length)
        all.push([0, 0], [100, 100]);
    const xs = all.map(p => p[0]), ys = all.map(p => p[1]);
    const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
    const scale = Math.min(820 / Math.max(100, xmax - xmin), 420 / Math.max(100, ymax - ymin));
    const cx = (xmin + xmax) / 2, cy = (ymin + ymax) / 2;
    const xy = (p: XY) => [460 + (p[0] - cx) * scale, 250 - (p[1] - cy) * scale];
    const path = (key: 'reference' | 'estimated' | 'baseline') => points.filter(p => p[key]).map((p, i) => `${i ? 'L' : 'M'}${xy(p[key] as XY).join(',')}`).join(' ');
    const last = points.at(-1), pos = last ? xy(last.estimated) : [460, 250];
    return <svg className="plot" viewBox="0 0 920 500" role="img" aria-label="EKF east-north trajectory in metres"><defs><pattern id="grid" width="46" height="50" patternUnits="userSpaceOnUse"><path d="M 46 0 L 0 0 0 50" fill="none" stroke="#303238" strokeWidth=".6"/></pattern><radialGradient id="glow"><stop stopColor="#f49b59" stopOpacity=".1"/><stop offset="1" stopColor="#f49b59" stopOpacity="0"/></radialGradient></defs><rect width="920" height="500" fill="url(#grid)"/><circle cx="460" cy="250" r="240" fill="url(#glow)"/>
    {roads.map((r, i) => <path key={i} d={`M${xy(r.a)} L${xy(r.b)}`} stroke="#53677a" strokeWidth="5" opacity=".45"/>)}
    <path d={path('baseline')} className="baseline"/><path d={path('reference')} className="reference"/><path d={path('estimated')} className="estimated"><title>EKF trajectory</title></path>
    {last && <><circle cx={pos[0]} cy={pos[1]} r={Math.min(110, (last.uncertainty || 3) * scale)} fill="#f49b59" opacity=".07" stroke="#f49b59"/><circle cx={pos[0]} cy={pos[1]} r="11" fill="#352619" stroke="#f49b59" strokeWidth="2"/><circle cx={pos[0]} cy={pos[1]} r="4" fill="#fff0de"/></>}
    {matched && <circle cx={xy(matched)[0]} cy={xy(matched)[1]} r="7" fill="#eab676"/>}
    <text x="28" y="32" fill="#81949d" fontSize="11" letterSpacing="2">LOCAL ENU • METRES</text><text x="870" y="35" fill="#93a6b0" fontSize="13">N ↑</text>
    <path d="M30 454v6h100v-6" stroke="#8d9da5" fill="none"/><text x="30" y="480" fill="#81949d" fontSize="11">{fmt(100 / scale, 0)} m</text>
  </svg>;
}
function Spark({ values }: {
    values: number[];
}) { const max = Math.max(.1, ...values.map(Math.abs)); return <svg viewBox="0 0 240 48" className="spark"><path d="M0 24H240" stroke="#273940"/><polyline points={values.map((n, i) => `${i * 240 / Math.max(1, values.length - 1)},${24 - n / max * 20}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.5"/></svg>; }
export default function App() {
    const isAndroid = Boolean((window as any).KinematiX);
    const [serverAddress, setServerAddress] = useState(() => localStorage.getItem('kinematix-server') || API);
    const [connectedServer, setConnectedServer] = useState('');
    const [checkingServer, setCheckingServer] = useState(false);
    const [serverMessage, setServerMessage] = useState('Requires connection to the desktop evaluation server.');
    const [gnssStatus, setGnssStatus] = useState('Searching for GPS position…');
    const [rawImu, setRawImu] = useState<{acc:number[], gyro:number[], time:number} | null>(null);
    const [fullscreen, setFullscreen] = useState(Boolean((window as any).KinematiX?.isFullscreen?.()));
    const [tab, setTab] = useState('cockpit'), [running, setRunning] = useState(false), [packet, setPacket] = useState<Packet | null>(null), [points, setPoints] = useState<Point[]>([]), [denied, setDenied] = useState(false);
    const [backend, setBackend] = useState(false), [result, setResult] = useState<any>(null), [busy, setBusy] = useState(false), [error, setError] = useState(''), [recording, setRecording] = useState('saved_example'), [duration, setDuration] = useState(30), [model, setModel] = useState<any>(null), [events, setEvents] = useState<string[]>(['KinematiX initialized. Local demonstration ready.']);
    const [roads, setRoads] = useState<Road[]>([]), [roadName, setRoadName] = useState(''), [live, setLive] = useState(false), [origin, setOrigin] = useState<XY | null>(null), [sensorHistory, setSensorHistory] = useState<number[]>([]), [report, setReport] = useState<any>(null);
    const demo = useRef(new Demo()), phone = useRef(new LocalEngine()), buffer = useRef<number[][]>([]), lastFix = useRef<any>(null), fixVersion = useRef(-1), forward = useRef<XY | number[]>([0, 0, 0]), correlation = useRef([0, 0, 0]), lastSpeed = useRef(0), lastMode = useRef(''), liveOrigin = useRef<XY | null>(null), imuPrevious = useRef(0), speedOffset = useRef(0);
    const log = (s: string) => setEvents(e => [`${new Date().toLocaleTimeString()}  ${s}`, ...e].slice(0, 24));
    const accept = (p: Packet) => { setPacket(p); setPoints(a => [...a, { estimated: [p.corrected_pos.x, p.corrected_pos.y], reference: p.ref_pos ? [p.ref_pos.x, p.ref_pos.y] : undefined, baseline: p.raw_dr_pos ? [p.raw_dr_pos.x, p.raw_dr_pos.y] : undefined, uncertainty: p.uncertainty_m } as Point].slice(-1600)); setSensorHistory(a => [...a, p.imu.ax].slice(-100)); if (p.state !== lastMode.current) {
        lastMode.current = p.state;
        log(p.state.replaceAll('_', ' '));
    } if (p.shock)
        log('Shock detected • acceleration update suppressed'); };
    useEffect(() => {
        if (isAndroid) return;
        let active = true;
        const check = async () => {
            try {
                const response = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(4000) });
                const health = await response.json();
                if (!response.ok || health.project !== 'KinematiX' || health.status !== 'ready') throw Error();
                if (active) { setConnectedServer(API); setBackend(true); }
            } catch { if (active) { setBackend(false); setConnectedServer(''); } }
        };
        check(); const timer = setInterval(check, 10000);
        return () => { active = false; clearInterval(timer); };
    }, [isAndroid]);
    useEffect(() => { fetch('./speed_model.json').then(r => r.ok ? r.json() : null).then(setModel).catch(() => { }); fetch('./benchmark_summary.json').then(r => r.ok ? r.json() : null).then(setReport).catch(() => { }); }, []);
    useEffect(() => { if (!running || live)
        return; const id = setInterval(() => accept(demo.current.step()), 100); return () => clearInterval(id); }, [running, live]);
    useEffect(() => {
        const handler = (event: any) => {
            if (!live)
                return;
            const d = event.detail;
            if (d.type === 'gnss-status') { setGnssStatus(d.message); return; }
            if (d.type === 'error') {
                setError(d.message);
                setLive(false);
                setRunning(false);
                return;
            }
            if (d.type === 'gnss') {
                lastFix.current = d;
                return;
            }
            if (d.type === 'imu') setRawImu({acc:d.acc, gyro:d.gyro, time:d.time});
            if (d.type !== 'imu' || !lastFix.current)
                return;
            const fix = lastFix.current;
            let o = liveOrigin.current;
            if (!o) {
                o = [fix.lat, fix.lon];
                liveOrigin.current = o;
                setOrigin(o);
                phone.current.v = fix.speed;
                phone.current.h = (90 - fix.bearing) * Math.PI / 180;
            }
            const g = d.gravity as number[], a = d.acc as number[], gyro = d.gyro as number[];
            const gn = Math.hypot(...g) || 9.80665, u = g.map(v => v / gn), lin = a.map((v, i) => v - g[i]);
            const vertical = lin.reduce((s, v, i) => s + v * u[i], 0), yaw = gyro.reduce((s: number, v: number, i: number) => s + v * u[i], 0);
            const horizontal = Math.sqrt(Math.max(0, lin.reduce((s, v) => s + v * v, 0) - vertical * vertical));
            buffer.current = [...buffer.current, [horizontal, vertical, yaw, Math.hypot(...gyro)]].slice(-20);
            const pred = forestPredict(model, buffer.current);
            const dt = imuPrevious.current ? Math.min(.5, Math.max(.001, (d.time - imuPrevious.current) / 1000)) : .1;
            imuPrevious.current = d.time;
            let measurement: any = undefined;
            if (fix.time !== fixVersion.current && !denied) {
                const dv = fix.speed - lastSpeed.current;
                correlation.current = correlation.current.map((v, i) => v * .98 + lin[i] * dv);
                const norm = Math.hypot(...correlation.current);
                if (norm > 1)
                    forward.current = correlation.current.map(v => v / norm);
                lastSpeed.current = fix.speed;
                fixVersion.current = fix.time;
                measurement = { x: (fix.lon - o[1]) * Math.PI / 180 * 6378137 * Math.cos(o[0] * Math.PI / 180), y: (fix.lat - o[0]) * Math.PI / 180 * 6378137, v: fix.speed, h: (90 - fix.bearing) * Math.PI / 180, accuracy: fix.accuracy };
                if (pred !== undefined)
                    speedOffset.current = fix.speed - pred;
            }
            const acc = lin.reduce((s, v, i) => s + v * forward.current[i], 0), shock = Math.abs(vertical) > 3.5 || Math.hypot(...lin) > 10;
            const e = phone.current;
            e.step(dt, yaw, model?.forward_acceleration_mode === 'speed-update-only' ? 0 : acc, measurement, shock, pred !== undefined ? Math.max(0, pred + speedOffset.current) : undefined);
            accept({ source: 'phone', timestamp: e.time, state: e.mode, gnss_available: e.time - e.lastFix < 1.5, distance_travelled: e.distance, outage_duration_s: e.outage, position_error_m: null, speed_mps: e.v, heading_deg: e.h * 180 / Math.PI, uncertainty_m: 2.448 * Math.sqrt(e.variance), corrected_pos: { x: e.x, y: e.y }, shock, imu: { ax: acc, ay: horizontal, az: vertical, gz: yaw } });
        };
        window.addEventListener('kinematix-sensor', handler);
        return () => window.removeEventListener('kinematix-sensor', handler);
    }, [live, model, denied]);
    async function connectServer() {
        setCheckingServer(true); setBackend(false); setConnectedServer('');
        try {
            const url = new URL(serverAddress.trim());
            if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw Error('Enter an HTTP or HTTPS server address without credentials or query parameters.');
            const address = url.href.replace(/\/$/, '');
            const response = await fetch(`${address}/api/health`, { signal: AbortSignal.timeout(8000) });
            const health = await response.json();
            if (!response.ok || health.project !== 'KinematiX' || health.status !== 'ready') throw Error('This address is not a ready KinematiX evaluation server.');
            setConnectedServer(address); setBackend(true); localStorage.setItem('kinematix-server', address);
            setServerMessage('Connected. Uploaded CSV files will be sent to this server for evaluation.');
        } catch (e: any) { setServerMessage(e.message.includes('address') ? e.message : 'Cannot connect. Check the laptop address, backend and Wi-Fi connection.'); }
        finally { setCheckingServer(false); }
    }
    async function evaluate(file?: File) { if (!backend || !connectedServer) return; setBusy(true); setError(''); try {
        let r;
        if (file) {
            const f = new FormData();
            f.append('file', file);
            r = await fetch(`${connectedServer}/api/evaluation/upload`, { method: 'POST', body: f });
        }
        else
            r = await fetch(`${connectedServer}/api/evaluation/preset?preset_id=${recording}&duration=${duration}`);
        const data = await r.json();
        if (!r.ok)
            throw Error(data.detail || 'Evaluation failed');
        setResult(data);
        setBackend(true);
        log(`Measured replay completed • ${data.track_name}`);
    }
    catch (e: any) {
        setError(e.message === 'Failed to fetch' ? 'Start the Python backend to run a new evaluation. Saved measured results remain available below.' : e.message);
    }
    finally {
        setBusy(false);
    } }
    function reset() { setGnssStatus('Searching for GPS position…'); setRawImu(null); demo.current = new Demo(); phone.current = new LocalEngine(); buffer.current = []; lastFix.current = null; liveOrigin.current = null; setOrigin(null); setRoads([]); setRoadName(''); imuPrevious.current = 0; fixVersion.current = -1; forward.current = [0, 0, 0]; correlation.current = [0, 0, 0]; setPacket(null); setPoints([]); setDenied(false); lastMode.current = ''; log('Session reset'); }
    function toggleLive() { const bridge = (window as any).KinematiX; if (!bridge) {
        setError('Live IMU capture is available in the Android app. Use the local demo in a desktop browser.');
        return;
    } const next = !live; reset(); setLive(next); setRunning(next); if (next)
        bridge.startSensors();
    else
        bridge.stopSensors(); log(next ? 'Phone sensors requested • acquire GNSS before driving' : 'Phone sensors stopped'); }
    useEffect(() => {
        const changed = () => setFullscreen(Boolean(document.fullscreenElement));
        document.addEventListener('fullscreenchange', changed);
        return () => document.removeEventListener('fullscreenchange', changed);
    }, []);
    async function toggleFullscreen() {
        const bridge = (window as any).KinematiX;
        if (bridge?.setFullscreen) {
            bridge.setFullscreen(!fullscreen);
            setFullscreen(!fullscreen);
            return;
        }
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
            else setError('Fullscreen is available in the Android app or a supporting browser.');
        } catch { setError('Fullscreen is unavailable in this browser window.'); }
    }
    const shown = tab === 'evidence'  && result ? result.trajectory : points;
    const matched = packet && roads.length ? matchRoad([packet.corrected_pos.x, packet.corrected_pos.y], packet.heading_deg * Math.PI / 180, roads) : null;
    return <div className={(window as any).KinematiX ? "app native-app" : "app"}><aside><a className="brand" href="#" onClick={e => e.preventDefault()}><span className="brand-icon">K<span>↗</span></span><span>Kinemati<span className="mint">X</span></span></a><div className="nav-label">WORKSPACE</div><nav>{[['cockpit', '◈', 'Navigation'], ['evidence', '⌁', 'Evaluation'], ['system', '▦', 'System']].map(([id, icon, label]) => <button className={tab === id ? 'selected' : ''} key={id} onClick={() => { setTab(id); setError(''); }}><span>{icon}</span>{label}<b>↗</b></button>)}</nav><div className="sidebar-note"><span className="eyebrow">SMART INDIA HACKATHON</span><p>ORIGIN <b>X</b></p><div className="mini-line"/><small>Team ID 134028<br />Problem Statement 26168</small></div><div className="side-status"><i className={backend ? 'dot' : 'dot amber'}/>{backend ? 'Evaluation engine ready' : 'Local demo ready'}<small>v5.8 · research prototype</small></div></aside>
  <main><header><div className="breadcrumb">KINEMATIX <span>/</span> {tab === 'cockpit' ? 'NAVIGATION LAB' : tab === 'evidence' ? 'BENCHMARK STUDIO' : 'SYSTEM DESIGN'}</div><div className="header-right"><span className="team-signature">ORIGIN <b>X</b><small>TEAM ID 134028</small></span><button className="fullscreen-button" onClick={toggleFullscreen} aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"} aria-pressed={fullscreen}>{fullscreen ? "↙" : "↗"}<span>{fullscreen ? "Exit fullscreen" : "Fullscreen"}</span></button></div></header>
  <section className="page-heading"><div><div className="eyebrow">{tab === 'cockpit' ? 'VEHICLE NAVIGATION' : tab === 'evidence' ? 'IO-VNBD DATASET REPLAY' : 'TECHNICAL OVERVIEW'}</div><h1>{tab === 'cockpit' ? 'Navigation console' : tab === 'evidence' ? 'Drive evaluation' : 'System architecture'}</h1><p>{tab === 'cockpit' ? 'Position, motion and GNSS status.' : tab === 'evidence' ? 'Compare estimated motion with a recorded reference.' : 'Sensor processing, model deployment and validation status.'}</p></div><div className="source-pill"><i className="dot"/>{live ? 'LIVE PHONE' : tab === 'evidence' ? 'RECORDED DATA' : 'SIMULATED DRIVE'}</div></section>
  {error && <div className="error" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
  {tab === 'cockpit' && <><section className="panel live-sensors"><div className="sensor-heading"><h2>Phone sensors</h2><button onClick={toggleLive}>{live ? 'Stop phone capture' : 'Connect phone sensors'}</button></div>{live ? <><p role="status">{!rawImu ? 'Waiting for sensor samples…' : !packet ? `IMU receiving · ${gnssStatus}` : `IMU receiving · ${gnssStatus}`}</p><div className="raw-sensor-grid">{[['Accelerometer', rawImu?.acc, 'm/s²'], ['Gyroscope', rawImu?.gyro, 'rad/s']].map(([label, values, unit]) => <div key={label as string}><h3>{label as string} <small>{unit as string}</small></h3><div className="sensor-axes">{['X','Y','Z'].map((axis,i) => <span key={axis}>{axis} <b>{fmt((values as number[] | undefined)?.[i],3)}</b></span>)}</div></div>)}</div><small>Raw phone axes; accelerometer includes gravity. Speed is an estimate, not a raw sensor reading.</small></> : <p>Connect to see live accelerometer and gyroscope readings.</p>}</section><div className="metrics"><Metric label="TRACKING MODE" value={live && !packet ? 'WAITING FOR GNSS' : packet?.state.replaceAll('_', ' ') || 'READY'} sub={live ? 'Phone sensor stream' : 'Simulated sensor fusion'} state/><Metric label="FORWARD SPEED" value={fmt((packet?.speed_mps || 0) * 3.6)} unit="km/h" sub="Vehicle motion estimate"/><Metric label="POSITION ERROR" value={fmt(packet?.position_error_m)} unit="m" sub={live ? 'No independent truth on live phone' : 'Against synthetic reference'}/><Metric label="OUTAGE DURATION" value={fmt(packet?.outage_duration_s || 0)} unit="s" sub="Detected after 1.5 s without fixes"/></div>
    <div className="cockpit-grid"><div className="panel map-panel"><div className="panel-header"><div><span className="eyebrow">TRAJECTORY VIEW</span><h2>EKF vehicle trajectory</h2></div><span className="badge">{live && !packet ? 'WAITING FOR GNSS' : running ? '● TRACKING' : '○ PAUSED'} · 10 Hz</span></div><Plot points={shown} roads={roads} matched={matched}/><div className="map-bottom"><div className="legend"><span className="mint">━ EKF trajectory</span><span className="blue">{!live && '┄ Synthetic reference'}</span>{!live && <span className="coral">━ Constant-speed baseline</span>}</div><span>{fmt(packet?.distance_travelled || 0, 0)} m travelled</span></div><div className="controls"><button className="primary" onClick={() => setRunning(!running)} disabled={live}>{running ? 'Ⅱ Pause' : '▶ Start drive'}</button><button className={denied ? 'danger active' : 'danger'} onClick={() => { setDenied(!denied); demo.current.denied = !denied; log(!denied ? 'GNSS feed disabled' : 'GNSS feed restored'); }}>{denied ? '↗ Restore GNSS' : '⊘ Simulate blackout'}</button><button onClick={() => { demo.current.shock = true; }} disabled={live || !running}>⌁ Inject pothole</button><button className="icon-button" onClick={reset} title="Reset session">↺</button></div></div>
    <div className="right-stack"><div className="panel signal-panel"><div className="eyebrow">SIGNAL HEALTH</div><div className="signal-title"><i className={denied ? 'dot amber' : 'dot'}/><h2>{denied ? 'Inertial continuity' : 'GNSS + inertial'}</h2></div><div className="signal-bars">{[12, 22, 31, 43, 53, 62, 72, 82, 90, 96, 100, 100].map((v, i) => <i key={i} style={{ height: v + '%', opacity: denied ? .15 : 1 }}/>)}</div><div className="pair"><span>Heading</span><b>{fmt(packet?.heading_deg || 0)}°</b></div><div className="pair"><span>Uncertainty indicator</span><b>± {fmt(packet?.uncertainty_m)} m</b></div><p className="fine">Uncertainty is a model estimate, not an accuracy guarantee.</p></div><div className="panel sensor-panel"><div className="eyebrow">MOTION OBSERVER</div><div className="pair"><h2>Forward acceleration</h2><b className="mint">{fmt(packet?.imu.ax, 2)}</b></div><Spark values={sensorHistory}/><p className="fine">m/s² · shock gating suppresses large impulses</p></div><div className="callout"><span>◉</span><div><b>Session source</b><p>{live ? 'Live phone IMU. Navigation starts after a usable GNSS speed and heading fix.' : 'This drive uses simulated sensors. Open Evaluation for measured IO-VNBD results.'}</p></div></div></div></div>
    <div className="bottom-grid"><div className="panel"><div className="panel-header"><h2>Session events</h2><span className="eyebrow">LATEST FIRST</span></div><div className="events">{events.slice(0, 5).map((e, i) => <div key={i}><i className="dot"/>{e}</div>)}</div></div><div className="panel integrations"><h2>Phone & data</h2><p>Connect the Android sensors or inspect an offline road extract.</p><div className="inline-actions"><button onClick={toggleLive}>{live ? 'Stop phone capture' : 'Connect phone sensors'}</button><button onClick={() => save('kinematix-session.json', { source: packet?.source, points, events })} disabled={!points.length}>Export session ↗</button></div><label className="file-label">＋ Import road GeoJSON<input type="file" accept=".json,.geojson" onChange={async (e) => { const f = e.target.files?.[0]; if (!f)
            return; try {
            const o = origin;
            if (!o)
                throw Error('Acquire a phone GNSS fix first, to establish the road-map origin.');
            setRoads(roadsFromGeoJSON(JSON.parse(await f.text()), o));
            setRoadName(f.name);
        }
        catch (x: any) {
            setError(x.message);
        } }}/></label><small>{roadName || 'Offline matching is gated by distance, heading, and ambiguity.'}</small></div></div></>}
  {tab === 'evidence' && <>{isAndroid && <div className="panel result-details"><h2>Desktop evaluation server</h2><p>Optional: connect your phone and laptop to the same Wi-Fi. Start the backend on the laptop with network access, then enter its address below.</p><label htmlFor="evaluation-server">Server address</label><div className="server-connect"><input id="evaluation-server" type="url" placeholder="http://192.168.1.10:8000" value={serverAddress} disabled={busy || checkingServer} onChange={e => { setServerAddress(e.target.value); setBackend(false); setConnectedServer(''); setServerMessage('Requires connection to the desktop evaluation server.'); }}/><button disabled={busy || checkingServer} onClick={connectServer}>{checkingServer ? 'Checking…' : 'Connect server'}</button></div><p role="status">{serverMessage}</p><label className="file-label" aria-disabled={!backend || busy}>Upload CSV · backend required<input disabled={!backend || busy} type="file" accept=".csv" onChange={e => { if (e.target.files?.[0]) evaluate(e.target.files[0]); e.target.value = ''; }}/></label><p className="fine">Saved examples and live navigation work offline.</p></div>}{!isAndroid && !backend && <p role="status" className="evaluation-help">Local evaluation engine unavailable. Start scripts/Start-KinematiX.ps1; this page reconnects automatically. Saved examples remain available.</p>}{!isAndroid && <div className="panel evaluation-controls"><div><label>RECORDING</label><select value={recording} onChange={e => setRecording(e.target.value)}><option value="saved_example">Selected saved example · below 10%</option><option value="test">S-Vw1 · stationary calibration</option><option value="held_out">S-S1 · development holdout</option><option value="mixed">S-M · training drive</option><option value="motorway">S-Vw4 · training drive</option></select></div><div><label>GNSS BLACKOUT</label><select disabled={recording === 'saved_example'} value={recording === 'saved_example' ? 10 : duration} onChange={e => setDuration(+e.target.value)}>{[10, 30, 60, 120].map(n => <option key={n} value={n}>{n} seconds</option>)}</select></div><button className="primary" disabled={busy || (recording === 'saved_example' ? !report : !backend)} onClick={() => recording === 'saved_example' ? setResult(report.runs.find((r: any) => r.split === 'development validation' && r.sih_target_met && r.drift_percentage < 10) || report.runs[0]) : evaluate()}>{busy ? 'Evaluating…' : recording === 'saved_example' ? 'Open saved example ↗' : 'Run measured replay ↗'}</button><label className="file-label" aria-disabled={!backend || busy}>Upload CSV<input disabled={busy || !backend} type="file" accept=".csv" onChange={e => e.target.files?.[0] && evaluate(e.target.files[0])}/></label></div>}
    {!result && <div className="panel empty-state"><span className="empty-icon">⌁</span><h2>Saved drive evaluation</h2><p>Explore a prerecorded trajectory offline. The default is a selected example below 10% drift, not a summary of overall performance. All recorded runs are available below.</p>{report && <button onClick={() => setResult(report.runs.find((r: any) => r.split === 'development validation' && r.sih_target_met && r.drift_percentage < 10) || report.runs.find((r: any) => r.sih_target_met && r.drift_percentage < 10) || report.runs[0])}>Open saved example ↗</button>}</div>}
    {result && <><div className="result-title"><h2>{result.track_name} <span className="tag">{result.split}</span></h2><span className={result.sih_target_met ? 'result-pass' : 'result-fail'}>{result.sih_target_met ? 'BELOW 10% ON THIS RUN' : 'TARGET NOT MET ON THIS RUN'}</span></div><div className="metrics"><Metric label="ENDPOINT DRIFT" value={fmt(result.drift_percentage, 2)} unit="%" sub="Endpoint error / reference distance"/><Metric label="POSITION RMSE" value={fmt(result.rmse_m, 2)} unit="m" sub="Across the complete outage"/><Metric label="OUTAGE DISTANCE" value={fmt(result.outage_distance_m, 0)} unit="m" sub={`${result.outage_duration_s} s · start ${fmt(result.start_s, 0)} s`}/><Metric label="PROCESSING P95" value={fmt(result.p95_processing_ms, 2)} unit="ms" sub="Measured desktop runtime"/></div><div className="panel"><div className="panel-header"><h2>Estimated vs reference trajectory</h2><button onClick={() => save('kinematix-evaluation.json', result)}>Download evidence ↓</button></div><Plot points={result.trajectory}/><div className="map-bottom legend"><span className="mint">━ EKF trajectory</span><span className="blue">┄ GPS reference</span><span className="coral">━ Constant-speed + gyro</span></div></div><div className="bottom-grid"><div className="panel result-details"><h2>Run integrity</h2><div className="pair"><span>Maximum position error</span><b>{fmt(result.max_error_m, 2)} m</b></div><div className="pair"><span>Endpoint error</span><b>{fmt(result.final_error_m, 2)} m</b></div><div className="pair"><span>Baseline endpoint error</span><b>{fmt(result.baseline_final_error_m, 2)} m</b></div><div className="pair"><span>Learned speed update</span><b>{result.ai_enabled ? 'Enabled' : 'Unavailable'}</b></div><small>Dataset SHA-256: {result.sha256?.slice(0, 24)}…</small></div><div className="panel result-details"><h2>Evaluation notes</h2><p>Selected runs describe individual blackout windows, not overall benchmark performance. One reproducible blackout on a real recording. It does not establish lane-level accuracy or performance across all vehicles.</p>{result.limitations?.map((s: string) => <p className="fine" key={s}>• {s}</p>)}</div></div></>}
    {report && <div className="panel report-table">{report.rejected_recordings?.map((r: any) => <p className="rejected-note" key={r.recording}>{r.recording} excluded: {r.reason}</p>)}<div className="panel-header"><h2>Recorded-drive results</h2><span className="eyebrow">SAVED BENCHMARKS · NOT THIS PHONE SESSION</span></div><p className="evaluation-help">Each result replays an IO-VNBD recording with GPS withheld for the listed blackout. Drift is endpoint position error divided by distance travelled; the target is below 10%. Training drives were used to fit the model; development holdout drives were used to assess it. Inspect opens the trajectory and detailed scores. Repeated windows are not independent drives.</p><details className="all-results"><summary>Browse all {report.runs.length} recorded runs</summary><table><thead><tr><th>Drive</th><th>Split</th><th>Blackout</th><th>Drift</th><th>Target</th><th /></tr></thead><tbody>{report.runs.map((r: any, i: number) => <tr key={i}><td data-label="Drive">{r.track_name}</td><td data-label="Data split">{r.split}</td><td data-label="Blackout">{r.outage_duration_s}s</td><td data-label="Endpoint drift">{fmt(r.drift_percentage, 2)}%</td><td data-label="Target">{r.sih_target_met ? 'Pass' : 'Not met'}</td><td data-label="Details"><button onClick={() => setResult(r)}>Inspect ↗</button></td></tr>)}</tbody></table></details></div>}</>}
  {tab === 'system' && <><section className="panel system-flow" aria-label="Navigation architecture"><h2>On-device navigation pipeline</h2><div className="flow-inputs"><div className="flow-node"><b>Phone IMU</b><span>Accelerometer · gyroscope · gravity</span><small>50 Hz requested sensor callbacks</small></div><div className="flow-node"><b>GNSS receiver</b><span>Position · speed · bearing · accuracy</span><small>1 Hz requested location updates</small></div></div><div className="flow-inputs"><div><div className="flow-arrow">↓</div><div className="flow-node"><b>Motion features + learned speed</b><span>Latest IMU sample forwarded at 10 Hz</span><small>Two-second feature window · local JSON model</small></div></div><div><div className="flow-arrow">↓</div><div className="flow-node"><b>GNSS measurement checks</b><span>Permissions · fix quality · availability</span><small>Accepted fixes correct the EKF</small></div></div></div><div className="flow-arrow">↘ &nbsp; ↙</div><div className="flow-node flow-ekf"><b>Five-state Extended Kalman Filter</b><span>East · north · speed · heading · gyro bias</span><small>10 Hz scheduled IMU processing · covariance and innovation gates</small></div><div className="flow-arrow">↓</div><div className="flow-node"><b>EKF trajectory + uncertainty</b><span>GPS available: fusion · GPS absent: inertial propagation</span></div><p className="fine">Offline roads → optional display overlay only; map matching does not currently correct the EKF.</p><p className="fine">Rates above are configured requests or scheduling targets, not measured device guarantees. Actual callbacks depend on hardware and Android scheduling. IMU forwarding uses the latest sample; it is not a 50 Hz navigation solution.</p><div className="flow-replay"><b>Desktop evaluation</b><p>IO-VNBD CSV → timing and calibration checks → Python EKF → reference-only scoring → saved report</p><small>Replay grid: 10 Hz. Current recordings change coordinates about every 9 s; this is not a measured GNSS receiver update rate. 200 Hz external-IMU performance is not validated.</small></div></section><div className="architecture">{[['01', 'Sense', 'Accelerometer · gyroscope · gravity · GNSS', 'SI units and timestamps; no vehicle CAN dependency.'], ['02', 'Understand', 'Causal two-second IMU windows', 'A compact learned speed prior, with pre-outage residual calibration.'], ['03', 'Propagate', 'Vehicle motion + uncertainty', 'Five-state EKF running locally in Python and the Android WebView.'], ['04', 'Display', 'Trajectory and optional road overlay', 'Ambiguous road matches are withheld; no map correction enters the EKF.']].map(([n, t, s, d]) => <div className="panel" key={n}><span className="step-number">{n}</span><h2>{t}</h2><b>{s}</b><p>{d}</p></div>)}</div><div className="bottom-grid"><div className="panel result-details"><div className="eyebrow">MODEL CARD</div><h2>On-device speed model</h2><div className="pair"><span>Architecture</span><b>{model?.trees?.length || 0}-tree ExtraTrees</b></div><div className="pair"><span>Input / window</span><b>4 IMU signals / 2 seconds</b></div><div className="pair"><span>Deployment</span><b>Portable JSON forest</b></div><div className="pair"><span>Training drives</span><b>{model?.train_recordings?.length || 0} recordings · drivers B/E</b></div><div className="pair"><span>Held-out drive</span><b>6 validation recordings · driver A</b></div><p>Absolute speed from IMU is not always observable. The learned prior is anchored using the last available GNSS speed and must be validated on new vehicles and mounts.</p></div><div className="panel result-details"><div className="eyebrow">PROTOTYPE BOUNDARIES</div><h2>Validation status</h2><p>Local Android EKF and sensor capture are implemented. Build checks and Python/JavaScript parity pass; independent phone drift performance remains unverified.</p><p>Lane-level performance, arbitrary remount recovery, sustained background operation, and 200 Hz FOG performance are not certified.</p><p>Road matching is an optional visualization layer. It never uses the evaluation reference trajectory and never modifies reported benchmark scores.</p><a href="https://github.com/onyekpeu/IO-VNBD" target="_blank" rel="noreferrer">IO-VNBD source & attribution ↗</a></div></div></>}
  <footer><span>KinematiX / ORIGIN X / Team ID 134028</span><span>SIH 26168 / RESEARCH PROTOTYPE</span></footer></main></div>;
}
function Metric({ label, value, unit, sub, state = false }: any) { return <div className="metric"><div className="eyebrow">{label}</div><div className={state ? 'metric-value mode' : 'metric-value'}>{state && <i className="dot"/>}{value}<span>{unit}</span></div><small>{sub}</small></div>; }
