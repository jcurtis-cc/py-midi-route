import logging
import sys, signal, threading
import time

import rtmidi

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

MIDI_INPUT_DEVICE_STR = "NANOKEY" # or "INTECH" etc
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
    __slots__ = ("in_name", "midiout", "out_lock", "_wallclock")
    
    def __init__(self, in_name: str, midiout: rtmidi.MidiOut, out_lock: threading.Lock):
        self.in_name = in_name
        self.midiout = midiout
        self.out_lock = out_lock
        self._wallclock = time.time()

    def __call__(self, event, data=None):
        try:
            message, deltatime = event
            self._wallclock += deltatime
            # logger.debug("[%s] @%0.6f %r" % (self.inport, self._wallclock, message))
            with self.out_lock:
                self.midiout.send_message(message)
        except Exception as e:
            logger.exception("Callback error on %s: %s", self.in_name, e)


def main():
    midiins, midiouts = list_ports()
    
    logger.info(f"MIDI ins  {midiins}")
    logger.info(f"MIDI outs {midiouts}")

    midiins = [(mi, port) for mi, port in midiins if MIDI_INPUT_DEVICE_STR.lower() in port.lower()]
    midiouts = [(mi, port) for mi, port in midiouts if MIDI_VOUT_DEVICE_STR.lower() in port.lower()]

    if len(midiins) > len(midiouts) or len(midiouts) == 0 or len(midiins) == 0:
        raise RuntimeError(f"Not enough Virtual MIDI ports for {MIDI_INPUT_DEVICE_STR} devices")

    opened = []

    for i, iport in midiins:
        # find a free vmidi port
        for o, oport in midiouts:
            if oport not in vport_map.values():
                # print(f"Attempting to map {iport} -> {oport}...")
                min = rtmidi.MidiIn()
                min.ignore_types(timing=True, active_sense=True, sysex=True)
                try:
                    min.open_port(i)
                except Exception as e:
                    logger.warning(f"Error opening input port {i}: '{iport}'")
                    continue
                mout = rtmidi.MidiOut()
                try:
                    mout.open_port(o)
                except Exception as e:
                    logger.warning(f"Error opening output port {o}: '{oport}'")
                    continue
                out_lock = out_locks.setdefault(o, threading.Lock())
                min.set_callback(MidiInputHandler(iport, mout, out_lock))
                logger.info(f"✓ Mapped {iport} -> {oport}")
                vport_map.setdefault(iport, oport)
                opened.append((iport, min, oport, mout))
                break
                
    
    if not opened:
        raise RuntimeError("MIDI io mapping failed: no opened ports")
    
    stop_evt = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop_evt.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_evt.set())
    try:
        while not stop_evt.is_set():
            stop_evt.wait(0.25)
    finally:
        for inport, min, outport, mout in opened:
            logger.info(f"Closing port {inport}...")
            min.close_port()
            logger.info(f"Closing port {outport}...")
            mout.close_port()

    logger.info("Exiting...")


if __name__ == "__main__":
    main()