const assert = require('node:assert/strict');
const fs = require('node:fs');
const {LocalEngine} = require('../.test-build/engine.js');
const rows = JSON.parse(fs.readFileSync('backend/tests/ekf_parity.json','utf8'));
const e = new LocalEngine();
let maxError=0;
for(const r of rows){
 e.step(r.dt,r.yaw,r.acc,r.fix??undefined,r.shock,r.ai);
 for(let i=0;i<5;i++){
  maxError=Math.max(maxError,Math.abs(e.state[i]-r.state[i]));
  assert.ok(Math.abs(e.state[i]-r.state[i])<1e-8,'EKF state parity');
  for(let j=0;j<5;j++)assert.ok(Math.abs(e.P[i][j]-r.covariance[i][j])<1e-8,'EKF covariance parity');
 }
 assert.equal(e.mode,r.mode);
}
assert.throws(()=>e.step(0,0,0));
console.log(`PASS: 500-step Python/JS EKF state, covariance and mode parity; maximum state error ${maxError}`);
