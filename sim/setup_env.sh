#!/usr/bin/env bash
# make the toolkit runnable under the plain system python3 (no venv).
# impedance.py / net_lengths.py / hs_audit.py need only numpy + matplotlib.
# openems_microstrip.py additionally needs the openEMS python bindings.
set -e

echo "installing python deps for the numpy tools ..."
pip install --user --break-system-packages numpy matplotlib h5py

# link the openEMS bindings (built at ~/opt/openEMS) into the user site so
# system python3 can import them without activating the build venv. the .so
# have an absolute RUNPATH to ~/opt/openEMS/lib, so this just works.
VENV_SP=~/opt/openEMS/venv/lib/python3.13/site-packages
USER_SITE=$(python3 -m site --user-site)
if [ -d "$VENV_SP/openEMS" ]; then
  mkdir -p "$USER_SITE"
  ln -sfn "$VENV_SP/openEMS" "$USER_SITE/openEMS"
  ln -sfn "$VENV_SP/CSXCAD" "$USER_SITE/CSXCAD"
  echo "linked openEMS + CSXCAD into $USER_SITE"
else
  echo "openEMS build not found at $VENV_SP; adjust the path if yours differs"
fi

echo
echo "verify:  python3 -c 'import openEMS, CSXCAD, numpy, matplotlib, h5py; print(\"ok\")'"
echo "for the 3D field animation you also need ParaView:  sudo apt install paraview"
