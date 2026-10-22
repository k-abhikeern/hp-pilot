# Stage 0: software, resources, etc.

**Job:** hold everything we install, download or set up for the project, so it is all in one place.

## What is here

| File | What it is |
|---|---|
| `env_install.log` | full log of creating the `osi` conda env |
| `check_env.py` | checks the env has every package the project needs |
| `env_versions.txt` | package versions found by `check_env.py` |
| `miro_project_card.md` | short project description for the hackathon MIRO board |

## Recreate or check the environment

```bash
# check
~/miniconda3/envs/osi/bin/python check_env.py

# recreate from scratch (same steps as the first install)
conda create -y -n osi python=3.11
conda activate osi
pip install ase pymatgen pyxtal
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install mace-torch
```

## Machine and software facts

- YARGLA: 48 CPU cores, 92 GB RAM, no GPU.
- VASP: `module load vasp/6.5.0` (also 5.4.4 available).
- Quantum ESPRESSO: not installed.
- MACE-MP-0 model files download automatically on first use (about 42 MB for medium) and are cached in `~/.cache/mace/`. No internet is needed after that.

When a new tool is installed for any stage, put its install log and notes here.
