#!/bin/sh
# SLURM job template for YARGLA, based on /home/abhikeern/imp_script/run_vasp_yargla.slurm.
# Stage 4 fills in the names written in curly brackets. Edit this file to run on another
# cluster (modules, VASP path, srun line); keep the curly-bracket names where they are.
#SBATCH --job-name=hp_b03
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --threads-per-core=1
#SBATCH --output=hp_b03.out
#SBATCH --time=01:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

# Run each calculation in this batch one after another, and record how each one ended.
# Paths are relative to the folder the job is submitted from, so the whole run folder can be moved.
for calc in ../calcs/s009_15GPa; do
    cd "$SLURM_SUBMIT_DIR/$calc" || continue
    echo "start $(date +%T)" > status.txt
    srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 --threads-per-core=1 vasp_std > vasp.out 2>&1
    echo "exit_code $? end $(date +%T)" >> status.txt
done
