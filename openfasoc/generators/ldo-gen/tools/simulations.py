import math
import os
import re
import shutil
import sys
import subprocess as sp
import csv
import matplotlib.pyplot as plt
from cairosvg import svg2png
from PIL import Image
from pathlib import Path

# ------------------------------------------------------------------------------
# Create Sim Directories
# ------------------------------------------------------------------------------
def create_sim_dirs(arrSize, simDir, freq_list):
    """Creates and performs error checking on pre/post PEX sim directories"""
    os.makedirs(simDir + "/run", exist_ok=True)
    prePEX_sim_dir = simDir + "run/" + "prePEX_PT_cells_" + str(arrSize)
    postPEX_sim_dir = simDir + "run/" + "postPEX_PT_cells_" + str(arrSize)
    sim_dir_structure = dict()
    for freq in freq_list:
        sim_dir_structure[str(freq) + "Hz"] = freq
    try:
        os.mkdir(prePEX_sim_dir)
        os.mkdir(postPEX_sim_dir)
        for dir_name in sim_dir_structure:
            os.mkdir(postPEX_sim_dir + "/" + dir_name)
            os.mkdir(prePEX_sim_dir + "/" + dir_name)
    except OSError as error:
        print(error)
        print(
            'Already ran simulations for this design\nRun "make clean_sims" to clear ALL simulation runs OR manually delete run directories.\n'
        )
        exit(1)
    return [prePEX_sim_dir + "/", postPEX_sim_dir + "/", sim_dir_structure]


# ------------------------------------------------------------------------------
# Prepare the complete LDO design PEX and prePEX spice netlists
# ------------------------------------------------------------------------------
def matchNetlistCell(cell_instantiation, IfFound, remove_mode=True):
    """HELPER FUNCTION:
    returns true if the input contains as a pin (as a substring) one
    of the identified cells to remove for partial simulations"""
    if type(IfFound) is not list:
        raise TypeError(
            'Function matchNetlistCell requires a list "IfFound" of strings to match.'
        )
    # names may not be exactly the same, but as long as part of the name matches then consider true
    # naming will automatically include some portion of the standard cell of origin name in the pin name
    found_status = False
    for name in IfFound:
        for pin in cell_instantiation:
            if name in pin:
                found_status = True
                break
        if found_status:
            break
    # if tested all cells and none are true then found_status=false (set by default)
    # if remove_mode then return true for found else return false for found
    if remove_mode:
        return found_status
    else:
        return not found_status


def process_prePEX_netlist(rawSynthNetlistPath):
    """Comments out identified cells in matchNetlistCell and adds VREF/VREG to toplevel subckt def.
    Return string containing the netlist."""
    with open(rawSynthNetlistPath, "r") as spice_in:
        netlist = spice_in.read()
    # comment out identified cells
    cells_array = netlist.split("\n")
    for cell in cells_array:
        if cell != "":
            cellPinout = cell.split(" ")
            cell_commented = cell
        if matchNetlistCell(cellPinout, ["vref_gen_nmos_with_trim"]):
            cell_commented = "*" + cell
        netlist = netlist.replace(cell, cell_commented)
    # prepare toplevel subckt def (assumes VDD VSS last two in pin out)
    netlist = netlist.replace("VDD VSS", "VDD VSS VREF", 1)
    return netlist


def process_power_array_netlist(rawSynthNetlistPath):
    """Comments out everything except the power array and adjusts inputs to direct control power array.
    Return string containing the netlist."""
    with open(rawSynthNetlistPath, "r") as spice_in:
        power_spice_netlist = spice_in.read()
    removeIfNotFound = ["Xpt_array_unit", "INCLUDE", "ENDS"]
    cells_array = power_spice_netlist.split("\n")
    for cell in cells_array:
        if cell != "":
            cellPinout = cell.split(" ")
            cell_commented = cell
        if "SUBCKT" in cell:
            power_spice_netlist = power_spice_netlist.replace(
                cell, ".SUBCKT ldoInst VREG VDD VSS\n"
            )
            continue
        elif matchNetlistCell(cellPinout, removeIfNotFound, False):
            cell_commented = "*" + cell
        elif "ctrl1.ctrl_word" in cell:
            for pin in cellPinout:
                if "ctrl1.ctrl_word" in pin:
                    cell_commented = cell_commented.replace(pin, "VSS")
        power_spice_netlist = power_spice_netlist.replace(cell, cell_commented)
    return power_spice_netlist


def process_PEX_netlist(rawExtractedNetlistPath):
    """Prepare PEX netlist for simulations. Return string containing the netlist."""
    with open(rawExtractedNetlistPath, "r") as spice_in:
        netlist = spice_in.read()
    netlist = netlist.replace(
        "r_VREG clk cmp_out", "r_VREG capacitor_test_nf_4/pin0 clk cmp_out", 1
    )
    cells_array = netlist.split("\n")
    i = 0
    while i < len(cells_array):
        if (
            cells_array[i].startswith("C")
            and "vref_gen_nmos_with_trim_0" in cells_array[i]
        ):
            cells_array[i] = "*" + cells_array[i]
        elif "Xvref_gen_nmos_with_trim_0" in cells_array[i]:
            cells_array[i] = "*" + cells_array[i]
            i = i + 1
            while cells_array[i][0] == "+":
                cells_array[i] = "*" + cells_array[i]
                i = i + 1
        i = i + 1
    netlist = "\n".join(cells_array)
    return netlist


# ------------------------------------------------------------------------------
# Prepare Simulation Scripts (add function for each new sim tool)
# ------------------------------------------------------------------------------
prePEX_SPICE_HEADER_GLOBAL_V = """clk cmp_out ctrl_out[0] ctrl_out[1] ctrl_out[2] ctrl_out[3]
+ ctrl_out[4] ctrl_out[5] ctrl_out[6] ctrl_out[7] ctrl_out[8] mode_sel[0] mode_sel[1]
+ reset std_ctrl_in std_pt_in_cnt[0] std_pt_in_cnt[1] std_pt_in_cnt[2] std_pt_in_cnt[3]
+ std_pt_in_cnt[4] std_pt_in_cnt[5] std_pt_in_cnt[6] std_pt_in_cnt[7] std_pt_in_cnt[8]
+ trim1 trim10 trim2 trim3 trim4 trim5 trim6 trim7 trim8 trim9 VDD VSS VREF VREG"""
postPEX_SPICE_HEADER_GLOBAL_V = """VREG VREF clk cmp_out ctrl_out[0] ctrl_out[1] ctrl_out[2] ctrl_out[3]
+ ctrl_out[4] ctrl_out[5] ctrl_out[6] ctrl_out[7] ctrl_out[8] mode_sel[0] mode_sel[1]
+ reset std_ctrl_in std_pt_in_cnt[0] std_pt_in_cnt[1] std_pt_in_cnt[2] std_pt_in_cnt[3]
+ std_pt_in_cnt[4] std_pt_in_cnt[5] std_pt_in_cnt[6] std_pt_in_cnt[7] std_pt_in_cnt[8]
+ trim1 trim10 trim2 trim3 trim4 trim5 trim6 trim7 trim8 trim9 VSS VDD"""


def ngspice_prepare_scripts(
    cap_list,
    templateScriptDir,
    sim_dir,
    sim_dir_structure,
    user_specs,
    arrSize,
    pdk_path,
    model_corner,
    pex=True,
):
    """Specializes ngspice simulations and returns (string) bash to run all sims."""
    designName = user_specs["designName"]
    vref = user_specs["vin"]
    max_load = user_specs["imax"]
    model_file = pdk_path + "/libs.tech/ngspice/sky130.lib.spice"
    with open(templateScriptDir + "ldoInst_ngspice.sp", "r") as sim_spice:
        sim_template = sim_spice.read()
    sim_template = sim_template.replace("@model_file", model_file)
    sim_template = sim_template.replace("@model_corner", model_corner)
    sim_template = sim_template.replace("@design_nickname", designName)
    sim_template = sim_template.replace("@VALUE_REF_VOLTAGE", str(vref))
    sim_template = sim_template.replace("@Res_Value", str(1.2 * vref / max_load))
    if pex:
        sim_template = sim_template.replace(
            "@proper_pin_ordering", postPEX_SPICE_HEADER_GLOBAL_V
        )
    else:
        sim_template = sim_template.replace(
            "@proper_pin_ordering", prePEX_SPICE_HEADER_GLOBAL_V
        )
    # create list of scripts to run (wheretocopy, filename, stringdata, ngspicecommand)
    scripts_to_run = list()
    for freq_dir in sim_dir_structure:
        freq = sim_dir_structure[freq_dir]
        sim_script = sim_template
        sim_script = sim_script.replace("@clk_period", str(1 / freq))
        sim_script = sim_script.replace("@duty_cycle", str(0.5 / freq))
        sim_time = 1.2 * arrSize / freq
        sim_script = sim_script.replace("@sim_time", str(sim_time))
        sim_script = sim_script.replace("@sim_step", str(sim_time / 3000))
        for cap in cap_list:
            sim_script_f = sim_script.replace("@Cap_Value", str(cap))
            output_raw = str(cap) + "_" + "cap_output.raw"
            sim_script = sim_script.replace("@output_raw", str(output_raw))
            sim_name = "ldoInst_" + str(cap) + ".sp"
            scripts_to_run.append(
                tuple(
                    (
                        sim_dir + freq_dir,
                        sim_name,
                        sim_script_f,
                        "ngspice -b -o " + str(cap) + "_out.txt -i " + sim_name,
                    )
                )
            )
    # add power array script to the list
    with open(templateScriptDir + "/pwrarr_sweep_ngspice.sp", "r") as sim_spice:
        pwr_sim_template = sim_spice.read()
    pwr_sim_template = pwr_sim_template.replace("@model_corner", model_corner)
    pwr_sim_template = pwr_sim_template.replace("@VALUE_REF_VOLTAGE", str(vref))
    pwr_sim_template = pwr_sim_template.replace("@model_file", model_file)
    scripts_to_run.append(
        tuple(
            (
                sim_dir,
                "pwrarr.sp",
                pwr_sim_template,
                "ngspice -b -o pwrout.txt -i pwrarr.sp",
            )
        )
    )
    # write scripts to their respective locations and create simulation bash script
    run_scripts_bash = "#!/usr/bin/env bash\n"
    for script in scripts_to_run:
        with open(script[0] + "/" + script[1], "w") as scriptfile:
            scriptfile.write(script[2])
        run_scripts_bash = run_scripts_bash + "cd " + os.path.abspath(script[0]) + "\n"
        run_scripts_bash = run_scripts_bash + script[3] + "\n"
    return run_scripts_bash


# ------------------------------------------------------------------------------
# max current binary search (deprecated, instead use dc linear sweep)
# ------------------------------------------------------------------------------
def rtr_sim_data(fname):
    """Read Id and VREG from sim output file."""
    with open(fname, "r") as result:
        entire_result = result.readlines()
    rtr_I = None
    rtr_VREG = None
    for line in entire_result:
        if "vreg" in line[0:6]:
            for num in line.split():
                try:
                    rtr_VREG = float(num)
                # Only the last word is a float
                except ValueError:
                    pass
        if "id" in line[0:4]:
            for num in line.split():
                try:
                    rtr_I = float(num)
                # Only the last word is a float
                except ValueError:
                    pass
        if rtr_I is not None and rtr_VREG is not None:
            break
    # final error check
    if rtr_I is None or rtr_VREG is None:
        raise ValueError("rtr_sim_data did not find VREG or id in sim output.")
    return rtr_VREG, rtr_I


def run_power_array_sim(run_dir, output_resistance, simTool="ngspice"):
    """Specializes sim template and solves for power array value."""
    if simTool != "ngspice":
        print("run_power_array_sim only supports ngspice. Exiting now.")
        exit(1)
    with open(
        run_dir + "power_array_template_" + simTool + ".sp", "r"
    ) as pwr_array_sim_template:
        specialized_pwr_array_sim = pwr_array_sim_template.read()
    specialized_pwr_array_sim = specialized_pwr_array_sim.replace(
        "@OUTPUT_RESISTANCE", str(output_resistance)
    )
    with open(run_dir + "power_array.sp", "w") as pwr_array_sim:
        pwr_array_sim.write(specialized_pwr_array_sim)
    with open(run_dir + "discard_banner.txt", "w") as discard_banner:
        sp.Popen(
            ["ngspice", "-b", "-o", "load_result.txt", "power_array.sp"],
            cwd=run_dir,
            stdout=discard_banner,
        ).wait()
    return rtr_sim_data(run_dir + "load_result.txt")


# 												  -> stop solving <-
# R=very small----{R is s.t. VREG=VREF-2*max_error}----------------{R is s.t. VREG=VREF-max_error}---{R is s.t. VREG=VREF}----R=very big
def binary_search_max_load(run_dir, VREF):
    """Starts with estimated output resistance range 1-100000 Ohms,
    then performs binary search to find the max load current supported
    with VREG maintained within max_error bounds.
    Smaller max_error results in increase in run time,
    you can configure this within the function
    This functions return a float (result)"""
    max_error = 0.001  # Volts
    range_min = float(1)
    range_max = float(100000)
    # TODO: add min and max range checking
    target_min = VREF - 2 * max_error
    target_max = VREF - max_error
    # check that max and min are actually bounds to our range
    # loop and divide search space by 2 on each iteration
    # perform no more than 1000 iterations
    for i in range(1, 1000):
        r_mid_value = (range_max + range_min) / 2
        print("Run load simulation, Rout = " + str(r_mid_value) + " Ohms.")
        VREG_result, i_load_result = run_power_array_sim(run_dir, r_mid_value)
        if target_min < VREG_result and target_max > VREG_result:
            return i_load_result
        elif VREG_result > target_max:
            range_max = r_mid_value
        elif VREG_result < target_min:
            range_min = r_mid_value
        else:
            raise RuntimeError(
                "function binary_search_current_at_acceptible_error failed to compare next step on the "
                + str(i)
                + " iteration."
            )
    # if the for loop is finished, then a solution has not been reached
    raise RuntimeError(
        "function binary_search_current_at_acceptible_error failed to solve in 1000 iterations."
    )


# ------------------------------------------------------------------------------
# Process simulation results
# ------------------------------------------------------------------------------
def save_sim_plot(run_dir, workDir):
    """Copy postscript sim outputs and convert into PNG."""
    svg2png(
        url=run_dir + "currentplot.svg",
        write_to=workDir + "currentplot.png",
    )
    svg2png(url=run_dir + "vregplot.svg", write_to=workDir + "vregplot.png")
