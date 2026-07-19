# Audio-board analog simulation checks (uses libngspice via ctypes - no ngspice binary needed).
# Run from this directory:  make sim   (or a specific target below)
PY := python3

.PHONY: sim sim-all sim-svf sim-phaser sim-chorus sim-real sim-svf-real sim-phaser-real sim-chain clean help

sim: sim-all              ## default: run every check

sim-all: sim-svf sim-phaser sim-chorus sim-real sim-chain   ## run all checks (behavioral + from-schematic)
	@echo "-------------------------------------------"
	@echo "all sim checks done"

sim-real: sim-svf-real sim-phaser-real   ## sims built from the ACTUAL schematic netlist (real wiring)

sim-chain:                ## FULL chain from AUDIO_BOARD.kicad_sch: verify every stage (input->VCF/VCA->SVF->drive/trem->phaser->out)
	@$(PY) test_chain_real.py

sim-svf-real:             ## SVF simulated from MASTER_FILTER.kicad_sch (real wiring + behavioral models)
	@$(PY) test_svf_real.py

sim-phaser-real:          ## phaser simulated from FX_PHASER.kicad_sch (real wiring)
	@$(PY) test_phaser_real.py

sim-svf:                  ## state-variable filter: LP/BP/HP shapes, resonance, cutoff tracks bias
	@$(PY) test_svf.py

sim-phaser:               ## phaser: all-pass flatness + notches that move with bias
	@$(PY) test_phaser.py

sim-chorus:               ## chorus: BBD delay+mix comb notches that sweep with delay time
	@$(PY) test_chorus.py

clean:                    ## remove sim scratch files
	@rm -f _*.txt _*.net _deck.cir

help:                     ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
