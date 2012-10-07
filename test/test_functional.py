#
# Functional test
#
# Requires WebTest http://webtest.pythonpaste.org/
# sudo aptitude install python-webtest
#
# Run as: nosetests functional_test.py
#

from nose.tools import assert_raises, raises, with_setup
from time import time
from datetime import datetime
from webtest import TestApp
import glob
import os
import shutil
import sys

from cork import Cork

REDIR = '302 Found'
app = None
tmpdir = None
orig_dir = os.getcwd()
tmproot = None

if sys.platform == 'darwin':
    tmproot = "/tmp"
else:
    tmproot = "/dev/shm" # In-memory filesystem allows faster testing.
                         # Not available in OSX.

def populate_conf_directory():
    """Populate a directory with valid configuration files, to be run just once
    The files are not modified by each test
    """
    global tmpdir
    tmpdir = "%s/cork_functional_test_source" % tmproot

    # only do this once, as advertised
    if os.path.exists(tmpdir): return

    os.mkdir(tmpdir)
    os.mkdir(tmpdir + "/example_conf")

    cork = Cork(tmpdir + "/example_conf", initialize=True)

    cork._store.roles['admin'] = 100
    cork._store.roles['editor'] = 60
    cork._store.roles['user'] = 50
    cork._store._savejson('roles', cork._store.roles)

    tstamp = str(datetime.utcnow())
    username = password = 'admin'
    cork._store.users[username] = {
        'role': 'admin',
        'hash': cork._hash(username, password),
        'email_addr': username + '@localhost.local',
        'desc': username + ' test user',
        'creation_date': tstamp
    }
    username = password = ''
    cork._store.users[username] = {
        'role': 'user',
        'hash': cork._hash(username, password),
        'email_addr': username + '@localhost.local',
        'desc': username + ' test user',
        'creation_date': tstamp
    }
    cork._store._save_users()

def remove_temp_dir():
    for f in glob.glob('%s/cork_functional_test_wd*' % tmproot, ):
        shutil.rmtree(f)

def setup_app():

    # create test dir and populate it using the example files
    global tmpdir
    global orig_dir

    # save the directory where the unit testing has been run
    if orig_dir is None:
        orig_dir = os.getcwd()
    #os.chdir(orig_dir)

    # create json files to be used by Cork
    populate_conf_directory()

    # purge the temporary test directory
    remove_temp_dir()

    # populate the temporary test dir
    tstamp = str(time())[5:]
    tmpdir = "%s/cork_functional_test_wd_%s" % (tmproot, tstamp)
    os.mkdir(tmpdir)

    # copy the needed files
    tmp_source = "%s/cork_functional_test_source" % tmproot
    shutil.copytree(tmp_source + '/example_conf', tmpdir + '/example_conf')
    shutil.copytree(orig_dir + '/test/views', tmpdir + '/views')

    # change to the temporary test directory
    # cork relies on this being the current directory
    os.chdir(tmpdir)

    # create global TestApp instance
    global app
    import simple_webapp
    app = TestApp(simple_webapp.app)


def login():
    """run setup_app and log in"""
    global app
    setup_app()
    p = app.post('/login', {'username': 'admin', 'password': 'admin'})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/', \
        "Incorrect redirect to %s" % p.location

def teardown():
    os.chdir(orig_dir)
    remove_temp_dir()
    app = None


@with_setup(login, teardown)
def test_functional_login():
    # fetch a page successfully
    assert app.get('/admin').status == '200 OK'

@with_setup(setup_app, teardown)
def test_login_existing_user_none_password():
    p = app.post('/login', {'username': 'admin', 'password': None})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login', \
        "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_nonexistent_user_none_password():
    p = app.post('/login', {'username': 'IAmNotHere', 'password': None})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login', \
        "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_existing_user_empty_password():
    p = app.post('/login', {'username': 'admin', 'password': ''})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login', \
        "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_nonexistent_user_empty_password():
    p = app.post('/login', {'username': 'IAmNotHere', 'password': ''})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login', \
        "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_login_existing_user_wrong_password():
    p = app.post('/login', {'username': 'admin', 'password': 'BogusPassword'})
    assert p.status == REDIR, "Redirect expected"
    assert p.location == 'http://localhost:80/login', \
        "Incorrect redirect to %s" % p.location

@with_setup(setup_app, teardown)
def test_functional_login_logout():
    # Incorrect login
    p = app.post('/login', {'username': 'admin', 'password': 'BogusPassword'})
    assert p.status == REDIR
    assert p.location == 'http://localhost:80/login', \
        "Incorrect redirect to %s" % p.location

    # log in and get a cookie
    p = app.post('/login', {'username': 'admin', 'password': 'admin'})
    assert p.status == REDIR
    assert p.location == 'http://localhost:80/', \
        "Incorrect redirect to %s" % p.location

    # fetch a page successfully
    assert app.get('/admin').status == '200 OK'

    # log out
    assert app.get('/logout').status == REDIR

    # drop the cookie
    app.reset()
    assert app.cookies == {}, "The cookie should be gone"

    # fetch the same page, unsuccessfully
    assert app.get('/admin').status == REDIR

@with_setup(login, teardown)
def test_functional_expiration():
    assert app.get('/admin').status == '200 OK'
    # change the cookie expiration in order to expire it
    app.app.options['timeout'] = 0
    assert app.get('/admin').status == REDIR, "The cookie should have expired"

