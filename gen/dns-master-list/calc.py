import json


def validate_master_list(master_list):
    try:
        list_data = json.loads(master_list)

        assert type(list_data) is list, "Must be a JSON list. Got a {}".format(type(list_data))
    except json.JSONDecodeError as ex:
        # TODO(cmaloney):
        assert False, "Must be a valid JSON list. Errors whilewhile parsing at position {}: {}".format(ex.pos, ex.msg)


def calc_num_masters(master_list):
    return str(len(json.loads(master_list)))

validate = [validate_master_list]

must = {
    'num_masters': calc_num_masters
}
