"""Module to organise storage elements."""

import posixpath

SE_by_name = {}
SE_by_host = {}

class StorageElement(object):
    """Representation of a grid storage element"""

    def __init__(self, name, host, type, location, basepath):
        """Initialise StorageElement.

        `name`: Identifier for element
        `host`: Hostname of element
        `type`: Storage type of element ('tape' or 'disk')
        `location`: Location of the SE, e.g. '/europe/uk/ral'
        `basepath`: Base path for standard storage paths on element
        """

        self.name = name
        self.host = host
        self.basepath = basepath
        self.location = location
        self.type = type

    def get_storage_path(self, remotepath):
        """Generate the standard storage path for this SE from a logical file name."""
        return posixpath.join(self.basepath, remotepath)

    def get_distance(self, other):
        """Return the distance to another StorageElement.

        Returns a negative number. The smaller (i.e. more negative) it is,
        the closer the two SE are together.
        """

        common = posixpath.commonprefix([self.location, other.location])
        # The more '/' are in the common prefix, the closer the SEs are.
        # So we can take the negative number as measure of distance.
        distance = -common.count('/')
        return distance

# Add actual SEs
SEs = [
    StorageElement('RAL-LCG22-tape',
        host = 'srm-t2k.gridpp.rl.ac.uk',
        type = 'tape',
        location = '/europe/uk/ral',
        basepath = 'srm://srm-t2k.gridpp.rl.ac.uk/castor/ads.rl.ac.uk/prod/t2k.org'),
    StorageElement('UKI-SOUTHGRID-RALPP-disk',
        host = 'heplnx204.pp.rl.ac.uk',
        type = 'disk',
        location = '/europe/uk/ral',
        basepath = 'rm://heplnx204.pp.rl.ac.uk/pnfs/pp.rl.ac.uk/data/t2k/t2k.org'),
    StorageElement('CA-TRIUMF-T2K1-disk',
        host = 't2ksrm.nd280.org',
        type = 'disk',
        location = '/americas/ca/ubc',
        basepath = 'srm://'),
    StorageElement('JP-KEK-CRC-02-disk',
        host = 'kek2-se01.cc.kek.jp',
        type = 'disk',
        location = '/asia/jp/kek',
        basepath = 'srm://'),
# TODO:
#GRIF-disk
#GridPPSandboxSE
#IFIC-LCG2-disk
#IN2P3-CC-disk
#INFN-BARI1-disk
#Nebraska1-disk
#UKI-LT2-IC-HEP-disk
#UKI-LT2-QMUL2-disk
#UKI-NORTHGRID-LANCS-HEP-disk
#UKI-NORTHGRID-LIV-HEP-disk
#UKI-NORTHGRID-MAN-HEP-disk
#UKI-NORTHGRID-SHEF-HEP-disk
#UKI-SOUTHGRID-OX-HEP-disk
#UNIBE-LHEP-disk
#pic-disk
    ]

def get_SE_by_path(path):
    """Return the StorageElement corresponsing to the given srm-path."""
    for SE in SEs:
        if SE.host in path:
            return SE
    return None