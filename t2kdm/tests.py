"""Tests for the T2K data Manager."""

import t2kdm
import t2kdm.commands as cmd
import t2kdm.cli as cli
from  t2kdm import backends
from  t2kdm import storage
from  t2kdm import utils

import argparse
from six import print_
from contextlib import contextmanager
import sys, os, sh
import tempfile
import posixpath
import re

testdir = '/test/t2kdm'
testfiles = ['test1.txt', 'test2.txt']
testSEs = ['UKI-LT2-QMUL2-disk']

@contextmanager
def no_output(redirect=True):
    stdout = sys.stdout
    stderr = sys.stderr
    with open('/dev/null', 'w') as null:
        try:
            if redirect:
                sys.stdout = null
                sys.stderr = null
            yield
        finally:
            sys.stdout = stdout
            sys.stderr = stderr

@contextmanager
def fake_argv(fake_argv):
    true_argv = sys.argv
    try:
        sys.argv = fake_argv
        yield
    finally:
        sys.sargv = true_argv

@contextmanager
def temp_dir():
    tempdir = tempfile.mkdtemp()
    try:
        yield tempdir
    finally:
        sh.rm('-r', tempdir)

def run_read_only_tests():
    print_("Testing ls...")

    entries = t2kdm.backend.ls(testdir)
    for e in entries:
        if e.name == testfiles[0]:
            break
    else:
        raise Exception("Test file not in listing.")

    print_("Testing ls_se...")

    entries = t2kdm.backend.ls_se(testdir, se=testSEs[0])
    for e in entries:
        if e.name == testfiles[0]:
            break
    else:
        raise Exception("Test file not in listing.")

    print_("Testing is_dir...")
    assert(t2kdm.is_dir('/test/t2kdm'))

    print_("Testing is_dir_se...")
    assert(t2kdm.is_dir_se('/test/t2kdm', se=testSEs[0]))

    print_("Testing replicas...")
    for rep in t2kdm.backend.replicas('/test/t2kdm/test1.txt'):
        if 'qmul.ac.uk' in rep:
            break
    else:
        raise Exception("Did not find expected replica.")

    print_("Testing is_file...")
    assert(t2kdm.backend.is_file('/test/t2kdm/test1.txt'))
    assert(not t2kdm.backend.is_file('/test/t2kdm/test666.txt'))

    print_("Testing is_file_se...")
    assert(t2kdm.backend.is_file_se('/test/t2kdm/test1.txt', testSEs[0]))
    assert(not t2kdm.backend.is_file_se('/test/t2kdm/test666.txt', testSEs[0]))

    print_("Testing exists...")
    assert(t2kdm.backend.exists(rep))
    assert(not t2kdm.backend.exists(posixpath.dirname(rep)))

    print_("Testing checksum...")
    assert(t2kdm.backend.checksum(rep) == '529506c1')

    print_("Testing state...")
    assert('ONLINE' in t2kdm.backend.state(rep))

    print_("Testing is_online...")
    assert(t2kdm.backend.is_online(rep))

    print_("Testing StorageElement...")
    # Test distance calculation
    assert(storage.SEs[0].get_distance(storage.SEs[1]) < 0)
    # Test getting SE by host
    assert('se03.esc.qmul.ac.uk' in storage.SE_by_host['se03.esc.qmul.ac.uk'].get_storage_path('/nd280/test'))
    # Test storage path arithmetic
    assert(storage.SEs[0].get_logical_path(storage.SEs[0].get_storage_path('/nd280/test')) == '/nd280/test')
    # Test getting the closest SE
    assert(storage.get_closest_SE('/test/t2kdm/test1.txt') is not None)

    print_("Testing get...")
    with temp_dir() as tempdir:
        path = posixpath.join(testdir, testfiles[0])
        filename = os.path.join(tempdir, testfiles[0])

        # Test choosing source SE automatically
        assert(t2kdm.backend.get(path, tempdir) == True)
        assert(os.path.isfile(filename))

        # Test providing the source SE
        try:
            t2kdm.backend.get(path, tempdir, source=testSEs[0], force=False)
        except backends.BackendException as e:
            assert("already exist" in e.args[0])
        else:
            raise Exception("Should have refused to overwrite!")
        assert(t2kdm.backend.get(path, tempdir, source=testSEs[0], force=True) == True)
        assert(os.path.isfile(filename))
        os.remove(filename)

        # Test recursive get
        assert(t2kdm.interactive.get(testdir, tempdir, recursive=True) == 0)
        assert(os.path.isfile(filename))

    print_("Testing check...")
    with temp_dir() as tempdir:
        filename = os.path.join(tempdir, 'faulty.txt')
        with no_output(True):
            assert(t2kdm.interactive.check(testdir, checksum=True, se=testSEs, recursive=True, quiet=False, verbose=True, list=filename) == 0)
        assert os.path.isfile(filename)
        assert os.path.getsize(filename) == 0
        with no_output(True):
            assert(t2kdm.interactive.check(testdir, se=testSEs[0:1], recursivese=testSEs[0], quiet=False, verbose=True) == 0)

    print_("Testing HTML index...")
    with temp_dir() as tempdir:
        utils.html_index("/test/", tempdir)
        utils.html_index("/test/", tempdir, recursive=True)

    print_("Testing Commands...")
    with no_output(True):
        assert(cmd.ls.run_from_cli('-l /') == False)
        assert(cmd.ls.run_from_cli('.') == False)

        cmd.ls.run_from_cli('abc') # This should not work, but not throw exception
        cmd.ls.run_from_cli('"abc') # This should not work, but not throw exception
        with fake_argv(['t2kdm-ls', '/']):
            assert(cmd.ls.run_from_console() == 0) # This should work
        with fake_argv(['t2kdm-cli', '/']):
            assert(cmd.ls.run_from_console() == 0) # This should work
        with fake_argv(['t2kdm-ls', '/abcxyz']):
            assert(cmd.ls.run_from_console() != 0) # This should not work, hence the not 0 return value

        # None of the Commands should return True in the CLI
        for com in cmd.all_commands:
            assert(com.run_from_cli('') == False)

    print_("Testing CLI...")
    cli = t2kdm.cli.T2KDmCli()
    with no_output(True):
        cli.onecmd('help ls')
        cli.onecmd('ls .')
        cli.onecmd('cd /user')
        cli.onecmd('cd ..')
        cli.onecmd('cd /abcxyz')
        cli.onecmd('lcd /')
        cli.onecmd('lcd .')
        cli.onecmd('lcd /root')
        cli.onecmd('lcd /abcxyz')
        cli.onecmd('lls .')
        cli.onecmd('lls ".')
        assert(cli.completedefault('s', 'ls us', 0, 0) == ['ser/'])
        assert(cli.completedefault('s', 'lls us', 0, 0) == ['sr/'])
        assert(cli.completedefault('"us', 'lls "us', 0, 0) == [])

def run_read_write_tests():
    print_("Cannot test replicate...")
    #print_("Testing replicate...")
    #with no_output():
    #    assert(t2kdm.interactive.replicate(testdir, testSEs[1], recursive=r'^test[1]\.t.t$', verbose=True) == 0)
    #    assert(t2kdm.interactive.replicate(testdir, testSEs[1], recursive=r'^test[2]\.t.t$', source=testSEs[0], verbose=True) == 0)

    print_("Testing put...")
    with temp_dir() as tempdir:
        tempf = 'thisfileshouldnotbehereforlong.txt'
        filename = os.path.join(tempdir, tempf)
        remotename = posixpath.join(testdir, tempf)
        # Make sure the file does not exist
        try:
            for SE in storage.SEs:
                t2kdm.remove(remotename, SE.name, final=True)
        except backends.DoesNotExistException:
            pass
        # Prepare something to upload
        with open(filename, 'wt') as f:
            f.write("This is testfile #3.\n")
        assert(t2kdm.put(filename, testdir+'/', destination=testSEs[0]))

    print_("Testing move...")
    assert(t2kdm.move(remotename, remotename+'dir/test.txt'))
    assert(t2kdm.move(remotename+'dir/test.txt', remotename))
    try:
        t2kdm.move(remotename, remotename)
    except backends.BackendException as e:
        pass
    else:
        raise Exception("Moving to existing file names should not be possible.")

    print_("Testing rename...")
    # Make sure the file does not exist
    renamed = re.sub('txt', 'TXT', remotename)
    try:
        for SE in storage.SEs:
            t2kdm.remove(renamed, SE.name, final=True)
    except backends.DoesNotExistException:
        pass
    assert(t2kdm.rename(remotename, 'txt', 'TXT'))
    assert(t2kdm.rename(renamed, 'TXT', 'txt'))

    print_("Testing rmdir...")
    assert(t2kdm.rmdir(remotename+'dir/'))
    try:
        t2kdm.rmdir(remotename+'dir/')
    except backends.DoesNotExistException:
        pass
    else:
        raise Exception("Should have failed to delete a dir that is not there.")

    print_("Testing disk SEs...")
    # Replicate test file to all SEs, to see if they all work
    for SE in storage.SEs:
        if SE.type == 'tape' or SE.is_blacklisted():
            # These SEs do not seem to cooperate
            continue
        print_(SE.name)
        assert(t2kdm.replicate(remotename, SE.name) == True)
        assert(SE.has_replica(remotename) == True)

    print_("Testing remove...")
    print_("Cannot test recursive wipe...")
    #with no_output():
    #    assert(t2kdm.interactive.remove(testdir, testSEs[1], recursive=True) == 0) # Remove everything from SE1
    # Remove uploaded file from previous test
    try:
        # This should fail!
        for SE in storage.SEs:
            t2kdm.remove(remotename, SE.name)
    except backends.BackendException as e:
        assert("Only one" in e.args[0])
    else:
        raise Exception("The last copy should not have been removed!")
    # With the `final` argument it should work
    try:
        for SE in storage.SEs:
            t2kdm.remove(remotename, SE.name, final=True)
            assert(SE.has_replica(remotename) == False)
        for SE in storage.SEs:
            t2kdm.remove(remotename, SE.name, final=True)
    except backends.DoesNotExistException:
        # The command will fail when the file no longer exists
        pass
    else:
        raise Exception("This should have raised a DoesNotExistException at some point.")

def run_tests():
    """Test the functions of the t2kdm."""

    parser = argparse.ArgumentParser(description="Run tests for the T2K Data Manager.")
    parser.add_argument('-w', '--write', action='store_true',
        help="do write tests. Default: read only")
    parser.add_argument('-b', '--backend', default=None,
        help="specify which backend to use")

    args = parser.parse_args()
    if args.backend is not None:
        t2kdm.config.backend = args.backend
        t2kdm.backend = backends.get_backend(t2kdm.config)

    run_read_only_tests()
    if args.write:
        run_read_write_tests()

    print_("All done.")

if __name__ == '__main__':
    run_tests()
