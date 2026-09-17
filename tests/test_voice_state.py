import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
from audio import Result
from daemon import Bridge


class Results(unittest.TestCase):
    def result(self):
        r=Result()
        r.receive({'type':'final_timestamps','text':'测试。','utterance_final':False})
        r.receive({'type':'final','text':'测试。','utterance_final':True})
        r.receive({'type':'closed'})
        return r

    def test_complete(self):
        self.assertEqual(self.result().accepted(0,True,False),'测试。')

    def test_cancelled_and_unrequested(self):
        self.assertIsNone(self.result().accepted(0,True,True))
        self.assertIsNone(self.result().accepted(0,False,False))

    def test_partial_promoted_by_upstream_is_rejected(self):
        r=Result()
        r.receive({'type':'partial','text':'未完成'})
        r.receive({'type':'final','text':'未完成','utterance_final':True})
        r.receive({'type':'closed'})
        self.assertIsNone(r.accepted(0,True,False))

    def test_error_after_final_is_rejected(self):
        r=self.result();r.receive({'type':'error','message':'connection lost'})
        self.assertIsNone(r.accepted(0,True,False))
        self.assertIsNone(self.result().accepted(1,True,False))

    def test_unacknowledged_segment_is_rejected(self):
        r=self.result();r.receive({'type':'final','text':'还有下一句','utterance_final':False})
        self.assertIsNone(r.accepted(0,True,False))


class Coordinator(unittest.TestCase):
    def setUp(self):
        self.b=Bridge.__new__(Bridge)
        self.b.generation=4; self.b.phase='processing';self.b.token='token';self.b.last=None
        self.b.session=type('Session',(),{'cancel':threading.Event()})()
        self.calls=[]
        self.b.fcitx=lambda *args: self.calls.append(args) or True
        self.b.notify=lambda *args: None

    def test_commit_once(self):
        self.b.event(4,'done',{'text':'测试'})
        self.b.event(4,'done',{'text':'测试'})
        self.assertEqual([x for x in self.calls if x[0]=='Commit'],[('Commit','token','测试')])

    def test_cancel_before_late_result(self):
        self.b.cancel('focus-out')
        self.b.event(4,'done',{'text':'测试'})
        self.assertFalse(any(x[0]=='Commit' for x in self.calls))
        self.assertEqual(self.b.last['outcome'],'focus-out')

    def test_old_generation(self):
        self.b.event(3,'done',{'text':'旧结果'})
        self.assertEqual(self.calls,[])
        self.assertIsNotNone(self.b.session)

    def test_recording_result_does_not_commit_without_stop(self):
        self.b.phase='recording'
        self.b.event(4,'done',{'text':'早到结果'})
        self.assertFalse(any(x[0]=='Commit' for x in self.calls))


if __name__=='__main__':unittest.main()
