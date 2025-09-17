# py-midi-route

MIDI router and splitter: intercepts each MIDI device input and fans out to unique dual virtual MIDI devices.

Useful for Ableton Live when needing to listen for MIDI via `Track` and `Remote` simultaneously.

## Windows

1. Get [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
2. Create ports for each expected device
3. Create venv `python -m venv .venv`
4. Run:

```
cd .venv/Scripts
activate
cd ..\..
pip install -r requirements.txt
python midi_route.py
```

git bash
```sh
cd .venv/Scripts
. activate
```
