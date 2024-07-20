import tempfile
import subprocess 
import os, sys
from typing import Optional, Union
from pathlib import Path

def generate_pre_or_postpex(
    gds_path, 
    design_name, 
    magic_drc_file: Optional[str] = None, 
    pre_or_post: Optional[bool] = True
):
    """
    Generate a magic script to extract prepex or postpex 
    
    Args:
        gds_path: str: the path to the gds file 
        design_name: str: the name of the design (do component.name = design_name first)
        magic_drc_file: str: the path to the .rc file for the pdk you want, already specified in code
        pre_or_post: bool
    
    Returns:
        None
    
    """
    
    if pre_or_post: 
        magic_script_content = f"""
gds flatglob *\\$\\$*
gds read {gds_path}
load {design_name}

select top cell
ext2resist all
extract all
ext2spice lvs
ext2spice extresist on 
ext2spice -o {design_name}_pex.spice
exit
"""
    else: 
        magic_script_content = f"""
gds read {gds_path}
flatten {design_name}
load {design_name}
select top cell
extract do local
extract all
ext2sim
extresist tolerance 10
extresist
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -o {design_name}_pex.spice
exit
"""

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as magic_script_file:
        magic_script_file.write(magic_script_content)
        magic_script_path = magic_script_file.name

    try:
        
        magicrc_file = str(Path("/usr/bin/miniconda3/share/pdk/sky130A/libs.tech/magic/sky130A.magicrc").resolve()) if magic_drc_file is None else magic_drc_file
        magic_cmd = f"bash -c 'magic -rcfile {magicrc_file} -noconsole -dnull < {magic_script_path}'",
        magic_subproc = subprocess.run(
            magic_cmd, 
            shell=True,
            check=True,
            capture_output=True
        )
        
        magic_subproc_code = magic_subproc.returncode
        magic_subproc_out = magic_subproc.stdout.decode('utf-8')
        print(magic_subproc_out)
    except:
        pass