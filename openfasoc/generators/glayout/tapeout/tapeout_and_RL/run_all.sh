#!/bin/bash

base_dir="./diffpair_run/nets"

# for i in {0..719}
# do 
#     echo "Running postpex $i"
#     cd "$base_dir/postpex/run_$i"
#     ngspice -b diffpair_perf_eval.sp
#     cd -

#     echo "Running prepex $i"
#     cd "$base_dir/postpex/run_$i"
#     ngspice -b diffpair_perf_eval.sp
#     cd -
# done 

export base_dir

parallel -j 10 --line-buffer 'cd {} && ngspice -b diffpair_perf_eval.sp && cd -' ::: \
    $base_dir/prepex/run_{572..719} $base_dir/postpex/run_{0..719}

