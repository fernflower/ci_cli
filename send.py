import argparse
import ConfigParser
import logging
import os
import requests
import sys
import time

# will store parsed user config
USER_CONFIG = {}
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def _form_job_url(job, config=None, job_type='deploy'):
    config = config or USER_CONFIG
    type_map = {'deploy': 'buildWithParameters',
                'replay': 'replay'}
    return ("%(url)s/job/%(job)s/%(postfix)s" %
            {'url': config["ci_host"], 'job': job,
             'postfix': type_map[job_type]})


def parse_args():
    # XXX FIXME use subparsers
    """Parses arguments by argparse. Returns a tuple (known, unknown"""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["deploy", "replay"],
                        help="Action to perform")
    parser.add_argument("--user", help="Jenkins API user")
    parser.add_argument("--token", help="Jenkins API token")
    parser.add_argument("--config", help="Configuration file for deploy job")
    parser.add_argument("--user-config", help="User config file",
                        default=os.path.join(
                            os.path.dirname(os.path.realpath(__file__)),
                            'user.conf'))
    parser.add_argument("--id", help="Build id to run replay", type=int)
    return parser.parse_known_args()


def _parse_user_config(config):
    # check user config file exists
    if not os.path.exists(config):
        LOG.error("User config file %s does not exist. "
                  "Create one from sample config." % config)
        sys.exit(1)
    cfg = ConfigParser.ConfigParser()
    cfg.read(config)
    return {k: v for k, v in cfg.items('default')}


def main():
    parsed, unknown = parse_args()
    USER_CONFIG.update(_parse_user_config(parsed.user_config))

    # turn unknown args into optional arguments
    # args should be passed as --OVERRIDE_ARGUMENT=VALUE
    override = dict((arg.split('=', 1)[0].replace('-', '_').upper(),
                     arg.split('=')[1])
                    for arg in [u.replace('--', '') for u in unknown])
    auth_data = {"user": USER_CONFIG.get('user') or parsed.user,
                 "token": USER_CONFIG.get('token') or parsed.token}
    if not all(auth_data[k] for k in auth_data):
        LOG.error("Both 'user' and 'token' parameters must be set")
        sys.exit(1)
    # validate that config parameter is set
    if not parsed.config:
        LOG.error("'Config' parameter must be set for %s job" % parsed.command)
        sys.exit(1)
    if not os.path.exists(parsed.config):
        LOG.error("Config file %s does not exist" % parsed.config)
        sys.exit(1)
    if parsed.command.startswith("deploy"):
        deploy(config=parsed.config, auth_data=auth_data, override=override)
    elif parsed.command == "replay":
        replay(config=parsed.config, auth_data=auth_data,
               override=override, job_id=parsed.id)
    else:
        LOG.error("Command %s not supported yet" % parsed.command)


def deploy(config, auth_data, override):
    data = _data_from_config(config, override=override)
    url = _form_job_url(data['_JENKINS_DATA']['JOB'])
    # pop all ci data if present
    data.pop('_JENKINS_DATA', None)
    _send_request(url, data, auth_data)


def replay(config, auth_data, override, job_id):
    config_data = _data_from_config(config, override=override)
    # will contain a unique job id (deploy_os_contrail_heat);
    # should have form unique_id/build_number for replay
    job = "%(job)s/%(id)s" % {'job': config_data['_JENKINS_DATA']['JOB'],
                              'id': job_id}
    # XXX FIXME exception handling
    with open(config_data['_JENKINS_DATA']['MAINSCRIPT']) as f:
        main = f.read()
    data = {'_.mainScript': main,
            'Submit': 'Run',
            'json': {'mainScript': main}}
    url = _form_job_url(job, job_type='replay')
    _send_request(url, data, auth_data, send_form=True)


def _data_from_config(config, override=None):
    """Transfer config values in data to be submitted.

       If override dictionary is passed, then the values from it override those
       in config.
    """
    cfg = ConfigParser.ConfigParser()
    cfg.read(config)
    data = {}
    for k, v in cfg.items('default'):
        if v.startswith('@'):
            # handling a file - substitute with contents
            with open(v.lstrip('@')) as f:
                v = f.read()
        data[k.upper()] = v
    # validate and choose proper job by checking [jenkins] session
    try:
        jenkins_data = {k.upper(): v for k, v in cfg.items('jenkins')}
        data['_JENKINS_DATA'] = jenkins_data
    except ConfigParser.NoSectionError:
        LOG.error("[jenkins] section not found in %s" % config)
        sys.exit(1)
    if not override:
        return data
    for param in {k: v for k, v in override.iteritems() if k in data}:
        data[param] = override[param]
    return data


def _send_request(url, data, auth_data, send_form=False):
    if not send_form:
        # send data via params
        r = requests.post(url, params=data,
                          auth=requests.auth.HTTPBasicAuth(auth_data['user'],
                                                           auth_data['token']))
    else:
        # send data via data
        r = requests.post(url, data=data,
                          auth=requests.auth.HTTPBasicAuth(auth_data['user'],
                                                           auth_data['token']))
    if r.ok:
        queue_id = r.headers.get('Location')
        attempts = 3
        if queue_id:
            job_url = queue_id + 'api/json'
            while attempts > 0:
                job_r = requests.get(job_url)
                if job_r.ok:
                    try:
                        job = job_r.json()['executable']['url']
                        LOG.info('Link to job: %s' % job)
                        break
                    except KeyError:
                        attempts -= 1
                        sleep_sec = 5
                        LOG.info('Job info not found for %s, retry in %s' %
                                 (queue_id, sleep_sec))
                        time.sleep(sleep_sec)
        LOG.info("Success!")
    else:
        LOG.info(r.text)


if __name__ == "__main__":
    main()
