export type XY = [
    number,
    number
];
export type Packet = {
    source: string;
    timestamp: number;
    state: string;
    gnss_available: boolean;
    distance_travelled: number;
    outage_duration_s: number;
    position_error_m: number | null;
    speed_mps: number;
    heading_deg: number;
    uncertainty_m: number;
    ref_pos?: {
        x: number;
        y: number;
    };
    corrected_pos: {
        x: number;
        y: number;
    };
    raw_dr_pos?: {
        x: number;
        y: number;
    };
    shock: boolean;
    imu: {
        ax: number;
        ay: number;
        az: number;
        gz: number;
    };
    note?: string;
};
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
type Matrix = number[][];
const identity = (): Matrix => Array.from({length:5},(_,i)=>Array.from({length:5},(_,j)=>+(i===j)));
const transpose = (a:Matrix):Matrix => a[0].map((_,j)=>a.map(row=>row[j]));
const multiply = (a:Matrix,b:Matrix):Matrix => a.map(row=>b[0].map((_,j)=>row.reduce((sum,v,k)=>sum+v*b[k][j],0)));
const add = (a:Matrix,b:Matrix):Matrix => a.map((row,i)=>row.map((v,j)=>v+b[i][j]));
/** Five-state planar EKF, matching Python NavigationEngine. Runs locally in Android WebView. */
export class LocalEngine {
    state = [0,0,12,0,0];
    P:Matrix = identity().map((row,i)=>row.map(v=>v*[4,4,1,.03,.0004][i]));
    get x(){return this.state[0]} set x(v:number){this.state[0]=v}
    get y(){return this.state[1]} set y(v:number){this.state[1]=v}
    get v(){return this.state[2]} set v(v:number){this.state[2]=v}
    get h(){return this.state[3]} set h(v:number){this.state[3]=v}
    get bias(){return this.state[4]} set bias(v:number){this.state[4]=v}
    get variance(){const a=this.P[0][0],b=this.P[0][1],c=this.P[1][1];return (a+c+Math.sqrt((a-c)**2+4*b*b))/2}
    time=0; lastFix=0; distance=0; outage=0; mode='GNSS_FUSION'; rejectedFixes=0;
    recoveryCount=0; candidate:{x:number,y:number,t:number}|null=null;
    private update(z:number[], indices:number[], noise:number[], angleIndex=-1, gate=Infinity){
        const residual=z.map((v,i)=>i===angleIndex?wrap(v-this.state[indices[i]]):v-this.state[indices[i]]);
        const S=indices.map((r,i)=>indices.map((c,j)=>this.P[r][c]+(i===j?noise[i]:0)));
        let inv:Matrix;
        if(S.length===1) inv=[[1/S[0][0]]];
        else {const det=S[0][0]*S[1][1]-S[0][1]*S[1][0];if(det<=0)return false;inv=[[S[1][1]/det,-S[0][1]/det],[-S[1][0]/det,S[0][0]/det]];}
        const weighted=multiply(inv,residual.map(v=>[v]));
        if(residual.reduce((v,r,i)=>v+r*weighted[i][0],0)>gate)return false;
        const K=multiply(this.P.map(row=>indices.map(j=>row[j])),inv);
        this.state=this.state.map((v,i)=>v+K[i].reduce((sum,k,j)=>sum+k*residual[j],0));this.h=wrap(this.h);
        const I=identity(); for(let i=0;i<5;i++)indices.forEach((j,k)=>I[i][j]-=K[i][k]);
        const R=noise.map((v,i)=>noise.map((_,j)=>i===j?v:0));
        this.P=add(multiply(multiply(I,this.P),transpose(I)),multiply(multiply(K,R),transpose(K)));
        this.P=this.P.map((row,i)=>row.map((v,j)=>(v+this.P[j][i])/2));return true;
    }
    step(dt:number,yaw:number,acc:number,fix?:{x:number,y:number,v:number,h:number|null,accuracy?:number},shock=false,ai?:number){
        if(![dt,yaw,acc].every(Number.isFinite)||dt<=0||dt>1)throw new Error('Finite SI inputs and 0 < dt <= 1 required');
        this.time+=dt;shock=shock||Math.abs(acc)>8;
        const a=shock?0:Math.max(-6,Math.min(4,acc)), h=this.h+(yaw-this.bias)*dt*.5,v=Math.max(0,this.v+a*dt*.5);
        const F=identity();F[0][2]=Math.cos(h)*dt;F[1][2]=Math.sin(h)*dt;F[0][3]=-v*Math.sin(h)*dt;F[1][3]=v*Math.cos(h)*dt;F[3][4]=-dt;
        this.x+=v*dt*Math.cos(h);this.y+=v*dt*Math.sin(h);this.v=Math.max(0,this.v+a*dt);this.h=wrap(this.h+(yaw-this.bias)*dt);
        this.distance+=v*dt;
        const Q=[.02,.02,.25,.0004,.000001];this.P=add(multiply(multiply(F,this.P),transpose(F)),identity().map((row,i)=>row.map(v=>v*Q[i]*dt)));
        if(ai!==undefined&&Number.isFinite(ai)&&!shock)this.update([Math.max(0,Math.min(60,ai))],[2],[25],-1,9);
        this.mode=this.time-this.lastFix>1.5?'DEAD_RECKONING':'GNSS_FUSION';
        if(fix){
            const accuracy=fix.accuracy??2;
            if(![fix.x,fix.y,fix.v,accuracy].every(Number.isFinite)||(fix.h!==null&&!Number.isFinite(fix.h))){this.rejectedFixes++;return;}
            if(this.time-this.lastFix>5){const c=this.candidate,elapsed=c?this.time-c.t:0;
                const consistent=c&&elapsed>0&&elapsed<=2&&Math.hypot(fix.x-c.x,fix.y-c.y)<Math.max(15,elapsed*Math.max(fix.v,1)*1.8+10);
                this.recoveryCount=consistent?this.recoveryCount+1:1;this.candidate={x:fix.x,y:fix.y,t:this.time};
                if(this.recoveryCount>=3){const inflation=(Math.hypot(fix.x-this.x,fix.y-this.y)/3)**2;this.P[0][0]+=inflation;this.P[1][1]+=inflation;}
            }else{this.recoveryCount=0;this.candidate=null;}
            if(this.update([fix.x,fix.y],[0,1],[Math.max(accuracy,2)**2,Math.max(accuracy,2)**2],-1,25)){
                this.mode=this.time-this.lastFix>1.5?'RECOVERING':'GNSS_FUSION';this.lastFix=this.time;
                this.update([fix.v],[2],[.25]);if(fix.v>2&&fix.h!==null)this.update([fix.h],[3],[.12**2],0);
            }else this.rejectedFixes++;
        }
        this.v=Math.max(0,this.v);this.outage=this.mode==='DEAD_RECKONING'?this.outage+dt:0;
    }
}
export class Demo {
    engine = new LocalEngine();
    t = 0;
    x = 0;
    y = 0;
    h = 0;
    rawX = 0;
    rawY = 0;
    rawH = 0;
    denied = false;
    shock = false;
    step(): Packet {
        const dt = .1;
        this.t += dt;
        const v = 12 + 2 * Math.sin(this.t * .04), a = .08 * Math.cos(this.t * .04), yaw = .035 * Math.sin(this.t * .09);
        this.h += yaw * dt;
        this.x += v * Math.cos(this.h) * dt;
        this.y += v * Math.sin(this.h) * dt;
        const gz = yaw + .002 + .001 * Math.sin(this.t * 13), ax = a + .008 + .06 * Math.sin(this.t * 17) + (this.shock ? 15 : 0);
        const fix = !this.denied && Math.round(this.t * 10) % 10 === 0 ? { x: this.x + Math.sin(this.t * 2), y: this.y + Math.cos(this.t * 3), v, h: this.h } : undefined;
        this.engine.step(dt, gz, ax, fix, this.shock);
        this.rawH += gz * dt;
        this.rawX += 12 * Math.cos(this.rawH) * dt;
        this.rawY += 12 * Math.sin(this.rawH) * dt;
        const e = this.engine, p = { source: 'synthetic', timestamp: this.t, state: e.mode, gnss_available: !this.denied, distance_travelled: e.distance,
            outage_duration_s: e.outage, position_error_m: Math.hypot(e.x - this.x, e.y - this.y), speed_mps: e.v, heading_deg: e.h * 180 / Math.PI, uncertainty_m: 2.448 * Math.sqrt(e.variance),
            ref_pos: { x: this.x, y: this.y }, corrected_pos: { x: e.x, y: e.y }, raw_dr_pos: { x: this.rawX, y: this.rawY }, shock: this.shock, imu: { ax, ay: v * yaw, az: 9.80665, gz } };
        this.shock = false;
        return p;
    }
}
export function forestPredict(model: any, buffer: number[][]): number | undefined {
    if (!model || buffer.length < 20)
        return undefined;
    const mean = [0, 1, 2, 3].map(j => buffer.reduce((s, r) => s + r[j], 0) / buffer.length);
    const std = mean.map((m, j) => Math.sqrt(buffer.reduce((s, r) => s + (r[j] - m) ** 2, 0) / buffer.length));
    const rms = mean.map((_, j) => Math.sqrt(buffer.reduce((s, r) => s + r[j] ** 2, 0) / buffer.length));
    const max = mean.map((_, j) => Math.max(...buffer.map(r => Math.abs(r[j]))));
    const f = [...mean, ...std, ...rms, ...max];
    return model.trees.reduce((sum: number, t: any) => { let n = 0; while (t.left[n] !== -1)
        n = f[t.feature[n]] <= t.threshold[n] ? t.left[n] : t.right[n]; return sum + t.value[n]; }, 0) / model.trees.length;
}
export type Road = {
    a: XY;
    b: XY;
};
export function roadsFromGeoJSON(data: any, origin: XY): Road[] {
    const roads: Road[] = [];
    const convert = (p: number[]): XY => [(p[0] - origin[1]) * Math.PI / 180 * 6378137 * Math.cos(origin[0] * Math.PI / 180), (p[1] - origin[0]) * Math.PI / 180 * 6378137];
    for (const f of data.features || []) {
        const g = f.geometry;
        const lines = g?.type === 'LineString' ? [g.coordinates] : g?.type === 'MultiLineString' ? g.coordinates : [];
        for (const line of lines)
            for (let i = 1; i < line.length; i++) {
                if (![...line[i - 1].slice(0, 2), ...line[i].slice(0, 2)].every(Number.isFinite))
                    continue;
                roads.push({ a: convert(line[i - 1]), b: convert(line[i]) });
            }
    }
    if (roads.length > 20000)
        throw new Error('Use a local extract with fewer than 20,000 segments.');
    if (!roads.length)
        throw new Error('GeoJSON must contain LineString roads.');
    return roads;
}
export function matchRoad(p: XY, heading: number, roads: Road[]): XY | null {
    const candidates = roads.map(r => {
        const dx = r.b[0] - r.a[0], dy = r.b[1] - r.a[1], l = dx * dx + dy * dy;
        const u = l ? Math.max(0, Math.min(1, ((p[0] - r.a[0]) * dx + (p[1] - r.a[1]) * dy) / l)) : 0;
        const q: XY = [r.a[0] + u * dx, r.a[1] + u * dy], d = Math.hypot(q[0] - p[0], q[1] - p[1]);
        const angle = Math.acos(Math.min(1, Math.abs(Math.cos(heading - Math.atan2(dy, dx)))));
        return { q, d, score: d + angle * 12, angle };
    }).filter(c => c.d < 20 && c.angle < .65).sort((a, b) => a.score - b.score);
    if (!candidates.length)
        return null;
    if (candidates[1] && candidates[1].score - candidates[0].score < 2 && Math.hypot(candidates[1].q[0] - candidates[0].q[0], candidates[1].q[1] - candidates[0].q[1]) > 5)
        return null;
    return candidates[0].q;
}
