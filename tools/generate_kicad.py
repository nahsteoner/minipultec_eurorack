#!/usr/bin/env python3
"""Generate the OnerLAB BoCu KiCad netlist + PCB (unrouted, footprints assigned).

Run from the repo root:
    python3 tools/generate_kicad.py

Then:
    python3 tools/place_pcb.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "hardware"
LIB = HW / "libraries"

os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")

sys.path.insert(0, str(ROOT))

from skidl import (  # noqa: E402
    KICAD7,
    Net,
    Part,
    POWER,
    lib_search_paths,
    generate_netlist,
    generate_pcb,
    reset,
    set_default_tool,
)
from skidl.net import NCNet  # noqa: E402

set_default_tool(KICAD7)
lib_search_paths[KICAD7].insert(0, str(LIB))
lib_search_paths[KICAD7].insert(1, "/usr/share/kicad/symbols")

FP = {
    "R": "Resistor_SMD:R_0603_1608Metric",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric",
    "C1206": "Capacitor_SMD:C_1206_3216Metric",
    "SOIC8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "SOT23": "Package_TO_SOT_SMD:SOT-23",
    "SOD123": "Diode_SMD:D_SOD-123",
    "SMA": "Diode_SMD:D_SMA",
    "FB": "Inductor_SMD:L_0805_2012Metric",
    "LED3": "LED_THT:LED_D3.0mm",
    "POT": "Potentiometer_THT:Potentiometer_Alpha_RD902F-40-00D_Dual_Vertical",
    "J35": "Connector_Audio:Jack_3.5mm_QingPu_WQP-PJ398SM_Vertical_CircularHoles",
    "J635": "Connector_Audio:Jack_6.35mm_Neutrik_NJ3FD-V_Vertical",
    "PWR": "Connector_IDC:IDC-Header_2x05_P2.54mm_Vertical",
    "SW": "OnerLAB:SW_Rotary_2P3T_SR16",
}

# JLCPCB / LCSC — prefer Basic parts. Verify stock before ordering.
LCSC = {
    "NE5532DR": "C7426",
    "10k": "C25803",
    "100k": "C1790",
    "1k": "C11702",
    "100R": "C22775",
    "220R": "C14754",
    "2.2k": "C17630",
    "2.7k": "C22933",
    "4.7k": "C13305",
    "15k": "C22847",
    "22k": "C14611",
    "33k": "C23214",
    "100n": "C14663",
    "10n_C0G": "C1710",
    "10u": "C15850",
    "8.2n": "C1804",
    "27n": "C1548",
    "39n": "C1653",
    "82n": "C39616",
    "100n_0805": "C49678",
    "150n": "C66719",
    "390n": "C1328",
    "1u": "C28323",
    "470n": "C1713",
    "BAT54S": "C8547",
    "1N4148W": "C2128",
    "SS14": "C8678",
    "FB600": "C16762",
    "LED3R": "C72038",
}


def tag(part: Part, lcsc: str | None, extra: dict | None = None) -> Part:
    if lcsc:
        part.fields["LCSC"] = lcsc
        part.fields["JLCPCB"] = lcsc
    if extra:
        for k, v in extra.items():
            part.fields[k] = v
    return part


def R(value: str, lcsc_key: str | None = None, ref=None) -> Part:
    p = Part("Device", "R", value=value, footprint=FP["R"], ref=ref)
    return tag(p, LCSC.get(lcsc_key or value))


def C(value: str, size: str = "0603", lcsc_key: str | None = None, ref=None) -> Part:
    fp = FP["C0603"] if size == "0603" else FP["C0805"] if size == "0805" else FP["C1206"]
    p = Part("Device", "C", value=value, footprint=fp, ref=ref)
    return tag(p, LCSC.get(lcsc_key or value))


def build():
    reset()
    set_default_tool(KICAD7)
    lib_search_paths[KICAD7].insert(0, str(LIB))

    gnd = Net("GND")
    vp = Net("+12V")
    vm = Net("-12V")
    gnd.drive = POWER
    vp.drive = POWER
    vm.drive = POWER

    # ----- Power inlet (Doepfer 10-pin, red stripe = pin 1 = -12V) -----
    pwr = Part("Connector_Generic", "Conn_02x05_Odd_Even", ref="J5",
               footprint=FP["PWR"], value="EURORACK_10P")
    tag(pwr, None, {"Note": "Shrouded 2x5, red stripe pin 1 = -12V"})
    d_plus = Part("Device", "D_Schottky", ref="D10", value="SS14", footprint=FP["SMA"])
    tag(d_plus, LCSC["SS14"])
    d_minus = Part("Device", "D_Schottky", ref="D11", value="SS14", footprint=FP["SMA"])
    tag(d_minus, LCSC["SS14"])
    fb_p = Part("Device", "FerriteBead", ref="FB1", value="600R@100MHz", footprint=FP["FB"])
    tag(fb_p, LCSC["FB600"])
    fb_m = Part("Device", "FerriteBead", ref="FB2", value="600R@100MHz", footprint=FP["FB"])
    tag(fb_m, LCSC["FB600"])

    n_raw_p, n_raw_m = Net("RAW+12"), Net("RAW-12")
    pwr[1] += n_raw_m          # -12V
    pwr[2] += gnd
    pwr[3] += gnd
    pwr[4] += gnd
    pwr[5] += gnd
    pwr[6] += gnd
    pwr[7] += n_raw_p          # +12V
    pwr[8] += n_raw_p
    pwr[9] += NCNet()               # +5V unused
    pwr[10] += NCNet()

    # SS14: pin1 = A, pin2 = K
    n_raw_p & d_plus["A"]
    d_plus["K"] & fb_p[1]
    fb_p[2] += vp
    n_raw_m & d_minus["K"]
    d_minus["A"] & fb_m[1]
    fb_m[2] += vm

    for ref, net in (("C80", vp), ("C81", vm)):
        c_b = C("10u", "0805", "10u", ref=ref)
        c_b[1] += net
        c_b[2] += gnd
        c_d = C("100n", "0603", "100n")
        c_d[1] += net
        c_d[2] += gnd

    led_p = Part("Device", "LED", ref="D12", value="LED_PWR", footprint=FP["LED3"])
    tag(led_p, LCSC["LED3R"])
    rled = R("10k", "10k")
    vp & rled[1]
    rled[2] & led_p["A"]
    led_p["K"] += gnd

    # ----- Dual-gang pots (L = pins 1-2-3, R = pins 4-5-6) -----
    rv_boost = Part("Device", "R_Potentiometer_Dual", ref="RV1", value="B50K_BOOST",
                    footprint=FP["POT"])
    rv_cut = Part("Device", "R_Potentiometer_Dual", ref="RV2", value="B50K_CUT",
                  footprint=FP["POT"])
    rv_mid = Part("Device", "R_Potentiometer_Dual", ref="RV3", value="B50K_MID",
                  footprint=FP["POT"])
    rv_high = Part("Device", "R_Potentiometer_Dual", ref="RV4", value="B50K_HIGH",
                   footprint=FP["POT"])

    # ----- Jacks -----
    jin_l = Part("Connector_Audio", "AudioJack2_SwitchT", ref="J1", value="IN_L_3.5",
                 footprint=FP["J35"])
    jin_r = Part("Connector_Audio", "AudioJack2_SwitchT", ref="J2", value="IN_R_3.5",
                 footprint=FP["J35"])
    jout_l = Part("Connector_Audio", "NJ3FD-V", ref="J3", value="OUT_L_6.35",
                  footprint=FP["J635"])
    jout_r = Part("Connector_Audio", "NJ3FD-V", ref="J4", value="OUT_R_6.35",
                  footprint=FP["J635"])

    n_in_l = Net("IN_L")
    n_in_r = Net("IN_R")
    jin_l["T"] += n_in_l
    jin_l["S"] += gnd
    jin_l["TN"] += NCNet()
    jin_r["T"] += n_in_r
    jin_r["S"] += gnd
    jin_r["TN"] += n_in_l  # mono-normal: unplug R → copy L

    # ----- Opamps -----
    def amp(ref: str) -> Part:
        u = Part("Amplifier_Operational", "NE5532", ref=ref, value="NE5532DR",
                 footprint=FP["SOIC8"])
        tag(u, LCSC["NE5532DR"])
        u["V+"] += vp
        u["V-"] += vm
        for rail, rxx in ((vp, "1"), (vm, "2")):
            d = C("100n", "0603", "100n")
            d[1] += rail
            d[2] += gnd
        return u

    u1, u2, u3, u4, u5 = amp("U1"), amp("U2"), amp("U3"), amp("U4"), amp("U5")

    # Frequency switches
    sw_l = Part("OnerLAB", "SW_Rotary_2P3T", ref="SW1", value="FREQ_L", footprint=FP["SW"])
    sw_r = Part("OnerLAB", "SW_Rotary_2P3T", ref="SW2", value="FREQ_R", footprint=FP["SW"])

    def add_channel(ch: str, n_in: Net, jout: Part, off: int, sw, u_buf, u_gyr, u_mk, u_inv, u_mid):
        p_ccw, p_w, p_cw = 1 + off, 2 + off, 3 + off

        rin = R("100k", "100k")
        n_in & rin[1]
        rin[2] += gnd
        cin = C("10u", "0805", "10u")
        rprot = R("1k", "1k")
        n_blk = Net(f"{ch}_BLK")
        n_in & cin[1]
        cin[2] & rprot[1]
        rprot[2] += n_blk
        clamp = Part("Diode", "BAT54S", value="BAT54S", footprint=FP["SOT23"])
        tag(clamp, LCSC["BAT54S"])
        clamp[3] += n_blk  # COM
        clamp[1] += vm     # A
        clamp[2] += vp     # K

        n_buf = Net(f"{ch}_BUF")
        u_buf["+"] += n_blk
        u_buf["-"] += n_buf
        u_buf["~"] += n_buf

        n_eq = Net(f"{ch}_EQ")
        rs = R("4.7k", "4.7k")
        rfloor = R("4.7k", "4.7k")
        n_buf & rs[1]
        rs[2] += n_eq
        n_eq & rfloor[1]
        rfloor[2] += gnd

        # ---- Mid cut series RLC to GND (gyrator L) ----
        n_mid_w = Net(f"{ch}_MIDW")
        n_mid_c = Net(f"{ch}_MIDC")
        n_mid_l = Net(f"{ch}_MIDL")
        rms = R("1k", "1k")
        n_eq & rms[1]
        rms[2] += n_mid_w
        rv_mid[p_w] += n_mid_w
        rv_mid[p_cw] += n_mid_c          # CCW (p_ccw) = max R between wiper and CW
        rv_mid[p_ccw] += NCNet()
        cm = C("100n", "0805", "100n_0805")
        n_mid_c & cm[1]
        cm[2] += n_mid_l
        # gyrator mid L=1H
        n_gplus = Net(f"{ch}_MIDG+")
        rg1 = R("10k", "10k")
        rg2 = R("10k", "10k")
        cg = C("10n", "0805", "10n_C0G")
        n_mid_l & rg1[1]
        rg1[2] += n_gplus
        n_gplus & cg[1]
        cg[2] += gnd
        u_mid["+"] += n_gplus
        u_mid["-"] += u_mid["~"]
        u_mid["~"] & rg2[1]
        rg2[2] += n_mid_l

        # ---- Low cut: (Rcut || Ccut) series EQ → POST ----
        n_post = Net(f"{ch}_POST")
        rv_cut[p_ccw] += n_eq            # rheostat pins 1-2: CCW = 0 Ω = min cut
        rv_cut[p_w] += n_post
        rv_cut[p_cw] += NCNet()
        sw["B"] += n_eq                  # common of cut caps on EQ side
        for pin, val, key in (("B1", "82n", "82n"), ("B2", "39n", "39n"), ("B3", "27n", "27n")):
            c = C(val, "0805", key)
            sw[pin] & c[1]
            c[2] += n_post
        rmake = R("10k", "10k")
        n_post & rmake[1]
        rmake[2] += gnd

        # ---- Makeup non-inverting + diodes + low/high boost from ninv ----
        n_out = Net(f"{ch}_MK")
        n_ninv = Net(f"{ch}_NINV")
        u_mk["+"] += n_post
        u_mk["-"] += n_ninv
        u_mk["~"] += n_out
        rf = R("15k", "15k")
        n_out & rf[1]
        rf[2] += n_ninv
        n_tap = Net(f"{ch}_TAP")
        rg1m = R("2.2k", "2.2k")
        rg2m = R("10k", "10k")
        n_ninv & rg1m[1]
        rg1m[2] += n_tap
        n_tap & rg2m[1]
        rg2m[2] += gnd

        # Asymmetric saturation across Rf
        n_d1, n_d2, n_d3 = Net(f"{ch}_D1"), Net(f"{ch}_D2"), Net(f"{ch}_D3")
        def diode(ref=None):
            d = Part("Diode", "1N4148W", value="1N4148W", footprint=FP["SOD123"], ref=ref)
            tag(d, LCSC["1N4148W"])
            return d
        d1, d2, d3 = diode(), diode(), diode()
        rsatp = R("22k", "22k")
        n_out & d1["A"]
        d1["K"] & d2["A"]
        d2["K"] & d3["A"]
        d3["K"] += n_d3
        n_d3 & rsatp[1]
        rsatp[2] += n_ninv
        led = Part("Device", "LED", value="LED_SAT", footprint=FP["LED3"])
        tag(led, LCSC["LED3R"])
        rsatn = R("22k", "22k")
        n_ninv & led["A"]
        led["K"] & rsatn[1]
        rsatn[2] += n_out

        # High boost: ninv -- 2.2k -- pot 2-3 -- 8.2n -- GND  (CCW = 50k = min)
        n_hi = Net(f"{ch}_HI")
        rhs = R("2.2k", "2.2k")
        chi = C("8.2n", "0805", "8.2n")
        n_ninv & rhs[1]
        rhs[2] += n_hi
        rv_high[p_w] += n_hi
        rv_high[p_cw] & chi[1]
        chi[2] += gnd
        rv_high[p_ccw] += NCNet()

        # Low boost: ninv -- 2.7k -- pot 2-3 -- Csel -- gyrator L -- GND
        n_lb = Net(f"{ch}_LB")
        n_lc = Net(f"{ch}_LC")
        n_ll = Net(f"{ch}_LL")
        rmin = R("2.7k", "2.7k")
        n_ninv & rmin[1]
        rmin[2] += n_lb
        rv_boost[p_w] += n_lb
        rv_boost[p_cw] += n_lc
        rv_boost[p_ccw] += NCNet()
        sw["A"] += n_lc
        # 40 Hz = 1u + 470n
        c40a = C("1u", "0805", "1u")
        c40b = C("470n", "0805", "470n")
        sw["A1"] & c40a[1]
        c40a[2] += n_ll
        sw["A1"] & c40b[1]
        c40b[2] += n_ll
        c80 = C("390n", "0805", "390n")
        sw["A2"] & c80[1]
        c80[2] += n_ll
        c120 = C("150n", "0805", "150n")
        sw["A3"] & c120[1]
        c120[2] += n_ll
        n_lgp = Net(f"{ch}_LG+")
        rgl1 = R("33k", "33k")
        rgl2 = R("33k", "33k")
        cgl = C("10n", "0805", "10n_C0G")
        n_ll & rgl1[1]
        rgl1[2] += n_lgp
        n_lgp & cgl[1]
        cgl[2] += gnd
        u_gyr["+"] += n_lgp
        u_gyr["-"] += u_gyr["~"]
        u_gyr["~"] & rgl2[1]
        rgl2[2] += n_ll

        # ---- Balanced line driver ----
        n_cold = Net(f"{ch}_COLD")
        n_invn = Net(f"{ch}_INVN")
        ria = R("10k", "10k")
        rfa = R("10k", "10k")
        n_out & ria[1]
        ria[2] += n_invn
        n_invn & rfa[1]
        rfa[2] += n_cold
        u_inv["+"] += gnd
        u_inv["-"] += n_invn
        u_inv["~"] += n_cold

        def ac_out(src: Net, dest_pin):
            rb = R("220R", "220R")
            cc = C("10u", "0805", "10u")
            rbias = R("100k", "100k")
            n_x = Net()
            src & rb[1]
            rb[2] & cc[1]
            cc[2] += n_x
            n_x & rbias[1]
            rbias[2] += gnd
            n_x += dest_pin

        ac_out(n_out, jout["T"])
        ac_out(n_cold, jout["R"])
        jout["S"] += gnd

    # Units: U1 A buf L, U1 B gyr L low
    # U2 A makeup L, U2 B inv L
    # U3 A buf R, U3 B gyr R low
    # U4 A makeup R, U4 B inv R
    # U5 A mid L, U5 B mid R
    add_channel("L", n_in_l, jout_l, 0, sw_l, u1.uA, u1.uB, u2.uA, u2.uB, u5.uA)
    add_channel("R", n_in_r, jout_r, 3, sw_r, u3.uA, u3.uB, u4.uA, u4.uB, u5.uB)

    net_path = HW / "OnerLAB_BoCu.net"
    pcb_path = HW / "OnerLAB_BoCu.kicad_pcb"
    print("ERC / netlist…")
    generate_netlist(file_=str(net_path), tool=KICAD7, do_backup=False)
    print("PCB…")
    generate_pcb(file_=str(pcb_path), tool=KICAD7, do_backup=False,
                 fp_libs=["/usr/share/kicad/footprints", str(LIB / "OnerLAB.pretty")])
    print("wrote", net_path)
    print("wrote", pcb_path)
    write_bom_from_netlist(net_path)


def write_bom_from_netlist(net_path: Path):
    import re
    text = Path(net_path).read_text()
    comps = re.findall(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\)\s*\(libsource', text, re.S)
    rows = ["Reference,Value,Footprint,LCSC,Mount,Notes"]
    for ref, body in comps:
        val = (re.search(r'\(value "([^"]*)"\)', body) or [None, ""])[1]
        fp = (re.search(r'\(footprint "([^"]*)"\)', body) or [None, ""])[1]
        lcsc = (re.search(r'\(name "LCSC"\) "([^"]*)"', body) or [None, ""])[1]
        tht = "THT" if any(k in fp for k in ("THT", "Jack", "IDC", "OnerLAB", "LED_D3", "Potentiometer")) else "SMT"
        rows.append(f"{ref},{val},{fp},{lcsc},{tht},")
    path = HW / "BOM_LCSC.csv"
    path.write_text("\n".join(rows) + "\n")
    print("wrote", path, "nparts", len(comps))


if __name__ == "__main__":
    os.chdir(HW)
    build()
