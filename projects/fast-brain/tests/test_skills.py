import json, tempfile, unittest, os
from harness.skills import mine,SkillStore
class TestSkills(unittest.TestCase):
    def test_mine_water_clutch(self):
        rows=[{"tick":1,"kind":"inventory","item":"water_bucket","count":1,"encounter_id":"e"},{"tick":2,"kind":"situation","name":"falling","active":True,"encounter_id":"e"},{"tick":3,"kind":"key","key":"use","encounter_id":"e"},{"tick":4,"kind":"label","encounter_id":"e","action":"good"}]
        with tempfile.TemporaryDirectory() as d:
            traj=os.path.join(d,"t.jsonl")
            with open(traj,"w",encoding="utf-8") as f: f.write("\n".join(map(json.dumps,rows)))
            store=mine(traj,os.path.join(d,"skills.json")); self.assertEqual(len(store.recall("falling",{"bucket":1})),0); self.assertEqual(len(store.recall("falling",{"water_bucket":1})),1)
if __name__=="__main__": unittest.main()
