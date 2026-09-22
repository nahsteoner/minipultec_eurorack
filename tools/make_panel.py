#!/usr/bin/env python3
"""16HP aluminium front panel for OnerLAB BoCu (holes only, no copper)."""
from pathlib import Path
import pcbnew

HW = Path(__file__).resolve().parents[1] / "hardware"
OUT = str(HW / "OnerLAB_BoCu_panel.kicad_pcb")

# Doepfer 16HP panel
W, H = 80.64, 128.5
# PCB is 78 x 118, origin bottom-left. Offset onto panel:
OX, OY = (W - 78.0) / 2.0, (H - 118.0) / 2.0


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def hole(board, x, y, d, ref):
    """NPTH circle on Edge.Cuts (milled) + Eco1 mark."""
    c = pcbnew.PCB_SHAPE(board)
    c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetLayer(pcbnew.Edge_Cuts)
    c.SetCenter(mm(x, y))
    c.SetEnd(mm(x + d / 2.0, y))
    c.SetWidth(pcbnew.FromMM(0.12))
    board.Add(c)
    t = pcbnew.PCB_TEXT(board)
    t.SetText(ref)
    t.SetPosition(mm(x, y + d / 2.0 + 1.8))
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.1), pcbnew.FromMM(1.1)))
    t.SetLayer(pcbnew.Dwgs_User)
    t.SetTextThickness(pcbnew.FromMM(0.12))
    board.Add(t)


def main():
    board = pcbnew.CreateEmptyBoard()
    # outline
    pts = [(0, 0), (W, 0), (W, H), (0, H), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(mm(*a))
        s.SetEnd(mm(*b))
        s.SetWidth(pcbnew.FromMM(0.15))
        board.Add(s)

    def p(x, y):
        return x + OX, y + OY

    # Mounting (panel coordinates)
    hole(board, 7.5, H - 3.0, 3.2, "M3")
    hole(board, W - 7.5, H - 3.0, 3.2, "M3")
    hole(board, 7.5, 3.0, 3.2, "M3")
    hole(board, W - 7.5, 3.0, 3.2, "M3")

    # Jacks / pots / switches — match tools/place_pcb.py
    hole(board, *p(12.0, 14.0 + 6.5), 6.2, "IN L")   # Thonkiconn bushing
    hole(board, *p(24.0, 14.0 + 6.5), 6.2, "IN R")
    hole(board, *p(44.0, 16.0 + 5.7), 11.2, "OUT L")  # Neutrik NJ3FD-V
    hole(board, *p(62.0, 16.0 + 5.7), 11.2, "OUT R")
    hole(board, *p(18.0, 92.0), 7.5, "BOOST")
    hole(board, *p(52.0, 92.0), 7.5, "CUT")
    hole(board, *p(18.0, 68.0), 7.5, "MID")
    hole(board, *p(52.0, 68.0), 7.5, "HIGH")
    hole(board, *p(22.0, 48.0), 7.5, "FREQ L")
    hole(board, *p(48.0, 48.0), 7.5, "FREQ R")
    hole(board, *p(39.0, 110.0), 3.2, "PWR")
    hole(board, *p(8.0, 50.0), 3.2, "SAT L")
    hole(board, *p(70.0, 50.0), 3.2, "SAT R")

    title = pcbnew.PCB_TEXT(board)
    title.SetText("OnerLAB  BoCu")
    title.SetPosition(mm(W / 2.0, H - 14))
    title.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(3.2), pcbnew.FromMM(3.2)))
    title.SetLayer(pcbnew.F_SilkS)
    title.SetTextThickness(pcbnew.FromMM(0.35))
    board.Add(title)

    board.Save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
