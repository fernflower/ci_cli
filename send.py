import argparse
import ConfigParser
import logging
import os
import requests
import sys

# will store parsed user config
USER_CONFIG = {}
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def _formUrl(job, server, vm_type, config=None):
    config = config or USER_CONFIG
    job = job.format(vm_type=vm_type, server=server)
    return _form_job_url(job, config)


def _form_job_url(job, config=None):
    config = config or USER_CONFIG
    return ("%(url)s/job/%(job)s/buildWithParameters" %
            {'url': config["ci_host"], 'job': job})


def parse_args():
    """Parses arguments by argparse. Returns a tuple (known, unknown"""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["deploy"],
                        help="Action to perform")
    parser.add_argument("--user", help="Jenkins API user")
    parser.add_argument("--token", help="Jenkins API token")
    parser.add_argument("--config", help="Configuration file for deploy job")
    parser.add_argument("--user-config", help="User config file",
                        default=os.path.join(
                            os.path.dirname(os.path.realpath(__file__)),
                            'user.conf'))
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
    if parsed.command.startswith("deploy"):
        # validate deploy-* command to have config parameter set
        if not parsed.config:
            LOG.error("'Config' parameter must be set for deploy-* job")
            sys.exit(1)
        if not os.path.exists(parsed.config):
            LOG.error("Config file %s does not exist" % parsed.config)
            sys.exit(1)
        deploy(config=parsed.config, auth_data=auth_data, override=override)
    else:
        LOG.error("Command %s not supported yet" % parsed.command)


def deploy(config, auth_data, override):
    data = _data_from_config(config, override=override)
    job = data.pop('JOB')
    url = _form_job_url(job)
    _send_request(url, data, auth_data)


def _data_from_config(config, override=None):
    """Transfer config values in data to be submitted.

       If override dictionary is passed, then the values from it override those
       in config.
    """
    cfg = ConfigParser.ConfigParser()
    cfg.read(config)
    data = {k.upper(): v for k, v in cfg.items('default')}
    # validate and choose proper job by checking [jenkins] session
    try:
        jenkins_data = {k.upper(): v for k, v in cfg.items('jenkins')}
        if jenkins_data.get('JOB'):
            data['JOB'] = jenkins_data['JOB']
    except ConfigParser.NoSectionError:
        LOG.error("[jenkins] section not found in %s" % config)
        sys.exit(1)
    if not override:
        return data
    for param in {k: v for k, v in override.iteritems() if k in data}:
        data[param] = override[param]
    return data


def _send_request(url, data, auth_data):
    r = requests.post(url, params=data,
                      auth=requests.auth.HTTPBasicAuth(auth_data['user'],
                                                       auth_data['token']))
    if r.ok:
        queue_id = r.headers.get('Location')
        if queue_id:
            job_url = queue_id + 'api/json'
            job_r = requests.get(job_url)
            if job_r.ok:
                try:
                    job = job_r.json()['executable']['url']
                    LOG.info('Link to job: %s' % job)
                except KeyError:
                    LOG.info('Job exec info not found for %s' % queue_id)
        LOG.info("Success!")
    else:
        LOG.info(r.text)


if __name__ == "__main__":
    main()
