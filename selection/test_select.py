import unittest
from anchors import quota_sizes
class TestQuota(unittest.TestCase):
 def test_largest_remainder_and_capacity(self):
  q=quota_sizes({('a','x'):7,('a','y'):3},6);self.assertEqual(q,{('a','x'):4,('a','y'):2});self.assertEqual(sum(q.values()),6)
 def test_reserve_is_respected(self):
  q=quota_sizes({'a':1,'b':99},50);self.assertEqual(q,{'a':1,'b':49})
if __name__=='__main__':unittest.main()
