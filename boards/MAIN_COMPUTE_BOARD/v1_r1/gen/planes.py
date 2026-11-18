import sys

import pcbnew

MM = 1e6
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
X0, Y0, W, H = 50.0, 50.0, 160.0, 100.0
INSET = 0.4


def zone(net, layer, pts, prio, name, thermal=True):
    z = pcbnew.ZONE(b)
    z.SetNet(b.FindNet(net))
    z.SetLayer(b.GetLayerID(layer))
    z.SetAssignedPriority(prio)
    z.SetZoneName(name)
    z.SetLocalClearance(int(0.2 * MM))
    z.SetMinThickness(int(0.2 * MM))
    z.SetThermalReliefGap(int(0.25 * MM))
    z.SetThermalReliefSpokeWidth(int(0.35 * MM))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(int(x * MM), int(y * MM))
    b.Add(z)
    return z


# drop zones from a previous run so this is repeatable
zs = b.Zones()
old = [zs[i] for i in range(len(zs)) if not zs[i].GetIsRuleArea()]
for z in old:
    b.Remove(z)

full = [(X0 + INSET, Y0 + INSET), (X0 + W - INSET, Y0 + INSET), (X0 + W - INSET, Y0 + H - INSET),
        (X0 + INSET, Y0 + H - INSET)]
for ly in ('In1.Cu', 'In3.Cu', 'In6.Cu'):
    zone('GND', ly, full, 0, 'GND_' + ly.split('.')[0])

# in4: 3v3 base plane with fpga islands carved out at higher priority
zone('+3V3', 'In4.Cu', full, 0, 'P3V3')
# vccint/vccbram ball block, fpga cols 7-11 rows H-T (ball grid x0 111.5, y0 81.5, 1 mm pitch)
zone('+1V0', 'In4.Cu', [(117.0, 86.8), (122.0, 86.8), (122.0, 98.4), (122.0, 106.0), (118.2, 106.0),
                        (118.2, 98.4), (117.0, 98.4)], 3, 'P1V0_CORE', thermal=False)
# bank 34 vcco balls + ddr3l
zone('+1V35', 'In4.Cu', [(110.8, 95.0), (116.6, 95.0), (116.6, 98.9), (117.9, 98.9), (117.9, 128.0),
                         (99.0, 128.0), (99.0, 104.0), (110.8, 104.0)], 2, 'P1V35_DDR', thermal=False)
# banks 35/16 vcco and the vita connector band
zone('VADJ', 'In4.Cu', [(98.6, 53.6), (183.0, 53.6), (183.0, 79.6), (133.7, 79.6), (133.7, 87.0),
                        (122.6, 87.0), (122.6, 86.4), (116.6, 86.4), (116.6, 94.6), (110.4, 94.6),
                        (110.4, 79.6), (98.6, 79.6)], 2, 'PVADJ', thermal=False)

# +12V on the bottom layer: input protection along the top edge to the vita bucks, and down the
# front strip under the panel connectors to the main bucks in the power corner
zone('+12V', 'B.Cu', [(64.5, 53.6), (190.6, 53.6), (190.6, 62.0), (180.0, 62.0), (180.0, 56.2), (99.0, 56.2), (99.0, 147.0),
                      (50.6, 147.0), (50.6, 64.8), (64.5, 64.8)], 1, 'P12V_BOT')
# vita supplies at the connector's right end (In5)
zone('+3V3_MEZZ', 'In5.Cu', [(158.0, 53.6), (190.6, 53.6), (190.6, 67.0), (158.0, 67.0)], 1, 'P3V3M_IN5', thermal=False)
# ddr3 vtt strip between the two termination rows (pcbbuild TERM_*), fed from the TPS51200 at its left end
zone('VTT_DDR', 'F.Cu', [(95.4, 122.85), (114.75, 122.85), (114.75, 124.95), (95.4, 124.95)], 2, 'VTT_STRIP',
     thermal=False)
# bottom vtt pour under the strip and the vtt decaps, stitched to the top strip through the pad vias
zone('VTT_DDR', 'B.Cu', [(95.4, 122.0), (114.75, 122.0), (114.75, 125.6), (110.2, 125.6), (110.2, 128.6),
                         (95.4, 128.6)], 2, 'VTT_BOT', thermal=False)
# +1V0 feed from its buck (left of the fpga) up the fpga's left side and in above the ddr balls to the
# core island; the band under the fpga (y > 95) is left to the ddr3 escape
zone('+1V0', 'In5.Cu', [(86.0, 113.5), (100.0, 113.5), (100.0, 94.3), (122.0, 94.3), (122.0, 86.0), (96.0, 86.0),
                        (96.0, 104.0), (86.0, 104.0)], 1, 'P1V0_FEED', thermal=False)

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(PCB)
zs = b.Zones()
for i in range(len(zs)):
    z = zs[i]
    if z.GetIsRuleArea():
        continue
    a = 0.0
    for ly in (z.GetLayerSet().Seq()):
        if z.HasFilledPolysForLayer(ly):
            a += z.GetFilledPolysList(ly).Area() / 1e12
    print('%-12s %-8s %-7s %.0f mm2' % (z.GetZoneName(), b.GetLayerName(z.GetLayer()), z.GetNetname(), a))
