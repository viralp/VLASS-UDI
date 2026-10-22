#!/usr/bin/env python3
"""
Flask web front-end for the VLASS joint-AWP pipeline.

Section 1:
  - Object name + RA/Dec (any format astropy understands).
  - Optional SIMBAD/NED name lookup (Simbad/NED search button).
  - Optional CSV upload with a list of objects:
       * either one column of object names
       * or object, RA, Dec columns
    For each row, find VLASS MS files and display per-object results.
  - Calls VLASS_Tile_Puller_Cleaned.py (the one in the same folder)
    and shows VLASS *.ms names parsed from its stdout.

Section 2:
  - Lets you set *all* parameters from VLASS_awp_joint_parameters.py
    in the same order, including:
      vis_list (via VLASS1/2/3 MS dropdowns)
      processing_flags (target_split, init_imaging, mask, selfcal,
                       delay_selfcal, pol_cleaning per epoch)
      joint_* flags, SPX flags, split parameters, imaging parameters,
      weighting parameters.
  - Writes VLASS_web_config.json, then calls:
      sbatch --mail-user=<email> run_casa.sh
  - If no MS is selected for VLASS1/2/3, it writes report_only=True so
    the CASA script can just generate HTML reports from existing FITS.

Section 3:
  - Per-epoch standard VLASS pipeline:
    * Choose MS for VLASS1/2/3 independently
    * Supply imagename, phasecenter RA/Dec (any reasonable format),
      imaging_mode, pblimit, search_radius_arcsec
    * For each selected MS:
         - Create folder named after MS (without .ms)
         - Create subfolder 'pipeline_run' inside it
         - Write SEIP_parameter.list in pipeline_run
         - Write casa_imaging_vlass.py in pipeline_run, with 'vis'
           set to the full path of the chosen MS
         - Write run_casa_pipeline.sh in pipeline_run and submit via sbatch
"""

import os
import json
import glob
import ast
import re
import socket
import subprocess
import shutil
import csv
import io
import shlex
import math
from datetime import datetime
from pathlib import Path

from flask import Flask, request, render_template_string

from astropy.coordinates import SkyCoord
from astropy import units as u

app = Flask(__name__)

# Path to THIS directory (where VLASS_web_interface.py lives)
SCRIPT_DIR = Path(__file__).resolve().parent
TILE_PULLER_SCRIPT = SCRIPT_DIR / "VLASS_Tile_Puller_Cleaned.py"
NRAO_ARCHIVE_SCRIPT = SCRIPT_DIR / "nrao_archive_get_cal_ms_script.py"
TILE_BOUNDARIES_CSV = SCRIPT_DIR / "Tile_Boundaries.csv"
VLASS_SDM_TO_TILE_CSV = SCRIPT_DIR / "vlass_sdm_to_tile.csv"
DEFAULT_MS_SEARCH_RADIUS_ARCMIN = 30.0
DEFAULT_ARCHIVE_LUSTRE_DIR = "/lustre/aoc/projects/vlass/vparekh/archive"
#VLASS_data_products = "/lustre/aoc/projects/vlass/vparekh/archive/project1"
VLASS_data_products = "/lustre/aoc/projects/vlass/vparekh/process"
STEP2_CASA_PATH = "/lustre/aoc/projects/vlass/vparekh/CASA/casa-6.7.1-12-py3.10.el8/bin/casa"
STEP3_CASA_PATH = "/lustre/aoc/projects/vlass/vparekh/CASA/casa-6.7.1-12-py3.10.el8/bin/casa"
STEP4_CASA_PATH = "/lustre/aoc/projects/vlass/vparekh/CASA/casa-6.7.1-12-py3.10.el8/bin/casa"

# ----------------------------------------------------------------------
# STEP 3 / STEP 4 standard-pipeline web-parameter exposure controls.
#
# Change only True/False here to independently choose which SEIP parameters
# are exposed on the web page for STEP 3 and STEP 4.  Parameter values are
# intentionally blank by default and come from the web form when supplied.
#
# The requested web label "Cutout imsize" is controlled by the "imsize"
# flag below; the existing standard-VLASS SEIP key remains "cutout_imsize".
# ----------------------------------------------------------------------
STEP3_PARAMETER_EXPOSURE = {
    "cell": False,
    "cfcache": False,
    "cfcache_nowb": False,
    "clean_no_mask_selfcal_image": False,
    "conjbeams": False,
    "cyclefactor": False,
    "cycleniter": False,
    "cycleniter_final_image_nomask": False,
    "datacolumn": False,
    "datatype": False,
    "deconvolver": False,
    "editmode": False,
    "field": False,
    "gridder": True,
    "imagename": True,
    "imaging_mode": False,
    "imsize": True,
    "intent": False,
    "mask": False,
    "nbin": False,
    "nchan": False,
    "niter": False,
    "nmajor": False,
    "nsigma": False,
    "nterms": False,
    "output_dir": False,
    "parameter_file": False,
    "pblimit": False,
    "pbmask": False,
    "phasecenter": True,
    "reffreq": False,
    "restfreq": False,
    "robust": True,
    "scales": False,
    "search_radius_arcsec": False,
    "sensitivity": False,
    "specmode": False,
    "spw": False,
    "start": False,
    "stokes": False,
    "threshold": False,
    "uvrange": True,
    "uvtaper": True,
    "vis": True,
    "vlass_plane_reject_ms": False,
    "width": False,
    "wprojplanes": True,
}

STEP4_PARAMETER_EXPOSURE = {
    "cell": False,
    "cfcache": False,
    "cfcache_nowb": False,
    "clean_no_mask_selfcal_image": False,
    "conjbeams": False,
    "cyclefactor": False,
    "cycleniter": False,
    "cycleniter_final_image_nomask": False,
    "datacolumn": False,
    "datatype": False,
    "deconvolver": False,
    "editmode": False,
    "field": False,
    "gridder": True,
    "imagename": True,
    "imaging_mode": False,
    "imsize": True,
    "intent": False,
    "mask": False,
    "nbin": False,
    "nchan": False,
    "niter": False,
    "nmajor": False,
    "nsigma": False,
    "nterms": False,
    "output_dir": False,
    "parameter_file": False,
    "pblimit": False,
    "pbmask": False,
    "phasecenter": True,
    "reffreq": False,
    "restfreq": False,
    "robust": True,
    "scales": False,
    "search_radius_arcsec": False,
    "sensitivity": False,
    "specmode": False,
    "spw": False,
    "start": False,
    "stokes": False,
    "threshold": False,
    "uvrange": True,
    "uvtaper": True,
    "vis": True,
    "vlass_plane_reject_ms": False,
    "width": False,
    "wprojplanes": True,
}

STANDARD_PARAMETER_NAMES = list(STEP3_PARAMETER_EXPOSURE.keys())
STANDARD_SPECIAL_WEB_PARAMS = {
    "vis", "imagename", "phasecenter", "imaging_mode", "imsize",
    "gridder", "wprojplanes", "robust", "uvtaper", "uvrange",
}
STANDARD_PARAMETER_LABELS = {
    "cell": "Cell",
    "cfcache": "Cfcache",
    "cfcache_nowb": "Cfcache nowb",
    "clean_no_mask_selfcal_image": "Clean no mask selfcal image",
    "conjbeams": "Conjbeams",
    "cyclefactor": "Cyclefactor",
    "cycleniter": "Cycleniter",
    "cycleniter_final_image_nomask": "Cycleniter final image nomask",
    "datacolumn": "Datacolumn",
    "datatype": "Datatype",
    "deconvolver": "Deconvolver",
    "editmode": "Editmode",
    "field": "Field",
    "gridder": "Gridder",
    "imagename": "Image name",
    "imaging_mode": "Imaging mode",
    "imsize": "Cutout imsize",
    "intent": "Intent",
    "mask": "Mask",
    "nbin": "Nbin",
    "nchan": "Nchan",
    "niter": "Niter",
    "nmajor": "Nmajor",
    "nsigma": "Nsigma",
    "nterms": "Nterms",
    "output_dir": "Output dir",
    "parameter_file": "Parameter file",
    "pblimit": "Pblimit",
    "pbmask": "Pbmask",
    "phasecenter": "Phasecenter",
    "reffreq": "Reffreq",
    "restfreq": "Restfreq",
    "robust": "Robust value",
    "scales": "Scales",
    "search_radius_arcsec": "Search radius arcsec",
    "sensitivity": "Sensitivity",
    "specmode": "Specmode",
    "spw": "Spw",
    "start": "Start",
    "stokes": "Stokes",
    "threshold": "Threshold",
    "uvrange": "UV range",
    "uvtaper": "UV taper",
    "vis": "Measurement set",
    "vlass_plane_reject_ms": "VLASS plane reject MS",
    "width": "Width",
    "wprojplanes": "W-projplanes",
}
STANDARD_PARAMETER_EXAMPLES = {
    "imsize": "e.g. 1500,1500",
    "gridder": "e.g. mosaic",
    "wprojplanes": "e.g. 1",
    "robust": "e.g. 0.5",
    "uvtaper": "e.g. 10arcsec or 5klambda,3klambda,45deg",
    "uvrange": "e.g. >4klambda or 0~1000klambda",
}

# ----------------------------------------------------------------------
# Script-only post-job cleanup/archive options. These are not shown in the web page.
# ----------------------------------------------------------------------
REMOVE_MS_FILES_AFTER_JOB = False        # remove raw/restored *.ms directories after successful job completion
REMOVE_SPLIT_MS_FILES_AFTER_JOB = False  # remove *split.ms directories after successful job completion
REMOVE_OTHER_FILES_AFTER_JOB = False     # remove non-science CASA products; keep images/models/residuals/SPX products


def normalize_archive_lustre_dir(path: str) -> str:
    """Return the user-supplied archive download directory as a stable path."""
    p = (path or DEFAULT_ARCHIVE_LUSTRE_DIR).strip()
    if not p:
        p = DEFAULT_ARCHIVE_LUSTRE_DIR
    p = os.path.expandvars(os.path.expanduser(p))
    return os.path.normpath(p)



def archive_lustre_dir_for_filesystem(path: str) -> str:
    """Return Archive download directory as a filesystem path for local/Slurm access."""
    p = normalize_archive_lustre_dir(path)
    if p.startswith("aoc/"):
        p = os.path.join("/lustre", p)
    elif p.startswith("lustre/"):
        p = "/" + p
    return os.path.normpath(p)


def replace_casa_command_path(line: str, casa_path: str) -> str:
    """Replace only the CASA executable token in a shell command line."""
    if not casa_path:
        return line
    new_line = re.sub(
        r'(^|\s)(\S*/bin/casa|casa)(?=\s|$)',
        lambda m: m.group(1) + shlex.quote(casa_path),
        line,
        count=1,
    )
    if "xvfb-run" not in new_line and re.search(r'(^|\s)' + re.escape(shlex.quote(casa_path)) + r'(?=\s|$)', new_line):
        new_line = re.sub(
            r'(^|\s)' + re.escape(shlex.quote(casa_path)) + r'(?=\s|$)',
            lambda m: m.group(1) + "xvfb-run -d " + shlex.quote(casa_path),
            new_line,
            count=1,
        )
    return new_line


def ensure_step2_run_script_uses_xvfb(run_script_path: Path):
    """Add xvfb-run -d before the CASA command in the copied Step 2 run script."""
    if not run_script_path.exists():
        return
    lines = run_script_path.read_text().splitlines()
    changed = False
    for idx, line in enumerate(lines):
        if "casa" in line and ("xvfb-run" in line or "--nologger" in line or "--pipeline" in line or "--nogui" in line):
            new_line = replace_casa_command_path(line, STEP2_CASA_PATH)
            if new_line != line:
                lines[idx] = new_line
                changed = True
            break
    if changed:
        run_script_path.write_text("\n".join(lines) + "\n")




def insert_step2_runtime_ms_resolution(run_script_path: Path, ms_names, archive_lustre_dir: str):
    """Insert Step 2 MS path resolution into the copied run_casa.sh before CASA starts."""
    ms_names = [m for m in (ms_names or []) if str(m).strip()]
    if not ms_names or not run_script_path.exists():
        return
    text = run_script_path.read_text()
    if "# Resolve restored archive MS path before CASA" in text:
        return
    resolve_block = make_archive_ms_resolution_shell_block(ms_names, archive_lustre_dir, mode="step2")
    if not resolve_block:
        return
    lines = text.splitlines()
    insert_at = None
    for idx, line in enumerate(lines):
        if "casa" in line and ("xvfb-run" in line or "--nologger" in line or "--pipeline" in line or "--nogui" in line):
            insert_at = idx
            break
    if insert_at is None:
        run_script_path.write_text(text.rstrip() + "\n" + resolve_block + "\n")
    else:
        lines.insert(insert_at, resolve_block.rstrip())
        run_script_path.write_text("\n".join(lines) + "\n")


def safe_path_name(value: str, fallback: str) -> str:
    """Make a compact filesystem-safe name from user/object text."""
    s = (value or "").strip()
    if not s:
        s = fallback
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = s.strip("._-")
    return s or fallback


def username_from_email(email: str) -> str:
    """Use the notification-email prefix as the user directory name."""
    return safe_path_name((email or "").split("@", 1)[0], "unknown_user")


def step_work_directory(email: str, object_name: str, step_suffix: str) -> Path:
    """Return VLASS_data_products/<username>/<object>_<step_suffix>."""
    user_dir = Path(VLASS_data_products) / username_from_email(email)
    obj_dir = safe_path_name(object_name, "unknown_object") + "_" + step_suffix
    work_dir = user_dir / obj_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def run_datetime_stamp() -> str:
    """Return a filesystem-safe local date/time stamp for a new run directory."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def copy_if_present(src_name: str, dest_dir: Path):
    """Copy a local support file into a job directory if it exists."""
    src = SCRIPT_DIR / src_name
    if not src.exists():
        src = Path(src_name)
    if src.exists() and src.is_file():
        shutil.copy2(str(src), str(dest_dir / src.name))


def copy_step2_support_files(dest_dir: Path, use_archive_download: bool = False, peeling_enabled: bool = False):
    """Copy files needed by the joint-AWP Step 2 job into its execution directory."""
    step2_files = [
        "run_casa.sh",
        "VLASS_awp_joint_parameters.py",
        "VLASS_awp_joint_run.py",
        "VLASS_awp_joint_workers.py",
    ]
    if use_archive_download:
        step2_files.append("nrao_archive_get_cal_ms_script.py")
    if peeling_enabled:
        step2_files.extend([
            "casa_img_rms_find_save_region.py",
            "casa_quartical_peeling_VLASS.py",
        ])
    for _name in step2_files:
        copy_if_present(_name, dest_dir)



def copy_step4_support_files(dest_dir: Path):
    """Copy files needed by the standard VLASS multi-MS Step 4 job into its execution directory."""
    for _name in [
        "casa_imaging_vlass_multims.py",
        "nrao_archive_get_cal_ms_script.py",
    ]:
        copy_if_present(_name, dest_dir)


def build_multims_casa_text(template_text: str, vis_values):
    """Inject vis1/vis2/... and matching hifv_importdata sessions into casa_imaging_vlass_multims.py."""
    vis_lines = []
    vis_refs = []
    sessions = []
    for _idx, _vis in enumerate(vis_values, start=1):
        vis_lines.append(f"vis{_idx}=r'{_vis}'")
        vis_refs.append(f"vis{_idx}")
        sessions.append(f"session_{_idx}")
    text = re.sub(r"^\s*vis\d+\s*=.*$", "", template_text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    import_line = "    hifv_importdata(vis=[" + ",".join(vis_refs) + "],session=" + repr(sessions) + ",nocopy=True)"
    if re.search(r"^\s*hifv_importdata\s*\(.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^\s*hifv_importdata\s*\(.*$", import_line, text, count=1, flags=re.MULTILINE)
    elif "try:" in text:
        text = text.replace("try:\n", "try:\n" + import_line + "\n", 1)
    else:
        text += "\ntry:\n" + import_line + "\nfinally:\n    h_save()\n"
    if "__rethrow_casa_exceptions" in text:
        text = text.replace("__rethrow_casa_exceptions", "\n".join(vis_lines) + "\n__rethrow_casa_exceptions", 1)
    else:
        text = "\n".join(vis_lines) + "\n" + text
    return text


def make_step4_archive_ms_resolution_shell_block(ms_items, lustre_dir, script_path="casa_imaging_vlass_multims.py"):
    """Resolve restored archive MS paths and update multi-MS CASA script before CASA starts."""
    archive_root = archive_lustre_dir_for_filesystem(lustre_dir)
    if not ms_items:
        return ""
    lines = []
    lines.append("")
    lines.append("# ----------------------------------------------------------------------")
    lines.append("# Resolve restored archive MS paths for Step 4 before CASA")
    lines.append("# ----------------------------------------------------------------------")
    lines.append("python3 - <<'PYARCHIVEMS4'")
    lines.append("import os, glob, re, time")
    lines.append(f"archive_root = {archive_root!r}")
    lines.append(f"ms_items = {ms_items!r}")
    lines.append(f"script_path = {script_path!r}")
    lines.append("def find_ms(ms_base):")
    lines.append("    for _try in range(720):")
    lines.append("        matches = glob.glob(os.path.join(archive_root, '**', ms_base), recursive=True)")
    lines.append("        matches = [m for m in matches if os.path.basename(m) == ms_base and os.path.exists(m)]")
    lines.append("        matches.sort(key=lambda m: os.path.getmtime(m), reverse=True)")
    lines.append("        if matches:")
    lines.append("            return matches[0]")
    lines.append("        time.sleep(60)")
    lines.append("    raise SystemExit('ERROR: Could not find restored MS %s under %s' % (ms_base, archive_root))")
    lines.append("resolved = []")
    lines.append("for item in ms_items:")
    lines.append("    if item.get('archive'):")
    lines.append("        resolved.append(find_ms(os.path.basename(item.get('name', ''))))")
    lines.append("    else:")
    lines.append("        resolved.append(item.get('path', ''))")
    lines.append("vis_lines = []")
    lines.append("vis_refs = []")
    lines.append("sessions = []")
    lines.append("for idx, vis in enumerate(resolved, start=1):")
    lines.append("    vis_lines.append(\"vis%d=r'%s'\" % (idx, vis))")
    lines.append("    vis_refs.append('vis%d' % idx)")
    lines.append("    sessions.append('session_%d' % idx)")
    lines.append("text = open(script_path).read()")
    lines.append("text = re.sub(r'^\\s*vis\\d+\\s*=.*$', '', text, flags=re.MULTILINE)")
    lines.append("import_line = '    hifv_importdata(vis=[' + ','.join(vis_refs) + '],session=' + repr(sessions) + ',nocopy=True)'")
    lines.append("if re.search(r'^\\s*hifv_importdata\\s*\\(.*$', text, flags=re.MULTILINE):")
    lines.append("    text = re.sub(r'^\\s*hifv_importdata\\s*\\(.*$', import_line, text, count=1, flags=re.MULTILINE)")
    lines.append("else:")
    lines.append("    text = text.replace('try:\\n', 'try:\\n' + import_line + '\\n', 1)")
    lines.append("if '__rethrow_casa_exceptions' in text:")
    lines.append("    text = text.replace('__rethrow_casa_exceptions', '\\n'.join(vis_lines) + '\\n__rethrow_casa_exceptions', 1)")
    lines.append("else:")
    lines.append("    text = '\\n'.join(vis_lines) + '\\n' + text")
    lines.append("open(script_path, 'w').write(text)")
    lines.append("print('Updated casa_imaging_vlass_multims.py vis/session list from archive restore directory:', resolved)")
    lines.append("PYARCHIVEMS4")
    lines.append("")
    return "\n".join(lines)

# ----------------------------
# Helpers
# ----------------------------

# liberal .ms matcher for anything the tile puller prints
MS_REGEX = re.compile(r"([A-Za-z0-9._\\-]+\\.ms)")


def _extract_ms_from_stdout(stdout_text: str):
    """
    Extract measurement-set names ending in '.ms' from tile-puller stdout,
    without dumping the whole stdout back to the user.

    Strategy:
      - Look only at lines containing '.ms'
      - Split on whitespace
      - Strip simple punctuation around tokens
      - Keep unique tokens ending with '.ms'
    """
    ms_names = []
    for line in stdout_text.splitlines():
        if ".ms" not in line:
            continue
        for tok in re.split(r"\s+", line.strip()):
            tok = tok.strip(",:;()")
            if tok.endswith(".ms") and tok not in ms_names:
                ms_names.append(tok)
    return ms_names


def run_cmd(cmd, cwd=None):
    """
    Python 3.6 compatible subprocess wrapper.
    Returns CompletedProcess with .stdout/.stderr as text.
    """
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        cwd=cwd,
    )


def _fix_dotted_dms(dec_str: str) -> str:
    """
    Fix Dec strings like '+67.25.48.780' -> '+67 25 48.780' so Astropy can parse them.
    If it doesn’t look like that pattern, return unchanged.
    """
    s = (dec_str or "").strip()
    if not s:
        return s

    sign = ""
    if s[0] in "+-":
        sign = s[0]
        s = s[1:]

    parts = s.split(".")
    # e.g. ["67","25","48","780"] -> "67 25 48.780"
    if len(parts) >= 3:
        deg = parts[0]
        arcmin = parts[1]
        sec = ".".join(parts[2:])
        return f"{sign}{deg} {arcmin} {sec}"
    else:
        return sign + s


def parse_ra_dec_to_deg(ra_str: str, dec_str: str):
    """
    Parse RA/Dec strings into decimal degrees using astropy.

    Accepts, for example:
      RA:
        - "266.4194"
        - "17 45 40.6"
        - "17:45:40.6"
      Dec:
        - "-29.0042"
        - "-29 00 15"
        - "-29:00:15"
        - "+67.25.48.780" (normalized to +67 25 48.780)

    Strategy:
      1) Try both as simple decimal degrees.
      2) Try RA hourangle, Dec degrees (hms + dms).
      3) Let SkyCoord guess.
    """
    ra_s = (ra_str or "").strip()
    dec_s_raw = (dec_str or "").strip()
    if not ra_s or not dec_s_raw:
        raise ValueError("RA and Dec must not be empty.")

    # Normalize dotted DMS formats and stray commas
    dec_s = _fix_dotted_dms(dec_s_raw.replace(",", " "))

    # 1) simple decimal degrees (RA, Dec)
    try:
        return float(ra_s), float(dec_s)
    except ValueError:
        pass

    # 2) hourangle for RA, degrees for Dec (hms, dms)
    try:
        c = SkyCoord(ra_s, dec_s, unit=(u.hourangle, u.deg), frame="icrs")
        return float(c.ra.deg), float(c.dec.deg)
    except Exception:
        pass

    # 3) let astropy guess
    c = SkyCoord(ra_s, dec_s, frame="icrs")
    return float(c.ra.deg), float(c.dec.deg)


def format_phasecenter_string(ra_str: str, dec_str: str) -> str:
    """
    Build CASA-ready phasecenter string for SEIP_parameter.list like:
        'J2000 03:05:06.51 +67.25.48.780'

    RA:  h:m:s with colons
    Dec: d.m.s with dots, e.g. +DD.MM.SS.sss
    """
    ra_deg, dec_deg = parse_ra_dec_to_deg(ra_str, dec_str)
    c = SkyCoord(ra_deg * u.deg, dec_deg * u.deg, frame="icrs")

    # RA in hms with colons, 2 decimal places in seconds
    ra_hms = c.ra.to_string(unit=u.hour, sep=":", precision=2, pad=True)

    # Dec in dms with colons, 3 decimal places in seconds, then replace ':' with '.'
    dec_dms = c.dec.to_string(
        unit=u.deg, sep=":", alwayssign=True, precision=3, pad=True
    )
    dec_dotted = dec_dms.replace(":", ".")

    return f"J2000 {ra_hms} {dec_dotted}"


def split_phasecenter_input(phasecenter_value: str):
    """Split one web-field value 'RA, Dec' into RA and Dec strings."""
    s = str(phasecenter_value or "").strip()
    if not s:
        return "", ""
    if "," in s:
        ra_s, dec_s = s.split(",", 1)
        return ra_s.strip(), dec_s.strip()
    m = re.search(r"\s([+-]\d)", s)
    if m:
        return s[:m.start()].strip(), s[m.start():].strip()
    raise ValueError("Phasecenter must be supplied as RA, Dec")


def format_phasecenter_input(phasecenter_value: str) -> str:
    """Build CASA-ready phasecenter string from one web-field value 'RA, Dec'."""
    ra_s, dec_s = split_phasecenter_input(phasecenter_value)
    if not ra_s or not dec_s:
        raise ValueError("Phasecenter must include both RA and Dec")
    return format_phasecenter_string(ra_s, dec_s)


def _format_generic_seip_value(raw_value):
    """Format a user-entered SEIP value without inventing a default."""
    s = str(raw_value or "").strip()
    if not s:
        return None
    try:
        return repr(ast.literal_eval(s))
    except Exception:
        return repr(s)


def _format_uvtaper_seip_value(raw_value):
    """Return CASA-style uvtaper as a Python string-vector literal."""
    s = str(raw_value or "").strip()
    if not s:
        return None
    if s.startswith("[") and s.endswith("]"):
        try:
            value = ast.literal_eval(s)
            if isinstance(value, (list, tuple)):
                return repr([str(v) for v in value if str(v).strip()])
        except Exception:
            pass
    parts = [part.strip().strip("'\"") for part in s.split(",") if part.strip()]
    return repr(parts) if parts else None



def convert_cutout_imsize_to_pixels(raw_value, mode_value):
    """Return cutout_imsize pixel pair from pixel or angular arcmin web input."""
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    mode = str(mode_value or "pixel").strip().lower()
    parts = [p for p in re.split(r"[\[\],\s]+", raw) if p]
    if not parts:
        return None
    values = [float(p) for p in parts[:2]]
    if len(values) == 1:
        values.append(values[0])
    if mode in ("arcmin", "angular", "angular_arcmin"):
        # Default VLASS imaging cell size is 0.6 arcsec/pixel.
        values = [(v * 60.0) / 0.6 for v in values]
    ci0 = int(round(values[0]))
    ci1 = int(round(values[1]))
    return ci0, ci1


def build_standard_seip_lines(params, exposure, vis_values):
    """Build only the enabled, user-supplied STEP 3/4 SEIP_parameter.list entries."""
    lines = []

    if exposure.get("imagename"):
        value = str(params.get("imagename", "") or "").strip()
        if value:
            lines.append("imagename=" + repr(value))

    if exposure.get("phasecenter"):
        phasecenter_value = str(params.get("phasecenter", "") or "").strip()
        ra_value = str(params.get("phase_ra", "") or "").strip()
        dec_value = str(params.get("phase_dec", "") or "").strip()
        if phasecenter_value:
            lines.append("phasecenter=" + repr(format_phasecenter_input(phasecenter_value)))
        elif ra_value or dec_value:
            if not ra_value or not dec_value:
                raise ValueError("Phasecenter must include both RA and Dec")
            lines.append("phasecenter=" + repr(format_phasecenter_string(ra_value, dec_value)))

    if exposure.get("imaging_mode"):
        value = str(params.get("imaging_mode", "") or "").strip()
        if value:
            lines.append("imaging_mode=" + repr(value))

    # The existing standard-VLASS parameter file uses cutout_imsize for this web control.
    if exposure.get("imsize"):
        pix_pair = convert_cutout_imsize_to_pixels(
            params.get("cutout_imsize", ""),
            params.get("cutout_imsize_mode", "pixel"),
        )
        if pix_pair is not None:
            ci0, ci1 = pix_pair
            lines.append("cutout_imsize=[%d,%d]" % (ci0, ci1))

    if exposure.get("gridder"):
        value = str(params.get("gridder", "") or "").strip()
        if value:
            gridder_key = value.lower()
            if gridder_key == "mosaic":
                lines.append("imaging_mode=" + repr("VLASS-SE-CONT-MOSAIC"))
            elif gridder_key == "awp2":
                lines.append("imaging_mode=" + repr("VLASS-SE-CONT-AWP2"))
            elif gridder_key == "awproject":
                lines.append("imaging_mode=" + repr("VLASS-SE-CONT-AWPROJECT"))
            lines.append("gridder=" + repr(value))

    if exposure.get("wprojplanes"):
        raw = str(params.get("wprojplanes", "") or "").strip()
        if raw:
            lines.append("wprojplanes=%d" % int(float(raw)))

    if exposure.get("robust"):
        raw = str(params.get("robust", "") or "").strip()
        if raw:
            lines.append("robust=" + repr(float(raw)))

    if exposure.get("uvtaper"):
        value = _format_uvtaper_seip_value(params.get("uvtaper", ""))
        if value is not None:
            lines.append("uvtaper=" + value)

    if exposure.get("uvrange"):
        value = str(params.get("uvrange", "") or "").strip()
        if value:
            lines.append("uvrange=" + repr(value))

    for param_name in STANDARD_PARAMETER_NAMES:
        if not exposure.get(param_name) or param_name in STANDARD_SPECIAL_WEB_PARAMS:
            continue
        value = _format_generic_seip_value(params.get(param_name, ""))
        if value is not None:
            lines.append(param_name + "=" + value)

    return lines


def _angle_sep_arcmin(ra1_deg, dec1_deg, ra2_deg, dec2_deg):
    """Small helper for angular separation in arcmin."""
    ra1 = math.radians(float(ra1_deg))
    dec1 = math.radians(float(dec1_deg))
    ra2 = math.radians(float(ra2_deg))
    dec2 = math.radians(float(dec2_deg))
    dra = (ra2 - ra1 + math.pi) % (2.0 * math.pi) - math.pi
    s1 = math.sin((dec2 - dec1) / 2.0)
    s2 = math.sin(dra / 2.0)
    a = s1 * s1 + math.cos(dec1) * math.cos(dec2) * s2 * s2
    a = min(1.0, max(0.0, a))
    return math.degrees(2.0 * math.asin(math.sqrt(a))) * 60.0


def _ra_inside_tile(ra_deg, ra_start_deg, ra_end_deg):
    """Return True if ra_deg is within tile RA limits, allowing wrap at 0/360."""
    ra = float(ra_deg) % 360.0
    start = float(ra_start_deg) % 360.0
    end = float(ra_end_deg) % 360.0
    if start <= end:
        return start <= ra <= end
    return ra >= start or ra <= end


def find_tile_boundary_candidates(ra_deg, dec_deg, search_radius_arcmin=None):
    """Find Tile_Boundaries.csv tile IDs containing the target RA/Dec position."""
    if not TILE_BOUNDARIES_CSV.exists():
        raise FileNotFoundError(f"Tile_Boundaries.csv not found at {TILE_BOUNDARIES_CSV}")

    tiles = []
    with open(TILE_BOUNDARIES_CSV, newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 6:
                continue
            try:
                tile_id = str(row[0]).strip()
                dec_start = float(row[1])
                dec_end = float(row[2])
                ra_start_deg = float(row[3]) * 15.0
                ra_end_deg = float(row[4]) * 15.0
            except Exception:
                continue
            dec_low = min(dec_start, dec_end)
            dec_high = max(dec_start, dec_end)
            if dec_low <= float(dec_deg) <= dec_high and _ra_inside_tile(ra_deg, ra_start_deg, ra_end_deg):
                if tile_id not in tiles:
                    tiles.append(tile_id)
    return tiles

def _parse_sdm_pointings(raw_value):
    """Parse source_ra_dec_deg from vlass_sdm_to_tile.csv."""
    s = str(raw_value or "").strip()
    if not s:
        return []
    try:
        value = json.loads(s)
    except Exception:
        try:
            value = ast.literal_eval(s)
        except Exception:
            return []
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            out.append((float(item["ra"]), float(item["dec"])))
        except Exception:
            continue
    return out


def _archive_mjd_like_value(archive_id: str):
    """Return the trailing MJD-like timestamp from a VLASS archive_id, if present."""
    m = re.search(r"\.(\d{5}\.\d+)(?:\.ms)?$", str(archive_id or "").strip())
    if not m:
        return -1.0
    try:
        return float(m.group(1))
    except Exception:
        return -1.0


def _sdm_epoch_sort_key(group_key):
    """Sort grouped SDM rows by epoch, epoch_half, then tile name."""
    tile_name, epoch, epoch_half = group_key
    try:
        epoch_val = float(epoch)
    except Exception:
        epoch_val = 999.0
    try:
        half_val = float(epoch_half)
    except Exception:
        half_val = 999.0
    return (epoch_val, half_val, str(tile_name))


def find_ms_from_tile_boundary_and_sdm_csv(object_name, ra_str, dec_str, search_radius_arcmin=None):
    """
    Step-1 MS discovery using both Tile_Boundaries.csv and vlass_sdm_to_tile.csv.
    Tile_Boundaries.csv supplies the tile ID(s) containing the target RA/Dec.
    vlass_sdm_to_tile.csv then supplies archive IDs for those same tile ID(s),
    across all available VLASS epochs/epoch halves. No search-radius filtering is used.

    If vlass_sdm_to_tile.csv has duplicate archive IDs for the same tile, epoch,
    and epoch_half, keep one MS by selecting the largest trailing MJD-like
    timestamp in archive_id.
    """
    if not VLASS_SDM_TO_TILE_CSV.exists():
        return [], f"vlass_sdm_to_tile.csv not found at {VLASS_SDM_TO_TILE_CSV}"

    try:
        ra_deg, dec_deg = parse_ra_dec_to_deg(ra_str, dec_str)
    except Exception as exc:
        return [], f"Could not parse RA/Dec into degrees: {exc}"

    try:
        tile_candidates = find_tile_boundary_candidates(ra_deg, dec_deg)
    except Exception as exc:
        return [], f"Could not read/search Tile_Boundaries.csv: {exc}"

    if not tile_candidates:
        return [], (
            f"No Tile_Boundaries.csv tile matched {object_name or 'target'} "
            f"at RA={ra_deg:.6f} deg, Dec={dec_deg:.6f} deg."
        )

    tile_candidate_set = set(tile_candidates)
    grouped_rows = {}
    found_tiles = []

    with open(VLASS_SDM_TO_TILE_CSV, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            tile_name = str(row.get("tile_name", "") or "").strip()
            if tile_name not in tile_candidate_set:
                continue
            archive_id = str(row.get("archive_id", "") or "").strip()
            if not archive_id:
                continue
            epoch = str(row.get("epoch", "") or "").strip()
            epoch_half = str(row.get("epoch_half", "") or "").strip()
            group_key = (tile_name, epoch, epoch_half)
            grouped_rows.setdefault(group_key, []).append(archive_id)
            if tile_name not in found_tiles:
                found_tiles.append(tile_name)

    if not grouped_rows:
        return [], (
            f"Tile_Boundaries.csv matched tile(s): {', '.join(tile_candidates)}. "
            f"No matching archive_id rows were found in vlass_sdm_to_tile.csv for those tile(s)."
        )

    found_ms = []
    duplicate_messages = []
    for group_key in sorted(grouped_rows.keys(), key=_sdm_epoch_sort_key):
        archive_ids = grouped_rows[group_key]
        archive_ids_unique = []
        for archive_id in archive_ids:
            if archive_id not in archive_ids_unique:
                archive_ids_unique.append(archive_id)
        chosen_archive_id = max(
            archive_ids_unique,
            key=lambda value: (_archive_mjd_like_value(value), str(value)),
        )
        ms_name = chosen_archive_id + ("" if chosen_archive_id.endswith(".ms") else ".ms")
        if ms_name not in found_ms:
            found_ms.append(ms_name)
        if len(archive_ids_unique) > 1:
            tile_name, epoch, epoch_half = group_key
            duplicate_messages.append(
                f"{tile_name} VLASS{epoch}.{epoch_half}: found {len(archive_ids_unique)} duplicate archive IDs; "
                f"kept latest {ms_name}"
            )

    # Success: keep the web page quiet and only display the matched MS checkboxes.
    # Error cases above still return a message so missing files or no tile matches are visible.
    return found_ms, None

def call_tile_puller(object_name: str, ra_str: str, dec_str: str):
    """
    Run VLASS_Tile_Puller_Cleaned.py (from the same folder as this file)
    and parse the MS names from stdout. Returns (ms_list, message).

    On success:
        (["foo.ms", "bar.ms"], None)

    On failure:
        ([], "short error message ...")
    """
    if not TILE_PULLER_SCRIPT.exists():
        msg = (
            "VLASS_Tile_Puller_Cleaned.py not found at:\n"
            f"  {TILE_PULLER_SCRIPT}\n"
            "Make sure the working tile-puller script is in the same folder as VLASS_web_interface.py."
        )
        return [], msg

    try:
        ra_deg, dec_deg = parse_ra_dec_to_deg(ra_str, dec_str)
    except Exception as e:
        return [], f"Could not parse RA/Dec into degrees: {e}"

    cmd = [
        "python3",
        str(TILE_PULLER_SCRIPT),
        str(object_name),
        str(ra_deg),
        str(dec_deg),
    ]

    try:
        result = run_cmd(cmd)
    except FileNotFoundError:
        return [], f"Could not run {TILE_PULLER_SCRIPT} (python3 not found or path issue)."

    stdout = result.stdout or ""
    stderr = (result.stderr or "").strip()

    # Robust, but quiet, MS extraction
    ms_names = _extract_ms_from_stdout(stdout)

    # Error / success handling
    if result.returncode != 0:
        if stderr:
            tail = "\n".join(stderr.splitlines()[-8:])
            msg = (
                "Tile puller failed (non-zero exit).\n"
                f"Command: {' '.join(cmd)}\n"
                f"stderr tail:\n{tail}"
            )
        else:
            msg = (
                "Tile puller failed (non-zero exit, no stderr).\n"
                f"Command: {' '.join(cmd)}"
            )
        return [], msg

    if not ms_names:
        # Success exit code but we couldn't see any .ms in the output
        msg = (
            "Tile puller ran but no VLASS *.ms names were parsed from its output. "
            "Please run the tile puller manually on the command line to inspect details."
        )
        return [], msg

    # Success: just return the extracted MS list, no huge stdout blob
    return ms_names, None



def ms_to_sdm_id_and_project_code(ms_name: str):
    """
    Convert a VLASS archive MS name into SDM_ID and project_code.
    Example:
      VLASS1.1.sb34418989.eb34425056.58011.2817505787.ms
    gives:
      SDM_ID = VLASS1.1.sb34418989.eb34425056.58011.2817505787
      project_code = VLASS1.1
    """
    sdm_id = (ms_name or "").strip()
    if sdm_id.endswith(".ms"):
        sdm_id = sdm_id[:-3]
    project_code = sdm_id.split(".sb", 1)[0] if ".sb" in sdm_id else sdm_id.split(".", 1)[0]
    return sdm_id, project_code


def request_calibrated_ms_from_archive(ms_name: str, email: str, lustre_dir: str):
    """
    Submit one NRAO archive restore/download request for a calibrated MS.
    Uses nrao_archive_get_cal_ms_script.py next to this web script.
    """
    if not NRAO_ARCHIVE_SCRIPT.exists():
        return False, f"nrao_archive_get_cal_ms_script.py not found at {NRAO_ARCHIVE_SCRIPT}"

    sdm_id, project_code = ms_to_sdm_id_and_project_code(ms_name)
    lustre_dir = normalize_archive_lustre_dir(lustre_dir)

    try:
        os.makedirs(lustre_dir, exist_ok=True)
    except Exception:
        # The archive service can still copy there if the path exists on the NRAO side.
        pass

    cmd = [
        "python3",
        str(NRAO_ARCHIVE_SCRIPT),
        "--sdm-id", sdm_id,
        "--project-code", project_code,
        "--email", email,
        "--lustre-path", lustre_dir,
    ]
    result = run_cmd(cmd)
    if result.returncode == 0:
        short = (result.stdout or "").strip().splitlines()[-8:]
        return True, f"{ms_name}: submitted archive request. " + " ".join(short)
    else:
        err = (result.stderr or result.stdout or "").strip()
        err_tail = "\n".join(err.splitlines()[-8:])
        return False, f"{ms_name}: archive request failed (code {result.returncode}). {err_tail}"



def expected_archive_ms_path(ms_name: str, lustre_dir: str):
    """
    Expected destination path for a restored calibrated MS requested from the NRAO archive.
    """
    root = archive_lustre_dir_for_filesystem(lustre_dir)
    ms_base = os.path.basename(ms_name)
    matches = glob.glob(os.path.join(root, "**", ms_base), recursive=True)
    matches = [
        m for m in matches
        if os.path.basename(m) == ms_base and (os.path.isdir(m) or os.path.isfile(m))
    ]
    if matches:
        matches.sort(key=lambda m: os.path.getmtime(m), reverse=True)
        return matches[0]
    return os.path.join(root, ms_base)


def epoch_index_from_ms_name(ms_name: str):
    """Return VLASS epoch index 1/2/3/4 from an MS name, or None."""
    m = re.search(r"VLASS\s*([1234])", ms_name or "", re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"VLASS([1234])", ms_name or "", re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None



def _archive_lustre_dir_for_shell(lustre_dir: str):
    """Filesystem path corresponding to the Archive download directory value."""
    return archive_lustre_dir_for_filesystem(lustre_dir)


def make_post_job_cleanup_shell_block(ms_names, lustre_dir, label="VLASS"):
    """
    Shell block added after the CASA command in generated Slurm scripts.
    It tars VLASS_processing_results* into the Archive download directory and,
    depending on script-only options above, removes selected intermediate data.
    """
    archive_root = _archive_lustre_dir_for_shell(lustre_dir)
    ms_bases = [os.path.basename(str(m).strip()) for m in (ms_names or []) if str(m).strip()]

    lines = []
    lines.append("")
    lines.append("# ----------------------------------------------------------------------")
    lines.append("# Post-job result archive and optional cleanup")
    lines.append("# ----------------------------------------------------------------------")
    lines.append("casa_status=$?")
    lines.append("echo \"CASA job exit code: ${casa_status}\"")
    lines.append("if [ \"${casa_status}\" -eq 0 ]; then")
    lines.append(f"  archive_root={shlex.quote(archive_root)}")
    lines.append("  mkdir -p \"${archive_root}\" 2>/dev/null || true")
    lines.append("  stamp=$(date +%Y%m%d_%H%M%S)")
    lines.append(f"  tar_name={shlex.quote(label)}_VLASS_processing_results_${{stamp}}.tar")
    lines.append("  result_dirs=$(find . -maxdepth 3 -type d -name 'VLASS_processing_results*' 2>/dev/null | sort)")
    lines.append("  if [ -n \"${result_dirs}\" ]; then")
    lines.append("    tar -cf \"${archive_root}/${tar_name}\" ${result_dirs}")
    lines.append("    echo \"Saved result tar: ${archive_root}/${tar_name}\"")
    lines.append("  else")
    lines.append("    echo \"No VLASS_processing_results* directory found for tar archive.\"")
    lines.append("  fi")

    if REMOVE_MS_FILES_AFTER_JOB or REMOVE_OTHER_FILES_AFTER_JOB:
        lines.append("  echo \"Removing raw/restored *.ms directories.\"")
        lines.append("  find . -type d -name '*.ms' ! -name '*split.ms' -prune -exec rm -rf {} + 2>/dev/null || true")
        for ms_base in ms_bases:
            q = shlex.quote(ms_base)
            lines.append(f"  find \"${{archive_root}}\" -type d -name {q} -prune -exec rm -rf {{}} + 2>/dev/null || true")

    if REMOVE_SPLIT_MS_FILES_AFTER_JOB or REMOVE_OTHER_FILES_AFTER_JOB:
        lines.append("  echo \"Removing split *.ms directories.\"")
        lines.append("  find . -type d -name '*split.ms' -prune -exec rm -rf {} + 2>/dev/null || true")
        lines.append("  find \"${archive_root}\" -type d -name '*split.ms' -prune -exec rm -rf {} + 2>/dev/null || true")

    if REMOVE_OTHER_FILES_AFTER_JOB:
        lines.append("  echo \"Removing non-science CASA products; keeping image/model/residual/SPX/spectral-index products.\"")
        lines.append("  find . -maxdepth 4 \\")
        lines.append("    \\( -name '*.psf' -o -name '*.psf.tt*' -o -name '*.pb' -o -name '*.pb.tt*' -o \\")
        lines.append("       -name '*.sumwt' -o -name '*.sumwt.tt*' -o -name '*.weight' -o -name '*.weight.tt*' -o \\")
        lines.append("       -name '*.mask' -o -name '*.mask.tt*' -o -name '*.workdirectory' -o -name '*.last' -o \\")
        lines.append("       -name '*.flagversions' -o -name '*.cal' -o -name '*.tbl' \\) \\")
        lines.append("    ! -iname '*image*' ! -iname '*model*' ! -iname '*residual*' ! -iname '*spx*' ! -iname '*spectral*' \\")
        lines.append("    -exec rm -rf {} + 2>/dev/null || true")
        lines.append("  find . -maxdepth 4 -type f \\")
        lines.append("    \\( -name '*.log' -o -name 'casa-*.log' -o -name '*.tmp' -o -name '*.npy' \\) \\")
        lines.append("    ! -iname '*image*' ! -iname '*model*' ! -iname '*residual*' ! -iname '*spx*' ! -iname '*spectral*' \\")
        lines.append("    -exec rm -f {} + 2>/dev/null || true")

    lines.append("else")
    lines.append("  echo \"CASA job failed; skipping result tar and cleanup.\"")
    lines.append("fi")
    lines.append("exit ${casa_status}")
    lines.append("")
    return "\n".join(lines)


def make_archive_ms_resolution_shell_block(ms_names, lustre_dir, mode, script_path="casa_imaging_vlass.py"):
    """
    Shell block that resolves restored NRAO archive MS paths from the nested
    archive directory before CASA starts.
    """
    archive_root = archive_lustre_dir_for_filesystem(lustre_dir)
    ms_bases = [os.path.basename(str(m).strip()) for m in (ms_names or []) if str(m).strip()]
    epoch_map = []
    for ms_base in ms_bases:
        epoch_idx = epoch_index_from_ms_name(ms_base)
        if epoch_idx is not None:
            epoch_map.append((ms_base, epoch_idx - 1))

    if mode == "step2" and not epoch_map:
        return ""
    if mode == "step3" and not ms_bases:
        return ""

    lines = []
    lines.append("")
    lines.append("# ----------------------------------------------------------------------")
    lines.append("# Resolve restored archive MS path before CASA")
    lines.append("# ----------------------------------------------------------------------")
    lines.append("python3 - <<'PYARCHIVEMS'")
    lines.append("import os, glob, json, re, time")
    lines.append(f"archive_root = {archive_root!r}")
    lines.append(f"ms_bases = {ms_bases!r}")
    lines.append(f"epoch_map = {epoch_map!r}")
    lines.append("def find_ms(ms_base):")
    lines.append("    for _try in range(720):")
    lines.append("        matches = glob.glob(os.path.join(archive_root, '**', ms_base), recursive=True)")
    lines.append("        matches = [m for m in matches if os.path.basename(m) == ms_base and os.path.exists(m)]")
    lines.append("        matches.sort(key=lambda m: os.path.getmtime(m), reverse=True)")
    lines.append("        if matches:")
    lines.append("            return matches[0]")
    lines.append("        time.sleep(60)")
    lines.append("    raise SystemExit('ERROR: Could not find restored MS %s under %s' % (ms_base, archive_root))")
    if mode == "step2":
        lines.append("cfg_path = 'VLASS_web_config.json'")
        lines.append("if os.path.exists(cfg_path):")
        lines.append("    with open(cfg_path) as fh:")
        lines.append("        cfg = json.load(fh)")
        lines.append("    vis_list = list(cfg.get('vis_list', []))")
        lines.append("    for ms_base, idx in epoch_map:")
        lines.append("        while len(vis_list) <= idx:")
        lines.append("            vis_list.append('')")
        lines.append("        vis_list[idx] = find_ms(ms_base)")
        lines.append("    cfg['vis_list'] = vis_list")
        lines.append("    with open(cfg_path, 'w') as fh:")
        lines.append("        json.dump(cfg, fh, indent=2)")
        lines.append("    print('Updated VLASS_web_config.json vis_list from archive restore directory:', vis_list)")
    elif mode == "step3":
        lines.append(f"script_path = {script_path!r}")
        lines.append("if ms_bases and os.path.exists(script_path):")
        lines.append("    resolved = find_ms(ms_bases[0])")
        lines.append("    text = open(script_path).read()")
        lines.append("    new_line = \"vis = r'%s'\" % resolved")
        lines.append("    if re.search(r'^\\s*vis\\s*=.*$', text, flags=re.MULTILINE):")
        lines.append("        text = re.sub(r'^\\s*vis\\s*=.*$', new_line, text, count=1, flags=re.MULTILINE)")
        lines.append("    else:")
        lines.append("        text = new_line + '\\n' + text")
        lines.append("    open(script_path, 'w').write(text)")
        lines.append("    print('Updated casa_imaging_vlass.py vis from archive restore directory:', resolved)")
    lines.append("PYARCHIVEMS")
    lines.append("")
    return "\n".join(lines)

def make_archive_then_casa_run_script(ms_names, email, lustre_dir, base_run_script="run_casa.sh"):
    """
    Create a temporary Slurm script that first submits/restores the selected calibrated MSes
    through nrao_archive_get_cal_ms_script.py, then runs the normal CASA pipeline command
    from base_run_script. The original run_casa.sh is not modified.
    """
    ms_names = [m for m in (ms_names or []) if str(m).strip()]
    if not ms_names:
        return base_run_script

    base_path = Path(base_run_script)
    if not base_path.exists():
        raise FileNotFoundError(f"Cannot find {base_run_script} in the current directory.")
    if not NRAO_ARCHIVE_SCRIPT.exists():
        raise FileNotFoundError(f"Cannot find {NRAO_ARCHIVE_SCRIPT}")

    base_text = base_path.read_text()
    archive_lines = []
    archive_lines.append("echo 'Starting NRAO archive calibrated-MS restore requests before CASA pipeline.'")
    for ms_name in ms_names:
        sdm_id, project_code = ms_to_sdm_id_and_project_code(ms_name)
        cmd = [
            "python3",
            str(NRAO_ARCHIVE_SCRIPT),
            "--sdm-id", sdm_id,
            "--project-code", project_code,
            "--email", email,
            "--lustre-path", lustre_dir,
        ]
        archive_lines.append("echo 'Requesting calibrated MS: " + ms_name.replace("'", "'") + "'")
        archive_lines.append(" ".join(shlex.quote(x) for x in cmd))
    archive_lines.append("echo 'Archive requests complete; starting CASA pipeline.'")
    archive_block = "\n".join(archive_lines) + "\n"

    lines = base_text.splitlines()
    insert_at = None
    casa_at = None
    for idx, line in enumerate(lines):
        if "casa" in line and ("xvfb-run" in line or "--nologger" in line or "--pipeline" in line):
            lines[idx] = replace_casa_command_path(line, STEP2_CASA_PATH)
            insert_at = idx
            casa_at = idx
            break
    resolve_block = make_archive_ms_resolution_shell_block(ms_names, lustre_dir, mode="step2")
    cleanup_block = make_post_job_cleanup_shell_block(ms_names, lustre_dir, label="step2")
    if insert_at is None:
        new_text = base_text.rstrip() + "\n\n" + archive_block + resolve_block + cleanup_block
    else:
        lines.insert(insert_at, (archive_block + resolve_block).rstrip())
        lines.insert(casa_at + 2, cleanup_block.rstrip())
        new_text = "\n".join(lines) + "\n"


    out_script = base_path.parent / "run_casa_with_archive.sh"
    out_script.write_text(new_text)
    os.chmod(out_script, 0o755)
    return str(out_script)

# ---- SIMBAD and NED query helpers for STEP 1 ----

def query_simbad_coords(object_name: str):
    """
    Query SIMBAD for RA/Dec of the given object name.
    Returns ((RA_str, Dec_str), error_message) where one of them is None.

    Astroquery/SIMBAD versions differ: some return RA/DEC, while newer
    versions may return ra/dec or RA_ICRS/DEC_ICRS. Keep this helper
    tolerant so Step 1 does not crash with KeyError: 'RA'.
    """
    try:
        from astroquery.simbad import Simbad
    except ImportError:
        return None, "astroquery.simbad not installed in this environment."

    obj = (object_name or "").strip()

    # SIMBAD usually wants Sagittarius A* as "Sgr A*" / "Sagittarius A*".
    # Common shorthand "SgrA" can fail with "Ran out of input", so keep a
    # tiny alias list here without changing the rest of the Step-1 logic.
    aliases = [obj]
    low = obj.lower().replace(" ", "")
    if low in ("sgra", "sgr-a", "sgr_a", "sagittariusa", "sagittariusa*"):
        aliases.extend(["Sgr A*", "Sagittarius A*", "Sgr A"])

    last_error = None
    result = None
    for name_try in aliases:
        if not name_try:
            continue
        try:
            result = Simbad.query_object(name_try)
        except Exception as e:
            last_error = f"SIMBAD query error: {e}"
            result = None
        if result is not None and len(result) > 0:
            break

    # Last-resort built-in fallback for the common Galactic-centre shorthand.
    # This keeps the web form usable even if SIMBAD rejects "SgrA" syntax.
    if (result is None or len(result) == 0) and low in ("sgra", "sgr-a", "sgr_a"):
        return ("266.41683708", "-29.00781056"), None

    if result is None or len(result) == 0:
        return None, last_error or "Object not found in SIMBAD."

    colnames = list(getattr(result, "colnames", []))

    def _first_existing(names):
        for nm in names:
            if nm in colnames:
                return nm
        lowmap = {str(c).lower(): c for c in colnames}
        for nm in names:
            if nm.lower() in lowmap:
                return lowmap[nm.lower()]
        return None

    ra_col = _first_existing(["RA", "ra", "RA_ICRS", "ra_icrs"])
    dec_col = _first_existing(["DEC", "dec", "DEC_ICRS", "dec_icrs"])

    if ra_col is None or dec_col is None:
        return None, f"SIMBAD query returned no RA/Dec columns. Columns were: {', '.join(colnames)}"

    ra_val = result[ra_col][0]
    dec_val = result[dec_col][0]

    try:
        ra_f = float(ra_val)
        dec_f = float(dec_val)
        return (f"{ra_f:.8f}", f"{dec_f:.8f}"), None
    except Exception:
        return (str(ra_val), str(dec_val)), None


def query_ned_coords(object_name: str):
    """
    Query NED for RA/Dec of the given object name.
    Returns ((RA_deg_str, Dec_deg_str), error_message) where one of them is None.
    """
    try:
        from astroquery.ned import Ned
    except ImportError:
        return None, "astroquery.ned not installed in this environment."

    try:
        result = Ned.query_object(object_name)
    except Exception as e:
        return None, f"NED query error: {e}"

    if result is None or len(result) == 0:
        return None, "Object not found in NED."

    ra_deg = float(result["RA"][0])
    dec_deg = float(result["DEC"][0])
    return (f"{ra_deg:.6f}", f"{dec_deg:.6f}"), None


def parse_bool_form(form, name, default):
    """Parse a True/False select element."""
    val = form.get(name, "True" if default else "False")
    return str(val).lower() in ("true", "1", "yes", "on")


def parse_pointingoff(s: str, default):
    """Parse pointingoff from a text input like '300,30' or '300 30'."""
    if not s.strip():
        return default
    try:
        parts = re.split(r"[,\s]+", s.strip())
        vals = [float(p) for p in parts if p]
        if len(vals) >= 2:
            return [vals[0], vals[1]]
        elif len(vals) == 1:
            return [vals[0], default[1]]
    except Exception:
        pass
    return default


def find_ms_in_cwd():
    """
    Return a sorted list of *.ms entries in the current working directory.
    Includes both directories and regular files ending with '.ms'.
    """
    ms_list = []
    for name in sorted(os.listdir(".")):
        path = os.path.join(".", name)
        if name.endswith(".ms") and (os.path.isdir(path) or os.path.isfile(path)):
            ms_list.append(name)
    return ms_list


def pick_epoch_ms(ms_list):
    """
    From a list of MS names, pick at most one MS per epoch (VLASS1/2/3).
    Returns (ms1, ms2, ms3).
    """
    ms1 = ms2 = ms3 = None
    others = []

    for m in ms_list:
        if "VLASS1" in m and ms1 is None:
            ms1 = m
        elif "VLASS2" in m and ms2 is None:
            ms2 = m
        elif "VLASS3" in m and ms3 is None:
            ms3 = m
        else:
            others.append(m)

    # If nothing matched VLASS1/2/3 explicitly, just fill from the front of the list
    remaining = [x for x in ms_list if x not in (ms1, ms2, ms3)]
    if ms1 is None and remaining:
        ms1 = remaining.pop(0)
    if ms2 is None and remaining:
        ms2 = remaining.pop(0)
    if ms3 is None and remaining:
        ms3 = remaining.pop(0)

    return ms1, ms2, ms3


# ----------------------------
# HTML template
# ----------------------------

TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>VESI – VLASS Extended Source Imaging</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        margin: 20px;
        background-color: #ffffff;
        color: #003366;
      }
      a { color: #0055aa; text-decoration: none; }
      a:hover { text-decoration: underline; }
      fieldset {
        margin-bottom: 1.5em;
        border: 1px solid #88aacc;
        border-radius: 6px;
      }
      legend {
        font-weight: bold;
        font-size: 1.05em;
        padding: 0 6px;
        color: #002244;
      }
      label { display: inline-block; width: 190px; vertical-align: top; }
      input[type=text] { width: 260px; }
      .ms-list { max-height: 260px; overflow-y: auto; border: 1px solid #ccc; padding: 6px; }
      .ms-block { border: 1px solid #ddd; padding: 8px; margin-bottom: 8px; border-radius: 4px; }
      .section-title { font-size: 1.05em; font-weight: bold; margin-top: 0.8em; }
      select { min-width: 80px; }
      textarea { width: 260px; height: 4em; }
      pre {
        font-size: 0.9em;
        white-space: pre-wrap;
        border-left: 4px solid #88aacc;
        padding-left: 8px;
      }
      button {
        background-color: #0055aa;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 6px 14px;
        cursor: pointer;
        font-weight: bold;
      }
      button:hover {
        background-color: #003f7d;
      }
      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
      }
      .header-logo img {
        max-height: 120px;
      }
      .header-title {
        text-align: center;
        flex: 1;
        margin: 0 20px;
      }
      .header-title img {
        max-height: 120px;
      }
      .header-title h2 {
        font-size: 1.6em;
        margin: 4px 0 8px;
        text-transform: none;
        letter-spacing: 0.12em;
      }
      .header-title p {
        margin: 4px 0 0;
        font-size: 0.95em;
      }
    </style>
    <script>
      function submitFormOnce(button) {
        if (!button || button.getAttribute("data-submitting") === "1") { return false; }
        var form = button.form;
        if (!form) { return true; }
        button.setAttribute("data-submitting", "1");
        if (button.name) {
          var actionInput = document.createElement("input");
          actionInput.type = "hidden";
          actionInput.name = button.name;
          actionInput.value = button.value;
          form.appendChild(actionInput);
        }
        form.submit();
        return false;
      }

      function openBrowse(fieldId) {
        var url = "/browse_ms?field=" + encodeURIComponent(fieldId);
        var browseWindow = window.open(url, "_blank", "width=900,height=650,menubar=no,toolbar=no,location=no,status=no,scrollbars=yes");
        if (browseWindow) { browseWindow.focus(); }
        return false;
      }
    </script>
  </head>
  <body>
    <div class="header">
      <div class="header-logo">
        <!-- Replace with actual VLA logo path if different -->
        <img src="{{ url_for('static', filename='vla_logo.png') }}" alt="VLA logo">
      </div>
      <div class="header-title">
        <!-- Center VESI logo image instead of text -->
        <img src="{{ url_for('static', filename='VESI.png') }}" alt="VESI logo">
        <h2>VLASS Extended Source Imaging</h2>
        <p>
          Download data from
          <a href="https://data.nrao.edu/" target="_blank">VLA Archive</a>
        </p>
      </div>
      <div class="header-logo">
        <!-- Replace with actual VLASS logo path if different -->
        <img src="{{ url_for('static', filename='vlass_logo.png') }}" alt="VLASS logo">
      </div>
    </div>

    {% if message %}
      <pre><b>{{ message }}</b></pre>
    {% endif %}

    <form method="post" action="{{ url_for('index') }}" enctype="multipart/form-data">
      <!-- SECTION 1: FIND MS -->
      <fieldset>
        <legend>STEP 1 – Find VLASS Measurement Sets</legend>
        <p>
          <label for="object_name">Object name:</label>
          <input type="text" id="object_name" name="object_name"
                 value="{{ object_name or '' }}">
          <button type="submit" name="action" value="query_name" onclick="return submitFormOnce(this);">Simbad/NED search</button>
        </p>
        <p>
          <label for="ra_tile">R.A.:</label>
          <input type="text" id="ra_tile" name="ra_tile"
                 value="{{ ra_tile or '' }}">
        </p>
        <p>
          <label for="dec_tile">Dec.:</label>
          <input type="text" id="dec_tile" name="dec_tile"
                 value="{{ dec_tile or '' }}">
        </p>


        {% if simbad_coords or simbad_error or ned_coords or ned_error %}
          <div style="margin-top: 0.5em; margin-bottom: 0.5em;">
            {% if simbad_coords %}
              <p><b>SIMBAD:</b> RA {{ simbad_coords[0] }}, Dec {{ simbad_coords[1] }}</p>
            {% elif simbad_error %}
              <p><b>SIMBAD:</b> {{ simbad_error }}</p>
            {% endif %}

            {% if ned_coords %}
              <p><b>NED:</b> RA {{ ned_coords[0] }} deg, Dec {{ ned_coords[1] }} deg</p>
            {% elif ned_error %}
              <p><b>NED:</b> {{ ned_error }}</p>
            {% endif %}
          </div>
        {% endif %}

        <p>
          <label for="csv_file">Object list CSV:</label>
          <input type="file" id="csv_file" name="csv_file" accept=".csv">
          <button type="submit" name="action" value="process_csv" onclick="return submitFormOnce(this);">Process CSV</button>
        </p>

        <p>
          <button type="submit" name="action" value="find_ms" onclick="return submitFormOnce(this);">Find VLASS MS</button>
        </p>

        {% if found_ms %}
          <p><b>VLASS MSes:</b></p>
          <div class="ms-list">
            {% for m in found_ms %}
              <p>
                <input type="checkbox" name="download_ms" value="{{ m }}" checked>
                {{ m }}
                <input type="hidden" name="found_ms_hidden" value="{{ m }}">
              </p>
            {% endfor %}
          </div>
          <p>
            <label for="email1">Notification email:</label>
            <input type="text" id="email1" name="email1" value="{{ email or '' }}">
          </p>
          <p>
            <label for="archive_lustre_dir">Archive download directory:</label>
            <input type="text" id="archive_lustre_dir" name="archive_lustre_dir"
                   value="{{ archive_lustre_dir or default_archive_lustre_dir }}">
          </p>
          <p>
            <button type="submit" name="action" value="download_selected_ms" onclick="return submitFormOnce(this);">
              Download selected calibrated MS
            </button>
          </p>
        {% endif %}

        {% if csv_results %}
          <p><b>VLASS MSes from CSV:</b></p>
          <div class="ms-list">
            {% for row in csv_results %}
              <div class="ms-block">
                <p><b>{{ row['object'] }}</b>
                   {% if row['ra'] or row['dec'] %}
                     (RA {{ row['ra'] or '?' }}, Dec {{ row['dec'] or '?' }})
                   {% endif %}
                </p>
                {% if row['error'] %}
                  <p>{{ row['error'] }}</p>
                {% else %}
                  <ul>
                    <li>VLASS1: {{ row['ms1'] or 'None found' }}</li>
                    <li>VLASS2: {{ row['ms2'] or 'None found' }}</li>
                    <li>VLASS3: {{ row['ms3'] or 'None found' }}</li>
                  </ul>
                {% endif %}
              </div>
            {% endfor %}
          </div>
        {% endif %}
      </fieldset>

      <!-- SECTION 2: PIPELINE OPTIONS & JOB SUBMISSION -->
      <fieldset>
        <legend>STEP 2 – Configure Imaging Pipeline & Submit Job</legend>

        <!-- 2.1 vis_list + processing_flags -->
        <p class="section-title">Observation Selection & Per-Epoch Options</p>
        <div class="ms-list">
          {% for i in vlass_indices %}
          <div class="ms-block">
            <p><b>VLASS {{ i }}</b></p>
            <p>
              <label>Measurement set:</label>
              <select name="vis{{i}}" id="vis{{i}}" style="width: 260px;">
                <option value="">-- none --</option>
                {% for m in local_ms %}
                  <option value="{{m}}"
                    {% if selected_vis[i] == m %}selected{% endif %}>{{m}}</option>
                {% endfor %}
              </select>
              <button type="button" onclick="return openBrowse('vis{{i}}');">Browse...</button>
            </p>
            <p>
              <label>Target split:</label>
              <select name="vis{{i}}_target_split">
                <option value="True"  {% if per_flags[i]['target_split'] %}selected{% endif %}>True</option>
                <option value="False" {% if not per_flags[i]['target_split'] %}selected{% endif %}>False</option>
              </select>
            </p>
            <p>
              <label>Initial imaging:</label>
              <select name="vis{{i}}_init_imaging">
                <option value="True"  {% if per_flags[i]['init_imaging'] %}selected{% endif %}>True</option>
                <option value="False" {% if not per_flags[i]['init_imaging'] %}selected{% endif %}>False</option>
              </select>
            </p>
            <p>
              <label>Mask:</label>
              <select name="vis{{i}}_mask">
                <option value="True"  {% if per_flags[i]['mask'] %}selected{% endif %}>True</option>
                <option value="False" {% if not per_flags[i]['mask'] %}selected{% endif %}>False</option>
              </select>
            </p>
            <p>
              <label>Selfcal:</label>
              <select name="vis{{i}}_selfcal">
                <option value="True"  {% if per_flags[i]['selfcal'] %}selected{% endif %}>True</option>
                <option value="False" {% if not per_flags[i]['selfcal'] %}selected{% endif %}>False</option>
              </select>
            </p>
            <p>
              <label>Delay selfcal:</label>
              <select name="vis{{i}}_delay_selfcal">
                <option value="True"  {% if per_flags[i]['delay_selfcal'] %}selected{% endif %}>True</option>
                <option value="False" {% if not per_flags[i]['delay_selfcal'] %}selected{% endif %}>False</option>
              </select>
            </p>
            <p>
              <label>Polarization map:</label>
              <select name="vis{{i}}_pol_cleaning">
                <option value="True"  {% if per_flags[i]['pol_cleaning'] %}selected{% endif %}>True</option>
                <option value="False" {% if not per_flags[i]['pol_cleaning'] %}selected{% endif %}>False</option>
              </select>
            </p>
          </div>
          {% endfor %}
        </div>

        <!-- 2.2 joint_deconvolution / joint_selfcal / joint_pol_deconvolution / awp_image_cube -->
        <p class="section-title">Joint Imaging Options</p>
        <p>
          <label for="joint_deconvolution">Joint deconvolution:</label>
          <select id="joint_deconvolution" name="joint_deconvolution">
            <option value="True"  {% if joint_deconvolution %}selected{% endif %}>True</option>
            <option value="False" {% if not joint_deconvolution %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="joint_selfcal">Joint selfcal:</label>
          <select id="joint_selfcal" name="joint_selfcal">
            <option value="True"  {% if joint_selfcal %}selected{% endif %}>True</option>
            <option value="False" {% if not joint_selfcal %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="joint_pol_deconvolution">Joint polarization deconvolution:</label>
          <select id="joint_pol_deconvolution" name="joint_pol_deconvolution">
            <option value="True"  {% if joint_pol_deconvolution %}selected{% endif %}>True</option>
            <option value="False" {% if not joint_pol_deconvolution %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="awp_image_cube">Image cube:</label>
          <select id="awp_image_cube" name="awp_image_cube">
            <option value="True"  {% if awp_image_cube %}selected{% endif %}>True</option>
            <option value="False" {% if not awp_image_cube %}selected{% endif %}>False</option>
          </select>
        </p>

        <!-- 2.3 SPX flags -->
        <p class="section-title">Spectral (Spx) Index Mapping</p>
        <p>
          <label for="spx_map_VLASS1">Spx map VLASS1:</label>
          <select id="spx_map_VLASS1" name="spx_map_VLASS1">
            <option value="True"  {% if spx_map_VLASS1 %}selected{% endif %}>True</option>
            <option value="False" {% if not spx_map_VLASS1 %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="spx_map_VLASS2">Spx map VLASS2:</label>
          <select id="spx_map_VLASS2" name="spx_map_VLASS2">
            <option value="True"  {% if spx_map_VLASS2 %}selected{% endif %}>True</option>
            <option value="False" {% if not spx_map_VLASS2 %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="spx_map_VLASS3">Spx map VLASS3:</label>
          <select id="spx_map_VLASS3" name="spx_map_VLASS3">
            <option value="True"  {% if spx_map_VLASS3 %}selected{% endif %}>True</option>
            <option value="False" {% if not spx_map_VLASS3 %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="spx_map_VLASS_combine">Spx map VLASS combine:</label>
          <select id="spx_map_VLASS_combine" name="spx_map_VLASS_combine">
            <option value="True"  {% if spx_map_VLASS_combine %}selected{% endif %}>True</option>
            <option value="False" {% if not spx_map_VLASS_combine %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="weighted_combine_maps">Weighted combine maps:</label>
          <select id="weighted_combine_maps" name="weighted_combine_maps">
            <option value="True"  {% if weighted_combine_maps %}selected{% endif %}>True</option>
            <option value="False" {% if not weighted_combine_maps %}selected{% endif %}>False</option>
          </select>
        </p>

        <!-- 2.4 split parameters -->
        <p class="section-title">Data Selection & Split Parameters</p>
        <p>
          <label for="colname">Column name:</label>
          <input type="text" id="colname" name="colname"
                 value="{{ colname or 'corrected' }}">
        </p>
        <p>
          <label for="channelaverage">Channel average:</label>
          <select id="channelaverage" name="channelaverage">
            <option value="True"  {% if channelaverage %}selected{% endif %}>True</option>
            <option value="False" {% if not channelaverage %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="timeaverage">Time average:</label>
          <select id="timeaverage" name="timeaverage">
            <option value="True"  {% if timeaverage %}selected{% endif %}>True</option>
            <option value="False" {% if not timeaverage %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="Ra_1">RA 1:</label>
          <input type="text" id="Ra_1" name="Ra_1"
                 value="{{ Ra_1 or '266.4194' }}">
        </p>
        <p>
          <label for="Dec_1">Dec 1:</label>
          <input type="text" id="Dec_1" name="Dec_1"
                 value="{{ Dec_1 or '-29.0042' }}">
        </p>
        <p>
          <label for="R">R (deg):</label>
          <input type="text" id="R" name="R"
                 value="{{ R or '0.1' }}">
        </p>

        <!-- 2.5 masking parameter -->
        <p class="section-title">Masking Threshold</p>
        <p>
          <label for="mask_threshold">Mask threshold (sigma):</label>
          <input type="text" id="mask_threshold" name="mask_threshold"
                 value="{{ mask_threshold or '3' }}">
        </p>

        <!-- 2.6 imaging parameters -->
        <p class="section-title">Imaging Configuration</p>
        <p>
          <label for="cell">Cell size:</label>
          <input type="text" id="cell" name="cell"
                 value="{{ cell or '0.6arcsec' }}">
        </p>
        <p>
          <label for="niter">Niter:</label>
          <input type="text" id="niter" name="niter"
                 value="{{ niter or '20000' }}">
        </p>
        <p>
          <label for="gridder">Gridder:</label>
          <input type="text" id="gridder" name="gridder"
                 value="{{ gridder or 'mosaic' }}">
        </p>
        <p>
          <label for="wprojplanes">W-projplanes:</label>
          <input type="text" id="wprojplanes" name="wprojplanes"
                 value="{{ wprojplanes or '1' }}">
        </p>

        <p>
          <label for="weighting">Visibility weights:</label>
          <select id="weighting" name="weighting">
            <option value="briggs"  {% if weighting == 'briggs' %}selected{% endif %}>briggs</option>
            <option value="natural" {% if weighting == 'natural' %}selected{% endif %}>natural</option>
            <option value="uniform" {% if weighting == 'uniform' %}selected{% endif %}>uniform</option>
          </select>
        </p>
        <p>
          <label for="robust">Robust:</label>
          <input type="text" id="robust" name="robust"
                 value="{{ robust or '0.0' }}">
        </p>

        <p>
          <label for="specmode">Specmode:</label>
          <input type="text" id="specmode" name="specmode"
                 value="{{ specmode or 'mfs' }}">
        </p>
        <p>
          <label for="parallel">Parallel:</label>
          <select id="parallel" name="parallel">
            <option value="True"  {% if parallel %}selected{% endif %}>True</option>
            <option value="False" {% if not parallel %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="imagename_base">Imagename base:</label>
          <input type="text" id="imagename_base" name="imagename_base"
                 value="{{ imagename_base or 'Sgr_pol' }}">
        </p>
<p>
          <label for="uvrange">Uvrange:</label>
          <input type="text" id="uvrange" name="uvrange"
                 value="{{ uvrange or '' }}">
        </p>
        <p>
          <label for="mask">Mask:</label>
          <input type="text" id="mask" name="mask"
                 value="{{ mask or '' }}">
        </p>
        <p>
          <label for="usepointing">Use pointing:</label>
          <select id="usepointing" name="usepointing">
            <option value="True"  {% if usepointing %}selected{% endif %}>True</option>
            <option value="False" {% if not usepointing %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="pointingoff">Pointing offset (e.g. 300,30):</label>
          <input type="text" id="pointingoff" name="pointingoff"
                 value="{{ pointingoff_text or '300,30' }}">
        </p>

        <p>
          <label for="peeling">Peeling:</label>
          <select id="peeling" name="peeling">
            <option value="True"  {% if peeling %}selected{% endif %}>True</option>
            <option value="False" {% if not peeling %}selected{% endif %}>False</option>
          </select>
        </p>
        <p>
          <label for="peeling_num_sources">Number of peel sources:</label>
          <input type="text" id="peeling_num_sources" name="peeling_num_sources"
                 value="{{ peeling_num_sources or '1' }}">
        </p>

        <!-- 2.7 weighted combined maps -->
        <p class="section-title">Weighted Combination of Epochs</p>
        <p>
          <label for="array_size">Array size:</label>
          <input type="text" id="array_size" name="array_size"
                 value="{{ array_size or '5' }}">
        </p>

        <!-- 2.8 SLURM email -->
        <p class="section-title">Job Submission & Email Notification (Joint AWP)</p>
        <p>
          <label for="email2">Notification email:</label>
          <input type="text" id="email2" name="email2"
                 value="{{ email or '' }}">
        </p>

        <p>
          <button type="submit" name="action" value="submit_job" onclick="return submitFormOnce(this);">
            Write VLASS_web_config.json & Submit SBATCH
          </button>
        </p>
      </fieldset>

      <!-- SECTION 3: STANDARD VLASS PIPELINE -->
      <fieldset>
        <legend>STEP 3 – Run Standard VLASS Pipeline</legend>

        <p class="section-title">Per-Epoch Inputs</p>
        <div class="ms-list">
          {% for i in vlass_indices %}
          <div class="ms-block">
            <p><b>VLASS {{ i }}</b></p>
            {% if step3_expose['vis'] %}
            <p>
              <label>Measurement set:</label>
              <select name="std_vis{{i}}" id="std_vis{{i}}" style="width: 260px;">
                <option value="">-- none --</option>
                {% for m in local_ms %}
                  <option value="{{m}}"
                    {% if std_params[i]['vis'] == m %}selected{% endif %}>{{m}}</option>
                {% endfor %}
              </select>
              <button type="button" onclick="return openBrowse('std_vis{{i}}');">Browse...</button>
            </p>
            {% endif %}
            {% if step3_expose['imagename'] %}
            <p>
              <label>Image name:</label>
              <input type="text" name="std_imagename{{i}}"
                     value="{{ std_params[i]['imagename'] }}">
            </p>
            {% endif %}
            {% if step3_expose['phasecenter'] %}
            <p>
              <label>Phasecenter (RA, Dec):</label>
              <input type="text" name="std_phasecenter{{i}}"
                     value="{{ std_params[i]['phasecenter'] }}"
                     placeholder="e.g. 03:05:06.51, +67:25:48.78 or 46.2771, 67.4302">
            </p>
            {% endif %}
            {% if step3_expose['imaging_mode'] %}
            <p>
              <label>Imaging mode:</label>
              <input type="text" name="std_imaging_mode{{i}}"
                     value="{{ std_params[i]['imaging_mode'] }}">
            </p>
            {% endif %}
            {% if step3_expose['imsize'] %}
            <p>
              <label>Cutout imsize:</label>
              <input type="text" name="std_cutout_imsize{{i}}"
                     value="{{ std_params[i]['cutout_imsize'] }}"
                     placeholder="e.g. 1500,1500 or 15">
              <br>
              <label></label>
              <input type="radio" name="std_cutout_imsize_mode{{i}}" value="pixel" {% if std_params[i]['cutout_imsize_mode'] != 'arcmin' %}checked{% endif %}> in pixel
              <input type="radio" name="std_cutout_imsize_mode{{i}}" value="arcmin" {% if std_params[i]['cutout_imsize_mode'] == 'arcmin' %}checked{% endif %}> in arcmin
            </p>
            {% endif %}
            {% if step3_expose['gridder'] %}
            <p>
              <label>Gridder:</label>
              <input type="radio" name="std_gridder{{i}}" value="mosaic" {% if std_params[i]['gridder'] == 'mosaic' %}checked{% endif %}> mosaic
              <input type="radio" name="std_gridder{{i}}" value="awp2" {% if std_params[i]['gridder'] == 'awp2' %}checked{% endif %}> awp2
              <input type="radio" name="std_gridder{{i}}" value="awproject" {% if std_params[i]['gridder'] == 'awproject' %}checked{% endif %}> awproject
            </p>
            {% endif %}
            {% if step3_expose['wprojplanes'] %}
            <p>
              <label>W-projplanes:</label>
              <input type="text" name="std_wprojplanes{{i}}"
                     value="{{ std_params[i]['wprojplanes'] }}"
                     placeholder="e.g. 1">
            </p>
            {% endif %}
            {% if step3_expose['robust'] %}
            <p>
              <label>Robust value:</label>
              <input type="text" name="std_robust{{i}}"
                     value="{{ std_params[i]['robust'] }}"
                     placeholder="e.g. 0.5">
            </p>
            {% endif %}
            {% if step3_expose['uvtaper'] %}
            <p>
              <label>UV taper:</label>
              <input type="text" name="std_uvtaper{{i}}"
                     value="{{ std_params[i]['uvtaper'] }}"
                     placeholder="e.g. 10arcsec or 5klambda,3klambda,45deg">
            </p>
            {% endif %}
            {% if step3_expose['uvrange'] %}
            <p>
              <label>UV range:</label>
              <input type="text" name="std_uvrange{{i}}"
                     value="{{ std_params[i]['uvrange'] }}"
                     placeholder="e.g. >4klambda or 0~1000klambda">
            </p>
            {% endif %}

            {% for param in standard_parameter_names %}
              {% if step3_expose.get(param) and param not in standard_special_web_params %}
            <p>
              <label>{{ standard_parameter_labels.get(param, param) }}:</label>
              <input type="text" name="std_extra_{{param}}{{i}}"
                     value="{{ std_params[i].get(param, '') }}"
                     {% if standard_parameter_examples.get(param) %}placeholder="{{ standard_parameter_examples.get(param) }}"{% endif %}>
            </p>
              {% endif %}
            {% endfor %}
          </div>
          {% endfor %}
        </div>

        <p class="section-title">Job Submission & Email Notification (Standard VLASS)</p>
        <p>
          <label for="email3">Notification email:</label>
          <input type="text" id="email3" name="email3"
                 value="{{ email or '' }}">
        </p>

        <p>
          <button type="submit" name="action" value="submit_std_pipeline" onclick="return submitFormOnce(this);">
            Create SEIP_parameter.list & Submit Standard VLASS Jobs
          </button>
        </p>
      </fieldset>

      <!-- SECTION 4: STANDARD VLASS PIPELINE MULTI-MS -->
      <fieldset>
        <legend>STEP 4 – Run Standard VLASS Pipeline for Multiple MSes</legend>

        <p class="section-title">Multi-MS Inputs</p>
        {% if step4_expose['vis'] %}
        <p>
          <label>Measurement set:</label>
          <select name="std4_vis" id="std4_vis" style="width: 260px;" multiple size="6">
            {% for m in local_ms %}
              <option value="{{m}}"
                {% if m in std4_params['vis_list'] %}selected{% endif %}>{{m}}</option>
            {% endfor %}
          </select>
          <button type="button" onclick="return openBrowse('std4_vis');">Browse...</button>
        </p>
        {% endif %}
        {% if step4_expose['imagename'] %}
        <p>
          <label>Image name:</label>
          <input type="text" name="std4_imagename"
                 value="{{ std4_params['imagename'] }}">
        </p>
        {% endif %}
        {% if step4_expose['phasecenter'] %}
        <p>
          <label>Phasecenter (RA, Dec):</label>
          <input type="text" name="std4_phasecenter"
                 value="{{ std4_params['phasecenter'] }}"
                 placeholder="e.g. 03:05:06.51, +67:25:48.78 or 46.2771, 67.4302">
        </p>
        {% endif %}
        {% if step4_expose['imaging_mode'] %}
        <p>
          <label>Imaging mode:</label>
          <input type="text" name="std4_imaging_mode"
                 value="{{ std4_params['imaging_mode'] }}">
        </p>
        {% endif %}
        {% if step4_expose['imsize'] %}
        <p>
          <label>Cutout imsize:</label>
          <input type="text" name="std4_cutout_imsize"
                 value="{{ std4_params['cutout_imsize'] }}"
                 placeholder="e.g. 1500,1500 or 15">
          <br>
          <label></label>
          <input type="radio" name="std4_cutout_imsize_mode" value="pixel" {% if std4_params['cutout_imsize_mode'] != 'arcmin' %}checked{% endif %}> in pixel
          <input type="radio" name="std4_cutout_imsize_mode" value="arcmin" {% if std4_params['cutout_imsize_mode'] == 'arcmin' %}checked{% endif %}> in arcmin
        </p>
        {% endif %}
        {% if step4_expose['gridder'] %}
        <p>
          <label>Gridder:</label>
          <input type="radio" name="std4_gridder" value="mosaic" {% if std4_params['gridder'] == 'mosaic' %}checked{% endif %}> mosaic
          <input type="radio" name="std4_gridder" value="awp2" {% if std4_params['gridder'] == 'awp2' %}checked{% endif %}> awp2
          <input type="radio" name="std4_gridder" value="awproject" {% if std4_params['gridder'] == 'awproject' %}checked{% endif %}> awproject
        </p>
        {% endif %}
        {% if step4_expose['wprojplanes'] %}
        <p>
          <label>W-projplanes:</label>
          <input type="text" name="std4_wprojplanes"
                 value="{{ std4_params['wprojplanes'] }}"
                 placeholder="e.g. 1">
        </p>
        {% endif %}
        {% if step4_expose['robust'] %}
        <p>
          <label>Robust value:</label>
          <input type="text" name="std4_robust"
                 value="{{ std4_params['robust'] }}"
                 placeholder="e.g. 0.5">
        </p>
        {% endif %}
        {% if step4_expose['uvtaper'] %}
        <p>
          <label>UV taper:</label>
          <input type="text" name="std4_uvtaper"
                 value="{{ std4_params['uvtaper'] }}"
                 placeholder="e.g. 10arcsec or 5klambda,3klambda,45deg">
        </p>
        {% endif %}
        {% if step4_expose['uvrange'] %}
        <p>
          <label>UV range:</label>
          <input type="text" name="std4_uvrange"
                 value="{{ std4_params['uvrange'] }}"
                 placeholder="e.g. >4klambda or 0~1000klambda">
        </p>
        {% endif %}

        {% for param in standard_parameter_names %}
          {% if step4_expose.get(param) and param not in standard_special_web_params %}
        <p>
          <label>{{ standard_parameter_labels.get(param, param) }}:</label>
          <input type="text" name="std4_extra_{{param}}"
                 value="{{ std4_params.get(param, '') }}"
                 {% if standard_parameter_examples.get(param) %}placeholder="{{ standard_parameter_examples.get(param) }}"{% endif %}>
        </p>
          {% endif %}
        {% endfor %}

        <p class="section-title">Job Submission & Email Notification (Standard VLASS Multi-MS)</p>
        <p>
          <label for="email4">Notification email:</label>
          <input type="text" id="email4" name="email4"
                 value="{{ email or '' }}">
        </p>

        <p>
          <button type="submit" name="action" value="submit_std_multims_pipeline" onclick="return submitFormOnce(this);">
            Create SEIP_parameter.list & Submit Standard VLASS Multi-MS Job
          </button>
        </p>
      </fieldset>

    </form>
  </body>
</html>
"""

BROWSE_TEMPLATE = r"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Browse .ms</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 16px; color: #003366; }
      a { color: #0055aa; text-decoration: none; }
      a:hover { text-decoration: underline; }
      code { background: #f3f6fb; padding: 2px 4px; border-radius: 4px; }
      .pathbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:10px; border:1px solid #c9d8ea; border-radius:8px; background:#f7fbff; }
      .pathbar input[type=text] { width: 560px; max-width: 70vw; }
      button { background-color:#0055aa; color:#fff; border:none; border-radius:4px; padding:6px 14px; cursor:pointer; font-weight:bold; }
      button:hover { background-color:#003f7d; }
      .grid { display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin-top:14px; }
      .panel { border:1px solid #c9d8ea; border-radius:8px; padding:10px; background:#fff; }
      table { width:100%; border-collapse:collapse; }
      td { padding:6px 8px; border-bottom:1px solid #eef3f9; vertical-align:top; }
      td.actions { white-space:nowrap; text-align:right; }
      .ms { font-weight:bold; color:#0b5b2a; }
      .dir { color:#003366; }
      .muted { color:#556; font-size:0.95em; }
    </style>
    <script>
      function submitBrowseOnce(button) {
        if (!button || button.getAttribute("data-submitting") === "1") { return false; }
        var form = button.form;
        if (!form) { return true; }
        button.setAttribute("data-submitting", "1");
        form.submit();
        return false;
      }

      function selectMS(fieldId, value) {
        if (!window.opener) { alert("No parent window found."); return; }
        var el = window.opener.document.getElementById(fieldId);
        if (!el) { var els = window.opener.document.getElementsByName(fieldId); if (els && els.length) el = els[0]; }
        if (!el) { alert("Could not find field " + fieldId + " in parent form."); return; }
        var tag = (el.tagName || "").toLowerCase();
        if (tag === "select") {
          var found=false;
          var selectedOption=null;
          for (var i=0;i<el.options.length;i++){
            if (el.options[i].value===value){
              found=true;
              selectedOption=el.options[i];
              break;
            }
          }
          if (!found){
            selectedOption=window.opener.document.createElement("option");
            selectedOption.value=value;
            selectedOption.text=value;
            el.appendChild(selectedOption);
          }
          if (fieldId === "std4_vis" && el.multiple){
            selectedOption.selected=true;
          } else {
            el.value=value;
          }
        } else { el.value=value; }
        window.close();
      }
    </script>
  </head>
  <body>
    <h3>Pick a <code>.ms</code> directory</h3>
    <div class="pathbar">
      <form method="get" action="/browse_ms" style="margin:0; display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
        <input type="hidden" name="field" value="{{ field }}">
        <label for="path" style="font-weight:bold;">Directory:</label>
        <input type="text" id="path" name="path" value="{{ path }}">
        <button type="submit" onclick="return submitBrowseOnce(this);">Go</button>
        {% if parent %}<span class="muted"><a href="/browse_ms?field={{ field }}&path={{ parent|e }}">⬅ parent</a></span>{% endif %}
      </form>
    </div>
    <p class="muted">Current folder: <code>{{ path }}</code></p>
    {% if error %}<p style="color:#b00;"><b>{{ error }}</b></p>{% endif %}
    <div class="grid">
      <div class="panel">
        <h4>Measurement Sets (.ms) in this folder</h4>
        {% if ms_entries %}
          <table><tbody>
          {% for e in ms_entries %}
            <tr><td><span class="ms">{{ e.name }}</span></td><td class="actions"><a href="#" onclick="selectMS('{{ field }}', '{{ e.full|e }}'); return false;">Select</a></td></tr>
          {% endfor %}
          </tbody></table>
        {% else %}<p class="muted"><i>No <code>.ms</code> directories here.</i></p>{% endif %}
      </div>
      <div class="panel">
        <h4>Folders</h4>
        {% if dir_entries %}
          <table><tbody>
          {% for e in dir_entries %}
            <tr><td><span class="dir">{{ e.name }}/</span></td><td class="actions"><a href="/browse_ms?field={{ field }}&path={{ e.full|e }}">Open</a></td></tr>
          {% endfor %}
          </tbody></table>
        {% else %}<p class="muted"><i>No subfolders found here.</i></p>{% endif %}
      </div>
    </div>
  </body>
</html>"""

@app.route("/browse_ms", methods=["GET"])
def browse_ms():
    field = (request.args.get("field", "") or "").strip()
    path = (request.args.get("path", "") or "").strip()
    if not path:
        path = os.path.abspath(os.getcwd())
    path = os.path.expandvars(os.path.expanduser(path))
    path = os.path.abspath(path)
    error = None
    if not os.path.isdir(path):
        error = f"Not a directory: {path}"
        path = os.path.abspath(os.getcwd())
    parent = None
    try:
        parent = os.path.abspath(os.path.join(path, os.pardir))
        if parent == path:
            parent = None
    except Exception:
        parent = None
    entries = []
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if not os.path.isdir(full):
                continue
            entries.append({"name": name, "full": full, "is_ms": name.endswith(".ms")})
        entries.sort(key=lambda d: (not d["is_ms"], d["name"].lower()))
    except Exception as exc:
        error = f"Could not list directory: {exc}"
        entries = []
    ms_entries = [e for e in entries if e.get("is_ms")]
    dir_entries = [e for e in entries if not e.get("is_ms")]
    return render_template_string(BROWSE_TEMPLATE, field=field, path=path, parent=parent, ms_entries=ms_entries, dir_entries=dir_entries, error=error)



@app.route("/", methods=["GET", "POST"])
def index():
    # Defaults mirroring VLASS_awp_joint_parameters.py
    object_name = ""
    ra_tile = ""
    dec_tile = ""

    # Parameter defaults
    joint_deconvolution = True
    joint_selfcal = True
    joint_pol_deconvolution = True
    awp_image_cube = True

    spx_map_VLASS1 = True
    spx_map_VLASS2 = True
    spx_map_VLASS3 = True
    spx_map_VLASS_combine = True
    weighted_combine_maps = True

    colname = "corrected"
    channelaverage = False
    timeaverage = False
    Ra_1 = "266.4194"
    Dec_1 = "-29.0042"
    R = "0.1"

    mask_threshold = "3"

    cell = "0.6arcsec"
    niter = "20000"
    gridder = "mosaic"
    specmode = "mfs"
    wprojplanes = "1"

    weighting = "briggs"
    robust = "0.0"

    parallel = False
    imagename_base = "Sgr_pol"
    field = ""
    spw = ""
    uvrange = ""
    mask = ""
    usepointing = True
    pointingoff = [300.0, 30.0]
    pointingoff_text = "300,30"
    peeling = False
    peeling_num_sources = "1"

    array_size = "5"

    email = ""
    archive_lustre_dir = normalize_archive_lustre_dir(DEFAULT_ARCHIVE_LUSTRE_DIR)
    found_ms = []
    message = None

    # SIMBAD / NED outputs for template
    simbad_coords = None
    simbad_error = None
    ned_coords = None
    ned_error = None

    # CSV results structure
    csv_results = []

    # Local MS entries for dropdown – *.ms dirs/files only
    try:
        local_ms = find_ms_in_cwd()
    except Exception:
        local_ms = []

    vlass_indices = [1, 2, 3, 4]

    # Per-epoch default flags
    per_flags = {
        1: {
            "target_split": False,
            "init_imaging": True,
            "mask": False,
            "selfcal": True,
            "delay_selfcal": False,
            "pol_cleaning": True,
        },
        2: {
            "target_split": False,
            "init_imaging": True,
            "mask": False,
            "selfcal": True,
            "delay_selfcal": False,
            "pol_cleaning": True,
        },
        3: {
            "target_split": False,
            "init_imaging": True,
            "mask": False,
            "selfcal": True,
            "delay_selfcal": False,
            "pol_cleaning": True,
        },
        4: {
            "target_split": False,
            "init_imaging": True,
            "mask": False,
            "selfcal": True,
            "delay_selfcal": False,
            "pol_cleaning": True,
        },

    }
    selected_vis = {1: "", 2: "", 3: "", 4: ""}

    # Section 3: per-epoch standard pipeline options.
    # All STEP 3 / STEP 4 standard-pipeline parameter values start blank and
    # are populated only from the web form (apart from coordinates copied by
    # the existing STEP 1 coordinate helper).
    std_params = {}
    for i in vlass_indices:
        std_params[i] = {name: "" for name in STANDARD_PARAMETER_NAMES}
        std_params[i].update({
            "vis": "",
            "phase_ra": "",
            "phase_dec": "",
            "phasecenter": "",
            "cutout_imsize": "",
            "cutout_imsize_mode": "pixel",
        })

    std4_params = {name: "" for name in STANDARD_PARAMETER_NAMES}
    std4_params.update({
        "vis_list": [],
        "phase_ra": "",
        "phase_dec": "",
        "phasecenter": "",
        "cutout_imsize": "",
        "cutout_imsize_mode": "pixel",
    })

    def copy_step1_coords_to_step2_step3():
        nonlocal Ra_1, Dec_1
        if ra_tile and dec_tile:
            Ra_1 = ra_tile
            Dec_1 = dec_tile
            phasecenter_text = f"{ra_tile}, {dec_tile}"
            for _i in vlass_indices:
                std_params[_i]["phase_ra"] = ra_tile
                std_params[_i]["phase_dec"] = dec_tile
                std_params[_i]["phasecenter"] = phasecenter_text
            std4_params["phase_ra"] = ra_tile
            std4_params["phase_dec"] = dec_tile
            std4_params["phasecenter"] = phasecenter_text

    if request.method == "POST":
        action = request.form.get("action")
        if action == "query_name":
            # Only SIMBAD/NED lookup; no tile puller
            object_name = request.form.get("object_name", "").strip()
            ra_tile = request.form.get("ra_tile", "").strip()
            dec_tile = request.form.get("dec_tile", "").strip()

            if not object_name:
                message = "Please enter an object name for SIMBAD/NED search."
            else:
                simbad_coords, simbad_error = query_simbad_coords(object_name)
                ned_coords, ned_error = query_ned_coords(object_name)
                if simbad_coords:
                    ra_tile, dec_tile = simbad_coords
                elif ned_coords:
                    ra_tile, dec_tile = ned_coords
                copy_step1_coords_to_step2_step3()

        elif action == "find_ms":
            # SECTION 1 – tile puller only, RA/Dec required
            object_name = request.form.get("object_name", "").strip()
            ra_tile = request.form.get("ra_tile", "").strip()
            dec_tile = request.form.get("dec_tile", "").strip()

            if object_name and (not ra_tile or not dec_tile):
                simbad_coords, simbad_error = query_simbad_coords(object_name)
                if simbad_coords:
                    ra_tile, dec_tile = simbad_coords
                ned_coords, ned_error = query_ned_coords(object_name)
                if (not ra_tile or not dec_tile) and ned_coords:
                    ra_tile, dec_tile = ned_coords

            copy_step1_coords_to_step2_step3()

            if not object_name or not ra_tile or not dec_tile:
                message = "Please fill object name, RA and Dec for tile puller."
            else:
                found_ms, msg = find_ms_from_tile_boundary_and_sdm_csv(
                    object_name, ra_tile, dec_tile
                )
                if msg:
                    message = msg

        elif action == "download_selected_ms":
            object_name = request.form.get("object_name", "").strip()
            ra_tile = request.form.get("ra_tile", "").strip()
            dec_tile = request.form.get("dec_tile", "").strip()
            found_ms = request.form.getlist("found_ms_hidden")
            selected_downloads = request.form.getlist("download_ms")
            email = request.form.get("email1", "").strip()
            archive_lustre_dir = normalize_archive_lustre_dir(request.form.get("archive_lustre_dir", DEFAULT_ARCHIVE_LUSTRE_DIR))

            if not selected_downloads:
                message = "Please select at least one VLASS MS to download."
            elif not email:
                message = "Please enter a notification email for NRAO archive download requests."
            else:
                download_messages = []
                for ms_name in selected_downloads:
                    ok, msg = request_calibrated_ms_from_archive(ms_name, email, archive_lustre_dir)
                    download_messages.append(msg)
                message = "NRAO archive calibrated MS requests:\n" + "\n".join(download_messages)

        elif action == "process_csv":
            # Process an uploaded CSV of objects
            object_name = request.form.get("object_name", "").strip()
            ra_tile = request.form.get("ra_tile", "").strip()
            dec_tile = request.form.get("dec_tile", "").strip()

            file = request.files.get("csv_file")
            if not file or file.filename == "":
                message = "Please choose a CSV file to process."
            else:
                try:
                    content = file.read().decode("utf-8")
                    reader = csv.reader(io.StringIO(content))
                    rows = [r for r in reader if any(c.strip() for c in r)]
                except Exception as exc:
                    message = f"Could not read CSV file: {exc}"
                    rows = []

                if rows:
                    # Detect simple header with RA/DEC column names
                    start_index = 0
                    first = rows[0]
                    lower = [c.strip().lower() for c in first]
                    if any("ra" == c or c.startswith("ra ") for c in lower) and \
                       any(c.startswith("dec") for c in lower):
                        start_index = 1

                    for row in rows[start_index:]:
                        if not row:
                            continue
                        obj = row[0].strip()
                        if not obj:
                            continue

                        ra_val = None
                        dec_val = None
                        tile_msg = None
                        ms_list = []

                        # Try to use RA/Dec from columns if present
                        if len(row) >= 3:
                            cand_ra = row[1].strip()
                            cand_dec = row[2].strip()
                            if cand_ra and cand_dec:
                                try:
                                    # Just test parsing; use original strings if OK
                                    _ = parse_ra_dec_to_deg(cand_ra, cand_dec)
                                    ra_val = cand_ra
                                    dec_val = cand_dec
                                except Exception:
                                    ra_val = None
                                    dec_val = None

                        # If RA/Dec not usable, fall back to SIMBAD
                        if ra_val is None or dec_val is None:
                            coords, err = query_simbad_coords(obj)
                            if coords:
                                ra_val, dec_val = coords
                            else:
                                # Can't proceed without coordinates
                                csv_results.append(
                                    {
                                        "object": obj,
                                        "ra": None,
                                        "dec": None,
                                        "ms1": None,
                                        "ms2": None,
                                        "ms3": None,
                                        "error": f"Could not get coordinates: {err}",
                                    }
                                )
                                continue

                        # Now we have RA/Dec strings; use Tile_Boundaries.csv + vlass_sdm_to_tile.csv
                        ms_list, tile_msg = find_ms_from_tile_boundary_and_sdm_csv(
                            obj, ra_val, dec_val
                        )
                        ms1, ms2, ms3 = pick_epoch_ms(ms_list)

                        csv_results.append(
                            {
                                "object": obj,
                                "ra": ra_val,
                                "dec": dec_val,
                                "ms1": ms1,
                                "ms2": ms2,
                                "ms3": ms3,
                                "error": tile_msg,
                            }
                        )
                else:
                    message = "CSV file appears to be empty or unreadable."

        elif action == "submit_job":
            # SECTION 2 ONLY (joint AWP)
            object_name = request.form.get("object_name", "").strip()
            found_ms = request.form.getlist("found_ms_hidden")
            selected_downloads = request.form.getlist("download_ms")
            archive_lustre_dir = normalize_archive_lustre_dir(request.form.get("archive_lustre_dir", DEFAULT_ARCHIVE_LUSTRE_DIR))

            # per-epoch MS and flags
            for i in vlass_indices:
                vis_val = request.form.get(f"vis{i}", "").strip()
                selected_vis[i] = vis_val
                per_flags[i]["target_split"] = parse_bool_form(
                    request.form, f"vis{i}_target_split", per_flags[i]["target_split"]
                )
                per_flags[i]["init_imaging"] = parse_bool_form(
                    request.form, f"vis{i}_init_imaging", per_flags[i]["init_imaging"]
                )
                per_flags[i]["mask"] = parse_bool_form(
                    request.form, f"vis{i}_mask", per_flags[i]["mask"]
                )
                per_flags[i]["selfcal"] = parse_bool_form(
                    request.form, f"vis{i}_selfcal", per_flags[i]["selfcal"]
                )
                per_flags[i]["delay_selfcal"] = parse_bool_form(
                    request.form, f"vis{i}_delay_selfcal", per_flags[i]["delay_selfcal"]
                )
                per_flags[i]["pol_cleaning"] = parse_bool_form(
                    request.form, f"vis{i}_pol_cleaning", per_flags[i]["pol_cleaning"]
                )

            # If Step 1 archive MS boxes are selected, use their expected lustre paths
            # as the Step 2 vis_list entries. This lets one Submit action request data
            # and then run the pipeline against the restored MS locations.
            for ms_name in selected_downloads:
                epoch_idx = epoch_index_from_ms_name(ms_name)
                if epoch_idx in selected_vis:
                    selected_vis[epoch_idx] = expected_archive_ms_path(ms_name, archive_lustre_dir)

            joint_deconvolution = parse_bool_form(
                request.form, "joint_deconvolution", joint_deconvolution
            )
            joint_selfcal = parse_bool_form(
                request.form, "joint_selfcal", joint_selfcal
            )
            joint_pol_deconvolution = parse_bool_form(
                request.form, "joint_pol_deconvolution", joint_pol_deconvolution
            )
            awp_image_cube = parse_bool_form(
                request.form, "awp_image_cube", awp_image_cube
            )

            spx_map_VLASS1 = parse_bool_form(
                request.form, "spx_map_VLASS1", spx_map_VLASS1
            )
            spx_map_VLASS2 = parse_bool_form(
                request.form, "spx_map_VLASS2", spx_map_VLASS2
            )
            spx_map_VLASS3 = parse_bool_form(
                request.form, "spx_map_VLASS3", spx_map_VLASS3
            )
            spx_map_VLASS_combine = parse_bool_form(
                request.form, "spx_map_VLASS_combine", spx_map_VLASS_combine
            )
            weighted_combine_maps = parse_bool_form(
                request.form, "weighted_combine_maps", weighted_combine_maps
            )

            colname = request.form.get("colname", colname).strip()
            channelaverage = parse_bool_form(
                request.form, "channelaverage", channelaverage
            )
            timeaverage = parse_bool_form(
                request.form, "timeaverage", timeaverage
            )
            Ra_1 = request.form.get("Ra_1", Ra_1).strip()
            Dec_1 = request.form.get("Dec_1", Dec_1).strip()
            R = request.form.get("R", R).strip()

            mask_threshold = request.form.get(
                "mask_threshold", mask_threshold
            ).strip()

            cell = request.form.get("cell", cell).strip()
            niter = request.form.get("niter", niter).strip()
            gridder = request.form.get("gridder", gridder).strip()
            wprojplanes = request.form.get("wprojplanes", wprojplanes).strip()
            weighting = request.form.get("weighting", weighting).strip() or "briggs"
            robust = request.form.get("robust", robust).strip() or "0.0"
            specmode = request.form.get("specmode", specmode).strip()
            parallel = parse_bool_form(request.form, "parallel", parallel)
            imagename_base = request.form.get(
                "imagename_base", imagename_base
            ).strip()
            field = request.form.get("field", field).strip()
            spw = request.form.get("spw", spw).strip()
            uvrange = request.form.get("uvrange", uvrange).strip()
            mask = request.form.get("mask", mask).strip()
            usepointing = parse_bool_form(
                request.form, "usepointing", usepointing
            )
            pointingoff_text = request.form.get(
                "pointingoff", pointingoff_text
            ).strip()
            pointingoff = parse_pointingoff(pointingoff_text, pointingoff)
            peeling = parse_bool_form(request.form, "peeling", peeling)
            peeling_num_sources = request.form.get("peeling_num_sources", peeling_num_sources).strip()

            array_size = request.form.get("array_size", array_size).strip()

            email = request.form.get("email2", "").strip()

            # Build vis_list and processing_flags for JSON
            vis_list = [selected_vis[i] for i in vlass_indices]
            processing_flags = [per_flags[i] for i in vlass_indices]

            # Report-only mode if no vis selected
            report_only = all((v.strip() == "" for v in vis_list))

            if not email:
                message = "Please enter an email address for job notification (Section 2)."
            else:
                step2_root = step_work_directory(email, object_name, "step_2")
                step2_dir = step2_root / ("run_" + run_datetime_stamp())
                step2_dir.mkdir(parents=True, exist_ok=True)
                copy_step2_support_files(step2_dir, use_archive_download=bool(selected_downloads), peeling_enabled=peeling)
                ensure_step2_run_script_uses_xvfb(step2_dir / "run_casa.sh")
                if not selected_downloads:
                    insert_step2_runtime_ms_resolution(
                        step2_dir / "run_casa.sh",
                        [v for v in selected_vis.values() if str(v).strip()],
                        archive_lustre_dir,
                    )

                # Convert numeric + RA/Dec for CASA
                try:
                    R_val = float(R)
                except ValueError:
                    R_val = 0.1
                try:
                    mask_val = float(mask_threshold)
                except ValueError:
                    mask_val = 3.0
                try:
                    niter_val = int(float(niter))
                except ValueError:
                    niter_val = 20000

                try:
                    Ra_1_deg, Dec_1_deg = parse_ra_dec_to_deg(Ra_1, Dec_1)
                except Exception as e:
                    message = f"Could not parse Ra_1/Dec 1: {e}"
                else:
                    cfg = {
                        "vis_list": vis_list,
                        "processing_flags": processing_flags,
                        "joint_deconvolution": joint_deconvolution,
                        "joint_selfcal": joint_selfcal,
                        "joint_pol_deconvolution": joint_pol_deconvolution,
                        "awp_image_cube": awp_image_cube,
                        "spx_map_VLASS1": spx_map_VLASS1,
                        "spx_map_VLASS2": spx_map_VLASS2,
                        "spx_map_VLASS3": spx_map_VLASS3,
                        "spx_map_VLASS_combine": spx_map_VLASS_combine,
                        "weighted_combine_maps": weighted_combine_maps,
                        "colname": colname,
                        "channelaverage": channelaverage,
                        "timeaverage": timeaverage,
                        "Ra_1": Ra_1_deg,
                        "Dec_1": Dec_1_deg,
                        "R": R_val,
                        "mask_threshold": mask_val,
                        "cell": cell,
                        "niter": niter_val,
                        "gridder": gridder,
                        "wprojplanes": int(float(wprojplanes)) if wprojplanes else 1,
                        "weighting": weighting,
                        "robust": float(robust) if robust else 0.0,
                        "specmode": specmode,
                        "parallel": parallel,
                        "imagename_base": imagename_base,
                        "field": field,
                        "spw": spw,
                        "uvrange": uvrange,
                        "mask": mask,
                        "usepointing": usepointing,
                        "pointingoff": pointingoff,
                        "peeling": peeling,
                        "peeling_num_sources": int(float(peeling_num_sources)) if peeling_num_sources else 1,
                        "array_size": int(float(array_size)) if array_size else 5,
                        "report_only": report_only,
                    }
                    with open(step2_dir / "VLASS_web_config.json", "w") as f:
                        json.dump(cfg, f, indent=2)

                    # Submit one Slurm job. If Step 1 archive MSes were selected,
                    # the generated wrapper script requests/restores those calibrated MSes
                    # first, then runs the normal CASA pipeline command.
                    try:
                        run_script = make_archive_then_casa_run_script(
                            selected_downloads, email, archive_lustre_dir, base_run_script=str(step2_dir / "run_casa.sh")
                        )
                        if selected_downloads:
                            try:
                                (step2_dir / "run_casa.sh").unlink()
                            except Exception:
                                pass
                        cmd = ["sbatch", f"--mail-user={email}", Path(run_script).name]
                        result = run_cmd(cmd, cwd=str(step2_dir))
                        if result.returncode == 0:
                            if selected_downloads:
                                message = (
                                    f"Submitted archive-download + pipeline job from {step2_dir} via sbatch. Slurm says: "
                                    + (result.stdout or "").strip()
                                )
                            else:
                                message = (
                                    f"Submitted job from {step2_dir} via sbatch. Slurm says: "
                                    + (result.stdout or "").strip()
                                )
                        else:
                            message = (
                                f"sbatch returned code {result.returncode}: "
                                f"{(result.stderr or '').strip()}"
                            )
                    except FileNotFoundError as exc:
                        message = str(exc)
                    except Exception as exc:
                        message = f"Could not create/submit archive-download + pipeline job: {exc}"

        elif action == "submit_std_pipeline":
            # SECTION 3 ONLY – standard VLASS pipeline
            object_name = request.form.get("object_name", "").strip()
            selected_downloads = request.form.getlist("download_ms")
            archive_lustre_dir = normalize_archive_lustre_dir(request.form.get("archive_lustre_dir", DEFAULT_ARCHIVE_LUSTRE_DIR))
            archive_download_by_epoch = {}
            for _ms_name in selected_downloads:
                _epoch_idx = epoch_index_from_ms_name(_ms_name)
                if _epoch_idx in vlass_indices:
                    archive_download_by_epoch[_epoch_idx] = _ms_name

            email = request.form.get("email3", "").strip()

            # Fill only STEP 3 values supplied by the web form.
            for i in vlass_indices:
                std_params[i]["vis"] = request.form.get(f"std_vis{i}", "").strip()
                if i in archive_download_by_epoch:
                    std_params[i]["vis"] = archive_download_by_epoch[i]
                std_params[i]["imagename"] = request.form.get(f"std_imagename{i}", "").strip()
                std_params[i]["phasecenter"] = request.form.get(f"std_phasecenter{i}", "").strip()
                std_params[i]["phase_ra"], std_params[i]["phase_dec"] = split_phasecenter_input(std_params[i]["phasecenter"]) if std_params[i]["phasecenter"] else ("", "")
                std_params[i]["imaging_mode"] = request.form.get(f"std_imaging_mode{i}", "").strip()
                std_params[i]["cutout_imsize"] = request.form.get(f"std_cutout_imsize{i}", "").strip()
                std_params[i]["cutout_imsize_mode"] = request.form.get(f"std_cutout_imsize_mode{i}", "pixel").strip() or "pixel"
                std_params[i]["gridder"] = request.form.get(f"std_gridder{i}", "").strip()
                std_params[i]["wprojplanes"] = request.form.get(f"std_wprojplanes{i}", "").strip()
                std_params[i]["robust"] = request.form.get(f"std_robust{i}", "").strip()
                std_params[i]["uvtaper"] = request.form.get(f"std_uvtaper{i}", "").strip()
                std_params[i]["uvrange"] = request.form.get(f"std_uvrange{i}", "").strip()
                for _param in STANDARD_PARAMETER_NAMES:
                    if STEP3_PARAMETER_EXPOSURE.get(_param) and _param not in STANDARD_SPECIAL_WEB_PARAMS:
                        std_params[i][_param] = request.form.get(f"std_extra_{_param}{i}", "").strip()

            if not email:
                message = "Please enter an email address for job notification (Section 3)."
            else:
                jobs = []
                step3_root = step_work_directory(email, object_name, "step_3")
                step3_stamp = run_datetime_stamp()
                casa_template = SCRIPT_DIR / "casa_imaging_vlass.py"
                if not casa_template.exists():
                    message = (
                        f"Cannot find casa_imaging_vlass.py at {casa_template}. "
                        "Place the standard VLASS pipeline script next to VLASS_web_interface.py."
                    )
                else:
                    template_text = casa_template.read_text()

                    for i in vlass_indices:
                        ms_name = std_params[i]["vis"]
                        if not ms_name:
                            continue  # skip empty epoch

                        ms_path = Path(ms_name)
                        archive_ms_name_for_epoch = archive_download_by_epoch.get(i)
                        if not ms_path.exists() and not archive_ms_name_for_epoch:
                            jobs.append(
                                f"VLASS {i}: MS '{ms_name}' not found in working directory; skipped."
                            )
                            continue

                        ms_base = ms_path.name
                        ms_root = ms_base[:-3] if ms_base.endswith(".ms") else ms_base
                        job_dir = step3_root / f"VLASS{i}_{step3_stamp}"
                        pipeline_dir = job_dir / "pipeline_run"

                        # Create ms_root and pipeline_run directories
                        job_dir.mkdir(exist_ok=True)
                        pipeline_dir.mkdir(exist_ok=True)

                        # --- Write enabled, user-supplied parameters to SEIP_parameter.list ---
                        if archive_ms_name_for_epoch:
                            initial_vis_path = expected_archive_ms_path(archive_ms_name_for_epoch, archive_lustre_dir)
                        else:
                            initial_vis_path = str(ms_path.resolve())

                        try:
                            seip_lines = build_standard_seip_lines(
                                std_params[i], STEP3_PARAMETER_EXPOSURE, [initial_vis_path]
                            )
                        except Exception as exc:
                            jobs.append(
                                f"VLASS {i}: could not prepare SEIP parameters: {exc}"
                            )
                            continue

                        seip_path = pipeline_dir / "SEIP_parameter.list"
                        with open(seip_path, "w") as f:
                            if seip_lines:
                                f.write("\n".join(seip_lines) + "\n")

                        # --- Write casa_imaging_vlass.py in pipeline_run, injecting vis path ---
                        full_vis_path = initial_vis_path
                        injected_line = f"vis = r'{full_vis_path}'\n"

                        archive_restore_block = ""
                        if archive_ms_name_for_epoch:
                            sdm_id, project_code = ms_to_sdm_id_and_project_code(archive_ms_name_for_epoch)
                            archive_cmd = [
                                "python3",
                                str(NRAO_ARCHIVE_SCRIPT),
                                "--sdm-id", sdm_id,
                                "--project-code", project_code,
                                "--email", email,
                                "--lustre-path", archive_lustre_dir,
                            ]
                            archive_restore_block = (
                                "echo 'Starting NRAO archive calibrated-MS restore request before Standard VLASS pipeline.'\n"
                                + "echo 'Requesting calibrated MS: " + archive_ms_name_for_epoch.replace("'", "'") + "'\n"
                                + " ".join(shlex.quote(x) for x in archive_cmd) + "\n"
                                + "echo 'Archive request complete; starting Standard VLASS pipeline.'\n"
                            )

                        vis_pattern = re.compile(r"^\s*vis\s*=.*$", re.MULTILINE)
                        if vis_pattern.search(template_text):
                            new_text = vis_pattern.sub(injected_line.rstrip(), template_text, count=1)
                        elif "__rethrow_casa_exceptions" in template_text:
                            new_text = template_text.replace(
                                "__rethrow_casa_exceptions",
                                injected_line + "__rethrow_casa_exceptions",
                                1,
                            )
                        else:
                            new_text = injected_line + "\n" + template_text


                        imaging_script_path = pipeline_dir / "casa_imaging_vlass.py"
                        imaging_script_path.write_text(new_text)

                        # --- Write run_casa_pipeline.sh in pipeline_run ---
                        run_sh = pipeline_dir / "run_casa_pipeline.sh"
                        run_sh_text = f"""#!/bin/sh
#Don't put any commands before the #SBATCH options or they will not work
#SBATCH --mem=200G                        # Amount of memory needed by the whole job.
#SBATCH --time=14-00:00                   # Expected runtime
#SBATCH --mail-type=END,FAIL              # Send email when Jobs end or fail
#SBATCH --mail-user={email}
#SBATCH -n 1

{archive_restore_block}{make_archive_ms_resolution_shell_block([archive_ms_name_for_epoch], archive_lustre_dir, mode='step3') if archive_ms_name_for_epoch else ''}
# casa's python requires a DISPLAY for matplotlib, so create a virtual X server
xvfb-run -d {shlex.quote(STEP3_CASA_PATH)} --pipeline --nogui -c casa_imaging_vlass.py
{make_post_job_cleanup_shell_block([archive_ms_name_for_epoch or ms_name], archive_lustre_dir, label='step3')}
"""
                        with open(run_sh, "w") as f:
                            f.write(run_sh_text)
                        os.chmod(run_sh, 0o755)

                        # --- Submit job from pipeline_run (one sbatch per epoch) ---
                        try:
                            result = run_cmd(["sbatch", run_sh.name], cwd=str(pipeline_dir))
                            if result.returncode == 0:
                                jobs.append(
                                    f"VLASS {i}: submitted from {pipeline_dir} – {(result.stdout or '').strip()}"
                                )
                            else:
                                jobs.append(
                                    f"VLASS {i}: sbatch returned {result.returncode} – {(result.stderr or '').strip()}"
                                )
                        except FileNotFoundError:
                            jobs.append(
                                f"VLASS {i}: sbatch command not found on this host."
                            )

                if jobs:
                    message = "Section 3 results:\n" + "\n".join(jobs)
                else:
                    message = "Section 3: no VLASS epochs had MS selected; nothing to do."

        elif action == "submit_std_multims_pipeline":
            # SECTION 4 ONLY – standard VLASS multi-MS pipeline
            object_name = request.form.get("object_name", "").strip()
            selected_downloads = request.form.getlist("download_ms")
            archive_lustre_dir = normalize_archive_lustre_dir(request.form.get("archive_lustre_dir", DEFAULT_ARCHIVE_LUSTRE_DIR))
            email = request.form.get("email4", "").strip()

            std4_params["vis_list"] = request.form.getlist("std4_vis")
            std4_params["imagename"] = request.form.get("std4_imagename", "").strip()
            std4_params["phasecenter"] = request.form.get("std4_phasecenter", "").strip()
            std4_params["phase_ra"], std4_params["phase_dec"] = split_phasecenter_input(std4_params["phasecenter"]) if std4_params["phasecenter"] else ("", "")
            std4_params["imaging_mode"] = request.form.get("std4_imaging_mode", "").strip()
            std4_params["cutout_imsize"] = request.form.get("std4_cutout_imsize", "").strip()
            std4_params["cutout_imsize_mode"] = request.form.get("std4_cutout_imsize_mode", "pixel").strip() or "pixel"
            std4_params["gridder"] = request.form.get("std4_gridder", "").strip()
            std4_params["wprojplanes"] = request.form.get("std4_wprojplanes", "").strip()
            std4_params["robust"] = request.form.get("std4_robust", "").strip()
            std4_params["uvtaper"] = request.form.get("std4_uvtaper", "").strip()
            std4_params["uvrange"] = request.form.get("std4_uvrange", "").strip()
            for _param in STANDARD_PARAMETER_NAMES:
                if STEP4_PARAMETER_EXPOSURE.get(_param) and _param not in STANDARD_SPECIAL_WEB_PARAMS:
                    std4_params[_param] = request.form.get(f"std4_extra_{_param}", "").strip()

            if not email:
                message = "Please enter an email address for job notification (Section 4)."
            else:
                archive_by_base = {os.path.basename(_m): _m for _m in selected_downloads}
                ms_items = []
                seen_bases = set()
                for _vis in std4_params["vis_list"]:
                    _vis = (_vis or "").strip()
                    if not _vis:
                        continue
                    _base = os.path.basename(_vis)
                    if _base in seen_bases:
                        continue
                    seen_bases.add(_base)
                    if _base in archive_by_base:
                        ms_items.append({"name": archive_by_base[_base], "path": expected_archive_ms_path(archive_by_base[_base], archive_lustre_dir), "archive": True})
                    else:
                        _path = Path(_vis)
                        if not _path.exists():
                            continue
                        ms_items.append({"name": _base, "path": str(_path.resolve()), "archive": False})
                for _ms_name in selected_downloads:
                    _base = os.path.basename(_ms_name)
                    if _base in seen_bases:
                        continue
                    seen_bases.add(_base)
                    ms_items.append({"name": _ms_name, "path": expected_archive_ms_path(_ms_name, archive_lustre_dir), "archive": True})

                if not ms_items:
                    message = "Section 4: no MS selected; nothing to do."
                else:
                    jobs = []
                    step4_root = step_work_directory(email, object_name, "step_4")
                    step4_run_dir = step4_root / ("multiMS_" + run_datetime_stamp())
                    pipeline_dir = step4_run_dir / "pipeline_run"
                    pipeline_dir.mkdir(parents=True, exist_ok=True)
                    copy_step4_support_files(pipeline_dir)

                    casa_template = SCRIPT_DIR / "casa_imaging_vlass_multims.py"
                    if not casa_template.exists():
                        message = (
                            f"Cannot find casa_imaging_vlass_multims.py at {casa_template}. "
                            "Place the standard VLASS multi-MS pipeline script next to VLASS_web_interface.py."
                        )
                    else:
                        initial_vis_values = [item["path"] for item in ms_items]
                        try:
                            seip_lines = build_standard_seip_lines(
                                std4_params, STEP4_PARAMETER_EXPOSURE, initial_vis_values
                            )
                        except Exception as exc:
                            message = f"Section 4: could not prepare SEIP parameters: {exc}"
                        else:
                            seip_path = pipeline_dir / "SEIP_parameter.list"
                            with open(seip_path, "w") as f:
                                if seip_lines:
                                    f.write("\n".join(seip_lines) + "\n")

                            template_text = casa_template.read_text()
                            new_text = build_multims_casa_text(template_text, initial_vis_values)
                            imaging_script_path = pipeline_dir / "casa_imaging_vlass_multims.py"
                            imaging_script_path.write_text(new_text)

                            archive_restore_lines = []
                            archive_items = [item for item in ms_items if item.get("archive")]
                            if archive_items:
                                archive_restore_lines.append("echo 'Starting NRAO archive calibrated-MS restore requests before Standard VLASS multi-MS pipeline.'")
                                for item in archive_items:
                                    archive_ms_name = item["name"]
                                    sdm_id, project_code = ms_to_sdm_id_and_project_code(archive_ms_name)
                                    archive_cmd = [
                                        "python3",
                                        str(NRAO_ARCHIVE_SCRIPT),
                                        "--sdm-id", sdm_id,
                                        "--project-code", project_code,
                                        "--email", email,
                                        "--lustre-path", archive_lustre_dir,
                                    ]
                                    archive_restore_lines.append("echo 'Requesting calibrated MS: " + archive_ms_name.replace("'", "'") + "'")
                                    archive_restore_lines.append(" ".join(shlex.quote(x) for x in archive_cmd))
                                archive_restore_lines.append("echo 'Archive requests complete; starting Standard VLASS multi-MS pipeline.'")
                            archive_restore_block = "\n".join(archive_restore_lines) + ("\n" if archive_restore_lines else "")

                            run_sh = pipeline_dir / "run_casa_multims_pipeline.sh"
                            run_sh_text = f"""#!/bin/sh
#Don't put any commands before the #SBATCH options or they will not work
#SBATCH --mem=200G                        # Amount of memory needed by the whole job.
#SBATCH --time=14-00:00                   # Expected runtime
#SBATCH --mail-type=END,FAIL              # Send email when Jobs end or fail
#SBATCH --mail-user={email}
#SBATCH -n 1

{archive_restore_block}{make_step4_archive_ms_resolution_shell_block(ms_items, archive_lustre_dir, script_path='casa_imaging_vlass_multims.py')}
# casa's python requires a DISPLAY for matplotlib, so create a virtual X server
xvfb-run -d {shlex.quote(STEP4_CASA_PATH)} --pipeline --nogui -c casa_imaging_vlass_multims.py
{make_post_job_cleanup_shell_block([item['name'] for item in ms_items], archive_lustre_dir, label='step4')}
"""
                            with open(run_sh, "w") as f:
                                f.write(run_sh_text)
                            os.chmod(run_sh, 0o755)

                            try:
                                result = run_cmd(["sbatch", run_sh.name], cwd=str(pipeline_dir))
                                if result.returncode == 0:
                                    jobs.append(
                                        f"STEP 4: submitted from {pipeline_dir} – {(result.stdout or '').strip()}"
                                    )
                                else:
                                    jobs.append(
                                        f"STEP 4: sbatch returned {result.returncode} – {(result.stderr or '').strip()}"
                                    )
                            except FileNotFoundError:
                                jobs.append("STEP 4: sbatch command not found on this host.")

                            if jobs:
                                message = "Section 4 results:\n" + "\n".join(jobs)
                            else:
                                message = "Section 4: no job was submitted."

    return render_template_string(
        TEMPLATE,
        object_name=object_name,
        ra_tile=ra_tile,
        dec_tile=dec_tile,
        found_ms=found_ms,
        local_ms=local_ms,
        vlass_indices=vlass_indices,
        per_flags=per_flags,
        selected_vis=selected_vis,
        joint_deconvolution=joint_deconvolution,
        joint_selfcal=joint_selfcal,
        joint_pol_deconvolution=joint_pol_deconvolution,
        awp_image_cube=awp_image_cube,
        spx_map_VLASS1=spx_map_VLASS1,
        spx_map_VLASS2=spx_map_VLASS2,
        spx_map_VLASS3=spx_map_VLASS3,
        spx_map_VLASS_combine=spx_map_VLASS_combine,
        weighted_combine_maps=weighted_combine_maps,
        colname=colname,
        channelaverage=channelaverage,
        timeaverage=timeaverage,
        Ra_1=Ra_1,
        Dec_1=Dec_1,
        R=R,
        mask_threshold=mask_threshold,
        cell=cell,
        niter=niter,
        gridder=gridder,
        wprojplanes=wprojplanes,
        weighting=weighting,
        robust=robust,
        specmode=specmode,
        parallel=parallel,
        imagename_base=imagename_base,
        field=field,
        spw=spw,
        uvrange=uvrange,
        mask=mask,
        usepointing=usepointing,
        pointingoff_text=pointingoff_text,
        peeling=peeling,
        peeling_num_sources=peeling_num_sources,
        array_size=array_size,
        archive_lustre_dir=archive_lustre_dir,
        default_archive_lustre_dir=DEFAULT_ARCHIVE_LUSTRE_DIR,
        email=email,
        message=message,
        std_params=std_params,
        std4_params=std4_params,
        step3_expose=STEP3_PARAMETER_EXPOSURE,
        step4_expose=STEP4_PARAMETER_EXPOSURE,
        standard_parameter_names=STANDARD_PARAMETER_NAMES,
        standard_special_web_params=STANDARD_SPECIAL_WEB_PARAMS,
        standard_parameter_labels=STANDARD_PARAMETER_LABELS,
        standard_parameter_examples=STANDARD_PARAMETER_EXAMPLES,
        simbad_coords=simbad_coords,
        simbad_error=simbad_error,
        ned_coords=ned_coords,
        ned_error=ned_error,
        csv_results=csv_results,
    )


if __name__ == "__main__":
    # Start from this port (can override with env var VLASS_WEB_PORT)
    base_port = int(os.environ.get("VLASS_WEB_PORT", 5000))
    max_tries = 20  # try base_port, base_port+1, ..., base_port+19

    port = base_port
    for _ in range(max_tries):
        # Try to bind the port ourselves first.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                # Port is busy, try the next one
                print(f"Port {port} in use, trying {port + 1}...")
                port += 1
                continue

        # If we got here, the port is free (we just bound it).
        print(f"Starting VLASS web interface on http://127.0.0.1:{port}")
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        break
    else:
        print(f"No free port found in range {base_port}–{base_port + max_tries - 1}")
