import json, os, uuid
from collections import defaultdict

class SkillStore:
    def __init__(self, path="skills.json"):
        self.path=path
        try: self.data=json.load(open(path,encoding="utf-8"))
        except (OSError,ValueError): self.data={}
    def save(self):
        with open(self.path,"w",encoding="utf-8") as f: json.dump(self.data,f,indent=2)
    def add(self,situation,seq,pre,success,source="teacher",encounter_id=None):
        item={"id":str(uuid.uuid4()),"action_seq":seq,"preconditions":{"inventory":pre},"outcomes":{"success":int(success),"fail":int(not success)},"source":source,"encounter_id":encounter_id}
        self.data.setdefault(situation,[]).append(item); self.save(); return item
    def recall(self,situation,inventory):
        out=[]
        for x in self.data.get(situation,[]):
            if all(inventory.get(k,0)>=v for k,v in x.get("preconditions",{}).get("inventory",{}).items()):
                o=x.get("outcomes",{}); total=o.get("success",0)+o.get("fail",0); x["_rate"]=o.get("success",0)/total if total else 0; out.append(x)
        return sorted(out,key=lambda x:x["_rate"],reverse=True)

def mine(path, store_path="skills.json"):
    rows=[]
    with open(path,encoding="utf-8") as f:
        for line in f:
            try: rows.append(json.loads(line))
            except ValueError: continue
    labels=defaultdict(list)
    for e in rows:
        if e.get("kind")=="label": labels[e.get("encounter_id")].append(e)
    store=SkillStore(store_path)
    for encounter, marks in labels.items():
        seq=[e for e in rows if e.get("encounter_id")==encounter and e.get("kind") in {"key","look","skill","inventory"}]
        onset=next((i for i,e in enumerate(rows) if e.get("encounter_id")==encounter and e.get("kind")=="situation" and e.get("name")=="falling" and e.get("active")),None)
        if onset is None: onset=next((i for i,e in enumerate(rows) if e.get("encounter_id")==encounter and e.get("kind")=="teacher" and e.get("field")=="falling"),None)
        if onset is None: continue
        seq=[e for e in rows[onset:] if e.get("encounter_id")==encounter and e.get("kind") in {"key","look","skill","inventory"}]
        pre={}
        for e in rows[:onset]:
            if e.get("kind")=="inventory":
                item=e.get("item",e.get("name")); count=e.get("count",0)
                if item: pre[item]=max(pre.get(item,0),count)
        for mark in marks: store.add("falling",seq,pre,mark.get("action")=="good", "teacher", encounter)
    return store

