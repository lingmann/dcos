#!/usr/bin/env python3
"""Integration tests for verirying the installer applicaiton.
TODO:
-test cases for run options
-test case for set_install_dir
-test case for set_log_level
"""

import pytest
import multiprocessing

@pytest.fixture
def setup_default_installer(request):
    import dcos_installer
    import run
    test_options=run.parse_args("")
    test_server=multiprocessing.Process(target=dcos_installer.DcosInstaller, args=(test_options,))
    test_server.start()
    def tear_down():
        test_server.terminate()
    request.addfinalizer(tear_down)
    return test_server

def test_basic_start(setup_default_installer):
    test_installer=setup_default_installer
    assert test_installer.is_alive()
