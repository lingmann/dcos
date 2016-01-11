from dcos_installer import DcosInstaller


def test_default_arg_parser():
    parser = DcosInstaller().parse_args([])
    assert parser.verbose is False
    assert parser.port == 9000
    assert parser.web is False
    assert parser.configure is False
    assert parser.preflight is False
    assert parser.deploy is False
    assert parser.postflight is False
    assert parser.validate_config is False
    assert parser.test is False


def test_set_arg_parser():
    parser = DcosInstaller().parse_args(['-v', '-p 12345'])
    assert parser.verbose is True
    assert parser.port == 12345
    parser = DcosInstaller().parse_args(['--web'])
    assert parser.web is True
    parser = DcosInstaller().parse_args(['--configure'])
    assert parser.configure is True
    parser = DcosInstaller().parse_args(['--preflight'])
    assert parser.preflight is True
    parser = DcosInstaller().parse_args(['--postflight'])
    assert parser.postflight is True
    parser = DcosInstaller().parse_args(['--deploy'])
    assert parser.deploy is True
    parser = DcosInstaller().parse_args(['--validate-config'])
    assert parser.validate_config is True
    parser = DcosInstaller().parse_args(['--test'])
    assert parser.test is True


def test_mutual_exclusion():
    try:
        DcosInstaller().parse_args(['--web', '--configure'])
    except SystemExit:
        pass

    try:
        DcosInstaller().parse_args(['--web', '--preflight'])
    except SystemExit:
        pass

    try:
        DcosInstaller().parse_args(['--web', '--postflight'])
    except SystemExit:
        pass

    try:
        DcosInstaller().parse_args(['--web', '--deploy'])
    except SystemExit:
        pass

    try:
        DcosInstaller().parse_args(['--web', '--validate-config'])
    except SystemExit:
        pass

    try:
        DcosInstaller().parse_args(['--web', '--test'])
    except SystemExit:
        pass
