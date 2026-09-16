from __future__ import annotations
import argparse, json, subprocess, sys, time, urllib.request, webbrowser
from pathlib import Path
from .dataset import validate_session
from .train import train
from .registry import SkillRegistry
from .tool import CombatTool

def main(argv=None):
    p=argparse.ArgumentParser(prog="agent37"); sub=p.add_subparsers(dest="group",required=True); c=sub.add_parser("combat"); cs=c.add_subparsers(dest="command",required=True)
    teach=cs.add_parser("teach"); teach.add_argument("--server",default="localhost"); teach.add_argument("--port",type=int,default=25565); teach.add_argument("--target",default="zombie"); teach.add_argument("--session",required=True); teach.add_argument("--environment",choices=["open_surface","underground","nether_open","fortress","end_island","bridge","other"],required=True); teach.add_argument("--notes",default=""); teach.add_argument("--data-dir",default="data/combat"); teach.add_argument("--web-port",type=int,default=8765)
    val=cs.add_parser("dataset"); val_sub=val.add_subparsers(dest="dataset_command",required=True); vv=val_sub.add_parser("validate"); vv.add_argument("path")
    tr=cs.add_parser("train"); tr.add_argument("sessions",nargs="+"); tr.add_argument("--out",default=None); tr.add_argument("--epochs",type=int,default=30); tr.add_argument("--allow-synthetic",action="store_true",help="TEST FIXTURES ONLY: train but mark the candidate synthetic and ineligible for promotion")
    ev=cs.add_parser("evaluate"); ev.add_argument("--candidate",required=True); ev.add_argument("--server-jar",required=True); ev.add_argument("--java",default="java"); ev.add_argument("--work-dir",default="data/arenas"); ev.add_argument("--trials-per-mob",type=int,default=5); ev.add_argument("--timeout",type=float,default=45); ev.add_argument("--accept-eula",action="store_true")
    pr=cs.add_parser("promote"); pr.add_argument("--candidate",required=True); pr.add_argument("--registry",default="skills_store")
    rb=cs.add_parser("rollback"); rb.add_argument("--skill",default="combat.engage"); rb.add_argument("--version",required=True); rb.add_argument("--registry",default="skills_store")
    eg=cs.add_parser("engage"); eg.add_argument("--target",default="zombie"); eg.add_argument("--required-environment",choices=["open_surface","underground","nether_open","fortress","end_island","bridge","other"]); eg.add_argument("--registry",default="skills_store"); eg.add_argument("--bridge",default="http://127.0.0.1:8765")
    st=cs.add_parser("status"); st.add_argument("--bridge",default="http://127.0.0.1:8765"); ca=cs.add_parser("cancel"); ca.add_argument("--bridge",default="http://127.0.0.1:8765")
    a=p.parse_args(argv)
    if a.group!="combat": return 2
    if a.command=="teach":
        session_dir=Path(a.data_dir)/a.session; session_dir.mkdir(parents=True,exist_ok=True); session_file=session_dir/"session.json"
        if not session_file.exists(): session_file.write_text(json.dumps({"schema_version":1,"session_id":a.session,"target":a.target,"source":"human","environment":a.environment,"notes":a.notes},indent=2)+"\n",encoding="utf-8")
        cmd=["node","bridge/server.js","--host",a.server,"--port",str(a.port),"--target",a.target,"--session",a.session,"--environment",a.environment,"--notes",a.notes,"--data-dir",a.data_dir,"--web-port",str(a.web_port)]
        child=subprocess.Popen(cmd); url=f"http://127.0.0.1:{a.web_port}/"
        try:
            for _ in range(50):
                try:
                    with urllib.request.urlopen(url,timeout=.2): webbrowser.open(url); break
                except Exception: time.sleep(.1)
            return child.wait()
        except KeyboardInterrupt:
            child.terminate(); return child.wait(timeout=5)
    if a.command=="dataset":
        r=validate_session(a.path); print(json.dumps(r.__dict__,indent=2)); return 0 if r.valid else 1
    if a.command=="train":
        out=a.out or str(Path("skills_store/candidates")/("candidate-"+__import__("hashlib").sha256("\n".join(sorted(a.sessions)).encode()).hexdigest()[:12])); print(json.dumps(train(a.sessions,out,epochs=a.epochs,allow_synthetic=a.allow_synthetic),indent=2)); return 0
    if a.command=="evaluate":
        if not a.accept_eula: raise SystemExit("evaluation requires --accept-eula for the disposable arena")
        from .arena import evaluate
        report=evaluate(a.candidate,server_jar=a.server_jar,java=a.java,work_dir=a.work_dir,trials_per_mob=a.trials_per_mob,timeout_s=a.timeout,accept_eula=True); print(json.dumps(report,indent=2)); return 0
    if a.command=="promote": print(json.dumps(SkillRegistry(a.registry).promote(a.candidate),indent=2)); return 0
    if a.command=="rollback": print(json.dumps(SkillRegistry(a.registry).rollback(a.skill,a.version),indent=2)); return 0
    tool=CombatTool(a.registry,a.bridge)
    if a.command=="engage": print(json.dumps(tool.engage(a.target,required_environment=a.required_environment),indent=2))
    elif a.command=="status": print(json.dumps(tool.status(),indent=2))
    else: print(json.dumps(tool.cancel(),indent=2))
    return 0
