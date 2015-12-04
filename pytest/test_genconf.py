from providers.genconf import load_yaml_stringify, stringify_dict

config_str = {
    "foo": "bar",
    "master_list": "[\"172.17.10.101\", \"172.17.10.102\", \"172.17.10.103\"]"
}

config_stringify = {
    "foo": "bar",
    "master_list": ["172.17.10.101", "172.17.10.102", "172.17.10.103"]
}

yaml_config_str = """
foo: bar
master_list: ["172.17.10.101", "172.17.10.102", "172.17.10.103"]
"""

yaml_config_stringify = """
foo: bar
master_list:
  - 172.17.10.101
  - 172.17.10.102
  - 172.17.10.103
"""


def test_stringify_dict():
    assert stringify_dict(config_str) == config_str
    assert stringify_dict(config_stringify) == config_str


def test_load_yaml_stringify():
    assert load_yaml_stringify(yaml_config_str) == config_str
    assert load_yaml_stringify(yaml_config_stringify) == config_str
