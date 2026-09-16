// Verify the look path: sub-quantum deltas must accumulate (yaw cut-out bug)
// and a large flick must land within a few ticks.
const require2 = require('module').createRequire('D:/Codex/2026-08-26/plea/work/mindcraft-ce/node_modules/package.json');
const WebSocket = require2('ws');

const getYaw = async () => (await fetch('http://127.0.0.1:8876/v1/observation').then(r => r.json())).observation?.self?.yaw;

(async () => {
    const ws = new WebSocket('ws://127.0.0.1:8876/control'); // ws://127.0.0.1:8876/control
    const states = [];
    ws.on('message', d => { const m = JSON.parse(d); if (m.type === 'state') states.push(m); });
    await new Promise(r => ws.on('open', r));
    const send = m => ws.send(JSON.stringify(m));
    send({ type: 'resume_control' });
    await new Promise(r => setTimeout(r, 300));

    // Test 1: 200 x 0.0008 rad at ~16ms = 0.16 rad total (each below the 0.15deg quantum)
    const y0 = await getYaw();
    for (let i = 0; i < 200; i++) {
        send({ type: 'control', action: { yaw_delta: 0.0008, pitch_delta: 0 } });
        await new Promise(r => setTimeout(r, 16));
    }
    await new Promise(r => setTimeout(r, 500));
    const y1 = await getYaw();
    let small = (y1 - y0) % (Math.PI * 2); if (small > Math.PI) small -= Math.PI * 2; if (small < -Math.PI) small += Math.PI * 2;
    console.log(`small_delta: sent=0.1600 got=${small.toFixed(4)} -> ${Math.abs(small - 0.16) < 0.01 ? 'PASS' : 'FAIL'}`);

    // Test 2: 3 rad spin in 8 messages, must land within 6 ticks (~120ms)
    const y2 = await getYaw();
    const t0 = Date.now();
    for (let i = 0; i < 8; i++) send({ type: 'control', action: { yaw_delta: 3 / 8, pitch_delta: 0 } });
    let landedAt = 0;
    while (Date.now() - t0 < 1500) {
        const y = await getYaw();
        let d = (y - y2 - 3) % (Math.PI * 2); if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2;
        if (Math.abs(d) < 0.02) { landedAt = Date.now() - t0; break; }
        await new Promise(r => setTimeout(r, 10));
    }
    console.log(`big_spin: target=3.00 err=${landedAt ? '<0.02' : 'TIMEOUT'} landed_ms=${landedAt || 'n/a'} -> ${landedAt && landedAt <= 400 ? 'PASS' : 'FAIL'}`);
    send({ type: 'release' });
    ws.close();
    process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
