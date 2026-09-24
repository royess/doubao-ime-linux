import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from gi.repository import GLib

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
        self.b.session=type('Session',(),{'cancel':threading.Event(),'stop':threading.Event()})()
        self.b.hold_generation=None
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

    def test_typing_reports_reason_and_rejects_late_result(self):
        notices=[]
        self.b.notify=notices.append
        self.b.invalidated(None,None,None,None,None,
                           GLib.Variant('(ss)',('token','typing')))
        self.b.event(4,'done',{'text':'测试'})
        self.assertEqual(self.b.last['outcome'],'fcitx-invalidated:typing')
        self.assertTrue(any('识别完成前' in notice for notice in notices))
        self.assertFalse(any(x[0]=='Commit' for x in self.calls))

    def test_old_generation(self):
        self.b.event(3,'preview',{'text':'旧预览'})
        self.b.event(3,'done',{'text':'旧结果'})
        self.assertEqual(self.calls,[])
        self.assertIsNotNone(self.b.session)

    def test_preview_during_recording_and_processing_never_commits(self):
        self.b.phase='recording'
        self.b.event(4,'preview',{'text':'初步'})
        self.b.phase='processing'
        self.b.event(4,'preview',{'text':'修订'})
        self.assertEqual(self.calls,[('Preview','token','初步'),('Preview','token','修订')])

    def test_cancel_discards_late_preview(self):
        self.b.cancel('cancelled')
        self.calls.clear()
        self.b.event(4,'preview',{'text':'过期'})
        self.assertEqual(self.calls,[])

    def test_rejected_preview_cancels_recording(self):
        self.b.fcitx=lambda *args: self.calls.append(args) or False
        self.b.event(4,'preview',{'text':'过期'})
        self.assertTrue(self.b.session.cancel.is_set())
        self.assertEqual(self.b.last['outcome'],'preview-rejected')

    def test_error_after_preview_clears_ticket_without_commit(self):
        self.b.event(4,'preview',{'text':'未确认'})
        self.b.event(4,'done',{'error':'provider-or-capture-error','text':None})
        self.assertEqual(self.calls,[('Preview','token','未确认'),('Cancel','token')])
        self.assertEqual(self.b.phase,'idle')

    def test_recording_result_does_not_commit_without_stop(self):
        self.b.phase='recording'
        self.b.event(4,'done',{'text':'早到结果'})
        self.assertFalse(any(x[0]=='Commit' for x in self.calls))

    def shortcut(self, action):
        self.b.shortcut(None,None,None,None,None,GLib.Variant('(ss)',(action,'context')))

    def test_release_while_connecting_finishes_buffered_audio(self):
        self.b.phase='connecting';self.b.hold_generation=4
        self.shortcut('hold-stop')
        self.assertEqual(self.b.phase,'processing')
        self.assertTrue(self.b.session.stop.is_set())
        self.assertFalse(self.b.session.cancel.is_set())

    def test_hold_release_does_not_stop_later_session(self):
        self.b.phase='recording';self.b.hold_generation=3
        self.shortcut('hold-stop')
        self.assertEqual(self.b.phase,'recording')
        self.assertFalse(self.b.session.stop.is_set())

    def test_space_latches_hold_and_release_is_ignored(self):
        self.b.phase='recording';self.b.hold_generation=4
        self.shortcut('toggle');self.shortcut('hold-stop')
        self.assertEqual(self.b.phase,'recording')
        self.assertIsNone(self.b.hold_generation)
        self.assertFalse(self.b.session.stop.is_set())
        self.shortcut('toggle')
        self.assertEqual(self.b.phase,'processing')
        self.assertTrue(self.b.session.stop.is_set())

    def test_stale_focus_rejects_shortcut_before_recording(self):
        self.b.phase='idle';self.b.session=None
        self.b.fcitx=lambda *args: self.calls.append(args) or ''
        with patch('daemon.Session') as session:
            self.shortcut('hold-start')
            session.assert_not_called()
        self.assertEqual(self.calls,[('BeginForContext','context')])
        self.assertEqual(self.b.phase,'idle')


if __name__=='__main__':unittest.main()
