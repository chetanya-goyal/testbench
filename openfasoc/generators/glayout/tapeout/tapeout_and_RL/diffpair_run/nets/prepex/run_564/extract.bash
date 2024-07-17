#!/bin/bash

# Actual
export PDK_ROOT=/usr/bin/miniconda3/share/pdk/

# args:
# first arg = gds file to read
# second arg = name of top cell in gds file to read
# third arg (optional) = noparasitics (basically an LVS extraction)

paropt="na"
prepex="yes"

if [ "$prepex" = "yes" ]; then

magic -rcfile ./sky130A/sky130A.magicrc -noconsole -dnull << EOF
gds read $1
flatten $2
load $2
select top cell
extract do local
extract all
ext2sim labels on
ext2sim
ext2spice lvs
ext2spice -o $2_pex.spice
exit
EOF

else 

if [ "$paropt" = "noparasitics" ]; then

magic -rcfile ./sky130A/sky130A.magicrc -noconsole -dnull << EOF
gds read $1
flatten $2
load $2
select top cell
extract do local
extract all
ext2sim labels on
ext2sim
ext2spice lvs
ext2spice cthresh 0
ext2spice -o $2_pex.spice
exit
EOF

else

magic -rcfile ./sky130A/sky130A.magicrc -noconsole -dnull << EOF
gds read $1
flatten $2
load $2
select top cell
extract do local
extract all
ext2sim labels on
ext2sim
extresist tolerance 10
extresist
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -o $2_pex.spice
exit
EOF

fi

fi

rm -f $2.nodes
rm -f $2.ext
rm -f $2.res.ext
rm -f $2.sim

