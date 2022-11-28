# Ucloud / Openstack job status overview report

This script is used to get an overview of the jobs running in UCloud and the corresponding stacks/status in openstack.


## Usage:

### Create environment (if needed)

```
python -m venv status
```

### Activate environment
```
source status/bin/activate
```

### Install dependencies
```
pip install -r requirements.txt
```

### Fill in config

Add a config file like config-secret.ini and fill in the settings.


### Run script

The env parameter is the name of the ini file you created.
```
python status.py secret
```
