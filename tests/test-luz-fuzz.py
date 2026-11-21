"""Deterministic hostile-input and atomic-write checks."""
import json
import random
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, "src")
import BombillaLocal as local
from Escenas import DEFAULT_SCENES, Scene, load_scenes, parse_scenes, save_scenes

rng = random.Random(8143)
alphabet = " \t\r\n\x00é漢🧪:/012345abcdefTOKENIP"
for size in [0, 1, 31, 32, 33, 16384, 16385, *range(250)]:
    data = "".join(rng.choices(alphabet, k=size))
    try:
        address, token = local.parse_extractor_clipboard(data)
    except ValueError:
        pass
    else:
        assert address is None and local.valid_token(token)

values = [None, True, False, -1, 0, 1, 65536, "x" * 65, "\x00", "Á🎨", [], {}]
for _ in range(300):
    record = dict(zip(("name", "mode", "level", "brightness"), rng.choices(values, k=4)))
    try:
        slots = parse_scenes([record, None, None])
    except ValueError:
        pass
    else:
        assert len(slots) == 3 and isinstance(slots[0], Scene)

with TemporaryDirectory() as folder:
    root = Path(folder)
    scene = root / "escenas.json"
    save_scenes(DEFAULT_SCENES, scene)
    original = scene.read_bytes()
    with patch.object(Path, "replace", side_effect=OSError("simulated replacement failure")):
        try:
            save_scenes([Scene("Cambio", "white", 2500, 5), *DEFAULT_SCENES[1:]], scene)
        except OSError:
            pass
        else:
            raise AssertionError("Injected write failure was ignored")
    assert scene.read_bytes() == original and load_scenes(scene) == DEFAULT_SCENES
    assert list(root.iterdir()) == [scene]
    profiles = root / "perfiles.json"
    profiles.write_text(json.dumps({"devices": []}), encoding="utf-8")
    with patch.object(local, "PROFILE_FILE", profiles), patch.object(
        Path, "replace", side_effect=OSError("simulated replacement failure")
    ):
        try:
            local._escribir_perfiles({"devices": [{"version": 2}]})
        except OSError:
            pass
        else:
            raise AssertionError("Injected profile write failure was ignored")
        assert local.read_profiles() == {"devices": []}

print("Entradas aleatorias deterministas y fallo de reemplazo atómico verificados")
