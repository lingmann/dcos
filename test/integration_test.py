#!/usr/bin/env python3
"""Integration tests for verirying the installer applicaiton.
TODO:
-test cases for run options
-test case for set_install_dir
-test case for set_log_level
"""
import multiprocessing

import pytest


# method to test multiple cmdline options across all tests
# @pytest.fixture(params=["",["-l","debug"]])
@pytest.fixture
def test_options():
    import run
    options=run.parse_args("")
    return options

@pytest.fixture
def default_installer(request, test_options):
    import dcos_installer
    import run
    #test_options=run.parse_args(request.param)
    test_server=multiprocessing.Process(
        target=dcos_installer.DcosInstaller,
        args=(test_options,))
    test_server.start()
    def tear_down():
        test_server.terminate()
    request.addfinalizer(tear_down)
    return test_server

def test_basic_start(default_installer):
    test_installer=default_installer
    assert test_installer.is_alive()
