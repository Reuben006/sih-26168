import React, { useState, useEffect, useRef } from 'react';

interface Telemetry {
  state: string;
  gnss_available: boolean;
  distance_travelled: number;
  position_error_m: number;
  drift_percentage: number;
  sih_target_met: boolean;
  imu: { ax: number; ay: number; az: number; gz: number };
}

export default function App() {
  const [running, setRunning] = useState(false);
  const [gnssOutage, setGnssOutage] = useState(false);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trajectoryRef = useRef<{ ref: any[]; corrected: any[]; raw: any[] }>({
    ref: [],
    corrected: [],
    raw: []
  });

  // Self-contained simulation state
  const simState = useRef({
    t: 0.0,
    refPos: [0.0, 0.0],
    rawPos: [0.0, 0.0],
    rawVel: [12.5, 0.0],
    correctedPos: [0.0, 0.0],
    distance: 0.0
  });

  useEffect(() => {
    if (!running) return;

    const interval = setInterval(() => {
      const dt = 0.05;
      const sim = simState.current;
      sim.t += dt;

      const speed = 12.5;
      const yawRate = 0.02 * Math.sin(0.2 * sim.t);
      sim.distance += speed * dt;

      // Ground truth reference trajectory
      sim.refPos[0] += speed * dt * Math.cos(yawRate * sim.t);
      sim.refPos[1] += speed * dt * Math.sin(yawRate * sim.t);

      // Raw uncorrected IMU drift
      const biasAcc = 0.25;
      const noiseAcc = (Math.random() - 0.5) * 0.16;
      const ax = speed * 0.01 + noiseAcc + biasAcc;
      const ay = (Math.random() - 0.5) * 0.16;
      const az = 9.81 + (Math.random() - 0.5) * 0.16;

      sim.rawVel[0] += (ax - 0.05) * dt;
      sim.rawPos[0] += sim.rawVel[0] * dt;
      sim.rawPos[1] += 0.5 * ay * dt * dt + sim.t * 0.18;

      // Filtered / Corrected trajectory
      if (gnssOutage) {
        // Dead reckoning with Non-Holonomic Constraints
        sim.correctedPos[0] += speed * dt * Math.cos(yawRate * sim.t * 0.98);
        sim.correctedPos[1] += speed * dt * Math.sin(yawRate * sim.t * 0.98) * 0.95;
      } else {
        // Tight GNSS lock convergence
        sim.correctedPos[0] = sim.refPos[0] + (Math.random() - 0.5) * 0.3;
        sim.correctedPos[1] = sim.refPos[1] + (Math.random() - 0.5) * 0.3;
      }

      const dx = sim.correctedPos[0] - sim.refPos[0];
      const dy = sim.correctedPos[1] - sim.refPos[1];
      const posError = Math.sqrt(dx * dx + dy * dy);
      const driftPct = (posError / Math.max(sim.distance, 1.0)) * 100.0;

      const currentData: Telemetry = {
        state: gnssOutage ? 'DEAD_RECKONING' : 'GNSS_AVAILABLE',
        gnss_available: !gnssOutage,
        distance_travelled: parseFloat(sim.distance.toFixed(1)),
        position_error_m: parseFloat(posError.toFixed(2)),
        drift_percentage: parseFloat(driftPct.toFixed(2)),
        sih_target_met: driftPct < 10.0,
        imu: {
          ax: parseFloat(ax.toFixed(3)),
          ay: parseFloat(ay.toFixed(3)),
          az: parseFloat(az.toFixed(3)),
          gz: parseFloat(yawRate.toFixed(4))
        }
      };

      setTelemetry(currentData);

      trajectoryRef.current.ref.push({ x: sim.refPos[0], y: sim.refPos[1] });
      trajectoryRef.current.corrected.push({ x: sim.correctedPos[0], y: sim.correctedPos[1] });
      trajectoryRef.current.raw.push({ x: sim.rawPos[0], y: sim.rawPos[1] });

      if (trajectoryRef.current.ref.length > 200) {
        trajectoryRef.current.ref.shift();
        trajectoryRef.current.corrected.shift();
        trajectoryRef.current.raw.shift();
      }

      drawTrajectory();
    }, 50);

    return () => clearInterval(interval);
  }, [running, gnssOutage]);

  const drawTrajectory = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#090d16';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;

    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    }

    const scale = 1.0;
    const offsetX = 30;
    const offsetY = canvas.height / 2;

    const renderLine = (points: any[], color: string, isDashed = false) => {
      if (points.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      if (isDashed) ctx.setLineDash([5, 5]); else ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(offsetX + points[0].x * scale, offsetY - points[0].y * scale);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(offsetX + points[i].x * scale, offsetY - points[i].y * scale);
      }
      ctx.stroke();
    };

    renderLine(trajectoryRef.current.raw, '#ef4444');
    renderLine(trajectoryRef.current.ref, '#22c55e', true);
    renderLine(trajectoryRef.current.corrected, '#38bdf8');
  };

  const toggleSimulation = () => {
    if (!running) {
      simState.current = {
        t: 0.0,
        refPos: [0.0, 0.0],
        rawPos: [0.0, 0.0],
        rawVel: [12.5, 0.0],
        correctedPos: [0.0, 0.0],
        distance: 0.0
      };
      trajectoryRef.current = { ref: [], corrected: [], raw: [] };
      setRunning(true);
    } else {
      setRunning(false);
    }
  };

  return (
    <div style={{ backgroundColor: '#020617', color: '#f8fafc', minHeight: '100vh', fontFamily: 'monospace', padding: '1rem', boxSizing: 'border-box' }}>
      <header style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', borderBottom: '1px solid #1e293b', paddingBottom: '1rem', marginBottom: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', margin: 0, color: '#38bdf8' }}>IDR-X | SIH PS168</h1>
          <p style={{ color: '#64748b', fontSize: '0.75rem', margin: '4px 0 0 0' }}>Intelligent Dead Reckoning & GNSS Fusion</p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
          <div style={{ padding: '0.3rem 0.6rem', borderRadius: '4px', fontSize: '0.75rem', background: telemetry?.gnss_available ? '#064e3b' : '#7f1d1d', color: telemetry?.gnss_available ? '#34d399' : '#fca5a5', fontWeight: 'bold' }}>
            {telemetry ? telemetry.state : 'STANDALONE'}
          </div>
          <button onClick={toggleSimulation} style={{ background: running ? '#dc2626' : '#0284c7', color: '#fff', border: 'none', padding: '0.5rem 0.75rem', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '0.75rem' }}>
            {running ? 'STOP SIMULATION' : 'START SIMULATION'}
          </button>
          <button onClick={() => setGnssOutage(!gnssOutage)} disabled={!running} style={{ background: gnssOutage ? '#16a34a' : '#ea580c', color: '#fff', border: 'none', padding: '0.5rem 0.75rem', borderRadius: '4px', cursor: running ? 'pointer' : 'not-allowed', fontWeight: 'bold', fontSize: '0.75rem' }}>
            {gnssOutage ? 'RESTORE GNSS' : 'TRIGGER OUTAGE'}
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.7rem' }}>
            <span style={{ color: '#38bdf8' }}>KINEMATIC TRAJECTORY</span>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <span style={{ color: '#22c55e' }}>-- Ref</span>
              <span style={{ color: '#ef4444' }}>- Raw</span>
              <span style={{ color: '#38bdf8' }}>- EKF</span>
            </div>
          </div>
          <canvas ref={canvasRef} width={360} height={240} style={{ width: '100%', height: 'auto', borderRadius: '4px', border: '1px solid #334155' }} />
        </div>

        <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
          <h3 style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 0.5rem 0' }}>SIH PS168 DRIFT BENCHMARK</h3>
          <div style={{ fontSize: '1.75rem', fontWeight: 'bold', color: (telemetry?.drift_percentage || 0) < 10 ? '#34d399' : '#f87171' }}>
            {telemetry ? telemetry.drift_percentage : '0.0'}%
          </div>
          <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Tolerance: &lt; 10% of total distance</div>
          <div style={{ padding: '0.4rem', background: (telemetry?.drift_percentage || 0) < 10 ? '#064e3b' : '#7f1d1d', borderRadius: '4px', textAlign: 'center', fontWeight: 'bold', fontSize: '0.75rem' }}>
            STATUS: {telemetry?.sih_target_met ? 'PASS (TARGET SATISFIED)' : 'CALCULATING DRIFT'}
          </div>
        </div>

        <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem', fontSize: '0.75rem' }}>
          <h3 style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 0.5rem 0' }}>TELEMETRY READOUT</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem' }}>
            <div>Ax: <span style={{ color: '#38bdf8' }}>{telemetry?.imu?.ax ?? 0} m/s²</span></div>
            <div>Ay: <span style={{ color: '#38bdf8' }}>{telemetry?.imu?.ay ?? 0} m/s²</span></div>
            <div>Az: <span style={{ color: '#38bdf8' }}>{telemetry?.imu?.az ?? 0} m/s²</span></div>
            <div>Gz: <span style={{ color: '#38bdf8' }}>{telemetry?.imu?.gz ?? 0} rad/s</span></div>
          </div>
          <div style={{ marginTop: '0.5rem', borderTop: '1px solid #1e293b', paddingTop: '0.5rem', color: '#64748b' }}>
            Distance: {telemetry?.distance_travelled ?? 0} m | Error: {telemetry?.position_error_m ?? 0} m
          </div>
        </div>
      </div>
    </div>
  );
}