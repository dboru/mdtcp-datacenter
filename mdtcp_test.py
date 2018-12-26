#!/usr/bin/python

from mininet.topo import Topo
from mininet.node import Host
from mininet.link import TCLink
from mininet.node import OVSKernelSwitch, RemoteController,CPULimitedHost
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import lg
from mininet.util import dumpNodeConnections, custom

import subprocess
from subprocess import Popen, PIPE
from time import sleep, time
from multiprocessing import Process
import termcolor as T
from argparse import ArgumentParser

import sys
import os
#from util.monitor import monitor_qlen
#from util.helper import stdev
# from mptcp_util import enable_mptcp, reset
# from dctopo import FatTreeTopo
from fattree import*
from workloads import OneToOneWorkload, OneToSeveralWorkload, AllToAllWorkload, progress


def cprint(s, color, cr=True):
    """Print in color
       s: string to print
       color: color to use"""
    if cr:
        print T.colored(s, color)
    else:
        print T.colored(s, color),


# Parse arguments
parser = ArgumentParser(description="Host throughput tests")
parser.add_argument('--bw', '-b',
                    dest="bw",
                    type=float,
                    action="store",
                    help="Bandwidth of links",
                    default=10)
parser.add_argument('--queue', '-q',
                    dest="queue",
                    type=int,
                    action="store",
                    help="Queue size (in packets)",
                    default=200)
parser.add_argument('--dir', '-d',
                    dest="dir",
                    action="store",
                    help="Directory to store outputs",
                    default="results")
parser.add_argument('--workload',
                    dest="workload",
                    action="store",
                    help="Type of workload",
                    required=True)

parser.add_argument('--pod',
                    dest="pod",
                    action="store",
                    type=int,
                    help="Number of pods",
                    default=4,
                    required=True)
parser.add_argument('--density',
                    dest="density",
                    action="store",
                    type=int,
                    help="FatTree density",
                    default=2,
                    required=True)

parser.add_argument('--iperf',
                    dest="iperf",
                    action="store",
                    help="Custom path for iperf",
                    required=True)
parser.add_argument('--time', '-t',
                    dest="time",
                    type=int,
                    action="store",
                    help="Length of experiment in seconds",
                    default=60)


parser.add_argument('--qmon',
                    dest="qmon",
                    action="store_true",
                    help="Turns on queue monitoring at switches if true",
                    default=False)


parser.add_argument('--mptcp',
                    action="store_true",
                    help="Enable MPTCP (net.mptcp.mptcp_enabled)",
                    default=False)

parser.add_argument('--pause',
                    action="store_true",
                    help="Pause before test start & end (to use wireshark)",
                    default=False)

parser.add_argument('--ndiffports',
                    action="store",
                    help="Set # subflows (net.mptcp.mptcp_ndiffports)",
                    default=1)
parser.add_argument('--enable_ecn',
                    dest="enable_ecn",
                    type=int,
                    help="Enable ECN or not",
                    default=0)
parser.add_argument('--enable_red',
                    dest="enable_red",
                    type=int,
                    help="Enable RED or not",
                    default=0)
parser.add_argument('--delay',
                    help="Link propagation delay (ms)",
                    required=True,
                    default='1ms')

parser.add_argument('--g',
                    type=int,
                    help="mdtcp_shift_g",
                    default=4)
parser.add_argument('--subflows',
                    type=int,
                    help="Number of subflows",
                    default=1)

parser.add_argument('--mdtcp',
                    type=int,
                    help="MDTCP test",
                    default=0)
parser.add_argument('--dctcp',
                    type=int,
                    help="DCTCP test",
                    default=0)
parser.add_argument('--redmax',
                    type=int,
                    help="RED max",
                    default=30001)
parser.add_argument('--redmin',
                    type=int,
                    help="RED min",
                    default=30000)
parser.add_argument('--burst',
                    type=int,
                    help="RED burst",
                    default=21)
parser.add_argument('--prob',
                    type=float,
                    help="RED prob",
                    default=1.0)
parser.add_argument('--lag',
                    type=int,
                    help="Time delay before starting MDTCP ",
                    default=0)
parser.add_argument('--avg_alfa',
                    type=int,
                    help="use mean of congestion signal measured by subflows",
                    default=0)

parser.add_argument('--iter',
                    type=int,
                    help="iteration number",
                    default=1)


# Experiment parameters
args = parser.parse_args()
CUSTOM_IPERF_PATH = args.iperf

lg.setLogLevel('info')

def enableMPTCP(subflows):
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=ndiffports")
    os.system(
        "sudo echo -n %i > /sys/module/mptcp_ndiffports/parameters/num_subflows" % int(subflows))
    # os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=olia")


def enableMDTCP(subflows, shift_g,use_avg_alfa):
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=ndiffports")
    os.system(
        "sudo echo -n %i > /sys/module/mptcp_ndiffports/parameters/num_subflows" % int(subflows))
    # os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=mdtcp")
    os.system(
        "sudo echo -n %i > /sys/module/mdtcp_coupled/parameters/mdtcp_shift_g" % int(shift_g))
    

def enableDCTCP():
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=0")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=dctcp")


def disableMDTCP():
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=ndiffports")
    os.system("sudo echo -n 1 > /sys/module/mptcp_ndiffports/parameters/num_subflows")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=olia")


def get_max_throughput(net, output_dir):
    #reset()
    #enableMDTCP()
   
        
    cprint("Finding max throughput...", 'red')
    seconds = args.time
    server, client = net.hosts[0], net.hosts[1]
    server.popen("%s -s -p %s" %
                 (CUSTOM_IPERF_PATH, 5001), shell=True)
    proc = client.popen("%s -c %s -p %s -t %d -yc -i 10 > %s/max_throughput.txt" %
                        (CUSTOM_IPERF_PATH, server.IP(), 5001, seconds, output_dir), shell=True)

    progress(args.time + 1)
    proc.communicate()
    os.system('killall -9 ' + CUSTOM_IPERF_PATH)

def get_workload(net):
    if args.workload == "one_to_one":
        return OneToOneWorkload(net, args.iperf, args.time)
    elif args.workload == "one_to_several":
        return OneToSeveralWorkload(net, args.iperf, args.time)
    else:
        return AllToAllWorkload(net, args.iperf, args.time)


def main():
    top_dir = os.path.join(args.dir, 'ft'+str(args.pod), args.workload)
    if not os.path.exists(top_dir):
        os.makedirs(top_dir)

    start = time()
    droptail = {'bw': args.bw, 'delay': str( args.delay)+'ms', 'max_queue_size': args.queue}
    red_ecn = {'bw': args.bw, 'delay': str(args.delay)+'ms', 'max_queue_size': args.queue,\
                'enable_ecn': args.enable_ecn, 'enable_red': args.enable_red,\
                'red_min': args.redmin, 'red_max': args.redmax, 'red_burst':  args.burst,\
                'red_prob': args.prob, 'red_avpkt': 1500, 'red_limit': 1000000}
    if args.mdtcp or args.dctcp:
        topo = topoCreate(args.pod, args.density,red_ecn, droptail)
    else:
        topo = topoCreate(args.pod, args.density,droptail, droptail)


    CONTROLLER_IP = "127.0.0.1"
    CONTROLLER_PORT = 6633
    net = Mininet(topo=topo, host=CPULimitedHost,link=TCLink,controller=None, autoSetMacs=True)
    net.addController('controller', controller=RemoteController,protocol='tcp',ip=CONTROLLER_IP, port=CONTROLLER_PORT)

    

    net.start()
    #nodes = net.hosts 
    #for node in nodes:
    #  for port in node.ports:
    #      if str.format('{}', port) != 'lo':
    #          node.cmdPrint(str.format('ethtool --offload {} gro off gso off tso off', port))
    
    
    sleep(5)

    # Set OVS's protocol as OF13.
    topo.set_ovs_protocol_13()
    # Set hosts IP addresses.
    set_host_ip(net, topo)
    # Install proactive flow entries
    install_proactive(net, topo)
    # dumpNodeConnections(net.hosts)
    sleep(2)

    workload = get_workload(net)
    #CLI(net)
    sleep(3)
    os.system('killall -9 ' + CUSTOM_IPERF_PATH)
    os.system('killall -9 iperf3')
    os.system('killall -9 netserver')
    os.system('killall -9 netperf')
  
    enableMDTCP(1,args.g,args.avg_alfa)
    get_max_throughput(net, top_dir)
    os.system('killall -9 ' + CUSTOM_IPERF_PATH)
    os.system('killall -9 iperf3')

    for nflows in range(4, 5):
        cwd = os.path.join(top_dir, "flows%dg%d" % (nflows,args.g))
        Popen("echo > /dev/null | sudo tee /var/log/syslog",shell=True).wait()

        if not os.path.exists(cwd):
            os.makedirs(cwd)
        if args.mdtcp:
            enableMDTCP(nflows, args.g,args.avg_alfa)
        elif args.dctcp:
            enableDCTCP()
        else:
            enableMPTCP(nflows)

        cprint("Starting experiment for workload %s with %i subflows" % (
            args.workload, nflows), "green")
        Popen('bwm-ng -t 100 -T rate -c 0  -o csv -C , -F %s/rates.txt &'%cwd, shell=True)
        workload.run(cwd, args.qmon,nflows,args.iter)

        # Shut down iperf processes
        os.system('killall -9 ' + CUSTOM_IPERF_PATH)
        os.system('killall -9 iperf3')
        os.system('killall -9 netserver')
        os.system('killall -9 netperf')

    net.stop()
    #disableMDTCP()

    # # kill pox controller
    # pox_c.kill()
    # pox_c.wait()

    Popen("killall -9 top bwm-ng tcpdump cat mnexec", shell=True).wait()
    end = time()
    #reset()
    disableMDTCP()
    cprint("Experiment took %.3f seconds" % (end - start), "yellow")


if __name__ == '__main__':
    try:
        # for repeat in range(5):
        main()
        # sleep(20)
    except:
        print "-"*80
        print "Caught exception.  Cleaning up..."
        print "-"*80
        import traceback
        #reset()
        disableMDTCP()
        traceback.print_exc()
        os.system("killall -9 top bwm-ng tcpdump cat mnexec iperf; mn -c")
