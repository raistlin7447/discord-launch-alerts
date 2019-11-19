import requests
from collections import defaultdict
from datetime import datetime

launch_provider = "National Aeronautics and Space Administration"
ROOT_URL = "https://launchlibrary.net/1.3/"
AGENCY_ENDPOINT = ROOT_URL + "agency"
LAUNCH_ENDPOINT = ROOT_URL + "launch"
PAD_ENDPOINT = ROOT_URL + "pad"

lsp_params = {"islsp": 1,
              "name": launch_provider}
lsp_json = requests.get(AGENCY_ENDPOINT, params=lsp_params).json()
lsp_id = lsp_json["agencies"][0]["id"]

pad_params = {"limit": 1000}
pad_json = requests.get(PAD_ENDPOINT, params=pad_params).json()
pads = {pad["id"]: pad["name"] for pad in pad_json["pads"]}

launches_params = {#"lsp": lsp_id,
                   "limit": 10000,
                   "mode": "verbose",
                   "status": "3,4"}
launches_json = requests.get(LAUNCH_ENDPOINT, params=launches_params).json()

launches_by_pad = defaultdict(list)
for launch in launches_json["launches"]:
    for pad in launch["location"]["pads"]:
        launches_by_pad[pad["id"]].append(launch)

for pad, launches in launches_by_pad.items():
    start_date = None
    start_launch = None
    shortest_interval = None
    shortest_launch_start = None
    shortest_launch_end = None
    for launch in launches:
        this_date = datetime.strptime(launch["isonet"], "%Y%m%dT%H%M%SZ")
        if start_date:
            interval = this_date - start_date
            if not shortest_interval or interval < shortest_interval:
                shortest_launch_start = start_launch
                shortest_launch_end = launch
                shortest_interval = interval
        start_date = this_date
        start_launch = launch

    if shortest_interval:
        print("Pad {} shortest interval is {}.".format(pads[pad], shortest_interval))
        print("\t{}: {}".format(shortest_launch_start["name"], shortest_launch_start["net"]))
        print("\t{}: {}".format(shortest_launch_end["name"], shortest_launch_end["net"]))
