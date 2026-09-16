// Verify cockpit control path: WS /control state + forward drive moves the bot.
const require2 = require('module').createRequire('D:/Codex/2026-08-26/plea/work/mindcraft-ce/node_modules/package.json');
const WebSocket = require2('ws');

const obs = async () => (await fetch('http://127.0.0.1:8876/v1/observation').then(r => r.json())).observation?.self?.position;

(async () => {
    const ws = new WebSocket('ws://127.0.0.1:8876/control');
    let gotState = null, firstMoveAt = 0, controlSentAt = 0;
    let startPos = null;
    ws.on('message', d => {
        const m = JSON.parse(d);
        if (m.type === 'state' && !gotState) gotState = m;
        // control->state latency: first state msg showing movement after forward was sent
        if (m.type === 'state' && controlSentAt && !firstMoveAt) {
            const p = m.observation?.self?.position;
            if (p && startPos && Math.hypot(p.x - startPos.x, p.y - startPos.y, p.z - startPos.z) > 0.05) {
                firstMoveAt = Date.now();
            }
        }
    });
    await new Promise(r => ws.on('open', r));
    const send = m => ws.send(JSON.stringify(m));
    send({ type: 'resume_control' });

    const before = await obs();
    startPos = before;
    controlSentAt = Date.now();
    // drive forward for ~1.5 s at 10 Hz (mimic the page heartbeat)
    const t0 = Date.now();
    while (Date.now() - t0 < 1500) {
        send({ type: 'control', action: { forward: true, sprint: false, hotbar: 0, yaw_delta: 0, pitch_delta: 0 } });
        await new Promise(r => setTimeout(r, 100));
    }
    send({ type: 'release' });
    const after = await obs();
    await new Promise(r => setTimeout(r, 300));

    console.log('state_seen:', !!gotState, '| viewer_port:', gotState?.viewer_port, '| session:', gotState?.session_id);
    console.log('pos before:', JSON.stringify(before));
    console.log('pos after :', JSON.stringify(after));
    const moved = before && after && Math.hypot(after.x - before.x, after.y - before.y, after.z - before.z);
    console.log('moved:', moved?.toFixed(3), 'blocks ->', moved > 0.5 ? 'PASS' : 'FAIL');
    console.log('control_to_state_ms:', firstMoveAt ? firstMoveAt - controlSentAt : 'n/a');
    ws.close();
    process.exit(moved > 0.5 ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
