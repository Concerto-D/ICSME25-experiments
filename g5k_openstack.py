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

_NWORKER = 1    
_NEXPE = 15
_DEFAULT_TIME = "04:00:00"
_DEFAULT_START = "now"


_PORT = 40001


# -------------
#  ROLES
# -------------
_BALLET = "ballet"

_MASTER = "master"
_WORKER_MDB = "worker"
_WORKER_NEUTRON = "wneutron"
_WORKER_NOVA = "wnova"

def book(site, cluster, time=_DEFAULT_TIME, start=_DEFAULT_START):
    my_network = G5kNetworkConf(id="my_galera_network", type="prod", roles=["my_network"], site=site)
    if start != "now":
        g5k = G5kConf.from_settings(job_type="allow_classic_ssh", job_name=f"openstack_ballet", walltime=time, reservation=start)
    else:
        g5k = G5kConf.from_settings(job_type="allow_classic_ssh", job_name=f"openstack_ballet", walltime=time)
    g5k.add_network_conf(my_network)
    # Machine 1: cuser_user; cprovider_provider; linear_provider; circular_provider; stratified_provider
    g5k.add_machine(roles=[_BALLET, _MASTER],
                    cluster=cluster, nodes=1, primary_network=my_network)
    # Machine | i ∈ [0;_COMPONENT[ : cuser_provider_i; cprovider_user_i; linear_transformer_i; circular_transformer_i; stratified_miduser_i
    for i in range(_NWORKER):
        g5k.add_machine(roles=[_BALLET, _WORKER_MDB, _WORKER_MDB+str(i)], cluster=cluster, nodes=1, primary_network=my_network)
        g5k.add_machine(roles=[_BALLET, _WORKER_NEUTRON, _WORKER_NEUTRON+str(i)], cluster=cluster, nodes=1, primary_network=my_network)
        g5k.add_machine(roles=[_BALLET, _WORKER_NOVA, _WORKER_NOVA+str(i)], cluster=cluster, nodes=1, primary_network=my_network)
    conf = g5k.finalize()
    provider = G5k(conf)
    roles, networks = provider.init()
    return roles, networks

def make_inventory_content(roles):
    inventory = {}
    # MASTER COMPONENTS
    master_address = roles[_MASTER][0].address
    inventory['mariadbmaster'] =  {'address': master_address, 'port_planner': _PORT}
    inventory['commonmaster'] =  {'address': master_address, 'port_planner': _PORT}
    inventory['haproxymaster'] =  {'address': master_address, 'port_planner': _PORT}
    inventory['memcachedmaster'] =  {'address': master_address, 'port_planner': _PORT}
    inventory['ovswitchmaster'] =  {'address': master_address, 'port_planner': _PORT}
    inventory['rabbitmqmaster'] =  {'address': master_address, 'port_planner': _PORT}
    inventory['factsmaster'] =  {'address': master_address, 'port_planner': _PORT}
    for wid in range(_NWORKER):
        # WORKER MDB COMPONENTS
        worker_mdb_address = roles[_WORKER_MDB+str(wid)][0].address
        inventory[f'mariadbworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT}
        inventory[f'commonworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT}
        inventory[f'haproxyworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT}
        inventory[f'memcachedworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT}
        inventory[f'ovswitchworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT}
        inventory[f'rabbitmqworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT}
        inventory[f'factsworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT} 
        inventory[f'keystoneworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT} 
        inventory[f'glanceworker{wid}'] =  {'address': worker_mdb_address, 'port_planner': _PORT} 
        # WORKER NEUTRON COMPONENT
        worker_neutron_address = roles[_WORKER_NEUTRON+str(wid)][0].address
        inventory[f'neutronworker{wid}'] = {'address': worker_neutron_address, 'port_planner': _PORT} 
        # WORKER NOVA COMPONENT
        worker_nova_address = roles[_WORKER_NOVA+str(wid)][0].address
        inventory[f'novaworker{wid}'] = {'address': worker_nova_address, 'port_planner': _PORT} 
    return inventory

def inventory_format_json(data):
    addresses = []
    for comp in data.keys():
        address = data[comp]["address"]
        port = data[comp]["port_planner"]
        addresses.append(f"\"{comp}\": {{\"address\": \"{address}\", \"port_planner\": {port}}}")
    return "{"+', '.join(addresses)+"}"

def make_inventory(roles):
    print(f"LET'S MAKE AN INVENTORY FOR openstack SCENARIO")
    data = make_inventory_content(roles)
    content = inventory_format_json(data)
    print(f"Inventory for openstack") 
    print(data) 
    filename = f"{project_dir}openstack_inventory.json"
    with play_on(pattern_hosts=_BALLET, roles=roles, run_as=username) as p:
        p.shell("echo '" + content + "' > " + filename )

def run(roles, ite, result_dir):
    make_inventory(roles)
    #1 Copy right python file
    script_place = f"{project_dir}examples/tests_gossip/version_openstack/"
    for i in range(_NWORKER):
        with play_on(pattern_hosts=_WORKER_MDB+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_worker_mariadb.py {project_dir}")
        with play_on(pattern_hosts=_WORKER_NEUTRON+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_worker_neutron.py {project_dir}")
        with play_on(pattern_hosts=_WORKER_NOVA+str(i), roles=roles, run_as=username) as p:
            p.shell(f"cp {script_place}run_worker_nova.py {project_dir}")
    with play_on(pattern_hosts=_MASTER, roles=roles, run_as=username) as p:
        p.shell(f"cp {script_place}run_master.py {project_dir}")
    #2.1 run SAT     
    for i in range(_NWORKER):
        with play_on(pattern_hosts=_WORKER_MDB+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_worker_mariadb.py -worker {_NWORKER} -i {i} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_sat_wmdb{i}.log 2>> {result_dir}{ite}openstack_sat_wmdb{i}.err", background=True)
        with play_on(pattern_hosts=_WORKER_NEUTRON+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_worker_neutron.py -worker {_NWORKER} -i {i} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_sat_wneutron{i}.log 2>> {result_dir}{ite}openstack_sat_wneutron{i}.err", background=True)
        with play_on(pattern_hosts=_WORKER_NOVA+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_worker_nova.py -worker {_NWORKER} -i {i} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_sat_wnova{i}.log 2>> {result_dir}{ite}openstack_sat_wnova{i}.err", background=True)
    with play_on(pattern_hosts=_MASTER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_master.py -worker {_NWORKER} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_sat_master.log 2>> {result_dir}{ite}openstack_sat_master.err")
    #2.2 run UNSAT
    for i in range(_NWORKER):
        with play_on(pattern_hosts=_WORKER_MDB+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_worker_mariadb.py --unsat -worker {_NWORKER} -i {i} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_unsat_wmdb{i}.log 2>> {result_dir}{ite}openstack_unsat_wmdb{i}.err", background=True)
        with play_on(pattern_hosts=_WORKER_NEUTRON+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_worker_neutron.py --unsat -worker {_NWORKER} -i {i} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_unsat_wneutron{i}.log 2>> {result_dir}{ite}openstack_unsat_wneutron{i}.err", background=True)
        with play_on(pattern_hosts=_WORKER_NOVA+str(i), roles=roles, run_as=username) as p:
            p.shell(f"{minizinc_path()}; python {project_dir}run_worker_nova.py --unsat -worker {_NWORKER} -i {i} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_unsat_wnova{i}.log 2>> {result_dir}{ite}openstack_unsat_wnova{i}.err", background=True)
    with play_on(pattern_hosts=_MASTER, roles=roles, run_as=username) as p:
        p.shell(f"{minizinc_path()}; python {project_dir}run_master.py --unsat -worker {_NWORKER} -inventory {project_dir}openstack_inventory.json --time -it {ite} -port {_PORT} >> {result_dir}{ite}openstack_unsat_master.log 2>> {result_dir}{ite}openstack_unsat_master.err")
    #get results
    for i in range(_NWORKER):
        with play_on(pattern_hosts=_WORKER_MDB+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}openstack_sat_wmdb{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}openstack_unsat_wmdb{i}.log", dest="~")
            p.shell(f"rm {project_dir}run_worker_mariadb.py ")
        with play_on(pattern_hosts=_WORKER_NEUTRON+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}openstack_sat_wneutron{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}openstack_unsat_wneutron{i}.log", dest="~")
            p.shell(f"rm {project_dir}run_worker_neutron.py ")
        with play_on(pattern_hosts=_WORKER_NOVA+str(i), roles=roles, run_as=username) as p:
            p.fetch(src=f"{result_dir}{ite}openstack_sat_wnova{i}.log", dest="~")
            p.fetch(src=f"{result_dir}{ite}openstack_unsat_wnova{i}.log", dest="~")
            p.shell(f"rm {project_dir}run_worker_nova.py ")
    with play_on(pattern_hosts=_MASTER, roles=roles, run_as=username) as p:
        p.fetch(src=f"{result_dir}{ite}openstack_sat_master.log", dest="~")
        p.fetch(src=f"{result_dir}{ite}openstack_unsat_master.log", dest="~")
        p.shell(f"rm {project_dir}run_master.py ")

if __name__ == "__main__":
    timestamp="2"
    result_dir = f"/tmp/{timestamp}/"
    roles, networks = book(site="nancy", cluster="gros")
    with play_on(pattern_hosts=_BALLET, roles=roles, run_as=username) as p:
        p.shell(f"mkdir -p {result_dir}")
    for ite in range(_NEXPE):    
        try:
            run(roles, ite, result_dir)
        except:
            print(f"Openstack ({ite}) FAILED !")