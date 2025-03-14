import csv
import math

FILES = ["cuser/cuser_sat.log","cuser/cuser_unsat.log",
         "cprovider/cprovider_sat.log", "cprovider/cprovider_unsat.log", 
         "linear/linear_sat.log", "linear/linear_unsat.log", 
         "circular/circular_sat.log", "circular/circular_unsat.log", 
         "stratified/stratified_sat.log", "stratified/stratified_unsat.log",
         "openstack/openstack_sat.log", "openstack/openstack_unsat.log"
         ]

class Entry:

    def __init__(self, id, key, iteration , value):
        self.id = id
        self.key = key
        self.iteration = int(iteration)  # Convert iteration to integer
        self.value = float(value) if '.' in value else int(value) 


def load_results(files):
    res = {}
    for file in files:
        res[file] = load_result(file)
    return res


def load_result(file_log):
    entries = []
    with open(file_log, "r", newline="") as file:
        reader = csv.reader(file, delimiter="|")
        next(reader, None)  # Skip the header
        for row in reader:
            entries.append(Entry(row[0], row[1], row[2], row[3]))
    return entries


def build_analysis(input):
    results = {}
    for (filename, entries) in input.items():
        results[filename] = {}
        res = results[filename]
        finest_analysis(entries, filename) 
        for entry in entries:
            if entry.iteration not in res.keys():
                res[entry.iteration] = []
            if "node_" in entry.id:
                if entry.key == "total_time":
                    res[entry.iteration].append((entry.id, entry.value) )
               
    for file in results.keys():
        max_entries = []
        for iteration in results[file].keys():
            max_entry = max(results[file][iteration], key=lambda x: x[1])
            max_entries.append(max_entry[1])
            # print(f"On itration {iteration} of {file} -> Maximum value: {max_entry[1]}, found at: {max_entry[0]}")
        average = sum(max_entries) / len(max_entries) if max_entries else 0
        variance = sum((x - average) ** 2 for x in max_entries) / len(max_entries) if max_entries else 0
        std_deviation = math.sqrt(variance)
        print(f"Average time for {file} is {average} sec (V={variance}, σ={std_deviation})") 


def finest_analysis(input,filename):
    maxeffort = ""
    results = {}
    # iteration -> node -> list of solving time
    for entry in input:
        if entry.iteration not in results.keys():
            results[entry.iteration] = {}
        if "node_" not in entry.id:
            if entry.id not in results[entry.iteration].keys():
                results[entry.iteration][entry.id] = []
            if entry.key in ["flocal", "ffinal", "funsat"]:
                results[entry.iteration][entry.id].append(entry.value)
    niteration = 0
    maximums = []
    for iteration in results.keys():
        niteration += 1
        max = 0
        for component in results[iteration].keys():
            tt = sum(results[iteration][component])
            if tt > max:
                max = tt
                maxeffort = component
        maximums.append(max)
    print(f"in average, the maximum local solving time in {filename} is for {maxeffort} (chuffed + qx): ", sum(maximums) / niteration)
    

if __name__ == "__main__":
    results = load_results(FILES)
    build_analysis(results)