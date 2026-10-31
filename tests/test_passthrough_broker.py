import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('passthrough_leases',
        ROOT / 'packaging/passthrough73/leases.py')
leases = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = leases
SPEC.loader.exec_module(leases)


def pool(count=14):
    return [leases.Buffer(i, 100 + i, 12443648) for i in range(count)]


def frame(index, sequence=0, generation=1):
    return leases.Frame(generation, index, sequence, sequence * 16666667,
                        3840, 2160, 3840, 3840 * 2160, 'rec709', 'limited')


class BrokerTests(unittest.TestCase):
    def broker(self):
        broker = leases.FrameBroker()
        broker.begin_generation(1, pool())
        return broker

    def test_local_display_continues_without_remote_clients(self):
        broker = self.broker()
        display = broker.subscribe('display', 3)
        held = []
        for seq in range(120):
            broker.publish(frame(seq % 4, seq))
            held.append(broker.take(display))
            if len(held) == 3:
                # Retirement is supplied by the adapter after the driver's
                # extra scan period, independent of application subscribers.
                broker.retire(held.pop(0))
                self.assertEqual(broker.take_recyclable(), [(1, (seq - 2) % 4)])
        self.assertEqual(broker.occupancy()['retained_buffers'], 2)

    def test_switching_apps_does_not_release_current_scanout(self):
        broker = self.broker()
        display = broker.subscribe('display', 3)
        onekvm = broker.subscribe('One-KVM', 2)
        broker.publish(frame(0))
        scanout, encode = broker.take(display), broker.take(onekvm)
        broker.disconnect(onekvm)
        jetkvm = broker.subscribe('JetKVM', 2)
        broker.publish(frame(1))
        self.assertIsNotNone(broker.take(jetkvm))
        broker.retire(encode)
        self.assertEqual(broker.take_recyclable(), [])
        broker.retire(scanout)
        self.assertEqual(broker.take_recyclable(), [(1, 0)])
        self.assertEqual(broker.take(display).frame.index, 1)

    def test_disconnect_preserves_reader_until_explicit_retirement(self):
        broker = self.broker()
        display = broker.subscribe('display', 3)
        broker.publish(frame(0))
        scanout = broker.take(display)
        broker.publish(frame(1))
        broker.disconnect(display)
        self.assertEqual(broker.take_recyclable(), [(1, 1)])
        with self.assertRaises(RuntimeError):
            broker.publish(frame(0, 2))
        broker.retire(scanout)
        self.assertEqual(broker.take_recyclable(), [(1, 0)])

    def test_slow_remote_keeps_latest_pending_and_does_not_block_display(self):
        broker = self.broker()
        display = broker.subscribe('display', 3)
        remote = broker.subscribe('PiKVM', 1)
        broker.publish(frame(0))
        old_remote, old_display = broker.take(remote), broker.take(display)
        for index in (1, 2, 3):
            broker.publish(frame(index, index))
            displayed = broker.take(display)
            broker.retire(displayed)
        self.assertIsNone(broker.take(remote))
        self.assertEqual(broker.take_recyclable(), [(1, 1), (1, 2)])
        broker.retire(old_remote)
        self.assertEqual(broker.take(remote).frame.index, 3)
        self.assertEqual(broker.take_recyclable(), [])
        broker.retire(old_display)
        self.assertEqual(broker.take_recyclable(), [(1, 0)])

    def test_generation_switch_requires_retirement_and_late_release_is_rejected(self):
        broker = self.broker()
        display = broker.subscribe('display', 3)
        broker.publish(frame(0))
        old = broker.take(display)
        broker.stop_generation()
        with self.assertRaises(RuntimeError):
            broker.begin_generation(2, pool())
        broker.retire(old)
        self.assertEqual(broker.take_recyclable(), [(1, 0)])
        broker.begin_generation(2, pool())
        broker.publish(frame(0, generation=2))
        current = broker.take(display)
        with self.assertRaises(ValueError):
            broker.retire(old)
        with self.assertRaises(ValueError):
            broker.publish(frame(1))
        self.assertEqual(broker.take_recyclable(), [])
        broker.retire(current)
        self.assertEqual(broker.take_recyclable(), [(2, 0)])

    def test_fault_stays_pinned_after_disconnect_and_stop(self):
        broker = self.broker()
        display = broker.subscribe('display', 3)
        broker.publish(frame(0))
        lease = broker.take(display)
        broker.pin_fault(lease)
        broker.disconnect(display)
        broker.stop_generation()
        with self.assertRaises(RuntimeError):
            broker.retire(lease)
        self.assertEqual(broker.take_recyclable(), [])
        with self.assertRaises(RuntimeError):
            broker.begin_generation(2, pool())

    def test_pool_admission_preserves_capture_working_buffers(self):
        broker = self.broker()
        broker.subscribe('display', 3)
        broker.subscribe('encoder', 7)
        with self.assertRaises(ValueError):
            broker.subscribe('second-encoder', 1)
        broker.stop_generation()
        with self.assertRaises(ValueError):
            broker.begin_generation(2, pool(13))
        broker.begin_generation(2, pool(14))
        other = leases.FrameBroker()
        with self.assertRaises(ValueError):
            other.begin_generation(1, pool(17))

    def test_no_consumers_immediately_returns_complete_frame(self):
        broker = self.broker()
        broker.publish(frame(0))
        self.assertEqual(broker.take_recyclable(), [(1, 0)])
        broker.publish(frame(0, 1))
        self.assertEqual(broker.take_recyclable(), [(1, 0)])


if __name__ == '__main__':
    unittest.main()
