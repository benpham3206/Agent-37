import unittest
from harness.stream import World
from harness.situations import SituationDetector
class TestSituations(unittest.TestCase):
    def test_falling_edges(self):
        w=World(); d=SituationDetector(); w.data={"self":{"velocity":{"y":-1},"on_ground":False}}
        w.add({"tick":7,"kind":"self","field":"motion","vel":{"y":-1}}); self.assertTrue(d.update(w)[0]["active"])
        w.data["self"]={"velocity":{"y":0},"on_ground":True}; w.add({"tick":8,"kind":"keyframe"}); edges=d.update(w)
        self.assertEqual((edges[0]["tick"],edges[0]["active"]),(8,False))
if __name__=="__main__": unittest.main()

