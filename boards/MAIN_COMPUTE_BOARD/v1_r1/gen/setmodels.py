import sys

import pcbnew

# apply project 3d models to footprints of an existing board (same table as pcbbuild)
SPECS = {'WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm': [('WSON-8_L8.0-W6.0-P1.27-TL-EP-1.step', 0.0, 0.0, 0)]}
b = pcbnew.LoadBoard(sys.argv[1])
fs = b.Footprints()
n = 0
for i in range(len(fs)):
    f = fs[i]
    item = str(f.GetFPID().GetUniStringLibItemName())
    if item in SPECS:
        ms = f.Models()
        while ms.size():
            ms.pop_back()
        for name, ox, oy, rz in SPECS[item]:
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = '${KIPRJMOD}/3dmodels/' + name
            m.m_Offset = pcbnew.VECTOR3D(ox, -oy, 0)
            m.m_Rotation = pcbnew.VECTOR3D(0, 0, rz)
            m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
            m.m_Show = True
            ms.push_back(m)
        n += 1
        print(f.GetReference(), 'B' if f.IsFlipped() else 'F', round(f.GetPosition().x / 1e6, 1), round(f.GetPosition().y / 1e6, 1))
b.Save(sys.argv[1])
print('models set on', n)
