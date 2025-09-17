import logging
import sys
import signal
import threading
import time

import rtmidi

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

MIDI_INPUT_DEVICE_STR = "INTECH"
MIDI_VOUT_DEVICE_STR = "LOOPMIDI"

midiins = []
midiouts = []
vport_map = {}
out_locks = {}


def list_ports():
    mi = rtmidi.MidiIn()
    mo = rtmidi.MidiOut()
    in_ports = [(i, mi.get_port_name(i)) for i in range(mi.get_port_count())]
    out_ports = [(i, mo.get_port_name(i)) for i in range(mo.get_port_count())]
    return in_ports, out_ports


class MidiInputHandler(object):
    #    __slots__ = ("in_name", "midiout_t", "out_lock", "_wallclock")

    def __init__(self,
                 in_name: str,
                 midiout: tuple[rtmidi.MidiOut, rtmidi.MidiOut],
                 out_lock: tuple[threading.Lock, threading.Lock]
                 ):
        self.in_name = in_name
        self.midiout_t = midiout[0]
        self.midiout_r = midiout[1]
        self.out_lock_t = out_lock[0]
        self.out_lock_r = out_lock[1]
        self._wallclock = time.time()

    def __call__(self, event, data=None):
        try:
            message, deltatime = event
            self._wallclock += deltatime
            # logger.debug("[%s] @%0.6f %r" % (self.inport, self._wallclock, message))
            with self.out_lock_t:
                self.midiout_t.send_message(message)
            with self.out_lock_r:
                self.midiout_r.send_message(message)
        except Exception as e:
            logger.exception("Callback error on %s: %s", self.in_name, e)


def main():
    midiins, midiouts = list_ports()

    logger.info(f"MIDI ins  {midiins}")
    logger.info(f"MIDI outs {midiouts}")

    midiins = [(mi, port)
               for mi, port in midiins if MIDI_INPUT_DEVICE_STR.lower() in port.lower()]
    midiouts = [(mi, port)
                for mi, port in midiouts if MIDI_VOUT_DEVICE_STR.lower() in port.lower()]

    if (len(midiins) * 2) > len(midiouts) or len(midiouts) == 0 or len(midiins) == 0:
        raise RuntimeError(
            f"Not enough Virtual MIDI ports for {MIDI_INPUT_DEVICE_STR} devices")

    opened = []

    # fan out one device to two virtual ports
    for i, iport in midiins:
        # find a free vmidi port
        o_t = None
        o_r = None
        o_tn = None
        o_rn = None
        for o, oport in midiouts:
            if oport not in vport_map.values() and "track" in oport.lower():
                o_t = o
                o_tn = oport
                continue
            if oport not in vport_map.values() and "remote" in oport.lower():
                o_r = o
                o_rn = oport
                continue
            if o_t and o_r:
                break

        if not o_t and not o_r:
            raise RuntimeError("Error finding output MIDI ports")

        logger.debug(f"Attempting to map {iport} -> {o_tn} & {o_rn}...")
        min = rtmidi.MidiIn()
        min.ignore_types(timing=True, active_sense=True, sysex=True)
        try:
            min.open_port(i)
        except Exception as e:
            logger.exception(f"Error opening input port {i}: '{iport}': {e}")
            continue
        mout_t = rtmidi.MidiOut()
        try:
            mout_t.open_port(o_t)
        except Exception as e:
            logger.warning(f"Error opening output port {o_t}: '{o_tn}' {e}")
            continue
        out_lock_t = out_locks.setdefault(o_t, threading.Lock())
        mout_r = rtmidi.MidiOut()
        try:
            mout_r.open_port(o_r)
        except Exception as e:
            logger.warning(f"Error opening output port {o_r}: '{o_rn}' {e}")
            continue
        out_lock_r = out_locks.setdefault(o_r, threading.Lock())
        min.set_callback(MidiInputHandler(
            iport, (mout_t, mout_r), (out_lock_t, out_lock_r)))
        logger.info(f"Mapped {iport} -> {o_tn} & {o_rn}")
        vport_map.setdefault(iport, o_tn)
        vport_map.setdefault(iport, o_rn)
        opened.append((iport, min, o_tn, mout_t, o_rn, mout_r))

    if not opened:
        raise RuntimeError("MIDI io mapping failed: no opened ports")

    stop_evt = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop_evt.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_evt.set())
    try:
        while not stop_evt.is_set():
            stop_evt.wait(0.25)
    finally:
        for inport, min, out_t, mout_t, out_r, mout_r in opened:
            logger.info(f"Closing port {inport}...")
            min.close_port()
            logger.info(f"Closing port {out_t}...")
            mout_t.close_port()
            logger.info(f"Closing port {out_r}...")
            mout_r.close_port()

    logger.info("Exiting...")


if __name__ == "__main__":
    main()
