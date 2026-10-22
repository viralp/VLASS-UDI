# VLASS-UDI — VLASS User Defined Imaging

VLASS UDI is a Flask-based pilot web interface for locating **VLA Sky Survey (VLASS)** measurement sets (MSes), requesting calibrated MSes from the NRAO archive, and launching user-configurable imaging jobs on NRAO computing resources via Slurm job. The interface provides four steps for finding data and running either joint imaging or the single epoch imaging via standard VLASS CASA pipeline.

> **Important:** The web page can be viewed locally, but submitting imaging jobs requires running the interface on an appropriately configured NRAO host (e.g. **nmpost**) with access to `sbatch`, CASA, the relevant Lustre directories, and the archive restoration workflow. Access permissions and available software must already be configured. In future, the interface will be configured such that it can run on any other luster system with Slum or HTCondor facility, with available VLASS archival data. 

## 1. Requirements

- Python 3 with `venv` and `pip` (a recent Python 3 version is recommended).
- Python packages: `flask`, `astropy`, `numpy`, `matplotlib`, `requests`, `pandas`.
- For object-name lookup: `astroquery` (SIMBAD and NED).
- For actual imaging jobs: the appropriate CASA/VLA pipeline installation, Slurm (`sbatch`), `xvfb-run`, and access to the NRAO archive and Lustre file systems. CASA is **not** installed by `pip install casa` here; configure the CASA executable paths in the interface for your environment.

### Set up the Python virtual environment

From your login node and in your project area on Luster system:

```bash

python3 -m <Youar_area>/venv vlass_venv
source <Youar_area>/vlass_venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install flask astropy numpy matplotlib requests pandas astroquery
```

For later sessions to launch interface after downloading VLASS-UDI, reactivate it with:

```bash
cd <Youar_area>/VLASS-UDI
source <Youar_area>/vlass_venv/bin/activate
```

To leave the virtual environment:

```bash
deactivate
```

## 2. Start the web interface

With the virtual environment active:

```bash
python3 VLASS_web_interface.py
```

On success, the terminal prints a message similar to:

```text
Starting VLASS web interface on http://127.0.0.1:5000
```

Open the page in your browser:

```bash
firefox http://127.0.0.1:5000
```

Or paste `http://127.0.0.1:5000` into your browser. If port `5000` is already occupied, the script attempts subsequent ports; use the URL printed in the terminal. To stop the server, press **Ctrl+C** in the terminal (**not** Ctrl+X).

### Access when running on nmpost

To submit jobs, **run the Python web interface on nmpost**, not only on your laptop. The application binds to `127.0.0.1` on the remote host, so if your browser is on your own computer, use SSH port forwarding, for example:

```bash
ssh -L 5000:127.0.0.1:5000 YOUR_USERNAME@nmpost
```

Then start the Flask app **on nmpost** and open `http://127.0.0.1:5000` **on your computer**. Adjust the forwarded port if the application selected another port, and use the appropriate NRAO SSH hostname/access method for your account.

## 3. What the four steps of web interface do

### Step 1 — Find VLASS Measurement Sets

Enter an object name and use **Simbad/NED search** to fill its RA and Dec, or enter coordinates directly. Click **Find VLASS MS**.

1. `Tile_Boundaries.csv` identifies the VLASS tile(s) containing the target position.
2. `vlass_sdm_to_tile.csv` finds the archive IDs for those tile(s), across available epochs and epoch halves.
3. When multiple archive IDs occur for the same tile/epoch/epoch-half, the interface retains the entry with the largest MJD-like timestamp in the archive ID (latest execution by that rule). This is a selection rule, **not** a guarantee that the selected observation has the best quality.
4. Matching archive IDs are displayed as selectable `.ms` names. You can request calibrated MS restoration to the specified Lustre destination.

The existing **Object list CSV** workflow allows multiple targets to be queried. 

### Step 2 — Configure Imaging Pipeline & Submit Job (Under testing)

Configure per-epoch measurement sets and processing flags (target split, initial imaging, masking, self-calibration, delay self-calibration, polarization imaging). Adjust joint imaging/self-calibration options, spectral-index products, data selection, imaging parameters, weighting, and optional peeling settings.

The interface writes `VLASS_web_config.json` and submits the associated CASA/Slurm job. This step supports the **joint-AWP workflow** and combined-epoch processing through the project's joint imaging scripts. This step is non-standard for the VLASS imaging as compared to other steps and it is under testing.

### Step 3 — Run Standard VLASS Pipeline (single epoch)

Select an MS independently for any available VLASS epoch and configure its standard VLASS imaging parameters, including image name, phase center, gridder (`mosaic`, `awp2`, `awproject`), W-projection planes, robust weighting, UV taper, UV range, and cutout image size.

The interface creates an epoch-specific run directory, writes `SEIP_parameter.list`, prepares `casa_imaging_vlass.py`, and submits a separate Slurm job for each chosen epoch.

### Step 4 — Run Standard VLASS Pipeline for Multiple MSes

Select multiple MSes to process together in the **standard multi-MS VLASS pipeline**. Configure the shared image name, phase center, gridder, W-projection planes, robust weighting, UV taper/range, and cutout size (pixels or arcminutes).

The interface creates a multi-MS run directory, prepares `SEIP_parameter.list` and `casa_imaging_vlass_multims.py`, and submits a Slurm job for combined processing of the selected measurement sets.

## 5. Output and execution notes

- Steps 2–4 use run-specific date/time directories to help prevent collisions with products from earlier runs.
- Archive-restored MSes may be placed inside nested subdirectories; the generated job scripts include logic to resolve these paths before CASA imaging.
- Job email notifications are requested using the email address entered in the relevant step.
- Job execution time depends on archive restoration, scheduling, data size, and imaging settings. Inspect Slurm and CASA logs on the execution host if a job fails.
- The default product root, CASA executable paths, and archive Lustre directory are configured at the beginning of `VLASS_web_interface.py`. Review them before deploying under another account.

## 6. Quick troubleshooting

**Missing tile or SDM mapping:** Confirm `Tile_Boundaries.csv` and `vlass_sdm_to_tile.csv` are in the same folder as `VLASS_web_interface.py`, and check that their column formats match the expected data.

**SIMBAD/NED unavailable:** Install `astroquery` and verify network access, or enter RA/Dec manually.

**`sbatch: command not found`:** You are likely on a machine without Slurm. Launch the interface on nmpost or another supported NRAO submission host.

**CASA or archive restore failed:** Confirm CASA executable paths, Lustre permissions, archived MS availability, and any required supporting scripts. Check the submitted job's Slurm output and CASA log.

**Port already in use:** Read the terminal output to find the actual port chosen by the script.
