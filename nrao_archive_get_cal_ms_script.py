import argparse
import requests
import time

archive_url = 'https://data.nrao.edu'

# Defaults retained from the original script
email = 'vparekh@nrao.edu'  # notification e-mail
workflow = 'runRestoreWorkflow'  # run the restore workflow
downloadDataFormat = 'CMS'  # calibrated MS
instrument = 'EVLA'
project_code = '22A-431'
SDM_ID = '22A-431.sb42103690.eb42523311.59803.860715601855'
lustre_path = 'aoc/users/vparekh/'


def normalize_lustre_root(path):
    """Archive API expects root without the leading /lustre/."""
    p = (path or '').strip()
    if p.startswith('/lustre/'):
        p = p[len('/lustre/'):]
    elif p == '/lustre':
        p = ''
    return p.strip('/') + ('/' if p and not p.endswith('/') else '')


def request_calibrated_ms(
    sdm_id=SDM_ID,
    project=project_code,
    notify_email=email,
    lustre_root=lustre_path,
    wait=True,
    archive=archive_url,
):
    """Submit a calibrated-MS restore request to the NRAO archive."""
    data_details = requests.get(
        f'{archive}/archive-service/restapi_product_details_view?sdm_id={sdm_id}'
    )
    data_details.raise_for_status()
    details_dict = data_details.json()

    product_locator = details_dict['details']['execution_blocks'][0]['sci_prod_locator']
    requested_casa = details_dict['details']['execution_blocks'][0]['cals'][0]['casa_version']
    cal_file = details_dict['details']['execution_blocks'][0]['cals'][0]['file_name']

    casa_payload = {
        'version': requested_casa,
        'capabilities': ['restore_basic_ms', 'restore_cms'],
        'telescope': instrument,
    }

    casareq = requests.post(
        f'{archive}/archive-service/restapi_get_casa_version_list', json=casa_payload
    )
    casareq.raise_for_status()
    casa_resp = casareq.json()
    casa_home = casa_resp['casa_data']['casa_version_list']['restore_cms'][0]['path']

    post_data_lustre = {
        'emailNotification': notify_email,
        'requestDescription': f'{instrument} Download Request',
        'overrideDefaultDownloadDir': True,
        'p_copyfileprefix': '/lustre/',
        'p_copyfileroot': normalize_lustre_root(lustre_root),
        'archive': 'VLA',
        'p_telescope': instrument,
        'p_project': project,
        'productLocator': product_locator,
        'requestCommand': workflow,
        'p_workflowEventName': workflow,
        'p_downloadDataFormat': downloadDataFormat,
        'p_intentsFileName': 'intents_hifv.xml',
        'p_proceduresFileName': 'procedure_hifv.xml',
        'p_applyTelescopeFlags': True,
        'p_casaHome': casa_home,
        'p_CalFile': cal_file,
    }

    submission = requests.post(f'{archive}/rh/submission', data=post_data_lustre)
    submission.raise_for_status()

    resp2 = requests.get(submission.url)
    resp2.raise_for_status()

    subrespurl = None
    for row in resp2.text.split():
        if 'window.location.href=' in row:
            subrespurl = row.split("'")[1]
            break

    if not subrespurl:
        print(f'Submitted request for {sdm_id}. Could not parse follow-up wait URL.')
        return submission.url

    nextresp = requests.get(subrespurl)
    nextresp.raise_for_status()
    wait_url = nextresp.url

    print(f'Submitted request for {sdm_id}')
    print(f'Project code: {project}')
    print(f'Notification email: {notify_email}')
    print(f'Destination: /lustre/{normalize_lustre_root(lustre_root)}')
    print(f'Wait URL: {wait_url}')

    if wait:
        while True:
            time.sleep(1)
            resp = requests.get(wait_url + '/state')
            resp.raise_for_status()
            print(resp.text, flush=True)
            if resp.text == 'COMPLETE':
                break

    return wait_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdm-id', default=SDM_ID)
    parser.add_argument('--project-code', default=project_code)
    parser.add_argument('--email', default=email)
    parser.add_argument('--lustre-path', default=lustre_path)
    parser.add_argument('--archive-url', default=archive_url)
    parser.add_argument('--no-wait', action='store_true')
    args = parser.parse_args()

    request_calibrated_ms(
        sdm_id=args.sdm_id,
        project=args.project_code,
        notify_email=args.email,
        lustre_root=args.lustre_path,
        wait=not args.no_wait,
        archive=args.archive_url,
    )


if __name__ == '__main__':
    main()
