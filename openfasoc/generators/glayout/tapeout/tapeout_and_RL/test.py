from sky130_nist_tapeout import *
from glayout.flow.pdk.sky130_mapped import sky130_mapped_pdk as sky130
import os, sys
sys.path.append(os.path.join(os.path.abspath(__file__), "..", ".."))
from glayout.flow.blocks.diff_pair import diff_pair
from gdsfactory.component import Component
from subprocess import Popen, PIPE
from glayout.flow.blocks.current_mirror import current_mirror
import shutil 

import multiprocessing as mp
cpu_count = mp.cpu_count() 

if len(os.sched_getaffinity(0)) < cpu_count:
    try:
        os.sched_setaffinity(0, range(cpu_count))
    except OSError:
        print('Could not set affinity')
        
def custom_run( 
    comp_name: str,
    params, 
    index: int, 
    temperature_info: tuple[int,str]=(25,"normal model"),
    cload: float=0.0,
    noparasitics: bool=False,
    hardfail: bool=False, 
    tmpdirname: Optional[Union[str,Path]]=None,
    prepex: bool=False, 
    comp: Optional[Component]=None
):
    if os.path.exists(str(tmpdirname / f"{comp_name}_pex.spice")):
        return
    global pdk
    global PDK_ROOT
    # if not tmpdirname.is_dir():
    #     tmpdirname.mkdir(parents=True, exist_ok=True)
    # dest_gds_copy = save_gds_dir / (str(index)+".gds")
    sky130pdk = pdk 
    
    if comp_name == "diffpair":
        new_params = diff_pair_parameters_de_serializer(params)
        component = sky130_add_diffpair_labels(diff_pair(sky130, **new_params))
    elif comp_name == "opamp":
        new_params = opamp_parameters_de_serializer(params)
        component = sky130_add_opamp_labels(opamp(sky130, **new_params))
    else:
        component = sky130_add_currmirror_labels(current_mirror(sky130, **params))
    component.name = comp_name + str(index)
    area = float(component.area())
    
    # tmpdirname = Path(__file__).parent.resolve() / f"{comp_name}_run"
    tmp_gds_path = Path(tmpdirname / f"{comp_name}.gds").resolve()
    
    component.write_gds(str(tmp_gds_path))
    # if tmp_gds_path.is_file():
    #     dest_gds_copy.write_bytes(tmp_gds_path.read_bytes())
    
    extract_bash_template = str()
    with open("extract.bash.template", "r") as extraction_script:
        extract_bash_template = extraction_script.read()
        extract_bash_template = extract_bash_template.replace("@@PDK_ROOT", PDK_ROOT).replace("@@@PAROPT", "noparasitics" if noparasitics else "na").replace("@@@PREPEX", "yes" if prepex else "no")
    
    with open(str(tmpdirname)+"/extract.bash", "w") as extraction_script:
        extraction_script.write(extract_bash_template)
    
    copyfile(f"{comp_name}_perf_eval.sp", str(tmpdirname / f"{comp_name}_perf_eval.sp"))
    copytree("sky130A", str(tmpdirname / "sky130A"), dirs_exist_ok=True)
    
def extract_mid(tmp_gds_path, comp_name, tmpdirname, params, index, temperature_info, cload, noparasitics, area):
    # if os.path.exists(str(tmpdirname / f"{comp_name}{index}_pex.spice")):
    #     pass
    # else: 
    #     return
    # if os.path.exists(str(tmpdirname / f"{comp_name}_pex.spice")):
    #     return
    # import pdb; pdb.set_trace()
    try:
        # Popen(["bash", "extract.bash", tmp_gds_path, comp_name + str(index)], cwd=tmpdirname).wait(timeout=750)
        # copyfile(f"{comp_name}_perf_eval.sp", str(tmpdirname / f"{comp_name}_perf_eval.sp"))
        copyfile(f"{comp_name}_perf_eval.sp", str(tmpdirname / f"{comp_name}_perf_eval.sp"))
        print(f"Running simulation at temperature: {temperature_info[0]}C")
        
        process_spice_testbench(str(tmpdirname / f"{comp_name}_perf_eval.sp"), temperature_info=temperature_info)
        
        if os.path.exists(str(tmpdirname / f"{comp_name}{index}_pex.spice")):
            with open(str(tmpdirname / f"{comp_name}_perf_eval.sp"), "r") as f:
                template = f.read()
                template = template.replace("@@NUM", str(index))
        else:  
            with open(str(tmpdirname / f"{comp_name}_perf_eval.sp"), "r") as f:
                template = f.read()
                template = template.replace("@@NUM", "")
            
        with open(str(tmpdirname / f"{comp_name}_perf_eval.sp"), "w") as f:
            f.write(template)
            
        if comp_name == "opamp":
            process_netlist_subckt(str(tmpdirname / f"{comp_name}_pex.spice"), temperature_info[1], cload=cload, noparasitics=noparasitics)
        
        # rename(str(tmpdirname / f"{comp_name}_pex.spice"), str(tmpdirname / f"{comp_name}_pex.spice"))
    except:
        pass

def run_subproc(tmp_gds_path, comp_name, tmpdirname, params, index, temperature_info, cload, noparasitics, area):
    # if os.path.exists(str(tmpdirname / f"result_ac.txt")):
    #     return
    try:
        
        Popen(["ngspice", "-b", f"{comp_name}_perf_eval.sp"], cwd=tmpdirname).wait(timeout=750)
        
        ac_file = tmpdirname / "result_ac.txt"
        ac_flag = 1 if ac_file.is_file() else 0
        power_file = tmpdirname / "result_power.txt"
        power_flag = 1 if power_file.is_file() else 0
        noise_file = tmpdirname / "result_noise.txt"
        noise_flag = 1 if noise_file.is_file() else 0
        
        result_dict = get_sim_results(ac_file, power_file, noise_file)
        result_dict["area"] = area
        
        if comp_name == "diffpair":
            results = diff_pair_results_serializer(**result_dict)
        elif comp_name == "opamp":
            results = opamp_results_serializer(**result_dict)
        else:
            results = currmirror_results_serializer(**result_dict)
        print(f'\n\n******* RESULTS ********: {results}\n\n')
        
        with open('output.txt', 'w') as f:
            f.write(f"Results for {comp_name} run {index} with the following params: \n{params}")
            f.write(f"\n\n******* RESULTS ********: \n{results}\n\n")

        shutil.rmtree(str(tmpdirname) + "sky130A")
        # delete the above extra files with shutil
        delete_files = [".ext", ".nodes", ".res.ext", ".sim"]
        for file in delete_files:
            if os.path.exists(str(tmpdirname) + f"/*{file}"):
                os.remove(str(tmpdirname) + f"/*{file}")
                
        # if output_dir is not None:
        #     if isinstance(output_dir, int):
        #         output_dir = save_gds_dir / f"dir_{output_dir}"
        #         output_dir = Path(output_dir).resolve()
        #     else:
        #         output_dir = Path(output_dir).resolve()
            
        #     output_dir.mkdir(parents=True, exist_ok=True)
            
        #     if not output_dir.is_dir():
        #         raise ValueError("Output directory must be a directory")
            
        #     copytree(str(tmpdirname), str(output_dir / "test_output"), dirs_exist_ok=True)
        
    except:
        if comp_name == "diffpair":
            results = diff_pair_results_serializer()
        elif comp_name == "opamp":
            results = opamp_results_serializer()
        else:
            results = currmirror_results_serializer()
        with open('get_training_data_ERRORS.log', 'a') as errlog:
            errlog.write(f"\n{comp_name} run {index} with the following params failed: \n{params}")

def extract_only(comp_name, params, tmpdirname: Path, noparasitics: bool=False, prepex: bool=False):
    if not tmpdirname.is_dir():
        tmpdirname.mkdir(parents=True, exist_ok=True)
    # currmirror_v = sky130_add_currmirror_labels(current_mirror(sky130, numcols = numcols))
    # currmirror_v.name = f"currmirror_{numcols}"
    if comp_name == "diffpair":
        component = sky130_add_diffpair_labels(diff_pair(sky130, **params))
    elif comp_name == "opamp":
        component = sky130_add_opamp_labels(sky130_add_lvt_layer(opamp(sky130, **params)))
    else:
        component = sky130_add_currmirror_labels(current_mirror(sky130, **params))
    component.name = comp_name
    area = float(component.area())
    tmp_gds_path = Path(f"./{comp_name}_run/{comp_name}.gds").resolve()
    component.write_gds(tmp_gds_path)
    with open("extract.bash.template","r") as extraction_script:
        extractbash_template = extraction_script.read()
        extractbash_template = extractbash_template.replace("@@PDK_ROOT",PDK_ROOT).replace("@@@PAROPT","noparasitics" if noparasitics else "na").replace("@@@PREPEX", "yes" if prepex else "no")
    with open(str(tmpdirname)+"/extract.bash","w") as extraction_script:
        extraction_script.write(extractbash_template)
    #copyfile("extract.bash",str(tmpdirname)+"/extract.bash")
    copyfile(f"{comp_name}_perf_eval.sp",str(tmpdirname)+f"/{comp_name}_perf_eval.sp")
    copytree("sky130A",str(tmpdirname)+"/sky130A", dirs_exist_ok=True)
    # extract layout
    Popen(["bash","extract.bash", tmp_gds_path, component.name],cwd=tmpdirname).wait()
    
    shutil.rmtree(str(tmpdirname) + "/sky130A")
    # delete the above extra files with shutil
    delete_files = [".ext", ".nodes", ".res.ext", ".sim"]
    for file in delete_files:
        if os.path.exists(str(tmpdirname) + f"/*{file}"):
            os.remove(str(tmpdirname) + f"/*{file}")  


def small_parameters_list(test_mode = False, clarge=False) -> np.array:
    """creates small parameter list intended for brute force"""
    # all diffpairs to try
    diffpairs = list()
    if test_mode:
        diffpairs.append((6,1,4))
        diffpairs.append((5,1,4))
    else:
        for width in [2,10]:
            for length in [0.5, 1]:
                for fingers in [2,8]:
                    diffpairs.append((width,length,fingers))
    # all bias2 (output amp bias) transistors
    bias2s = list()
    if test_mode:
        bias2s.append((6,1,4,3))
    else:
        for width in [6]:
            for length in [1, 2]:
                for fingers in [4, 3]:
                    for mults in [6]:
                        bias2s.append((width,length,fingers,mults))
    # all pmos first stage load transistors
    half_pload = list()
    if test_mode:
        half_pload.append((6,1,6))
    else:
        for width in [6]:
            for length in [1]:
                for fingers in [8]:
                    half_pload.append((width,length,fingers))
    # all output pmos transistors
    pamp_hparams = list()
    if test_mode:
        pamp_hparams.append((7,1,8,3))
    else:
        for width in [7]:
            for length in [0.5,1]:
                for fingers in [8,2]:
                    pamp_hparams.append((width,length,fingers,3))
    # diffpair bias cmirror
    diffpair_cmirrors = list()
    if test_mode:
        pass
    else:
        for width in [6]:
            for length in [2]:
                for fingers in [3]:
                    diffpair_cmirrors.append((width,length,fingers))
    # rows of the cap array to try
    cap_arrays = [3]
    # routing mults to try
    rmults = [2]
    # ******************************************
    # create and return the small parameters list
    short_list_len = len(diffpairs) * len(bias2s) * len(pamp_hparams) * len(cap_arrays) * len(rmults) * len(diffpair_cmirrors) * len(half_pload)
    short_list_len += 2 if test_mode else 0
    short_list = np.empty(shape=(short_list_len,len(opamp_parameters_serializer())),dtype=np.float64)
    index = 0
    for diffpair_v in diffpairs:
        for bias2_v in bias2s:
            for pamp_o_v in pamp_hparams:
                for cap_array_v in cap_arrays:
                    for rmult in rmults:
                        for diffpair_cmirror_v in diffpair_cmirrors:
                            for halfpld in half_pload:
                                tup_to_add = opamp_parameters_serializer(
                                    half_pload=halfpld,
                                    half_diffpair_params=diffpair_v,
                                    half_common_source_bias=bias2_v,
                                    mim_cap_rows=cap_array_v,
                                    half_common_source_params=pamp_o_v,
                                    rmult=rmult,
                                    diffpair_bias=diffpair_cmirror_v,
                                )
                                short_list[index] = tup_to_add
                                index = index + 1
    # if test_mode create a failed attempt (to test error handling)
    if test_mode:
        short_list[index] = opamp_parameters_serializer(mim_cap_rows=-1)
        short_list[index+1] = opamp_parameters_serializer(mim_cap_rows=0)
    # global _GET_PARAM_SET_LENGTH_
    # if _GET_PARAM_SET_LENGTH_:
    #     print("created parameter set of length: "+str(len(short_list)))
    #     import sys
    #     sys.exit()
    return short_list
import multiprocessing 


def generate(params, comp_name):
    new_params = opamp_parameters_de_serializer(params)
    comp = sky130_add_opamp_labels(sky130_add_lvt_layer(opamp(sky130, **new_params)))
    comp.name = comp_name
    return comp

if __name__ == "__main__":
    
    # extract_only(heredir)
    # parse arguments 
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", type=str, help="component to run", required=True, choices=["diffpair","opamp","currmirror"])
    
    if sys.argv[-1] == "diffpair":
        heredir = Path(__file__).parent.resolve() / "diffpair_run" / "nets"
        params = get_diffpair_params_list(test_mode=False)
        # params = diff_pair_parameters_de_serializer(diff_pair_parameters_serializer())
        comp_name = "diffpair"
        index = 0
        
        
    elif sys.argv[-1] == "currmirror":
        
        heredir = Path(__file__).parent.resolve() / "currmirror_run" / "nets"
        params = currmirror_parameters_de_serializer(currmirror_parameters_serializer())
        comp_name = "currmirror"
        index = 0

        # extract_only(tmpdirname=heredir, noparasitics=False)
        
    elif sys.argv[-1] == "opamp":
        heredir = Path(__file__).parent.resolve() / "opamp_run" / "nets"

        params = get_small_parameter_list()
        # params = small_parameters_list(test_mode=False)
        # params = opamp_parameters_serializer()
        print(params)
        comp_name = "opamp"
        index = 0
    
    n = len(os.sched_getaffinity(0))
    print('Using', n, 'processes for the pool')
    dir1 = heredir / "postpex"
    dir2 = heredir / "prepex"
    dir1.mkdir(parents=True, exist_ok=True)
    dir2.mkdir(parents=True, exist_ok=True)
    
    
    # custom_run(comp_name, params, index, (25, "normal_mode"), 0.0, False, False, Path(dir1 / f"run_{index}"), True)
    # opamps = []
    # with Pool(n-1) as cores:
    #     cores.starmap(custom_run, [(comp_name, params[i], i, (25, "normal_mode"), 0.0, False, False, Path(dir1 / f"run_{i}"), False) for i in range(len(params))])
        
    # with Pool(n-1) as cores:
    #     cores.starmap(custom_run, [(comp_name, params[i], i, (25, "normal_mode"), 0.0, False, False, Path(dir2 / f"run_{i}"), True) for i in range(len(params))])
    
    # index = 704
    # extract_mid(Path(dir1 / f"run_{index}/{comp_name}.gds"), comp_name, Path(dir1 / f"run_{index}"), params[index], index, (25, "normal_mode"), 0.0, False, 0.0)
    with Pool(n-1) as cores:
        cores.starmap(extract_mid, [(Path(dir1 / f"run_{i}/{comp_name}.gds"), comp_name, Path(dir1 / f"run_{i}"), params[i], i, (25, "normal_mode"), 0.0, False, 0.0) for i in range(len(params))])
        
    with Pool(n-1) as cores:
        cores.starmap(extract_mid, [(Path(dir2 / f"run_{i}/{comp_name}.gds"), comp_name, Path(dir2 / f"run_{i}"), params[i], i, (25, "normal_mode"), 0.0, False, 0.0) for i in range(len(params))])
        
    # with Pool(n-1) as cores: 
    #     cores.starmap(run_subproc, [(Path(dir1 / f"run_{i}/{comp_name}.gds"), comp_name, Path(dir1 / f"run_{i}"), params[i], i, (25, "normal_mode"), 0.0, False, 0.0) for i in range(len(params))])
    
    # with Pool(n-1) as cores:
    #     cores.starmap(run_subproc, [(Path(dir2 / f"run_{i}/{comp_name}.gds"), comp_name, Path(dir2 / f"run_{i}"), params[i], i, (25, "normal_mode"), 0.0, False, 0.0) for i in range(len(params))])
    # for i in range(len(params)):
    #     run_subproc(str(dir1 / f"run_{i}/{comp_name}.gds"), comp_name, Path(dir1 / f"run_{i}"), params[i], i, (25, "normal_mode"), 0.0, False, 0.0)
    #     run_subproc(str(dir1 / f"run_{i}/{comp_name}.gds"), comp_name, Path(dir1 / f"run_{i}"), params[i], i, (25, "normal_mode"), 0.0, True, 0.0)
    # with Pool(n-1) as cores:
    #     # cores.starmap(extract_only, [(comp_name, params, heredir / f'run_{i}', False, True) for i in range(25)])
    #     cores.starmap(custom_run, [(comp_name, params[i], i, (25, "normal_mode"), 0.0, False, False, Path(dir1 / f"run_{i}"), False) for i in range(len(params))])
        
    # with Pool(n-1) as cores:
    #     cores.starmap(custom_run, [(comp_name, params[i], i, (25, "normal_mode"), 0.0, False, False, Path(dir2 / f"run_{i}"), True) for i in range(len(params))])
        
        
    # params = diff_pair_parameters_serializer()
    # __run_single_brtfrc(0, params, save_gds_dir=Path(__file__).parent.resolve() / "diffpair_run")
    