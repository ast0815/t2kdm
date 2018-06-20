"""T2K Data Manager

Helpful tools to manage the T2K data on the grid.
"""

import configuration
import backends
import storage
import utils
import sys

if sys.argv[0].endswith('t2kdm-config'):
    # Someone is calling t2kdm-config.
    # Do not try to load any configuration, as that is what they might be trying to fix!
    pass
else:
    # Load configuration
    config = configuration.load_config()
    # Get backend according to configuration
    backend = backends.get_backend(config)

    # Get functions from backend
    ls = backend.ls
    replicas = backend.replicas
    replicate = backend.replicate
    remove = backend.remove
    get = backend.get
    put = backend.put
