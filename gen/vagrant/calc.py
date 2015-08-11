import os

arguments = {
    "num_masters": 1,
    "cluster_name": "Vagrant_SingleNode"
}

defaults = {
    "resolvers": "[\"8.8.8.8\"]",
    "ip_detect_filename": os.path.join('scripts', 'vagrant', 'ip-detector.sh'),
}
