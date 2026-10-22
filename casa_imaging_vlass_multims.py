__rethrow_casa_exceptions = True
context = h_init()
context.set_state('ProjectSummary', 'proposal_code', 'VLASS')
context.set_state('ProjectSummary', 'proposal_title', 'unknown')
context.set_state('ProjectSummary', 'piname', 'unknown')
context.set_state('ProjectSummary', 'observatory', 'Karl G. Jansky Very Large Array')
context.set_state('ProjectSummary', 'telescope', 'EVLA')
context.set_state('ProjectStructure', 'ppr_file', 'PPR.xml')
context.set_state('ProjectStructure', 'recipe_name', 'hifv_vlassSEIP')
vis1='VLASS1.1.sb34638721.eb34661415.58062.02459759259.ms'
vis2='VLASS2.1.sb38539731.eb38565870.59072.39593302083.ms'
vis3='VLASS3.1.sb43615987.eb43722812.60018.9553462037.ms'


try:
    hifv_importdata(vis=[vis1,vis2,vis3],session=['session_1','session_2','session_3'],nocopy=True)
    hif_editimlist(parameter_file='SEIP_parameter.list')
    hif_transformimagedata(datacolumn='corrected', clear_pointing=False, modify_weights=True, wtmode='nyq')
    hifv_vlassmasking(maskingmode='vlass-se-tier-1', vlass_ql_database='/lustre/aoc/users/mlacy/VLASS12Q_CIRADA.fits')
    hif_makeimages(hm_masking='manual')
    hifv_checkflag(checkflagmode='vlass-imaging')
    hifv_statwt(statwtmode='VLASS-SE', datacolumn='residual_data')
    hifv_selfcal(selfcalmode='VLASS-SE')
    hif_editimlist(parameter_file='SEIP_parameter.list')
    hif_makeimages(hm_masking='manual')
    hif_editimlist(parameter_file='SEIP_parameter.list')
    hifv_vlassmasking(maskingmode='vlass-se-tier-2')
    hif_makeimages(hm_masking='manual')
    hifv_pbcor()
    hif_makermsimages()
    hif_makecutoutimages()
    hif_analyzealpha()
    hifv_exportvlassdata()
finally:
    h_save()
