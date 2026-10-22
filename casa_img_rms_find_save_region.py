from casatools import image
from casatasks import imfit
import numpy as np
import sys

def compute_rms(data):
    return np.sqrt(np.mean(data[np.isfinite(data)]**2))

def compute_global_rms(image_name):
    ia = image()
    ia.open(image_name)
    data = ia.getchunk()
    ia.done()
    return compute_rms(data)

def region_already_covered(x, y, previous_coords, exclusion_radius):
    for x0, y0 in previous_coords:
        if np.sqrt((x - x0)**2 + (y - y0)**2) < exclusion_radius:
            return True
    return False

def find_next_worst_region(ia, shape, checked_coords, box_size=200, step=200, exclusion_radius=100):
    nx, ny = shape[0], shape[1]
    worst_rms = 0
    worst_coords = None

    for x in range(0, nx - box_size + 1, step):
        for y in range(0, ny - box_size + 1, step):
            if region_already_covered(x + box_size // 2, y + box_size // 2, checked_coords, exclusion_radius):
                continue
            chunk = ia.getchunk(blc=[x, y, 0, 0], trc=[x + box_size - 1, y + box_size - 1, 0, 0])
            rms = compute_rms(chunk)
            if rms > worst_rms:
                worst_rms = rms
                worst_coords = (x, y)

    return worst_coords, worst_rms

def fit_peak_source(image_name, x0, y0, box_size=200, peak_halfsize_arcsec=5):
    ia = image()
    ia.open(image_name)

    x1, y1 = x0 + box_size - 1, y0 + box_size - 1
    chunk = ia.getchunk(blc=[x0, y0, 0, 0], trc=[x1, y1, 0, 0])
    chunk2d = chunk[:, :, 0, 0]
    dx, dy = np.unravel_index(np.nanargmax(chunk2d), chunk2d.shape)
    x_peak = x0 + dx
    y_peak = y0 + dy
    peak_flux = chunk2d[dx, dy]

    csys = ia.coordsys()
    world = csys.toworld([x_peak, y_peak, 0, 0])
    ra_deg = np.degrees(world['numeric'][0])
    dec_deg = np.degrees(world['numeric'][1])
    ia.done()

    arcsec_to_deg = 1.0 / 3600.0
    half_deg = peak_halfsize_arcsec * arcsec_to_deg
    ra1 = ra_deg - half_deg
    ra2 = ra_deg + half_deg
    dec1 = dec_deg - half_deg
    dec2 = dec_deg + half_deg
    region_str = f"box[[{ra1}deg, {dec1}deg], [{ra2}deg, {dec2}deg]]"

    result = imfit(imagename=image_name, region=region_str)
    return result, ra_deg, dec_deg, ra1, dec1, ra2, dec2, peak_flux, x_peak, y_peak

def save_crtf_regions(region_list, filename="brightest_faulty_source_world.crtf"):
    with open(filename, 'w') as f:
        f.write("#CRTFv0 CASA Region Text Format version 0\n")
        for ra1, dec1, ra2, dec2 in region_list:
            f.write(f"box [[{ra1:.8f}deg, {dec1:.8f}deg], [{ra2:.8f}deg, {dec2:.8f}deg]] coord=J2000, linewidth=1, linestyle=-, color=magenta\n")

def main():
    if len(sys.argv) < 4:
        print("Usage: python script.py <image_name> <num_regions> <threshold> [output_crtf]")
        sys.exit(1)

    image_name = sys.argv[1]
    num_regions = int(sys.argv[2])
    threshold = int(sys.argv[3])
    output_crtf = sys.argv[4] if len(sys.argv) > 4 else "brightest_faulty_source_world.crtf"
    box_size = 200
    step = 200
    exclusion_radius = 200  # in pixels, used to avoid overlapping detections

    global_rms = compute_global_rms(image_name)
    print(f"Global RMS = {global_rms:.6e}")

    ia = image()
    ia.open(image_name)
    shape = ia.shape()
    ia.done()

    found_coords = []
    saved_regions = []

    for i in range(num_regions):
        ia = image()
        ia.open(image_name)
        (x0, y0), local_rms = find_next_worst_region(
            ia, shape, found_coords, box_size=box_size, step=step, exclusion_radius=exclusion_radius
        )
        ia.done()

        if (x0, y0) is None:
            print(f"No more unique regions found after {i} iterations.")
            break

        result, ra_deg, dec_deg, ra1, dec1, ra2, dec2, peak_flux, x_peak, y_peak = fit_peak_source(
            image_name, x0, y0, box_size, peak_halfsize_arcsec=5
        )

        if not result['converged']:
            print(f"[{i}] Fit did not converge. Skipping.")
            continue

        try:
            total_flux = result['results']['component0']['flux']['value'][0]
        except Exception:
            print(f"[{i}] Error reading total flux. Skipping.")
            continue

        if total_flux > threshold * global_rms:
            print(f"[{i}] Valid source found at RA={ra_deg:.5f}, Dec={dec_deg:.5f}, Total Flux={total_flux:.4f} > {threshold}*RMS")
            saved_regions.append((ra1, dec1, ra2, dec2))
            found_coords.append((x_peak, y_peak))
        else:
            print(f"[{i}] Source flux {total_flux:.4f} < threshold * Global RMS. Skipping.")
            found_coords.append((x_peak, y_peak))  # Still mark as checked

    if saved_regions:
        save_crtf_regions(saved_regions, output_crtf)
        print(f"Saved {len(saved_regions)} valid sources to CRTF file.")
    else:
        print(f"No valid sources found above {threshold}× global RMS.")

if __name__ == "__main__":
    main()

