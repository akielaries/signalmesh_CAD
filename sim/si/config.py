# per-board config loader. a board yaml names its kicad_pcb, stackup, net
# classes, high-speed bus groups, and the driver edge rate. everything the
# suite does is parameterized by this so APM and ACM run identically.

import os
import yaml
from dataclasses import dataclass, field
from . import stackup as stackup_mod
from . import netclass as netclass_mod

BOARDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "boards")


@dataclass
class Group:
    name: str
    match: str                 # regex over net names
    z_target: float = 50.0
    clock: str = None          # reference net for skew, or None
    clock_mhz: float = 100.0
    skew_fraction: float = 0.10


@dataclass
class BoardConfig:
    name: str
    kicad_pcb: str
    stackup: object
    classes: list
    groups: list = field(default_factory=list)
    class_map: list = field(default_factory=list)  # [(regex, class_name)] explicit assignment
    ems_dir: str = None        # gerber2ems working dir (staged fab/) for tier-3 crosstalk
    rise_ps: float = 1000.0    # driver edge rise time (STM32H7 GPIO ~1 ns)
    raw: dict = field(default_factory=dict)

    @property
    def classes_by_name(self):
        return netclass_mod.by_name(self.classes)


def load(board):
    """board: a name (looked up in boards/) or a path to a yaml."""
    path = board if os.path.isfile(board) else os.path.join(BOARDS_DIR, board + ".yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError("no board config at %s" % path)
    d = yaml.safe_load(open(path))
    cfg_dir = os.path.dirname(path)
    pcb = d["kicad_pcb"]
    if not os.path.isabs(pcb):
        pcb = os.path.normpath(os.path.join(cfg_dir, pcb))
    st = stackup_mod.get(d.get("stackup", "default"))
    classes = netclass_mod.load_classes(d.get("netclasses", "default"))
    groups = [Group(**g) for g in d.get("groups", [])]
    class_map = [(m["match"], m["class"]) for m in d.get("class_map", [])]
    ems = d.get("ems_dir")
    if ems and not os.path.isabs(ems):
        ems = os.path.normpath(os.path.join(cfg_dir, ems))
    return BoardConfig(name=d.get("name", board), kicad_pcb=pcb, stackup=st,
                       classes=classes, groups=groups, class_map=class_map,
                       ems_dir=ems, rise_ps=float(d.get("rise_ps", 1000.0)), raw=d)
