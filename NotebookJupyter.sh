#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH -p cpu
#SBATCH -J Caos
#SBATCH --time=6:00:00

source ~/.bashrc
conda init
conda activate ilumpy

ipaddress=172.20.10.15
echo $ipaddress

jupyter-notebook --ip=$ipaddress
