import sys
import os
from pathlib import Path
import pandas as pd
from sky130_nist_tapeout import get_sim_results
def extract_metrics(base_path):
    results = []
    for run_path in base_path.iterdir():
        if run_path.is_dir() and run_path.name.startswith("run_"):
            ac_path = run_path / "result_ac.txt"
            noise_path = run_path / "result_noise.txt"
            dc_path = run_path / "result_power.txt"
            
            # try:
            #     with open(ac_path, "r") as file:
            #         ac_data = file.readlines()[0].split()
            #         ac_metrics = {
            #             "BiasCurr": float(ac_data[1]) if len(ac_data) >= 12 else float('nan'),
            #             "bw_3db": float(ac_data[-3]) if len(ac_data) >= 12 else float('nan'),
            #             "cmrr": float(ac_data[9]) if len(ac_data) >= 12 else float('nan'),
            #             "common_mode_gain": float(ac_data[7]) if len(ac_data) >= 12 else float('nan'),
            #             "diff_mode_gain": float(ac_data[5]) if len(ac_data) >= 12 else float('nan'), 
            #             "Bias Resistance": float (ac_data[-1]) if len(ac_data) >= 12 else float('nan')
            #         }
            # except FileNotFoundError:
            #     ac_metrics = {"BiasCurr": float('nan'), "bw_3db": float('nan'), "cmrr": float('nan'), "common_mode_gain": float('nan'), "diff_mode_gain": float('nan')}
            
            # try:
            #     with open(dc_path, "r") as file:
            #         dc_data = file.readlines()[0].split()
            #         dc_metrics = {"power": float(dc_data[1]) if len(dc_data) >= 2 else float('nan')}
            # except FileNotFoundError:
            #     dc_metrics = {"power": float('nan')}
                
            # try:
            #     with open(noise_path, "r") as file:
            #         noise_data = file.readlines()[0].split()
            #         noise_metrics = {"noise": float(noise_data[1]) if len(noise_data) >= 2 else float('nan')}
            # except FileNotFoundError:
            #     noise_metrics = {"noise": float('nan')}
            
            # # Merge all dictionaries
            # run_metrics = {**ac_metrics, **dc_metrics, **noise_metrics}
            run_metrics = get_sim_results(acpath=ac_path, dcpath=dc_path, noisepath=noise_path)
            run_metrics['run'] = run_path.name
            results.append(run_metrics)
    
    return pd.DataFrame(results)

def main():
    project_dir = Path(__file__).parent / "opamp_run" 
    pre_pex_dir = project_dir / "nets" / "prepex" 
    # post_pex_dir = project_dir / "nets" / "postpex" 
    
    pre_pex_df = extract_metrics(pre_pex_dir)
    # post_pex_df = extract_metrics(post_pex_dir)
    
    # Writing to Excel with separate sheets
    with pd.ExcelWriter(project_dir / 'opamp_pex_results.xlsx', engine='xlsxwriter') as writer:
        pre_pex_df.to_excel(writer, sheet_name='PrePEX', index=False, float_format="%.10f")
        # post_pex_df.to_excel(writer, sheet_name='PostPEX', index=False, float_format="%.10f")

if __name__ == "__main__":
    main()




# ac_path = Path(__file__).parent / "diffpair_run" / "nets" / "postpex" / "run_0" / "result_ac.txt"
# noise_path = Path(__file__).parent / "diffpair_run" / "nets" / "postpex" / "run_0" / "result_noise.txt"
# dc_path = Path(__file__).parent / "diffpair_run" / "nets" / "postpex" / "run_0" / "result_power.txt"

# with open(ac_path, "r") as ACReport:
#     RawAC = ACReport.readlines()[0]
#     ACColumns = [item for item in RawAC.split() if item]

# with open(dc_path, "r") as DCReport:
#     RawDC = DCReport.readlines()[0]
#     DCColumns = [item for item in RawDC.split() if item]

# with open(noise_path, "r") as NoiseReport:
#     RawNoise = NoiseReport.readlines()[0]
#     NoiseColumns = [item for item in RawNoise.split() if item]
    
    
# na = -987.654321
# noACresults = (ACColumns is None) or len(ACColumns)<12
# noDCresults = (DCColumns is None) or len(DCColumns)<4
# nonoiseresults = (NoiseColumns is None) or len(NoiseColumns)<2
# return_dict = {
#     "BiasCurr": na if noACresults else ACColumns[1],
#     "bw_3db": na if noACresults else ACColumns[-1],
#     "cmrr": na if noACresults else ACColumns[9],
#     "common_mode_gain": na if noACresults else ACColumns[7],
#     "power": na if noDCresults else DCColumns[1],
#     "noise": na if nonoiseresults else NoiseColumns[1],
#     "diff_mode_gain": na if noACresults else ACColumns[5]
# }

# print(return_dict)