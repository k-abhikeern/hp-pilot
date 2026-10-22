# Checks that the osi conda env has every package HP-Pilot needs.
from importlib.metadata import version
import torch

packages = ["ase", "pymatgen", "pyxtal", "mace-torch"]
for name in packages:
    print(f"{name:12s} {version(name)}")
print(f"{'torch':12s} {torch.__version__}  (CUDA available: {torch.cuda.is_available()})")
