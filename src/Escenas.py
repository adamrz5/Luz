"""Three local scene slots and their persistence format."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from BombillaLocal import STATE_DIR, read_bounded_json

SCENE_FILE = STATE_DIR / "escenas.json"


@dataclass(frozen=True)
class Scene:
    name: str
    mode: str
    level: int | tuple[int, int, int]
    brightness: int

    def command(self):
        return self.mode, self.level, self.brightness

    def detail(self):
        color = f"{self.level} K" if self.mode == "white" else "#%02X%02X%02X" % self.level
        return f"{color} · {self.brightness} %"


WHITE_SCENE = Scene("Blanco", "white", 4000, 100)


DEFAULT_SCENES = [
    Scene("Lectura", "white", 4400, 85),
    Scene("Cine", "color", (106, 67, 255), 22),
    Scene("Noche", "white", 2000, 12),
]


def load_scenes(path=None):
    path = SCENE_FILE if path is None else path
    try:
        data = read_bounded_json(path, 64 * 1024, "Escena inválida.")
    except FileNotFoundError:
        return DEFAULT_SCENES.copy()
    return parse_scenes(data)


def parse_scenes(data):
    if not isinstance(data, list) or len(data) != len(DEFAULT_SCENES):
        raise ValueError("Se esperaban tres espacios de escenas.")
    result = []
    for entry in data:
        if entry is None:
            result.append(WHITE_SCENE)
            continue
        if not isinstance(entry, dict):
            raise ValueError("Escena inválida.")
        name, mode = entry.get("name"), entry.get("mode")
        level, brightness = entry.get("level"), entry.get("brightness")
        valid = ((mode == "white" and type(level) is int and 1700 <= level <= 6500)
                 or (mode == "color" and isinstance(level, (list, tuple)) and len(level) == 3
                     and all(type(channel) is int and 0 <= channel <= 255 for channel in level)))
        if (not valid or not isinstance(name, str) or not name.strip() or len(name) > 32
                or type(brightness) is not int or not 1 <= brightness <= 100):
            raise ValueError("Escena inválida.")
        try:
            name.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Escena inválida.") from None
        result.append(Scene(name, mode, tuple(level) if mode == "color" else level, brightness))
    return result


def save_scenes(scenes, path=None):
    path = SCENE_FILE if path is None else path
    data = [asdict(scene) for scene in scenes]
    parse_scenes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".escenas-", suffix=".tmp",
                                mode="w", encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
