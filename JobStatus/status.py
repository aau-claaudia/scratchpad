import argparse
import configparser
import csv
import json

import jwt
import requests
from heatclient import client
from keystoneauth1 import loading, session
from requests.structures import CaseInsensitiveDict

CONFIG = None
ACCESS_TOKEN = None


def get_access_token():
    global ACCESS_TOKEN
    if ACCESS_TOKEN:
        try:
            jwt.decode(ACCESS_TOKEN, options={"verify_signature": False})
            return ACCESS_TOKEN
        except jwt.ExpiredSignatureError:
            print("Access token expired")

    ACCESS_TOKEN = refresh_access_token()

    return ACCESS_TOKEN


def refresh_access_token():
    print("Refreshing access token")
    payload = {
        "items": [
            {
                "refreshToken": CONFIG['ucloud']['refresh_token']
            }
        ]
    }

    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"

    r = requests.post(
        url=f"{CONFIG['ucloud']['url']}/auth/providers/refresh",
        headers=headers,
        json=payload)

    return r.json()["responses"][0]["accessToken"]


def get_ucloud_job_from_stack(stack):
    job_id = get_jobid_from_stack(stack)

    job = get_ucloud_job(job_id)

    if not job:
        jobs = browse_ucloud_job(job_id)
        print("browsed jobs", len(jobs["items"]))
        if len(jobs["items"]):
            job = jobs["items"][0]

    return job


def get_ucloud_job(job_id):
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = "Bearer " + get_access_token()

    payload = {
        "filterApplication": None,
        "filterState": None,
        "includeParameters": None,
        "includeApplication": None,
        "includeProduct": True,
        "includeOthers": False,
        "includeUpdates": False,
        "includeSupport": False,
        "filterCreatedBy": None,
        "filterCreatedAfter": None,
        "filterCreatedBefore": None,
        "filterProvider": None,
        "filterProductId": None,
        "filterProductCategory": None,
        "filterProviderIds": None,
        "filterIds": None,
        "hideProductId": None,
        "hideProductCategory": None,
        "hideProvider": None,
        "id": job_id
    }

    r = requests.get(
        url=f"{CONFIG['ucloud']['url']}/api/jobs/control/retrieve",
        headers=headers,
        params=payload)

    if r.status_code == 200:
        return json.loads(r.text)
    else:
        print(r.status_code)
        print("Job not found")


def browse_ucloud_job(job_id):
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = "Bearer " + get_access_token()

    payload = {
        "filterApplication": None,
        "filterState": None,
        "includeParameters": None,
        "includeApplication": None,
        "includeProduct": True,
        "includeOthers": False,
        "includeUpdates": False,
        "includeSupport": False,
        "filterCreatedBy": None,
        "filterCreatedAfter": None,
        "filterCreatedBefore": None,
        "filterProvider": None,
        "filterProductId": None,
        "filterProductCategory": None,
        "filterProviderIds": job_id,
        "filterIds": None,
        "hideProductId": None,
        "hideProductCategory": None,
        "hideProvider": None
    }

    print("#"*60)

    print("payload", payload)
    print("headers", headers)
    print("url", f"{CONFIG['ucloud']['url']}/api/jobs/control/browse")

    print("#"*60)

    r = requests.get(
        url=f"{CONFIG['ucloud']['url']}/api/jobs/control/browse",
        headers=headers,
        params=payload)

    print("browsing job", job_id)

    if r.status_code == 200:
        return json.loads(r.text)
    else:
        print(r.status_code)
        print("Job not found")


def get_stacks():
    loader = loading.get_plugin_loader('password')
    auth = loader.load_from_options(
        auth_url=CONFIG['openstack']['auth_url'],
        username=CONFIG['openstack']['username'],
        password=CONFIG['openstack']['password'],
        project_id=CONFIG['openstack']['project_id'],
        project_name=CONFIG['openstack']['project_id'],
        user_domain_name="default"
    )

    sess = session.Session(auth=auth)
    print("Got openstack session:", sess)
    heat = client.Client('1', session=sess)
    print("Got heat client:", heat)
    # Man kan hive deleted stacks ud hvis man vil
    # deleted_stacks = heat.stacks.list(show_deleted=True)
    active_stacks = list(heat.stacks.list(
        filters={"stack_status": [
            "CREATE_COMPLETE",
            "CREATE_FAILED",
            "RESUME_COMPLETE",
            "CHECK_COMPLETE",
            "UPDATE_COMPLETE",
            "UPDATE_FAILED",
            "DELETE_FAILED"]}))
    print(f"Found {len(active_stacks)} stacks")

    return active_stacks


def get_jobid_from_stack(stack):
    return stack.stack_name.removeprefix(CONFIG['openstack']['stack_prefix'])


def read_config(env):
    config_parser = configparser.ConfigParser()
    config = config_parser.read(f'config-{env}.ini')
    if not config:
        raise Exception(f'config file config-{env}.ini not found')
    return config_parser


def main(env):
    print(f"Creating report for: {args.env}")
    stacks = get_stacks()

    data = []

    for stack in stacks:
        print(f'Getting ucloud info for stack: {stack.stack_name} {stack.stack_status}')
        job = get_ucloud_job_from_stack(stack)

        output = {
            "stack_name": stack.stack_name,
            "stack_status": stack.stack_status,
            "stack_creation_time": stack.creation_time,
            "stack_tags": stack.tags[0] if stack.tags else "",
            "job_id": job["id"] if job else "",
            "job_status": job["status"]["state"] if job else "",
            "job_product": job["specification"]["product"]["id"] if job else "",
            "job_owner": job["owner"]["createdBy"] if job else "",
        }

        data.append(output)

    # Sort by stack status
    data.sort(key=lambda x: x['stack_status'])

    field_names = list(data[0].keys())

    with open(f'{env}-status.csv', 'w') as csvfile:
        print("Writing file:", csvfile)
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(data)


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('env', type=str)
    args = parser.parse_args()

    # Setup config
    CONFIG = read_config(args.env)

    main(args.env)
