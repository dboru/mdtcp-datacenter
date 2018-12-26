#!/usr/bin/env python

from random import choice, shuffle,randint,randrange,uniform
from subprocess import Popen, PIPE
from mininet.util import pmonitor
from time import time, sleep
import sys
import termcolor as T
from mininet.cli import CLI
from collections import defaultdict, Counter
from monitor import monitor_qlen
from multiprocessing import Process
from util.helper import *
import random



def median(l):
    "Compute median from an unsorted list of values"
    s = sorted(l)
    if len(s) % 2 == 1:
        return s[(len(l) + 1) / 2 - 1]
    else:
        lower = s[len(l) / 2 - 1]
        upper = s[len(l) / 2]
        return float(lower + upper) / 2

def progress(t):
    while t > 0:
        print T.colored('  %3d seconds left \r' % (t), 'cyan'),
        t -= 1
        sys.stdout.flush()
        sleep(1)
    print '\r\n'

class Workload():
    def __init__(self, net, iperf, seconds):
        self.iperf = iperf
        self.seconds = seconds
        self.mappings = []
        self.net = net

    def run(self, output_dir, qmon_status,nflows,repeat):
        servers = list(set([mapping[0] for mapping in self.mappings]))
        for server in servers:
            server.popen("%s -s -p %s > %s/server_iperf-%siter%s.txt" %
                         (self.iperf, 5001, output_dir, server.name,repeat), shell=True)
            # server.popen("iperf3 -s -p %s > %s/server_iperf3-%s.txt" %
            #               (6002, output_dir, server.name), shell=True)
            #server.popen("netserver &",shell=True)
            #server.popen("ethtool -K eth0  tso off gso off gro off",shell=True).wait()

        # start CPU monitor
        Popen('mpstat 2 %d > %s/cpu_utilization-iter%s.txt' % (self.seconds/2 + 2,
                                                        output_dir,repeat), shell=True)
        procs = []
        iperf3_procs=[]
        # netperf_proc=[]
        size=[150000,500000,1000000,5000000,10000000]
        
        for mapping in self.mappings:
            server, client = mapping

            # flent tcp_upload -p totals -l 60 -H address-of-netserver -t text-to-be-included-in-plot -o filename.png

            # procs.append(client.popen( "flent tcp_upload -p totals -l 30 -H %s  -t %s-%s-%s -o netperf-subflows%s-%s-%s.png"%
            #         (server.IP(), output_dir, client.name, server.name, nflows,client.name, server.name), shell=True))

            #client.popen("ethtool -K eth0 tso off gso off gro off ",shell=True).wait()
            procs.append(client.popen(
                    "%s -c %s -p %s -t %d -yc -i 10 > %s/client_iperf-%s-%s-iter%s.txt" %
                    (self.iperf, server.IP(), 5001, self.seconds,
                     output_dir, client.name, server.name,repeat), shell=True))
            break
            
            flow_size=size[randrange(0,5)];

                       
            timeDelay = random.randrange(0, 50)
            sleep(timeDelay/1000)

        interfaces = []
        for node in self.net.switches:
            for intf in node.intfList():
                if intf.link:
                    interfaces.append(intf.link.intf1.name)
                    interfaces.append(intf.link.intf2.name)

        if qmon_status:
            qmons = []
            switch_names = [switch.name for switch in self.net.switches]
            for iface in interfaces:
                if iface.split('-')[0] in switch_names:
                    qmons.append(start_qmon(iface,
                                            outfile="%s/queue_size-%s-iter%s.txt"
                                            % (output_dir, iface,repeat)))

        # take utilization samples
        get_rates(interfaces, output_dir)

        progress(self.seconds - 10) # remove some time for get_rates 
        for proc in procs:
            proc.communicate()
        for proc in iperf3_procs:
            proc.communicate()

        if qmon_status:
            for qmon in qmons:
                qmon.terminate()

class OneToOneWorkload(Workload):
    def __init__(self, net, iperf, seconds):
        Workload.__init__(self, net, iperf, seconds)
        hosts = list(net.hosts)
        shuffle(hosts)
        group1, group2 = hosts[::2], hosts[1::2]
        self.create_mappings(list(group1), list(group2))
        self.create_mappings(group2, group1)

    def create_mappings(self, group1, group2):
        while group1:
            server = choice(group1)
            group1.remove(server)
            client = choice(group2)
            group2.remove(client)
            self.mappings.append((server, client))        


class OneToSeveralWorkload(Workload):
    def __init__(self, net, iperf, seconds, num_conn=4):
        Workload.__init__(self, net, iperf, seconds)
        self.create_mappings(net.hosts, num_conn)

    def create_mappings(self, group, num_conn):
        for server in group:
            clients = list(group)
            clients.remove(server)
            shuffle(clients)
            for client in clients[:num_conn]:
                self.mappings.append((server, client))

class AllToAllWorkload(Workload):
    def __init__(self, net, iperf, seconds):
        Workload.__init__(self, net, iperf, seconds)
        self.create_mappings(net.hosts)

    def create_mappings(self, group):
        for server in group:
            for client in group:
                if client != server:
                    self.mappings.append((server, client))


def get_txbytes(iface):
    f = open('/proc/net/dev', 'r')
    lines = f.readlines()
    for line in lines:
        if iface in line:
            break
    f.close()
    if not line:
        raise Exception("could not find iface %s in /proc/net/dev:%s" %
                        (iface, lines))
    # Extract TX bytes from:                                                           
    #Inter-|   Receive                                                |  Transmit      
    # face |bytes    packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed                                                   
# lo: 6175728   53444    0    0    0     0          0         0  6175728   53444 0    0    0     0       0          0                                                          
    return float(line.split()[9])

NSAMPLES = 5
SAMPLE_PERIOD_SEC = 1.0
SAMPLE_WAIT_SEC = 15.0

def get_rates(ifaces, output_dir,nsamples=NSAMPLES, period=SAMPLE_PERIOD_SEC,
              wait=SAMPLE_WAIT_SEC):
    """Returns the interface @iface's current utilization in Mb/s.  It                 
    returns @nsamples samples, and each sample is the average                          
    utilization measured over @period time.  Before measuring it waits                 
    for @wait seconds to 'warm up'."""
    # Returning nsamples requires one extra to start the timer.                        
    nsamples += 1
    last_time = 0
    last_txbytes = Counter()
    ret = []
    sleep(wait)
    txbytes = Counter()
    ret = defaultdict(list)
    while nsamples:
        nsamples -= 1
        for iface in ifaces:
            txbytes[iface] = get_txbytes(iface)
        now = time()
        elapsed = now - last_time
        #if last_time:                                                                 
        #    print "elapsed: %0.4f" % (now - last_time)                                
        last_time = now
        # Get rate in Mbps; correct for elapsed time.
        for iface in txbytes:
            rate = (txbytes[iface] - last_txbytes[iface]) * 8.0 / 1e6 / elapsed
            if last_txbytes[iface] != 0:
                # Wait for 1 second sample
                ret[iface].append(rate)
        last_txbytes = txbytes.copy()
        print '.',
        sys.stdout.flush()
        sleep(period)
    f = open("%s/link_util.txt" % output_dir, 'w')
    for iface in ret:
        f.write("%f\n" % median(ret[iface]))
    f.close()

def start_qmon(iface, interval_sec=1.0, outfile="q.txt"):
    monitor = Process(target=monitor_qlen,
                      args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor
