
import httplib
import json
import prettytable
import sys

def fetch_list(master):
    con = httplib.HTTPConnection(master)
    con.request("GET", "/__processes__")
    return json.loads(con.getresponse().read())

def get_counts(data):

    def acc_names(acc, x):
        if not "name" in x:
            return acc
        acc[x["name"]] = acc.get(x["name"], 0) + 1
        return acc

    for actor in data:
        yield [actor["id"], '', len(actor["events"])]
        for k,v in reduce(acc_names, actor["events"], {}).iteritems():
            yield [actor["id"], k, v]

def run(host):
    tb = prettytable.PrettyTable(
        ["Actor", "Event", "Count"],
        border=False,
        max_table_width=80,
        hrules=prettytable.NONE,
        vrules=prettytable.NONE,
        left_padding_width=0,
        right_padding_width=1
    )
    for line in get_counts(fetch_list(host)):
        tb.add_row(line)

    print tb

if __name__ == "__main__":
    run(sys.argv[1])
