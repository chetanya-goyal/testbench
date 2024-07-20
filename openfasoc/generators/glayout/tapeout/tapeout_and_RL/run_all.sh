#!/bin/bash

base_dir="./opamp_run/nets"

# for i in {0..719}
# do 
#     echo "Running postpex $i"
#     cd "$base_dir/postpex/run_$i"
#     ngspice -b opamp_perf_eval.sp
#     cd -

#     echo "Running prepex $i"
#     cd "$base_dir/postpex/run_$i"
#     ngspice -b opamp_perf_eval.sp
#     cd -
# done 

export base_dir

parallel -j 11 --line-buffer 'cd {} && ngspice -b opamp_perf_eval.sp && cd -' ::: \
    $base_dir/postpex/run_{168..320}

