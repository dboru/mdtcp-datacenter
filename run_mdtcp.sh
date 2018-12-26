#!/bin/bash

# Exit on any failure
set -e

ctrlc() {
    killall -9 python
    mn -c
    exit
}

trap ctrlc SIGINT

iperf="iperf"
time=60
bw=10
delay=0.0
redmax=30001
redmin=30000
redburst=21
redprob=1.0
enable_ecn=1
enable_red=1
mdtcp=1
dctcp=0
g=4
subflows=1
pod=4
density=2
queue_size=100
topo_to_run=6
wl_to_run="one_to_one"
qmon=""
qmon_status="False"
avg_alfa=0

#killall -9 iperf 
#killall -9 netperf 
#killall -9 netserver

# ----- Get arguments ------
#get topo
# if [ "$1" = "all" ]
# then
#   topo_to_run=(4 6 8 10 12)
# else
#   if [ -n "$1" ] && [ $1 -ge 4 ]
#   then
#     topo_to_run=$1
#   fi
# fi

# get workload
if [ -n "$1" ]
then
  wl_to_run=$1
fi
if [ "$1" = "all" ]
then
  wl_to_run=('one_to_one' 'one_to_several' 'all_to_all')
fi

#get qmon
if [ -n "$2" ]
then
  qmon="--qmon"
  qmon_status="True"
fi

# echo "Experiments to run..."
# print_topo=''
# for i in ${topo_to_run[*]}
# do
#   print_topo="$print_topo $i"
# done
# echo "Fat Tree topologies: k = $print_topo"

print_wl=''
for i in ${wl_to_run[*]}
do
  print_wl="$print_wl $i"
done
echo "Workloads: $print_wl"
echo "Queue monitoring enabled: $qmon_status"
echo

# create directory for plot output
mkdir -p plots
rm -rf results

# ----- Run Mininet tests ------
# for k in ${topo_to_run[*]} #4 6 8 10 12
# do
  for workload in ${wl_to_run[*]} #one_to_one one_to_several all_to_all
  do
  for repeat in 1 
  do 
      # run experiment
      python mdtcp_test.py \
          --bw $bw \
          --delay $delay\
          --mdtcp $mdtcp\
          --dctcp $dctcp\
          --redmax $redmax\
          --redmin $redmin\
          --burst  $redburst\
          --queue  $queue_size\
          --prob $redprob\
          --enable_ecn $enable_ecn\
          --enable_red $enable_red\
          --g $g\
          --subflows $subflows\
          --queue $queue_size \
          --workload $workload \
          --pod $pod\
          --density $density\
          --time $time \
          --iperf $iperf \
          --iter $repeat\
          --avg_alfa $avg_alfa\
          --qmon
  done
  
  sleep 5

       # plot RTT
      # python plot_ping.py -k $pod -w $workload -f results/ft$pod/$workload/*/client_ping* -o plots/ft$pod-$workload-rtt.png
       # plot throughput
      # python iperf3Jsontocsv.py -k $pod -w $workload -f results/ft$pod/$workload/*/client_iperf3* -o plots/ft$pod-$workload-iperf3.csv
       python plot_hist.py -k $pod -w $workload -t $time -f results/ft$pod/$workload/*/client_iperf* results/ft$pod/$workload/max_throughput.txt -o plots/ft$pod-$workload-throughput.png
       # plot link util
       python plot_link_util.py -k $pod -w $workload -f results/ft$pod/$workload/*/link_util* -o plots/ft$pod-$workload-link_util.png
       # plot queue size
       if [ -n "$qmon" ]
       then
         for f in {1..8}
         do
             python plot_queue.py -k $pod -w $workload -f results/ft$pod/$workload/flows$f/queue_size* -o plots/ft$pod-$workload-flows$f-queue_size.png
         done
       fi
  done
# done

# for workload in ${wl_to_run[*]}
# # do
#   # plot cpu utilization
# python plot_cpu.py -w $workload -f results/ft*/$workload/flows*/cpu_utilization.txt -o plots/cpu_util-$workload.png
# # done
