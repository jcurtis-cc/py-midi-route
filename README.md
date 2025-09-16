# py-midi-route

MIDI router and splitter: echoes each MIDI device input to unique virtual MIDI device.

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