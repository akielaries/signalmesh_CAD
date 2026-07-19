# Audio-board analog simulation checks (uses libngspice via ctypes - no ngspice binary needed).
# Run from this directory:  make sim   (or a specific target below)
PY := python3

.PHONY: sim sim-all sim-svf sim-phaser clean help

sim: sim-all              ## default: run every check

sim-all: sim-svf sim-phaser   ## run all block checks
	@echo "-------------------------------------------"
	@echo "all sim checks done"

sim-svf:                  ## state-variable filter: LP/BP/HP shapes, resonance, cutoff tracks bias
	@$(PY) test_svf.py

sim-phaser:               ## phaser: all-pass flatness + notches that move with bias
	@$(PY) test_phaser.py

clean:                    ## remove sim scratch files
	@rm -f _*.txt _deck.cir

help:                     ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
