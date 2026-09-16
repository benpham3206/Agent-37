import argparse,json,time
from .actor import Actor
def main():
    p=argparse.ArgumentParser(); p.add_argument("--minutes",type=float,default=10); a=p.parse_args(); start=time.time(); actor=Actor(); turns=max(1,int(a.minutes*60/5)); actor.run(turns); return 0
if __name__=="__main__": main()

