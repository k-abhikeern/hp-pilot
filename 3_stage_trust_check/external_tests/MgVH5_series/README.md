# MgVH5 test series (database structure, 32 to 90 GPa)

**Question:** the HPCSD database has one MgVH₅ structure at each pressure. Does the machine-learning model (ML) stay close to DFT as pressure rises?

## Inputs

The CIFs come from the HPCSD database (arXiv 2605.14471, calypso.cn after sign-in). They are in `0_stage_softwares_resources_etc/data/` and are gitignored.

| File | Pressure |
|---|---|
| `MgVH5.cif` | 32 GPa |
| `MgVH5 (1).cif` to `MgVH5 (6).cif` | 40, 50, 60, 70, 80, 90 GPa |

## Run it

```bash
cd /home/abhikeern/project/7_OSI/3_stage_trust_check/external_tests/MgVH5_series
~/miniconda3/envs/osi/bin/python run_series.py submit    # ML relax + DFT inputs + one SLURM job
~/miniconda3/envs/osi/bin/python run_series.py collect   # table and figure, after the job finishes
```

## I want to... (where to change things)

| I want to... | Change in `run_series.py` |
|---|---|
| test other pressures or files | the `CASES` list at the top |
| use a different accuracy | `PROFILE` (`"quick"` or `"standard"`) |
| check the inputs first | `submit --dry-run` (builds inputs, sends nothing) |

## Files

| File | What it is |
|---|---|
| `run_series.py` | ML relax, DFT inputs, SLURM submit, collect and plot |
| `series_<date>_<time>/` | one run: `calcs/` (VASP, gitignored), `jobs/`, `ml_results.csv` |
| `outputs/series_results.csv` | one row per pressure: ML and DFT enthalpy and volume, error |
| `outputs/mgvh5_ml_vs_dft.png` | the figure: ML minus DFT vs pressure, and volumes vs pressure |
| `outputs/mgvh5_ml_error_video.png` | single panel, large text, for the video (optional) |

## Results (quick DFT, 23 Oct)

| Pressure | DFT pressure | ML minus DFT | DFT volume | ML volume |
|---|---|---|---|---|
| 32 GPa | 32.8 GPa | −164 meV/atom | 5.115 Å³ | 4.816 Å³ |
| 40 GPa | 40.8 GPa | −184 meV/atom | 4.940 Å³ | 4.737 Å³ |
| 50 GPa | 50.7 GPa | −195 meV/atom | 4.755 Å³ | 4.655 Å³ |
| 60 GPa | 60.7 GPa | −221 meV/atom | 4.594 Å³ | 4.513 Å³ |
| 70 GPa | 70.6 GPa | −224 meV/atom | 4.454 Å³ | 4.445 Å³ |
| 80 GPa | 80.6 GPa | −227 meV/atom | 4.330 Å³ | 4.386 Å³ |
| 90 GPa | 90.7 GPa | −218 meV/atom | 4.217 Å³ | 4.282 Å³ |

- DFT keeps the database structure at every pressure: its volume equals the CIF volume.
- ML is wrong at every pressure, against the 50 meV/atom line, and its volume trend differs from DFT's.
- **Caveats:** ML relaxations did not converge in 300 steps, so ML numbers are approximate. ML and VASP energies have different zero points, so only the change with pressure is meaningful. One phase is not enough to calibrate the trust limits.
