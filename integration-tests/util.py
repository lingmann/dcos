import os
import subprocess


def run(cmd, *args, **kwargs):
    proc = subprocess.Popen(cmd, *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout, stderr = proc.communicate()
    print("STDOUT: ", stdout.decode('utf-8'))
    print("STDERR: ", stderr.decode('utf-8'))

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)

    assert len(stderr) == 0
    return stdout.decode('utf-8')


def expect_folder(path, files):
    path_contents = os.listdir(path)
    assert set(path_contents) == set(files)


def expect_fs(folder, contents):
    if isinstance(contents, list):
        expect_folder(folder, contents)
    elif isinstance(contents, dict):
        expect_folder(folder, contents.keys())

        for path in iter(contents):
            if contents[path] is not None:
                expect_fs(os.path.join(folder, path), contents[path])
    else:
        raise ValueError("Invalid type {0} passed to expect_fs".format(type(contents)))
