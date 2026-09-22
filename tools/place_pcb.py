#!/usr/bin/env python3
"""Place OnerLAB BoCu footprints on a 16HP Eurorack PCB.

Panel parts (jacks, pots, switches, LEDs) go to their front-panel
neighbourhood. SMT parts are laid out in a labelled grid so you can
drag them before running the KiCad autorouter.
"""
from __future__ import annotations

from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1] / "hardware"
PCB_PATH = str(HW / "OnerLAB_BoCu.kicad_pcb")

# 16 HP usable PCB (panel is 80.6 x 128.5 mm)
W, H = 78.0, 118.0


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def set_pos(fp, x, y, rot=0):
    fp.SetPosition(mm(x, y))
    try:
        fp.SetOrientationDegrees(rot)
    except Exception:
        fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))


def add_edge(board):
    existing = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    for d in existing:
        board.Remove(d)
    pts = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(mm(*a))
        seg.SetEnd(mm(*b))
        seg.SetWidth(pcbnew.FromMM(0.15))
        board.Add(seg)


def add_text(board, text, x, y, size=1.5, layer=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(mm(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetLayer(layer or pcbnew.F_SilkS)
    t.SetTextThickness(pcbnew.FromMM(0.18))
    board.Add(t)


def add_hole(board, x, y, i):
    lib = "/usr/share/kicad/footprints/MountingHole.pretty"
    name = "MountingHole_3.2mm_M3"
    plugin = pcbnew.IO_MGR.PluginFind(pcbnew.IO_MGR.KICAD_SEXP)
    fp = plugin.FootprintLoad(lib, name)
    fp.SetReference(f"H{i}")
    fp.SetValue("M3")
    fp.SetPosition(mm(x, y))
    board.Add(fp)


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    add_edge(board)

    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    # --- Front panel neighbourhood (coordinates in mm, origin bottom-left) ---
    panel = {
        "J1": (12.0, 14.0, 180),   # IN L 3.5
        "J2": (24.0, 14.0, 180),   # IN R 3.5
        "J3": (44.0, 16.0, 180),   # OUT L 6.35
        "J4": (62.0, 16.0, 180),   # OUT R 6.35
        "RV1": (18.0, 92.0, 0),    # LOW BOOST
        "RV2": (52.0, 92.0, 0),    # LOW CUT
        "RV3": (18.0, 68.0, 0),    # MID CUT
        "RV4": (52.0, 68.0, 0),    # HIGH BOOST
        "SW1": (22.0, 48.0, 0),    # FREQ L
        "SW2": (48.0, 48.0, 0),    # FREQ R
        "J5": (12.0, 110.0, 0),    # power
        "D12": (39.0, 110.0, 0),   # power LED
    }
    for ref, (x, y, rot) in panel.items():
        if ref in fps:
            set_pos(fps[ref], x, y, rot)

    # Saturation LEDs (3 mm THT, not D12)
    sat = [fp for ref, fp in fps.items()
           if "LED_D3" in (fp.GetFPIDAsString() or fp.GetValue() or "")
           and ref != "D12"]
    sat = sorted(sat, key=lambda f: f.GetReference())
    for fp, x in zip(sat, (8.0, 70.0)):
        set_pos(fp, x, 50.0, 0)

    # Opamps in a row under the pots
    for i, ref in enumerate(["U1", "U2", "U3", "U4", "U5"]):
        if ref in fps:
            set_pos(fps[ref], 10.0 + i * 14.0, 36.0, 0)

    placed = set(panel) | {fp.GetReference() for fp in sat} | {"U1", "U2", "U3", "U4", "U5"}

    rest = [fp for ref, fp in sorted(fps.items(), key=lambda kv: kv[0]) if ref not in placed]
    cols, x0, y0, dx, dy = 9, 7.0, 28.0, 7.4, 3.6
    for n, fp in enumerate(rest):
        col, row = n % cols, n // cols
        set_pos(fp, x0 + col * dx, y0 + row * dy, 0)

    # Mounting holes (Eurorack-ish)
    if "H1" not in fps:
        add_hole(board, 5.0, 113.0, 1)
        add_hole(board, 73.0, 113.0, 2)
        add_hole(board, 5.0, 5.0, 3)
        add_hole(board, 73.0, 5.0, 4)

    add_text(board, "OnerLAB BoCu", 39.0, 84.0, 2.0)
    add_text(board, "BOOST          CUT", 35.0, 98.0, 1.2)
    add_text(board, "MID            HIGH", 35.0, 74.0, 1.2)
    add_text(board, "IN L  IN R     OUT L  OUT R", 36.0, 6.0, 1.0)
    add_text(board, "16HP  +/-12V  unrouted  JLCPCB", 39.0, 116.5, 1.0)

    pcbnew.Refresh()
    board.Save(PCB_PATH)
    print("placed", len(fps), "footprints ->", PCB_PATH)


if __name__ == "__main__":
    main()
