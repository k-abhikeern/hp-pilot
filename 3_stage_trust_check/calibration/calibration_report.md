# Trust-limit calibration on DFT results

ML counts as **wrong** when |DFT − ML| enthalpy above best > 50 meV/atom. *Caught* = share of wrong ML results sent to DFT; *trusted* = share of right ML results let through. Limits are fitted and tested on the same structures, so read them as what the signals can do.

## Si: 20 structures, 14 with a wrong ML result

Current limits (tuned on Si): caught 43%, trusted 0%.

| Signal | Best limit | Caught | Trusted | Balanced |
|---|---|---|---|---|
| enthalpy_spread_meV | 1.95e+04 | 7% | 100% | 54% |
| max_pressure_dev_GPa | 4.19 | 43% | 67% | 55% |
| max_force_eV_A | 0.0145 | 64% | 67% | 65% |

All three calibrated limits together: caught 79%, trusted 50%.

## NaCl: 18 structures, 18 with a wrong ML result

Current limits (tuned on Si): caught 100%, trusted n/a.

| Signal | Best limit | Caught | Trusted | Balanced |
|---|---|---|---|---|
| enthalpy_spread_meV | 0 | 100% | n/a | 100% |
| max_pressure_dev_GPa | 0 | 100% | n/a | 100% |
| max_force_eV_A | 0 | 61% | n/a | 61% |

All three calibrated limits together: caught 100%, trusted n/a.

## CaSiO3: 14 structures, 8 with a wrong ML result

Current limits (tuned on Si): caught 100%, trusted 0%.

| Signal | Best limit | Caught | Trusted | Balanced |
|---|---|---|---|---|
| enthalpy_spread_meV | 331 | 25% | 100% | 62% |
| max_pressure_dev_GPa | 7.74 | 100% | 83% | 92% |
| max_force_eV_A | 0.715 | 50% | 100% | 75% |

All three calibrated limits together: caught 100%, trusted 83%.

## all materials (one shared limit): 52 structures, 40 with a wrong ML result

Current limits (tuned on Si): caught 80%, trusted 0%.

| Signal | Best limit | Caught | Trusted | Balanced |
|---|---|---|---|---|
| enthalpy_spread_meV | 331 | 52% | 100% | 76% |
| max_pressure_dev_GPa | 12.3 | 28% | 100% | 64% |
| max_force_eV_A | 0.715 | 15% | 100% | 57% |

All three calibrated limits together: caught 65%, trusted 100%.

