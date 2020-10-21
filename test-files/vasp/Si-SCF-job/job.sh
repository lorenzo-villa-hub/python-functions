#!/bin/sh
#SBATCH -A project01136
#SBATCH --job-name=Si-PBE-SCF
#SBATCH --mail-user=villa@mm.tu-darmstadt.de
#SBATCH --mail-type=ALL
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --time=00:05:00
#SBATCH -p deflt
#SBATCH --exclusive
#SBATCH --mem-per-cpu=2400
#SBATCH -C avx2
ml intel/2019.2 
ml intel/2019.3 
ml intelmpi/2019.3 
ml fftw/3.3.8 

srun /home/lv51dypu/vasp-5-3-3

automation_vasp.py --contcar --chgcar --wavecar --check-kpoints --error-check
