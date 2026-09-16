import argparse, glob, os
from .actor import Actor
from .skills import mine
def main():
    p=argparse.ArgumentParser(prog="python -m harness"); sub=p.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run"); r.add_argument("--turns",type=int,default=3)
    m=sub.add_parser("mine"); m.add_argument("path")
    sub.add_parser("eval").add_argument("--minutes",type=float,default=10)
    sub.add_parser("encounters")
    j=sub.add_parser("jev")
    j.add_argument("--target-name",default="zombie")
    j.add_argument("--target-id",type=int,default=None)
    j.add_argument("--seconds",type=float,default=60)
    j.add_argument("--hz",type=float,default=5.0)
    j.add_argument("--ttl-ms",type=int,default=600)
    j.add_argument("--goal",default=None)
    j.add_argument("--strategy",default=None)
    j.add_argument("--waypoints",default=None,help="label:x,y,z;label2:x,y,z remembered places in the Jev state")
    j.add_argument("--mock",action="store_true")
    a=p.parse_args()
    if a.command=="run": Actor().run(a.turns)
    elif a.command=="mine": mine(a.path); print("mined",a.path)
    elif a.command=="eval": os.environ.setdefault("HARNESS_MODEL","mock"); Actor().run(max(1,int(a.minutes*12)))
    elif a.command=="jev":
        from .jev import JevActor,JevClient,mock_transport
        intent={"goal":a.goal,"strategy":a.strategy} if a.goal or a.strategy else None
        client=JevClient(transport=mock_transport) if a.mock else JevClient()
        actor=JevActor(client=client,target_name=a.target_name,target_id=a.target_id,intent=intent,hz=a.hz,ttl_ms=a.ttl_ms)
        for wp in (a.waypoints or "").split(";"):
            if not wp.strip(): continue
            label,_,xyz=wp.partition(":")
            actor.remember(label.strip(),*[float(v) for v in xyz.split(",")])
        actor.run(a.seconds)
    else:
        from .stream import Stream; print(Stream().get("/v1/encounters").get("encounters",[]))
if __name__=="__main__": main()

