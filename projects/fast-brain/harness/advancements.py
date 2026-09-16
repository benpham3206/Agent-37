import json, os
class Advancements:
    def __init__(self, path="unlocked.json"):
        self.path=path; self.items=[]
        if os.path.exists(path):
            try: self.items=json.load(open(path, encoding="utf-8"))
            except (OSError, ValueError): pass
    def add(self, event):
        if event.get("kind")=="advancement" and event.get("name") not in self.items:
            self.items.append(event.get("name")); json.dump(self.items, open(self.path,"w",encoding="utf-8"))
    @property
    def count(self): return len(self.items)
    def last(self): return self.items[-5:]

