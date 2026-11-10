import collections,json,pathlib,unittest
import support
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent/'selection'
class SupportTests(unittest.TestCase):
 def setUp(self):
  self.rows=support.load(ROOT/'PAIR_METADATA.jsonl')[:12];self.profile=support.read(ROOT/'SOURCE_PROFILE.json');self.anchor=[x['canonical_candidate_id'] for x in self.rows[:4]]
  q=collections.Counter((x['domain'],x['provenance_group']) for x in self.rows[:4]);self.quota=[dict(domain=d,provenance_group=g,count=n) for (d,g),n in q.items()]
 def test_zero_h_identity(self):
  r=support.solve(self.rows,self.profile,self.anchor,self.quota,'0',10);self.assertTrue(r['integer_proven_optimal']);self.assertEqual(set(r['selected']),set(self.anchor));self.assertEqual(r['H_exact'],'0');self.assertLessEqual(r['lp_lower_bound'],r['integer_optimum']+1e-8)
 def test_bad_anchor(self):
  with self.assertRaises(ValueError):support.solve(self.rows,self.profile,self.anchor+['missing'],self.quota,'0',10)
 def test_bad_quota(self):
  with self.assertRaises(ValueError):support.solve(self.rows,self.profile,self.anchor,[],'1/100',10)
 def test_no_response(self):
  self.rows[0]['model_outputs']=[]
  with self.assertRaises(ValueError):support.solve(self.rows,self.profile,self.anchor,self.quota,'1/100',10)
if __name__=='__main__':unittest.main()
