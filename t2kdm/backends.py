import sh
import itertools
import posixpath
from os import path
from t2kdm import storage
import re

class GridBackend(object):
    """Class that handles the actual work on the grid.

    This is just a base class that other classes must inherit from.

    The convention for remote paths is that public methods expect "t2k paths",
    i.e. paths within the t2k grid directory, omitting the common prefix.
    Internal methods, i.e. the ones beginning with an underscore '_',
    expect the full path to be passed to them.
    """

    def __init__(self, **kwargs):
        """Initialise backend.

        Accepts the follwoing keyword arguments:

        basedir: String. Default: '/t2k.org'
            Sets the base directory of the backend.
            All paths are specified relative to that position.
        """

        self.basedir = kwargs.pop('basedir', '/t2k.org')
        if len(kwargs) > 0:
            raise TypeError("Invalid keyword arguments: %s"%(list(kwargs.keys),))

    def full_path(self, relpath):
        """Prepend the base dir to a path."""
        return posixpath.normpath(self.basedir + relpath)

    def _ls(self, remotepath, **kwargs):
        raise NotImplementedError()

    def ls(self, remotepath, **kwargs):
        """List contents of a remote logical path.

        Supported keyword arguments:

        long: Bool. Default: False
            Print a longer, more detailed listing.
        directory: Bool. Default: False
            List directory entries instead of contents.
        """
        _path = self.full_path(remotepath)
        return self._ls(_path, **kwargs)

    def _is_dir(self, remotepath):
        """Is the remote path a directory?"""
        return str(self._ls(remotepath, long=True, directory=True)).strip()[0] == 'd'

    def is_dir(self, remotepath):
        """Is the remote path a directory?"""
        return self._is_dir(self.full_path(remotepath))

    def _replica_state(self, storagepath, **kwargs):
        """Internal method to get the state of a replica, e.g. 'ONLINE'."""
        raise NotImplementedError()

    def _replica_checksum(self, storagepath, **kwargs):
        """Internal method to get the checksum of a replica."""
        raise NotImplementedError()

    def _replicas(self, remotepath, **kwargs):
        raise NotImplementedError()

    def _add_replica_info(self, rep):
        SE = storage.get_SE_by_path(rep)
        if SE is not None:
            return "%-32s %-4s %-7s %8.8s %s"%(SE.name, SE.type, self._replica_state(rep), self._replica_checksum(rep), rep)
        else:
            return "%-32s %-4s %-7s %8.8s %s"%('UNKNOWN', '?', self._replica_state(rep), self._replica_checksum(rep), rep)

    @staticmethod
    def _iterable_output_from_text(text, **kwargs):
        """Turn a block of text into an iterable if necessary."""
        it = kwargs.pop('_iter', False)
        if it == False:
            # Nothing to do here
            return text
        else:
            # Split by lines and return iterable
            lines = text.split('\n')
            if text[-1] == '\n':
                # Remove last empty string from split
                lines = lines[:-1]
            return (line+'\n' for line in lines)

    @staticmethod
    def _iterable_output_from_iterable(iterable, **kwargs):
        """Turn an iterable into a block of text if necessary."""
        it = kwargs.pop('_iter', False)
        if it == True:
            # Nothing to do here
            return iterable
        else:
            # Concatenate all lines
            text = ""
            for line in iterable:
                text += line
            return text

    def replicas(self, remotepath, **kwargs):
        """List replicas of a remote logical path.

        Supported keyword arguments:

        long: Bool. Default: False
            Print a longer, more detailed listing.
        """
        _path = self.full_path(remotepath)
        l = kwargs.pop('long', False)
        if l:
            # Parse each line and add additional information
            it = kwargs.pop('_iter', False)
            kwargs['_iter'] = True
            return self._iterable_output_from_iterable(
                    (self._add_replica_info(line) for line in self._replicas(_path, **kwargs)),
                    _iter=it)
        else:
            return self._replicas(_path, **kwargs)

    def _replicate(self, source_storagepath, destination_storagepath, **kwargs):
        raise NotImplementedError()

    def replicate(self, remotepath, destination, source=None, tape=False, recursive=False, **kwargs):
        """Replicate the file to the specified storage element.

        If no source storage elment is provided, the closest replica is chosen.
        If `tape` is `True`, tape SEs are considered when choosing the closest one.
        If `recursive` is `True`, all files and sub-directories of a given path are replicated.
        if `recursive` is a string, it is treated as regular expression
        and only matching subfolders or files are replicated.
        """

        # Do thing recursively if requested
        if isinstance(recursive, str):
            regex = re.compile(recursive)
            recursive = True
        else:
            regex = None
        _path = self.full_path(remotepath)
        if recursive and self._is_dir(_path):
            # Go through the contents of the directory recursively
            it = kwargs.pop('_iter', False)
            newpaths = []
            for element in self.ls(remotepath, _iter=True):
                element = element.strip()
                if regex is None or regex.search(element):
                    newpaths.append(posixpath.join(remotepath, element))
            def outputs(paths):
                for path in paths:
                    # Ignore errors when running recursively
                    yield self.replicate(path, destination, source, tape, recursive,
                            _iter=True, _ok_code=list(range(-255,256)), **kwargs)
            iterable = itertools.chain.from_iterable(outputs(newpaths))
            return self._iterable_output_from_iterable(iterable, _iter=it)

        # Get destination SE and check if file is already present
        dst = storage.get_SE(destination)
        if dst.has_replica(remotepath):
            # Replica already at destination, nothing to do here
            return self._iterable_output_from_text(
                    "%s\nReplica already present at destination storage element %s.\n"%(remotepath, dst.name,), **kwargs)

        # Get source SE
        if source is None:
            src = dst.get_closest_SE(remotepath, tape=tape)
            if src is None:
                raise sh.ErrorReturnCode_1('', '',
                        "Could not find valid storage element with replica of %s.\n"%(remotepath,))
        else:
            src = storage.get_SE(source)
            if src is None:
                raise sh.ErrorReturnCode_1('', '',
                        "Could not find storage element %s.\n"%(source,))

            if not src.has_replica(remotepath):
                # Replica not present at source, throw error
                raise sh.ErrorReturnCode_1('', '',
                        "%s\nNo replica present at source storage element %s\n"%(remotepath, src.name,))

        source_path = src.get_replica(remotepath)
        destination_path = dst.get_storage_path(remotepath)
        return self._replicate(source_path, destination_path, **kwargs)

    def _get(self, storagepath, localpath, **kwargs):
        raise NotImplementedError()

    def get(self, remotepath, localpath, source=None, tape=False, **kwargs):
        """Download a file from the grid.

        If no source storage elment is provided, the closest replica is chosen.
        If `tape` is True, tape SEs are considered when choosing the closest one.
        """

        if source is None:
            # Get closest SE
            SE = storage.get_closest_SE(remotepath, tape=tape)
            if SE is None:
                raise sh.ErrorReturnCode_1('', '',
                        "Could not find valid storage element with replica of %s.\n"%(remotepath,))
        else:
            # Use the provided source
            SE = storage.get_SE(source)
            if SE is None:
                raise sh.ErrorReturnCode_1('', '',
                        "Could not find storage element %s.\n"%(source,))

        # Get the source replica
        replica = SE.get_replica(remotepath)

        # Append the basename to the localpath if it is a directory
        if path.isdir(localpath):
            localpath = path.join(localpath, posixpath.basename(remotepath))

        # Do the actual copying
        return self._get(replica, localpath, **kwargs)

class LCGBackend(GridBackend):
    """Grid backend using the LCG command line tools `lfc-*` and `lcg-*`."""

    def __init__(self, **kwargs):
        # LFC paths alway put a '/grid' as highest level directory.
        # Let us not expose that to the user.
        kwargs['basedir'] = '/grid'+kwargs.pop('basedir', '/t2k.org')
        GridBackend.__init__(self, **kwargs)

        self._proxy_init_cmd = sh.Command('voms-proxy-init')
        self._ls_cmd = sh.Command('lfc-ls')
        self._replicas_cmd = sh.Command('lcg-lr')
        self._replica_state_cmd = sh.Command('lcg-ls')
        self._replica_checksum_cmd = sh.Command('lcg-get-checksum')
        self._replicate_cmd = sh.Command('lcg-rep')
        self._cp_cmd = sh.Command('lcg-cp')

    def _ls(self, remotepath, **kwargs):
        # Translate keyword arguments
        l = kwargs.pop('long', False)
        d = kwargs.pop('directory', False)
        args = []
        if l:
            args.append('-l')
        if -d:
            args.append('-d')
        args.append(remotepath)

        return self._ls_cmd(*args, **kwargs)

    def _replicas(self, remotepath, **kwargs):
        return(self._replicas_cmd('lfn:'+remotepath, **kwargs))

    def _replica_state(self, storagepath, **kwargs):
        _path = storagepath.strip()
        it = kwargs.pop('_iter', None)
        try:
            listing = self._replica_state_cmd('-l', _path, **kwargs)
        except sh.ErrorReturnCode:
            listing = '- - - - - ?'
        return listing.split()[5]

    def _replica_checksum(self, storagepath, **kwargs):
        _path = storagepath.strip()
        it = kwargs.pop('_iter', None)
        try:
            listing = self._replica_checksum_cmd(_path, **kwargs)
        except sh.ErrorReturnCode:
            listing = '? -'
        try:
            checksum = listing.split()[0]
        except IndexError:
            # Something weird happened
            checksum = '?'
        return checksum

    @staticmethod
    def _ignore_identical_lines(iterable, **kwargs):
        last_line = None
        for line in iterable:
            if line == last_line:
                continue
            else:
                last_line = line
                yield line

    def _replicate(self, source_storagepath, destination_storagepath, **kwargs):
        kwargs['_err_to_out'] = True # Verbose output is on stderr
        kwargs.pop('_err', None) # Cannot specify _err and _err_ro_out at same time
        it = kwargs.pop('_iter', False) # should the out[put be an iterable?
        kwargs['_iter'] = True # Need iterable to ignore identical lines

        # Get original command output
        iterable = self._replicate_cmd('-v', '--checksum', '-d', destination_storagepath, source_storagepath, **kwargs)
        # Ignore lines that are identical to the previous
        iterable = self._ignore_identical_lines(iterable)

        # return requested kind of output
        return self._iterable_output_from_iterable(iterable, _iter=it)

    def _get(self, storagepath, localpath, **kwargs):
        kwargs['_err_to_out'] = True # Verbose output is on stderr
        kwargs.pop('_err', None) # Cannot specify _err and _err_ro_out at same time
        it = kwargs.pop('_iter', False) # should the out[put be an iterable?
        kwargs['_iter'] = True # Need iterable to ignore identical lines

        # Get original command output
        iterable = self._cp_cmd('-v', '--checksum', storagepath, localpath, **kwargs)
        # Ignore lines that are identical to the previous
        iterable = self._ignore_identical_lines(iterable)

        # return requested kind of output
        return self._iterable_output_from_iterable(iterable, _iter=it)

def get_backend(config):
    """Return the backend according to the provided configuration."""

    if config.backend == 'lcg':
        return LCGBackend(basedir = config.basedir)
    else:
        raise config.ConfigError('backend', "Unknown backend!")
