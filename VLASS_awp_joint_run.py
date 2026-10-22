import sys,os,re,shutil,glob,subprocess
sys.path.append(os.getcwd())
from VLASS_awp_joint_workers import *
from VLASS_awp_joint_parameters import *

img_size=vlass_imagesize(R, pixel_scale=0.00016, min_size=512, round_to=32)
imsize= [img_size,img_size] 


################################################################...################################################################
################################################################...################################################################
# Main loop over vis_list
for i, vis in enumerate(vis_list):
    # Allow "report-only" mode: skip entries with no MS selected
    if not str(vis).strip():
        print(f"Skipping VLASS {i+1}: no MS selected (report-only mode).")
        continue

    flags = processing_flags[i]
    vis_base = vis[:-3]
    imagename = f"{imagename_base}_{vis_base}"
    vis_out = vis

    # -----------------------------------------------------------------
    # ... your existing CASA / selfcal / combine logic for this vis ...
    # (splits, tclean calls, selfcal, joint imaging, SPX maps, etc.)
    # -----------------------------------------------------------------

    # Optional peeling: find bright source regions and run QuartiCal peeling
    if globals().get('peeling', False):
        try:
            peel_candidates = []
            if 'imagename_out' in locals():
                peel_candidates.append(imagename_out + '.image.tt0')
            peel_candidates.extend(sorted(glob.glob(imagename + '*sc.image.tt0')))
            peel_candidates.extend(sorted(glob.glob(imagename + '*image.tt0')))
            peel_image = next((x for x in peel_candidates if os.path.exists(x)), None)

            if peel_image:
                peel_base = peel_image.replace('.image.tt0', '')
                region_file = peel_base + '_peel_regions.crtf'
                rms_script = os.path.join(os.getcwd(), 'casa_img_rms_find_save_region.py')
                peel_script = os.path.join(os.getcwd(), 'casa_quartical_peeling_VLASS.py')
                num_peel = int(globals().get('peeling_num_sources', 1))
                peel_thresh = int(globals().get('peeling_threshold', 10))

                if os.path.exists(rms_script):
                    subprocess.call([sys.executable, rms_script, peel_image, str(num_peel), str(peel_thresh), region_file])
                else:
                    print(f"Peeling skipped region finding: missing script {rms_script}")

                if os.path.exists(region_file) and os.path.exists(peel_script):
                    subprocess.call([
                        sys.executable, peel_script,
                        '--vis', vis_out,
                        '--imagename', peel_base,
                        '--region-file', region_file,
                        '--phasecenter', phasecenter,
                        '--imsize', str(imsize[0]), str(imsize[1]),
                        '--cell', cell,
                        '--niter', str(niter),
                        '--mask', mask if 'mask' in globals() and mask else '',
                    ])
                    if os.path.exists(peel_base + '.dd.image.tt0') and 'imagename_out' in locals():
                        imagename_out = peel_base + '.dd'
                else:
                    print(f"Peeling skipped QuartiCal step: missing region file {region_file} or script {peel_script}")
            else:
                print(f"Peeling skipped: no image found for {imagename}")
        except Exception as _peel_exc:
            print('Peeling block failed:', _peel_exc)


# ---------------------------------------------------------------------
# AFTER the loop: build HTML report pages under VLASS_processing_results/
# This runs once, regardless of how many vis were processed.
# ---------------------------------------------------------------------

# Collect FITS products from previous run(s)
input_init_files = sorted(glob.glob(imagename_base + "*init.image.tt0.fits"))
input_sc_files = sorted(glob.glob(imagename_base + "*sc.image.tt0.fits"))
input_sc_files = [f for f in input_sc_files if "combined" not in f]
input_GK_files = sorted(glob.glob(imagename_base + "*GK_SC.image.tt0.fits"))
input_pol_files = sorted(glob.glob(imagename_base + "*_single_*_map.fits"))
input_comb_files = sorted(glob.glob(joint_image + ".image.tt0.fits"))
input_comb_sc_files = sorted(glob.glob(joint_image + ".sc.image.tt0.fits"))
input_comb_pol_files = sorted(glob.glob(joint_image + "_spw*" + "_*_map.fits"))
input_weighted_files = [
    imagename_base + "_normal_average.fits",
    imagename_base + "_weighted_average.fits",
    imagename_base + "_weighted_median.fits",
    imagename_base + "_weighted_sigma_clip.fits",
]

input_files = sorted(glob.glob(imagename_base + "*init.sc.image.tt0.fits"))
input_files.append(joint_image + ".image.tt0.fits")
input_files.append(joint_image + ".sc.image.tt0.fits")

# Directory to hold all web outputs
results_dir = os.path.join(os.getcwd(), "VLASS_processing_results")
os.makedirs(results_dir, exist_ok=True)

section_pages = []  # list of (filename, title, body_html)

# Section 1: initial images
if input_init_files:
    body = analyze_and_plot_group(input_init_files, "Initial Images")
    section_pages.append(("initial_images.html", "Initial Images", body))

# Section 2: self-cal images
if input_sc_files:
    body = analyze_and_plot_group(input_sc_files, "Self-Calibrated Images")
    section_pages.append(("selfcal_images.html", "Self-Calibrated Images", body))

# Section 3: delay-cal images
if input_GK_files:
    body = analyze_and_plot_group(input_GK_files, "Delay cal Images")
    section_pages.append(("delay_images.html", "Delay cal Images", body))

# Section 4: polarization images
if input_pol_files:
    body = analyze_and_plot_group(input_pol_files, "Polarization Images")
    section_pages.append(("pol_images.html", "Polarization Images", body))

# Section 5: combined Stokes-I images
if input_comb_files:
    body = analyze_and_plot_group(input_comb_files, "Combined Image")
    section_pages.append(("combined_image.html", "Combined Image", body))

# Section 6: combined self-cal image
if input_comb_sc_files:
    body = analyze_and_plot_group(input_comb_sc_files, "Combined Selfcal Image")
    section_pages.append(("combined_selfcal_image.html", "Combined Selfcal Image", body))

# Section 7: combined polarization images
if input_comb_pol_files:
    body = analyze_and_plot_group(input_comb_pol_files, "Polarisation Combined Images")
    section_pages.append(("combined_pol_images.html", "Polarisation Combined Images", body))

# Section 8: RMS-weighted images
existing_weighted = [f for f in input_weighted_files if os.path.exists(f)]
if existing_weighted:
    body = analyze_and_plot_group(existing_weighted, "RMS Weighted Images")
    section_pages.append(("rms_weighted_images.html", "RMS Weighted Images", body))

# Section 9: Self-cal flux measurements
if input_files:
    multi_html = ""
    for f in input_files:
        print(f"Processing {f}")
        multi_html += process_fits_file(f, "Selfcal map flux measurements")
    section_pages.append(("selfcal_flux.html", "Selfcal map flux measurements", multi_html))
else:
    print("No self-cal FITS files found for flux-measurement section.")

# Section 10: polarization flux measurements
if input_pol_files:
    pol_html = ""
    for f1 in input_pol_files:
        print(f"Processing {f1}")
        pol_html += process_pol_fits_file(f1, "Polarization map flux measurements")
    section_pages.append(("pol_flux.html", "Polarization map flux measurements", pol_html))

# Section 11: combined polarization flux measurements
if input_comb_pol_files:
    comb_pol_html = ""
    for f2 in input_comb_pol_files:
        print(f"Processing {f2}")
        comb_pol_html += process_pol_fits_file(
            f2, "Combined polarization map flux measurements"
        )
    section_pages.append(
        ("combined_pol_flux.html",
         "Combined polarization map flux measurements",
         comb_pol_html)
    )

# Section 12: Spectral index maps
spx_files = glob.glob(imagename_base + "*spx*.fits")
spx_files = sorted(spx_files, key=extract_version_number)
spx_html_body = "<h2>Spectral Index Maps</h2>\n"
if not spx_files:
    spx_html_body += "<p>No spectral index maps found.</p>"
else:
    for spx_file in spx_files:
        print(f"Adding spectral index map: {spx_file}")
        img_tag = plot_fits_image(spx_file, title=os.path.basename(spx_file))
        spx_html_body += img_tag
section_pages.append(("spectral_index_maps.html", "Spectral Index Maps", spx_html_body))

# Write per-section pages
for fname, title, body in section_pages:
    page_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title} – VLASS processing</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 20px; }}
      img  {{ margin-top: 10px; margin-bottom: 10px; }}
      hr   {{ margin-top: 40px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p><a href="index.html">&larr; Back to index</a></p>
    {body}
</body>
</html>
"""
    with open(os.path.join(results_dir, fname), "w") as f:
        f.write(page_html)

# Write main index page
index_items = "\n".join(
    f'<li><a href="{fname}">{title}</a></li>' for fname, title, _ in section_pages
)
index_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>VLASS processing results</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 20px; }}
      li   {{ margin-bottom: 0.4em; }}
    </style>
</head>
<body>
    <h1>VLASS processing results</h1>
    <ul>
      {index_items}
    </ul>
</body>
</html>
"""
with open(os.path.join(results_dir, "index.html"), "w") as f:
    f.write(index_html)

print(f"\nHTML report pages written under: {results_dir}")

