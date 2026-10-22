#!/bin/sh

#Don't put any commands before the #SBATCH options or they will not work
#SBATCH --mem=200G                        # Amount of memory needed by the whole job.
#SBATCH --time=14-00:00                 # Expected runtime of 2 hours and 30 minutes
#SBATCH --mail-type=END,FAIL             # Send email when Jobs end or fail
#SBATCH -n 10

# casa's python requires a DISPLAY for matplot, so create a virtual X server
echo 'Starting NRAO archive calibrated-MS restore requests before CASA pipeline.'
echo 'Requesting calibrated MS: VLASS1.1.sb34418989.eb34425056.58011.2817505787.ms'
python3 /home/rarg/VLASS_script/non_standard/VLASS_web_project/nrao_archive_get_cal_ms_script.py --sdm-id VLASS1.1.sb34418989.eb34425056.58011.2817505787 --project-code VLASS1.1 --email vparekh@nrao.edu --lustre-path /lustre/aoc/projects/vlass/vparekh/archive/3C75
echo 'Requesting calibrated MS: VLASS2.1.sb38530355.eb38576088.59078.34299474537.ms'
python3 /home/rarg/VLASS_script/non_standard/VLASS_web_project/nrao_archive_get_cal_ms_script.py --sdm-id VLASS2.1.sb38530355.eb38576088.59078.34299474537 --project-code VLASS2.1 --email vparekh@nrao.edu --lustre-path /lustre/aoc/projects/vlass/vparekh/archive/3C75
echo 'Requesting calibrated MS: VLASS3.1.sb43928060.eb43975449.60083.774904618054.ms'
python3 /home/rarg/VLASS_script/non_standard/VLASS_web_project/nrao_archive_get_cal_ms_script.py --sdm-id VLASS3.1.sb43928060.eb43975449.60083.774904618054 --project-code VLASS3.1 --email vparekh@nrao.edu --lustre-path /lustre/aoc/projects/vlass/vparekh/archive/3C75
echo 'Requesting calibrated MS: VLASS4.1.sb49207167.eb49619673.60971.29332094907.ms'
python3 /home/rarg/VLASS_script/non_standard/VLASS_web_project/nrao_archive_get_cal_ms_script.py --sdm-id VLASS4.1.sb49207167.eb49619673.60971.29332094907 --project-code VLASS4.1 --email vparekh@nrao.edu --lustre-path /lustre/aoc/projects/vlass/vparekh/archive/3C75
echo 'Archive requests complete; starting CASA pipeline.'
xvfb-run -d /lustre/aoc/users/vparekh/CASA/casa-6.7.0-31-py3.10.el8/bin/casa --nologger --nogui -c VLASS_awp_joint_run.py

