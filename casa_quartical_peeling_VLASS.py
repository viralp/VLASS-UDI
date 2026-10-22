import os,glob,sys,argparse
from casatools import table
from casatasks import tclean, exportfits, importfits, applycal, makemask, immath

tb = table()

mask=False
selfcal=True
delay_selfcal=False
ddcal=True 

vis='VLASS3.1.sb43271439.eb43441449.59966.291735266204_split.ms'  
#imaging parameters
imsize= [12500,12500] 
cell= '0.6arcsec'
niter=20000
parallel=False
imagename='3C286_target_array_solve' 
region_file='bright_src_region.crtf'
phasecenter='J2000 13:32:18.5436 +30.29.59.904'
field=''
spw=''
uvrange=''
mask='mypipelinerun_vlass_casa.mask.fitsimage'


# Optional CLI overrides, used by the VESI web pipeline peeling option.
if '--vis' in sys.argv:
    parser = argparse.ArgumentParser()
    parser.add_argument('--vis', default=vis)
    parser.add_argument('--imagename', default=imagename)
    parser.add_argument('--region-file', default=region_file)
    parser.add_argument('--phasecenter', default=phasecenter)
    parser.add_argument('--imsize', nargs=2, type=int, default=imsize)
    parser.add_argument('--cell', default=cell)
    parser.add_argument('--niter', type=int, default=niter)
    parser.add_argument('--field', default=field)
    parser.add_argument('--spw', default=spw)
    parser.add_argument('--uvrange', default=uvrange)
    parser.add_argument('--mask', default=mask)
    args = parser.parse_args()

    vis = args.vis
    imagename = args.imagename
    region_file = args.region_file
    phasecenter = args.phasecenter
    imsize = args.imsize
    cell = args.cell
    niter = args.niter
    field = args.field
    spw = args.spw
    uvrange = args.uvrange
    mask = args.mask

def addModelData(msname, colname):
    tb.open(vis,nomodify=False)
    cnames = tb.colnames()
    # Check if the source column exists
    try:
        cdesc = tb.getcoldesc("DATA")  # Copy column description
    except:
        raise ValueError("Column DATA does not exist")
    hasTiled = False
    dminfo = None
    # Fix the incorrect loop
    try:
        dminfo = tb.getdminfo("DATA")
        if "TYPE" in dminfo and dminfo["TYPE"][:5] == "Tiled":
            hasTiled = True
    except:
        hasTiled = False
    # If not tiled, define default settings
    if not hasTiled:
        dminfo = {"TYPE": "TiledShapeStMan", "SPEC": {"DEFAULTTILESHAPE": [4, 32, 128]}}
    if colname in cnames:
        print(f"Column {colname} not added; it already exists.")
    else:
        dminfo["NAME"] = colname  # Set the new column name
        cdesc["comment"] = "The model data column"
        # Add the column
        tb.addcols({colname: cdesc}, dminfo)
        print(f"Column {colname} added successfully!")

        # Initialize the column with zeros (to prevent 'no array in row 0' error)
        import numpy as np
        nrows = tb.nrows()
        shape = tb.getcell("DATA", 0).shape  # Get data shape
        zero_data = np.zeros(shape, dtype=np.complex64)  # Ensure dtype matches
        for i in range(nrows):
            tb.putcell(colname, i, zero_data)
    tb.flush()
    tb.close()
    
def cleaning(vis=vis,field=field,spw=['2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17'], uvrange='',
       antenna=['0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25&'],
       scan=[''],
       intent='OBSERVE_TARGET#UNSPECIFIED', datacolumn='corrected',
       imagename=imagename, imsize=imsize,
       cell='0.6arcsec', phasecenter=phasecenter,
       stokes='I', specmode='mfs', reffreq='3.0GHz', nchan=-1, outframe='LSRK',
       perchanweightdensity=False, gridder='mosaic', wprojplanes=32,
       mosweight=False, conjbeams=False, usepointing=False, rotatepastep=5.0,
       pointingoffsetsigdev=[300, 30], pblimit=0.2, deconvolver='mtmfs',
       scales=[0, 5, 12], nterms=2, smallscalebias=0.4, restoration=True,
       restoringbeam='common', pbcor=False, weighting='briggs', robust=0.0,
       npixels=0, niter=20000, threshold='1e-06', nsigma=10, cycleniter=500,
       cyclefactor=3.0, interactive=False, fullsummary=True,mask=mask,
       pbmask=0.4, fastnoise=True, restart=True, savemodel='modelcolumn',
       calcres=True, calcpsf=True, parallel=False):
  if os.path.exists(imagename+'.mask'):
        os.system("rm -rf "+str(imagename+'.mask')) 
  tclean(vis=vis,field=field,spw=spw,uvrange=uvrange,antenna=antenna,
       scan=scan,intent=intent,datacolumn=datacolumn,imagename=imagename,imsize=imsize,cell=cell,
       phasecenter=phasecenter,stokes=stokes,specmode=specmode,reffreq=reffreq,
       nchan=nchan,outframe=outframe,perchanweightdensity=perchanweightdensity,
       gridder=gridder,wprojplanes=wprojplanes,mosweight=mosweight,
       conjbeams=conjbeams,usepointing=usepointing,rotatepastep=rotatepastep,
       pointingoffsetsigdev=pointingoffsetsigdev,pblimit=pblimit,
       deconvolver=deconvolver,scales=scales,nterms=nterms,smallscalebias=smallscalebias,
       restoration=restoration,restoringbeam=restoringbeam,
       pbcor=pbcor, weighting=weighting,robust=robust,npixels=npixels,
       niter=niter,threshold=threshold,nsigma=nsigma,cycleniter=cycleniter,
       cyclefactor=cyclefactor,interactive=interactive,fullsummary=fullsummary,
       mask=mask,pbmask=pbmask,fastnoise=fastnoise,
       restart=restart,savemodel=savemodel,calcres=calcres,calcpsf=calcpsf,parallel=parallel)
  exportfits(imagename=str(imagename)+'.image.tt0',fitsimage=str(imagename)+'.image.tt0.fits',overwrite=True)
    

def remove_column_if_exists(msname, colname):
    tb.open(msname, nomodify=False)
    cnames = tb.colnames()
    if colname in cnames:
        print(f"Removing column: {colname}")
        tb.removecols(colname)
    else:
        print(f"Column {colname} does not exist, skipping removal.")
    tb.close()

if mask==True:
 
 cleaning(imagename=imagename,datacolumn='corrected')
 os.system("breizorro --restored-image "+imagename+".image.tt0.fits --threshold 10 --outfile "+imagename+".sigma.mask.fits")
 importfits(fitsimage=imagename+".mask.fits",imagename=imagename+".sigma.mask")
 mask=imagename+".sigma.mask"

if selfcal==True:
 applycal(vis=vis,spw='',selectdata=True,
         gaintable=[vis+'.G.selfcal'], field='',interp=['linear'], calwt=False, parang=False,
         applymode='calonly')
    
 cleaning(imagename=imagename+'.sc')
 imagename=imagename+'.sc'


if delay_selfcal==True: 
   os.system("goquartical input_ms.path="+str(vis)+" input_ms.data_column=CORRECTED_DATA input_ms.select_fields=["+str(field)+"] input_ms.time_chunk='0' input_ms.freq_chunk='0' input_model.recipe=MODEL_DATA solver.terms='[G,K]' solver.iter_recipe='[50,50,50,50,50,50]' solver.propagate_flags=False solver.robust=False solver.threads=1 solver.convergence_fraction=0.99 solver.convergence_criteria=1e-06 output.log_directory=output/KG.outputs.qc/log output.gain_directory=output/KG.output.gain.qc output.overwrite=1 output.products=[corrected_data,corrected_residual] output.columns=[CORRECTED_DATA,CORRECTED_RESIDUAL] output.flags=False dask.threads=6 dask.workers=6 dask.scheduler=threads G.type=phase G.time_interval='5s' G.freq_interval='0' G.initial_estimate=False G.solve_per=antenna G.interp_mode=reim G.interp_method=2dlinear mad_flags.enable=False mad_flags.threshold_bl=6 mad_flags.threshold_global=8 mad_flags.max_deviation=1000 K.time_interval='1s' K.freq_interval='0' K.type=delay_and_offset K.initial_estimate=False K.interp_mode=reim K.interp_method=2dlinear")
   cleaning(imagename=imagename+'.GK_SC',datacolumn='corrected',mask=mask,savemodel='modelcolumn')
   imagename=imagename+'.GK_SC'

 
if ddcal==True:
 remove_column_if_exists(vis, "ALL_SKY_MODEL")
 addModelData(vis,'ALL_SKY_MODEL')
 tb.open(vis,nomodify=False)
 data=tb.getcol("MODEL_DATA")
 tb.putcol("ALL_SKY_MODEL", data)
 tb.flush()
 tb.close()

 model_images=glob.glob(imagename+'*')
 models=[]
 model_images = [f for f in model_images if not f.endswith('.fits')]
#region=''
 lines = open(region_file).readlines()
 for i in range(1,len(lines)):
  models.append(f"BRIGHT_Source_MODEL{i}")
  for j in range(len(model_images)):
    inp_image=model_images[j]
    label=model_images[j].replace(imagename,'')
    inpimage=model_images[j].replace(label,'')
    outputimg=inpimage+'_new_model_bright_src'+label
    output_mask=imagename+'_mask_bright_sources.im'
    makemask(mode='copy', inpimage=imagename+'.model.tt0',
         inpmask=lines[i], output=output_mask,overwrite=True)
    if os.path.exists(outputimg):
        os.system("rm -rf "+str(outputimg))     
    immath(imagename=[inp_image, output_mask],expr='IM0*IM1',outfile=outputimg)
    


 tclean(vis=vis,field='',spw=['2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17'], uvrange='',
       antenna=['0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25&'],
       scan=[''],
       intent='OBSERVE_TARGET#UNSPECIFIED', datacolumn='corrected',
       imagename=imagename+'_new_model_bright_src', imsize=imsize,
       cell='0.6arcsec', phasecenter=phasecenter,
       stokes='I', specmode='mfs', reffreq='3.0GHz', nchan=-1, outframe='LSRK',
       perchanweightdensity=False, gridder='mosaic', wprojplanes=32,
       mosweight=False, conjbeams=False, usepointing=False, rotatepastep=5.0,
       pointingoffsetsigdev=[300, 30], pblimit=0.2, deconvolver='mtmfs',
       scales=[0, 5, 12], nterms=2, smallscalebias=0.4, restoration=False,
       restoringbeam='common', pbcor=False, weighting='briggs', robust=0.0,
       npixels=0, niter=0, threshold='1e-06', nsigma=10, cycleniter=500,
       cyclefactor=3.0, interactive=False, fullsummary=True,mask=mask,
       pbmask=0.4, fastnoise=True, restart=True, savemodel='modelcolumn',
       calcres=False, calcpsf=False, parallel=False)

 remove_column_if_exists(vis, f"BRIGHT_Source_MODEL{i}")
 addModelData(vis,f'BRIGHT_Source_MODEL{i}')
 tb.open(vis,nomodify=False)
 data=tb.getcol("MODEL_DATA")  # Get contents of MODEL_DATA column.
 tb.putcol(f"BRIGHT_Source_MODEL{i}", data)  # Put contents of MODEL_DATA into BRIGHT_Source_MODEL.
 tb.flush()
 tb.close()
 if models:  # Ensure there's at least one line after skipping the first
    model_string = f"ALL_SKY_MODEL~{'~'.join(models)}:{':'.join(models)}"


 os.system("goquartical input_ms.path="+str(vis)+" input_ms.data_column=CORRECTED_DATA input_ms.select_fields=["+str(field)+"] input_ms.time_chunk='0' input_ms.freq_chunk='0' input_model.recipe="+str(model_string)+" solver.terms='[G,K,dE]' solver.iter_recipe='[100,100,100,100,100,100,100,100,100]' solver.robust=False solver.propagate_flags=False solver.threads=1 solver.convergence_fraction=0.99 solver.convergence_criteria=1e-06 output.log_directory=output/KG.outputs.qc/log output.gain_directory=output/KG.output.gain.qc output.log_to_terminal=True output.overwrite=True output.products=[corrected_residual] output.columns=[CORRECTED_DATA] output.flags=False output.subtract_directions=[1] dask.threads=6 dask.workers=6 dask.scheduler=threads G.type=phase G.solve_per=antenna G.time_interval='15' G.freq_interval='0' G.initial_estimate=False G.interp_mode=reim G.interp_method=2dlinear G.respect_scan_boundaries=True G.solve_per=array dE.direction_dependent=True dE.type=complex dE.solve_per=array dE.freq_interval='100' mad_flags.enable=False mad_flags.threshold_bl=6 mad_flags.threshold_global=8 mad_flags.max_deviation=1000 K.time_interval='1s' K.freq_interval='0' K.type=delay_and_offset K.initial_estimate=False K.interp_mode=reim K.interp_method=2dlinear K.solve_per=array")

 cleaning(imagename=imagename+'.dd')


