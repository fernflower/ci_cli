### What's this all about?
Making mos-neutron everyday devlab interaction a more pleasant experience.

### How?
Jenkins has a way to remotely trigger builds via its [Remote access API](https://wiki.jenkins-ci.org/display/JENKINS/Remote+access+API).
In short, a trivial usecase like triggering parameterized builds is performed by issuing a HTTP POST with basic access authentication.

As long as mos-neutron team uses jenkins jobs as a common way to fire up and manage virtual environments of different kinds, why
not utilize this cool feature and make UI haters life a bit easier? For those incapable of memorizing proper configuration defaults this
also brings a tempting feature to save cluster configurations as ini files with possibility to override defaulted values via cli.

### How can I try it?

#### Manage existing or create new environments without Jenkins UI interaction
You will need a username and Jenkins API token for this to work. Visiting [Jenkins account settings](http://networking-ci.vm.mirantis.net:8080/me/configure)
is a way to get these.

Copy user.conf.sample to user.conf, setting  **user**, **ssh_user** and **token** variables.
To make life easier you can make an alias *ci* to *python ci_cli/send.py* by adding a file */usr/local/bin/ci* with the following contents:

```
#~/bin/sh
python PATH_TO_THE_CLONED_REPO/ci_cli/send.py "$@"
```

* To deploy a new OC3 environment

`python send.py deploy --config configurations/deploy_heat_os_ha_contrail_3`

* To deploy an environment using overrides, like custom reclass branch

`python send.py deploy --config configurations/deploy_heat_os_ha_contrail_4 --STACK_RECLASS_BRANCH=refs/changes/80/25780/7`

#### Save configurations for future use as ini files
The existing configurations are stored in ci_cli/configurations.
Currently configurations may be passed to deploy command via --config option. Any parameter defined in config file may be overridden
by passing it on the command line as an optional argument.
