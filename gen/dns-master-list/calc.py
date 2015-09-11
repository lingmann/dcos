import json


def validate(arguments):
    assert type(json.loads(arguments['master_list'])) is list


def calc_num_masters(arguments):
    return len(json.loads(arguments['master_list']))

must = {
    'num_masters': calc_num_masters
}
