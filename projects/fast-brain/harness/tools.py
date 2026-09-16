import base64, hashlib, json, os, socket, struct, time
from urllib.request import Request, urlopen
from .stream import Stream

class Tools:
    def __init__(self, stream=None, log_path="harness.jsonl"):
        self.stream=stream or Stream(); self.log_path=log_path; self.seq=0
    def _post(self, path, payload):
        req=Request(self.stream.base+path, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(req, timeout=8) as r: return json.loads(r.read().decode())
    def observe(self):
        o=self.stream.observe(); s=o.get("self",{}); p=s.get("position",{})
        ents=[]
        for e in self.stream.world.data.get("entities",[])[:12]:
            pos=e.get("position",{}); dist=e.get("distance")
            if dist is None: dist=math_dist(p,pos)
            ents.append(f"{e.get('name','?')}#{e.get('id','?')} d={dist:.1f}")
        active=[k for k,v in self.stream.world.situations.items() if v]
        ev=[f"{e.get('kind')}:{e.get('field',e.get('name',''))}" for e in self.stream.recent(20) if e.get('kind')!='self']
        inv=','.join(f"{x.get('name')}={x.get('count')}" for x in o.get('inventory',[]))
        return f"pose=({p.get('x',0):.1f},{p.get('y',0):.1f},{p.get('z',0):.1f}) hp={s.get('health')} food={s.get('hunger',s.get('food'))} held={s.get('held_item')} inv=[{inv}] entities=[{'; '.join(ents)}] situations={active} events=[{', '.join(ev)}] advancements=0"
    def run_skill(self,name,target_id=None,block_name=None,timeout_s=10):
        args={}
        if target_id is not None: args["entity_id"]=target_id
        elif block_name is not None: args["block_at"]=block_name if isinstance(block_name,list) else block_name
        if timeout_s: args["timeout_ticks"]=max(1,int(timeout_s*20))
        return self._post("/v1/skill",{"name":name,"args":args})
    def equip(self,item,hand="main"): return self._post("/v1/equip",{"item":item,"hand":hand})
    def stop(self): return self._post("/v1/stop",{})
    def command(self,slash):
        if os.getenv("HARNESS_ALLOW_COMMANDS")!="1": raise PermissionError("commands disabled")
        return self._post("/v1/command",{"command":slash})
    def recall(self,situation):
        from .skills import SkillStore; return SkillStore().recall(situation, {})
    def note(self,text): return self._log({"kind":"note","text":text})
    def label(self,encounter,action):
        event={"kind":"label","encounter_id":encounter,"action":action}
        self._log(event)
        try: _send_control(self.stream.base, {"type":"label","label":action,"encounter_id":encounter})
        except Exception: pass
        return event
    def _log(self,e):
        with open(self.log_path,"a",encoding="utf-8") as f: f.write(json.dumps(e)+"\n")
        return e
def math_dist(a,b): return ((a.get('x',0)-b.get('x',0))**2+(a.get('y',0)-b.get('y',0))**2+(a.get('z',0)-b.get('z',0))**2)**.5

def _send_control(base, payload):
    """Small RFC6455 client sufficient for the bridge's one-shot control message."""
    from urllib.parse import urlsplit
    u=urlsplit(base.replace("http://","ws://").replace("https://","wss://")); port=u.port or (443 if u.scheme=="wss" else 80)
    if u.scheme=="wss": raise OSError("TLS websocket unavailable in stdlib fallback")
    s=socket.create_connection((u.hostname,port),timeout=3); key=base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /control HTTP/1.1\r\nHost: {u.hostname}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    if b"101" not in s.recv(4096): raise OSError("websocket handshake failed")
    raw=json.dumps(payload,separators=(",",":" )).encode(); mask=os.urandom(4); masked=bytes(x^mask[i%4] for i,x in enumerate(raw)); n=len(raw)
    header=bytes([0x81,0x80|n]) if n<126 else bytes([0x81,0xFE])+struct.pack("!H",n)
    s.sendall(header+mask+masked); s.close()
