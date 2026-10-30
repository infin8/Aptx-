# Rollback
Rollback aptx executable/config schema using prior version and DB backup only after compatibility check. System package operations are non-atomic; do not promise reversal. For failed dpkg use guided `dpkg --configure -a`, `apt-get -f install` only with reviewed plan and authorization.
