from enoslib import *
from enoslib.infra.enos_g5k.g5k_api_utils import get_api_username
from random import randrange
import shutil
import os
import time
import argparse
import json


username = get_api_username()
project_dir = f"/home/{username}/Project/Ballet/"
minizinc = f"/home/{username}/Software/MiniZincIDE-2.7.6-bundle-linux-x86_64/bin"

def minizinc_path():
    return f"export PATH={minizinc}:$PATH"  

_COMPONENT=15    
_NEXPE = 10
_DEFAULT_TIME = "01:55:00"
_DEFAULT_START = "now"

# _SCENARIOS = ["cuser"]
_SCENARIOS = ["linear","circular","stratified"]

_PORT = 40001

# -------------
#  ROLES
# -------------
_BALLET = "ballet"

_CUSER_USER = "cuseruser"
_CUSER_PROVIDER = "cuserprovider"

_CPROVIDER_PROVIDER = "cproviderprovider"
_CPROVIDER_USER = "cprovideruser"

_LINEAR_PROVIDER="linearprovider"
_LINEAR_TRANSFORMER="lineartransformer"

_CIRCULAR_PROVIDER="circularprovider"
_CIRCULAR_TRANSFORMER="circulartransformer"
_CIRCULAR_USER="circularuser"

_STRATIFIED_PROVIDER="stratifiedprovider"
_STRATIFIED_MIDUSER="stratifiedmiduser"
_STRATIFIED_USER="stratifieduser"


def book(site, cluster, time=_DEFAULT_TIME, start=_DEFAULT_START):
    my_network = G5kNetworkConf(id="my_topological", type="prod", roles=["my_network"], site=site)
    if start != "now":
        g5k = G5kConf.from_settings(job_type="allow_classic_ssh", job_name=f"topological_ballet", walltime=time, reservation=start)
    else:
        g5k = G5kConf.from_settings(job_type="allow_classic_ssh", job_name=f"topological_ballet", walltime=time)
    g5k.add_network_conf(my_network)
    # Machine 1: cuser_user; cprovider_provider; linear_provider; circular_provider; stratified_provider
    g5k.add_machine(roles=[_BALLET, _CUSER_USER, _CPROVIDER_PROVIDER, _LINEAR_PROVIDER, _CIRCULAR_PROVIDER, _STRATIFIED_PROVIDER],
                    cluster=cluster, nodes=1, primary_network=my_network)
    # Machine 2: circular_user; stratified_user
    g5k.add_machine(roles=[_BALLET, _CIRCULAR_USER, _STRATIFIED_USER],
                    cluster=cluster, nodes=1, primary_network=my_network)
    # Machine | i ∈ [0;_COMPONENT[ : cuser_provider_i; cprovider_user_i; linear_transformer_i; circular_transformer_i; stratified_miduser_i
    for i in range(_COMPONENT):
        g5k.add_machine(roles=[_BALLET, 
                               _CUSER_PROVIDER, _CUSER_PROVIDER+str(i), 
                               _CPROVIDER_USER, _CPROVIDER_USER+str(i),
                               _LINEAR_TRANSFORMER, _LINEAR_TRANSFORMER+str(i), 
                               _CIRCULAR_TRANSFORMER, _CIRCULAR_TRANSFORMER+str(i), 
                               _STRATIFIED_MIDUSER, _STRATIFIED_MIDUSER+str(i)], 
                        cluster=cluster, nodes=1, primary_network=my_network)
    conf = g5k.finalize()
    provider = G5k(conf)
    roles, networks = provider.init()
    return roles, networks

def make_inventory_content(roles, scenario):
    inventory = {}
    # Inventory for cuser
    if scenario == "cuser":
        user_address = roles[_CUSER_USER][0].address
        inventory["user"] =  {'address': user_address, 'port_planner': _PORT}
        for i in range(_COMPONENT):
            provider_address = roles[_CUSER_PROVIDER+str(i)][0].address
            inventory[f'provider{i}'] =  {'address': provider_address, 'port_planner': _PORT}
    # Inventory for cprovider
    if scenario == "cprovider":
        provider_address = roles[_CPROVIDER_PROVIDER][0].address
        inventory["provider"] =  {'address': provider_address, 'port_planner': _PORT}
        for i in range(_COMPONENT):
            user_address = roles[_CPROVIDER_USER+str(i)][0].address
            inventory[f'user{i}'] =  {'address': user_address, 'port_planner': _PORT}
    # Inventory for linear
    if scenario == "linear":
        provider_address = roles[_LINEAR_PROVIDER][0].address
        inventory["provider"] =  {'address': provider_address, 'port_planner': _PORT}
        for i in range(_COMPONENT):
            transformer_address = roles[_LINEAR_TRANSFORMER+str(i)][0].address
            inventory[f'transformer{i}'] =  {'address':transformer_address, 'port_planner': _PORT}
    # Inventory for circular
    if scenario == "circular":
        provider_address = roles[_CIRCULAR_PROVIDER][0].address
        inventory["provider"] =  {'address': provider_address, 'port_planner': _PORT}
        user_address = roles[_CIRCULAR_USER][0].address
        inventory["user"] =  {'address': user_address, 'port_planner': _PORT}
        for i in range(_COMPONENT):
            transformer_address = roles[_CIRCULAR_TRANSFORMER+str(i)][0].address
            inventory[f'transformer{i}'] = {'address': transformer_address, 'port_planner': _PORT}
    # Inventory for stratified
    if scenario == "stratified":
        provider_address = roles[_STRATIFIED_PROVIDER][0].address
        inventory["provider"] =  {'address': provider_address, 'port_planner': _PORT}
        user_address = roles[_STRATIFIED_USER][0].address
        inventory["enduser"] =  {'address': user_address, 'port_planner': _PORT}
        for i in range(_COMPONENT):
            miduser_address = roles[_STRATIFIED_MIDUSER+str(i)][0].address
            inventory[f'user{i}'] = {'address': miduser_address, 'port_planner': _PORT}
    return inventory

def inventory_format_json(data):
    addresses = []
    for comp in data.keys():
        address = data[comp]["address"]
        port = data[comp]["port_planner"]
        addresses.append(f"\"{comp}\": {{\"address\": \"{address}\", \"port_planner\": {port}}}")
    return "{"+', '.join(addresses)+"}"

def make_inventory(roles, scenario):
    print(f"LET'S MAKE AN INVENTORY FOR {scenario} SCENARIO")
    data = make_inventory_content(roles, scenario)
    content = inventory_format_json(data)
    print(f"Inventory for {scenario}") 
    print(data) 
    filename = f"{project_dir}{scenario}_inventory.json"
    with play_on(pattern_hosts=_BALLET, roles=roles, run_as=username) as p:
        p.shell("echo '" + content + "' > " + filename )

def run(scenario, roles, ite, result_dir):
    make_inventory(roles, scenario)
    if scenario == "cuser":
        run_cuser(roles, ite, result_dir)
    if scenario == "cprovider":
        run_cprovider(roles, ite, result_dir)
    if scenario == "linear":
        run_linear(roles, ite, result_dir)
    if scenario == "circular":
        run_circular(roles, ite, result_dir)
    if scenario == "stratified":
        run_stratified(roles, ite, result_dir)

def run_cuser(roles, ite, result_dir):
    #1 Copy right python file
    script_place = f"{project_dir}examples/tests_gossip/central_user/"
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CUSER_PROVIDER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_provider.py {project_dir}")
    with play_on(pattern_hosts=_CUSER_USER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_user.py {project_dir}")
    #2.1 run SAT 
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CUSER_PROVIDER+str(i), roles=roles, run_as=username) as p:
            id_provider = i + 1
            p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py -n {_COMPONENT} -i {id_provider} -inventory {project_dir}cuser_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}cuser_sat_provider{i}.log 2>> {result_dir}{ite}cuser_sat_provider{i}.err", background=True)
    with play_on(pattern_hosts=_CUSER_USER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_user.py -n {_COMPONENT} -inventory {project_dir}cuser_inventory.json --time -it {ite}  -port {_PORT} >> {result_dir}{ite}cuser_sat_user.log 2>> {result_dir}{ite}cuser_sat_user.err")
    #2.2 run UNSAT
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CUSER_PROVIDER+str(i), roles=roles, run_as=username) as p:
            id_provider = i + 1
            p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py --unsat -n {_COMPONENT} -i {id_provider} -inventory {project_dir}cuser_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}cuser_unsat_provider{i}.log 2>> {result_dir}{ite}cuser_unsat_provider{i}.err", background=True)
    with play_on(pattern_hosts=_CUSER_USER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_user.py --unsat -n {_COMPONENT} -inventory {project_dir}cuser_inventory.json --time -it {ite}  -port {_PORT} >> {result_dir}{ite}cuser_unsat_user.log 2>> {result_dir}{ite}cuser_unsat_user.err")
    #get results
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CUSER_PROVIDER+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}cuser_sat_provider{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}cuser_unsat_provider{i}.log", dest="~")
            # p.shell(f"rm {project_dir}run_provider.py ")
    with play_on(pattern_hosts=_CUSER_USER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}cuser_sat_user.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}cuser_unsat_user.log", dest="~")
        # p.shell(f"rm {project_dir}run_user.py ")

def run_cprovider(roles, ite, result_dir):
    #1 Copy right python file
    script_place = f"{project_dir}examples/tests_gossip/central_provider/"
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CPROVIDER_USER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_user.py {project_dir}")
    with play_on(pattern_hosts=_CPROVIDER_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_provider.py {project_dir}")
    #2.1 run SAT 
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CPROVIDER_USER+str(i), roles=roles, run_as=username) as p:
            id_user = i + 1
            p.shell(f"{minizinc_path()}; python {project_dir}run_user.py -n {_COMPONENT} -i {id_user} -inventory {project_dir}cprovider_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}cprovider_sat_user{i}.log 2>> {result_dir}{ite}cprovider_sat_user{i}.err", background=True)
    with play_on(pattern_hosts=_CPROVIDER_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py -n {_COMPONENT} -inventory {project_dir}cprovider_inventory.json --time -it {ite}  -port {_PORT} >> {result_dir}{ite}cprovider_sat_provider.log 2>> {result_dir}{ite}cprovider_sat_provider.err")
    #2.2 run UNSAT
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CPROVIDER_USER+str(i), roles=roles, run_as=username) as p:
            id_user = i + 1
            p.shell(f"{minizinc_path()}; python {project_dir}run_user.py --unsat -n {_COMPONENT} -i {id_user} -inventory {project_dir}cprovider_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}cprovider_unsat_user{i}.log 2>> {result_dir}{ite}cprovider_unsat_user{i}.err", background=True)
    with play_on(pattern_hosts=_CPROVIDER_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py --unsat -n {_COMPONENT} -inventory {project_dir}cprovider_inventory.json --time -it {ite}  -port {_PORT} >> {result_dir}{ite}cprovider_unsat_provider.log 2>> {result_dir}{ite}cprovider_unsat_provider.err")
    #get results
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CPROVIDER_USER+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}cprovider_sat_user{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}cprovider_unsat_user{i}.log", dest="~")
            # p.shell(f"rm {project_dir}run_user.py ")
    with play_on(pattern_hosts=_CPROVIDER_PROVIDER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}cprovider_sat_provider.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}cprovider_unsat_provider.log", dest="~")
        # p.shell(f"rm {project_dir}run_provider.py ")

def run_linear(roles, ite, result_dir):
    #1 Copy right python file
    script_place = f"{project_dir}examples/tests_gossip/linear/"
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_LINEAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_transformer.py {project_dir}")
    with play_on(pattern_hosts=_LINEAR_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_provider.py {project_dir}")
    #2.1 run SAT
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_LINEAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            id_tr = i + 1
            p.shell(f"{minizinc_path()}; python {project_dir}run_transformer.py -n {_COMPONENT} -i {id_tr} -inventory {project_dir}linear_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}linear_sat_transformer{i}.log 2>> {result_dir}{ite}linear_sat_transformer{i}.err", background=True)
    with play_on(pattern_hosts=_LINEAR_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py -n {_COMPONENT} -inventory {project_dir}linear_inventory.json --time -it {ite}  -port {_PORT} >> {result_dir}{ite}linear_sat_provider.log 2>> {result_dir}{ite}linear_sat_provider.err")
    #2.2 run UNSAT
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_LINEAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            id_tr = i + 1
            p.shell(f"{minizinc_path()}; python {project_dir}run_transformer.py --unsat -n {_COMPONENT} -i {id_tr} -inventory {project_dir}linear_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}linear_unsat_transformer{i}.log 2>> {result_dir}{ite}linear_unsat_transformer{i}.err", background=True)
    with play_on(pattern_hosts=_LINEAR_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py --unsat -n {_COMPONENT} -inventory {project_dir}linear_inventory.json --time -it {ite}  -port {_PORT} >> {result_dir}{ite}linear_unsat_provider.log 2>> {result_dir}{ite}linear_unsat_provider.err")
    #get results
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_LINEAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}linear_sat_transformer{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}linear_unsat_transformer{i}.log", dest="~")
            # p.shell(f"rm {project_dir}run_transformer.py ")
    with play_on(pattern_hosts=_LINEAR_PROVIDER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}linear_sat_provider.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}linear_unsat_provider.log", dest="~")
        # p.shell(f"rm {project_dir}run_provider.py")


def run_circular(roles, ite, result_dir):
    #1 Copy right python file
    script_place = f"{project_dir}examples/tests_gossip/circular/"
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CIRCULAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_circular_transformer.py {project_dir}")
    with play_on(pattern_hosts=_CIRCULAR_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_circular_provider.py {project_dir}")
    with play_on(pattern_hosts=_CIRCULAR_USER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_circular_user.py {project_dir}")
    #2.1 Sat
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CIRCULAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_circular_transformer.py -n {_COMPONENT} -i {i} -inventory {project_dir}circular_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}circular_sat_transformer{i}.log 2>> {result_dir}{ite}circular_sat_transformer{i}.err", background=True)
    with play_on(pattern_hosts=_CIRCULAR_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_circular_provider.py -n {_COMPONENT} -inventory {project_dir}circular_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}circular_sat_provider.log 2>> {result_dir}{ite}circular_sat_provider.err", background=True)
    with play_on(pattern_hosts=_CIRCULAR_USER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_circular_user.py -n {_COMPONENT} -inventory {project_dir}circular_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}circular_sat_user.log 2>> {result_dir}{ite}circular_sat_user.err")
    #2.2 Unsat
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CIRCULAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_circular_transformer.py --unsat -n {_COMPONENT} -i {i} -inventory {project_dir}circular_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}circular_unsat_transformer{i}.log 2>> {result_dir}{ite}circular_unsat_transformer{i}.err", background=True)
    with play_on(pattern_hosts=_CIRCULAR_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_circular_provider.py --unsat -n {_COMPONENT} -inventory {project_dir}circular_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}circular_unsat_provider.log 2>> {result_dir}{ite}circular_unsat_provider.err", background=True)
    with play_on(pattern_hosts=_CIRCULAR_USER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_circular_user.py --unsat -n {_COMPONENT} -inventory {project_dir}circular_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}circular_unsat_user.log 2>> {result_dir}{ite}circular_unsat_user.err")
    #get result
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_CIRCULAR_TRANSFORMER+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}circular_sat_transformer{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}circular_unsat_transformer{i}.log", dest="~")
            # p.shell(f"rm {project_dir}run_circular_transformer.py ")
    with play_on(pattern_hosts=_CIRCULAR_PROVIDER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}circular_sat_provider.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}circular_unsat_provider.log", dest="~")
        # p.shell(f"rm {project_dir}run_circular_provider.py")
    with play_on(pattern_hosts=_CIRCULAR_USER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}circular_sat_user.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}circular_unsat_user.log", dest="~")
        # p.shell(f"rm {project_dir}run_circular_user.py")

def run_stratified(roles, ite, result_dir):
    #1 Copy right python file
    script_place = f"{project_dir}examples/tests_gossip/stratified/"
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_STRATIFIED_MIDUSER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_miduser.py {project_dir}")
    with play_on(pattern_hosts=_STRATIFIED_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_provider.py {project_dir}")
    with play_on(pattern_hosts=_STRATIFIED_USER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_end_user.py {project_dir}")
    #2.1 Sat
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_STRATIFIED_MIDUSER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_miduser.py -n {_COMPONENT} -i {i} -inventory {project_dir}stratified_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}stratified_sat_miduser{i}.log 2>> {result_dir}{ite}stratified_sat_miduser{i}.err", background=True)
    with play_on(pattern_hosts=_STRATIFIED_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py -n {_COMPONENT} -inventory {project_dir}stratified_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}stratified_sat_provider.log 2>> {result_dir}{ite}stratified_sat_provider.err", background=True)
    with play_on(pattern_hosts=_STRATIFIED_USER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_end_user.py -n {_COMPONENT} -inventory {project_dir}stratified_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}stratified_sat_user.log 2>> {result_dir}{ite}stratified_sat_user.err")
    #2.2 Unsat
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_STRATIFIED_MIDUSER+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_miduser.py --unsat -n {_COMPONENT} -i {i} -inventory {project_dir}stratified_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}stratified_unsat_miduser{i}.log 2>> {result_dir}{ite}stratified_unsat_miduser{i}.err", background=True)
    with play_on(pattern_hosts=_STRATIFIED_PROVIDER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_provider.py --unsat  -n {_COMPONENT} -inventory {project_dir}stratified_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}stratified_unsat_provider.log 2>> {result_dir}{ite}stratified_unsat_provider.err", background=True)
    with play_on(pattern_hosts=_STRATIFIED_USER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_end_user.py --unsat -n {_COMPONENT} -inventory {project_dir}stratified_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}stratified_unsat_user.log 2>> {result_dir}{ite}stratified_unsat_user.err")
    #get result
    for i in range(_COMPONENT):
        with play_on(pattern_hosts=_STRATIFIED_MIDUSER+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}stratified_sat_miduser{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}stratified_unsat_miduser{i}.log", dest="~")
            # p.shell(f"rm {project_dir}run_miduser.py ")
    with play_on(pattern_hosts=_STRATIFIED_PROVIDER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}stratified_sat_provider.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}stratified_unsat_provider.log", dest="~")
        # p.shell(f"rm {project_dir}run_provider.py")
    with play_on(pattern_hosts=_STRATIFIED_USER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}stratified_sat_user.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}stratified_unsat_user.log", dest="~")
        # p.shell(f"rm {project_dir}run_end_user.py")

if __name__ == "__main__":
    timestamp="2"
    result_dir = f"/tmp/{timestamp}/"
    roles, networks = book(site="nancy", cluster="gros")
    with play_on(pattern_hosts=_BALLET, roles=roles, run_as=username) as p:
        p.shell(f"mkdir -p {result_dir}")
    for scenario in _SCENARIOS:
        for ite in range(_NEXPE):    
            try:
                run(scenario, roles, ite, result_dir)
            except:
                print(f"{scenario}({ite}) FAILED !")