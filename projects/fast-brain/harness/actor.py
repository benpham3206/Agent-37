import json, os, time
from urllib.request import Request,urlopen
from .tools import Tools

class Actor:
    def __init__(self, tools=None):
        self.tools=tools or Tools(); self.model=os.getenv("HARNESS_MODEL", "mock")
        if self.tools.stream._thread is None: self.tools.stream.start()
    def _chat(self,prompt):
        base=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        body={"model":self.model,"messages":[{"role":"system","content":"You control Minecraft through coarse tools. Survive, unlock advancements, prefer recalled skills, and label outcomes."},{"role":"user","content":prompt}],"tools":[]}
        req=Request(base+"/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+os.getenv("OPENAI_API_KEY","")},method="POST")
        with urlopen(req,timeout=30) as r: return json.loads(r.read().decode())
    def decide(self,prompt,turn):
        if self.model=="mock": return ("observe",{},0)
        result=self._chat(prompt); msg=result["choices"][0]["message"]; call=(msg.get("tool_calls") or [None])[0]
        if not call: return ("observe",{},0)
        return call["function"]["name"],json.loads(call["function"].get("arguments","{}")),result.get("usage",{}).get("prompt_tokens",0)
    def run(self,turns,log_path="harness.jsonl"):
        before=self.tools.stream.observe().get("self",{}).get("position",{})
        for i in range(turns):
            started=time.perf_counter(); prompt=self.tools.observe()
            tool,args,tokens=self.decide(prompt,i)
            if self.model=="mock":
                target=self._nearest()
                tool,args=("run_skill",{"name":"approach","block_name":target})
            try:
                if tool=="run_skill": result=self.tools.run_skill(**args)
                elif tool=="observe": result=self.tools.observe()
                elif tool=="equip": result=self.tools.equip(**args)
                elif tool=="stop": result=self.tools.stop()
                else: result={"error":"unknown tool"}
            except Exception as exc: result={"error":str(exc)}
            row={"kind":"llm","prompt_tokens":tokens,"tool":tool,"args":args,"latency_ms":round((time.perf_counter()-started)*1000,1)}
            with open(log_path,"a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")
            time.sleep(.25)
        after=self.tools.stream.observe().get("self",{}).get("position",{})
        print(json.dumps({"turns":turns,"position_before":before,"position_after":after,"delta":{k:after.get(k,0)-before.get(k,0) for k in ("x","y","z")},"log":log_path}))
    def _nearest(self):
        try:
            targets=self.tools.stream.get("/v1/targets").get("targets",[])
            if targets:
                t=max(targets,key=lambda x:x.get("distance",0))
                p=t.get("position",{}); return [p.get("x"),p.get("y"),p.get("z")]
        except Exception: pass
        return None
