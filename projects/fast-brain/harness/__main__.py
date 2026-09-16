import argparse, glob, os
from .actor import Actor
from .skills import mine
def main():
    p=argparse.ArgumentParser(prog="python -m harness"); sub=p.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run"); r.add_argument("--turns",type=int,default=3)
    m=sub.add_parser("mine"); m.add_argument("path")
    sub.add_parser("eval").add_argument("--minutes",type=float,default=10)
    sub.add_parser("encounters")
    a=p.parse_args()
    if a.command=="run": Actor().run(a.turns)
    elif a.command=="mine": mine(a.path); print("mined",a.path)
    elif a.command=="eval": os.environ.setdefault("HARNESS_MODEL","mock"); Actor().run(max(1,int(a.minutes*12)))
    else:
        from .stream import Stream; print(Stream().get("/v1/encounters").get("encounters",[]))
if __name__=="__main__": main()

