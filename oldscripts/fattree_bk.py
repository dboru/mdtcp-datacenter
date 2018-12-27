'''
based on riplpox 
'''

import sys
sys.path.append(".")

from mininet.topo import Topo
from mininet.node import Controller, RemoteController, OVSKernelSwitch, CPULimitedHost
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.util import custom
from mininet.log import setLogLevel, info, warn, error, debug
from random import choice, shuffle,randint,randrange,uniform
import random
from fattree import*
import termcolor as T
from subprocess import Popen, PIPE
from argparse import ArgumentParser
import multiprocessing
from multiprocessing import Process
from monitor.monitor import monitor_qlen
from time import time,sleep
from monitor.monitor import monitor_devs_ng
from collections import defaultdict, Counter
from flows import flow
import os
import subprocess
import time


###################################### Hash & Dijkstras Test ######################################################
# import networkx as nx
# from Hashed import HashHelperFunction
# from Dijkstras import dijkstraHelperFunction
# G=nx.Graph()
###################################### Hash & Dijkstras Test ######################################################


# Number of pods in Fat-Tree 
K = 4

# Queue Size
QUEUE_SIZE = 100

# Link capacity (Mbps)
BW = 10 
flowSource="../emp-tg/conf/DCTCP_CDF.txt"
conn_per_host=1


parser = ArgumentParser(description="minient_fattree")

parser.add_argument('-d', '--dir', dest='output_dir', default='log',
        help='Output directory')

parser.add_argument('-i', '--input', dest='input_file',
        default='inputs/all_to_all_data',
        help='Traffic generator input file')

parser.add_argument('-t', '--time', dest='time', type=int, default=30,
        help='Duration (sec) to run the experiment')

parser.add_argument('-K', '--K', dest='K', type=int, default=4,
        help='No. pods in Fattree topology')
parser.add_argument('--density',dest="density",action="store",type=int,\
        help="FatTree density=no. hosts per edge?!",default=2,required=True)
parser.add_argument('-p', '--cpu', dest='cpu', type=float, default=-1,
        help='cpu fraction to allocate to each host')

parser.add_argument('--iperf', dest='iperf', default=False, action='store_true',
        help='Use iperf to generate traffics')

parser.add_argument('--workload',dest="workload",default="one_to_one",action="store",help="Type of workload",required=True)
parser.add_argument('--subflows',type=int,help="Number of subflows",default=1)

parser.add_argument('--bw', '-b',dest="bw",type=float,action="store",help="Bandwidth of links",default=10)
parser.add_argument('--queue', '-q',dest="queue",type=int,action="store",help="Queue size (in packets)", default=200)

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
parser.add_argument('--load',
                    type=float,
                    help="Network load",
                    default=1.0)
parser.add_argument('--mdtcp_debug',
                    type=int,
                    help="enable debug output",
                    default=0)
parser.add_argument('--num_reqs',
                    type=int,
                    help="number of client requests",
                    default=1)

parser.add_argument('--iter',
                    type=int,
                    help="iteration number",
                    default=1)
parser.add_argument('--test',
                    type=int,
                    help="Test type(throughput=0/FCT=1)",
                    default=0)

parser.add_argument('--qmon',
                    type=int,
                    dest="qmon",
                    help="Turns on queue monitoring at switches if true",
                    default=0)

parser.add_argument('--avg_flow_length',
                    type=int,
                    dest="flow_length",
                    help="Mean flow length for Pareto Traffic Generator",
                    default=30)

args = parser.parse_args()

def median(l):
    "Compute median from an unsorted list of values"
    s = sorted(l)
    if len(s) % 2 == 1:
        return s[(len(l) + 1) / 2 - 1]
    else:
        lower = s[len(l) / 2 - 1]
        upper = s[len(l) / 2]
        return float(lower + upper) / 2
def saveClntServMapping(clnt_server_mappings,clnt):
    if clnt:
        with open('clnts', 'w') as fp:
            for item in clnt_server_mappings:
                fp.write("%s\n"%item)
    else:
        with open('servs', 'w') as fp:
            for item in clnt_server_mappings:
                fp.write("%s\n"%item)
def getClntServMapping(yclnt):
    clnt=[]
    if yclnt is True:
        with open ('clnts', 'r') as fp:
            lines = fp.readlines()
            for line in lines:
                clnt.append(line)
    else:
        with open ('servs', 'r') as fp:
            lines = fp.readlines()
            for line in lines:
                clnt.append(line)
    return clnt
class Workload():
    def __init__(self, net, iperf, seconds):
        self.iperf = iperf
        self.seconds = seconds
        self.mappings = []
        self.net = net
        self.conn_perhost=1

    def run(self, output_dir,subflows):

        servers = list(set([mapping[0] for mapping in self.mappings]))
 
        for server in servers:

            if args.test==0:
                server.cmd('iperf -s -p 5001 >> /dev/null & ')
            # elif args.test==1:
            #     # server.cmd('./bin/server -p 5050 >> /dev/null &')
            #     server.cmd('iperf3 -s -p 6002 & ')
            #     # server.cmd("netserver -p 5402 & ")
            #     # server.cmd('./pareto_tg/tg 6081 >> /dev/null &')
            #     # server.cmd('./pareto_tg/tg 6081 >>' + output_dir+'/serv_log_'+server.IP()+'_iter'+ str(args.iter)+ ' &')
            #     sleep(0.5)

        
        if args.test == 1:
            self_flow=flow(flowSource)
            avg_flow_size=self_flow.meanSize()
            mean_period=8.0*avg_flow_size*4/(args.bw*1000000.0)
            exp_lambda=1.0/mean_period;
            print(mean_period,exp_lambda)
            exp_lambda=5.0

        port=6002

        interfaces = []
        for node in self.net.switches:
            for intf in node.intfList():
                if intf.link:
                    interfaces.append(intf.link.intf1.name)
                    interfaces.append(intf.link.intf2.name)
    
        if args.qmon == 1:
            print('started queue monitoring! ',subflows)
            qmons = []
            switch_names = [switch.name for switch in self.net.switches]


            for iface in interfaces:
                
                if iface.split('-')[0] in switch_names:                    
                    sw=self.layer(iface.split('-')[0])
                    #if subflows ==2:
                    #Popen("tcpdump -i %s -s 96 -w %s/trace-iface-%s.pcap"%(iface,output_dir,iface), shell=True)
 
                    qmons.append(start_qmon(iface,
                                            outfile="%s/queue_size_%s-%s_iter%s.txt"
                                            % (output_dir, sw,iface,str(args.iter))))


        # expovariate(lambda) lambda is 1.0 divided by the desired mean
       
        if args.test==1:
            # start CPU monitor
            # Popen('mpstat 2 %d >> %s/cpu_utilization.txt' % (10*self.seconds + 2,
            #                                             output_dir), shell=True)
            # self.iperf3_fixed_rate(output_dir)
            self.emptraffic_generator(output_dir)
            #self.hktraffic_generator(output_dir)
            # Popen('bwm-ng -t 100 -T rate -c 0  -o csv -C , -F %s/rates_iter%s.txt &'%(output_dir,args.iter), shell=True)

                
        if args.test==0:
            for mapping in self.mappings:
                timeDelay = random.randrange(100, 10000)
                server, client = mapping
                client.cmd('iperf -c '+ server.IP()+ ' -p 5001 -t '+ str(self.seconds)+ \
                    ' -yc  -i 0.25 > '+output_dir+'/client_iperf-'+client.IP()+'-'+server.IP()+'_iter'+str(args.iter)+'.txt &')
                # sleep(timeDelay/100000)
                #Popen('bwm-ng -t 100 -T rate -c 0  -o csv -C , -F %s/rates_iter%s.txt &'%(output_dir,args.iter), shell=True)
                #break 

        # get_rates(interfaces, output_dir)
        time_run=time.time()+300
        # and time.time()-time_run < 0
        if args.test == 1:
            while True:
                clnt=os.popen("ps ax | grep 'conf/client_10.' ").read()

                nclnt=len(clnt.split('\n'))
                
                if 'emp-tg/conf/client_10' in clnt : 
                    sleep (1)
                else:

                    break
        elif args.test==0:
            progress(args.time+2)

        # progress(10*args.time)
        # t=self.seconds;
        # while t > 0:
        #     print T.colored('  %3d seconds left \r' % (t), 'cyan'),
        #     t -= 1
        #     sys.stdout.flush()
        #     sleep(1)
        #     print '\r\n'

        if args.qmon==1:
            for qmon in qmons:
                qmon.terminate()
    def layer(self, name):
        ''' Return layer of node '''
        # node = self.node_gen(name = name)

        name_str=name.split('h')
        if int(name_str[0])==args.K:
            return 'core'
        elif int(name_str[2])==1:
            if int(name_str[1]) < args.K/2:
                return 'edge'
            else:
                return 'agg'
        else:
            return 'host'

    def iperf3_fixed_rate(self,output_dir):

        myInterMap={}
        total_transfer=0
        tstart=time.time()
        rate=0
        t=args.time
        self_flow=flow(flowSource)
        avg_flow_size=self_flow.meanSize()
        mean_period=8.0*avg_flow_size*4/(args.bw*1000000.0)
        exp_lambda=1.0/mean_period;
        print(mean_period,exp_lambda)
        exp_lambda=10.0
        # monitor_devs_ng(output_dir+'/txrate.txt')

        while t > 0:
            for mapping in self.mappings:
                server, client = mapping
                if mapping not in myInterMap.keys():
                    myInterMap[mapping]={}
                    myInterMap[mapping]['next']=time.time()
                    myInterMap[mapping]['iter']=args.iter
                    myInterMap[client]={}
                    myInterMap[client]['sent']=0
                    myInterMap[client]['rate']=0
                else:
                    if myInterMap[mapping]['next']<=time.time():
                        port=random.randrange(5000,10000)
                        # handle one client connection and exit
                        server.cmd('iperf3 -s -1 -p '+str(port) +' >> /dev/null &')                    
                        # server.cmd('iperf3 -s -1 -p '+str(port) +' > '+ output_dir+'/server_iperf3-'+client.name+\
                        # '-'+server.name+'_iter'+str(myInterMap[mapping]['iter'])+'.json &')
                        sleep(0.2)
                        flow_size=self_flow.randomSize()
                        
                        # flow_min,flow_max=self_flow.randomSize()
                        # if flow_min==flow_max:
                        #     flow_size=random.randrange(1024,flow_max+1)
                        # else:
                        #     flow_size=random.randrange(flow_min,flow_max+1)

                        myInterMap[client]['sent']+=flow_size

                        total_transfer+=flow_size
                        # 1-to-4 connection
            
                        client.cmd('iperf3 -c '+ server.IP()+ ' -p '+ str(port)  +' -b '+str(args.bw*args.load/4.0) +'M  -n '+ \
                            str(flow_size)+ ' -J > '+output_dir+'/client_iperf3-'+client.name+'-'+server.name+\
                            '_iter'+str(myInterMap[mapping]['iter'])+'.json &')
                        next_time=random.expovariate(exp_lambda)
                        myInterMap[mapping]['next']+=next_time
                        myInterMap[mapping]['iter']+=1
            sleep(1)
            Popen('mpstat 1 %d >> %s/cpu_utilization.txt' % (5,output_dir), shell=True)
            #Popen('bwm-ng -t 100 -T rate -c 0  -o csv -C , -F %s/rates.txt &'%output_dir, shell=True)
            t -= 1.2
            Popen('echo tg time,'+str(t)+',runtime,'+str(time.time()-tstart)+' >> '+output_dir+'/run_time.txt',shell=True)
            

    

    def expo_flow_arrival(self,output_dir):

        myInterMap={}
        total_transfer=0
        tstart=time.time()
        rate=0
        t=args.time

        while t > 0:
            for mapping in self.mappings:
                server, client = mapping
                rate=8*total_transfer/(time.time()-tstart)/1000000
                if mapping not in myInterMap.keys():
                    myInterMap[mapping]={}
                    myInterMap[mapping]['next']=time.time()
                    myInterMap[mapping]['iter']=args.iter
                    myInterMap[client]={}
                    myInterMap[client]['sent']=0
                    myInterMap[client]['rate']=0
                    
                else:
                    myInterMap[client]['rate']=8*myInterMap[client]['sent']/(time.time()-tstart)/1000000 
                    if myInterMap[mapping]['next']<=time.time() and myInterMap[client]['rate']<100:
                        port=random.randrange(5000,10000)
                        server.cmd('iperf3 -s -p '+str(port) +' > '+ output_dir+'/server_iperf3-'\
                                +client.name+'-'+server.name+'_iter'+str(myInterMap[mapping]['iter'])+'.json &')
                        # flow_size=self_flow.randomSize()
                        flow_min,flow_max=self_flow.randomSize()
                        if flow_min==flow_max:
                            flow_size=random.randrange(1024,flow_max+1)
                        else:
                            flow_size=random.randrange(flow_min,flow_max+1)
                        myInterMap[client]['sent']+=flow_size

                        total_transfer=total_transfer+flow_size
                        
                        client.cmd('iperf3 -c '+ server.IP()+ ' -p '+ str(port)  +' -n '+ str(flow_size)+ \
                        ' -J -i 1 > '+output_dir+'/client_iperf3-'+client.name+'-'+server.name+'_iter'+\
                        str(myInterMap[mapping]['iter'])+'.json &')
                        
                        next_time=random.expovariate(exp_lambda)
                        myInterMap[mapping]['next']=time.time()+next_time
                        # myInterMap[mapping]['next']=random.expovariate(exp_lambda)+time.time()
                        myInterMap[mapping]['iter']=myInterMap[mapping]['iter']+1
            # if t==args.time:
            #     monitor_devs_ng(output_dir+'/txrate.txt')

            sleep(1)
            t -= 1
            
    def emptraffic_generator(self, output_dir):
        # timeDelay=5.0
        
        srvrs={} 
        for mapping in self.mappings:
            server, client = mapping
            if server.IP() not in srvrs.keys():
               srvrs[server.IP()]=1
            elif srvrs[server.IP()] < 3:
               srvrs[server.IP()]=srvrs[server.IP()]+1
            else:
               continue  
            port=random.randrange(5000,10000)
            server.cmd('./../emp-tg/bin/server -p '+str(port) +'  >> /dev/null &')
            sleep(1.0)
            client.cmd('rm ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('echo server '+ server.IP() +' '+ str(port) +' >> ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('echo req_size_dist ../emp-tg/conf/DCTCP_CDF.txt >> ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('echo load '+str(args.bw*args.load/self.conn_perhost)+'Mbps >> ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('echo fanout 1 100 >> ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP())

            client.cmd('echo num_reqs '+str(args.num_reqs)+' >> ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('./../emp-tg/bin/client  -c ../emp-tg/conf/client_'+client.IP()+'_to_'+server.IP()+ \
                 '  -s ' +str(random.randrange(100,50000))+\
                 ' -l flows_'+client.IP()+'_to_'+server.IP()+'_iter'+str(args.iter)+ \
                 '  > log_'+client.IP()+'_to_'+server.IP()+'_iter'+ str(args.iter)+ ' &')
            Popen('bwm-ng -t 100 -T rate -c 0  -o csv -C , -F %s/rates.txt &'%output_dir, shell=True)
            break

    def hktraffic_generator(self, output_dir):
        # timeDelay=5.0
        timeDelay = random.randrange(10, 100)
        srvrs={} 
        for mapping in self.mappings:
            server, client = mapping
            if server.IP() not in srvrs.keys():
               srvrs[server.IP()]=1
            elif srvrs[server.IP()] < 3:
               srvrs[server.IP()]=srvrs[server.IP()]+1
            else:
               continue  
            port=random.randrange(5000,10000)
            server.cmd('./../tg/bin/server -p '+str(port) +'  >> /dev/null &')
            sleep(1.0)
            client.cmd('rm ../tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('echo server '+ server.IP() +' '+ str(port) +' >> ../tg/conf/client_'+client.IP()+'_to_'+server.IP())
            client.cmd('echo req_size_dist ../tg/conf/DCTCP_CDF.txt >> ../tg/conf/client_'+client.IP()+'_to_'+server.IP())
            #client.cmd('echo rate 90Mbps 100 >> ../tg/conf/client_'+client.IP()+'_to_'+server.IP())
            #client.cmd('echo fanout 1 100 >> ../tg/conf/client_'+client.IP()+'_to_'+server.IP())
           
            client.cmd('./../tg/bin/client  -b '+str(args.bw*args.load/self.conn_perhost) +' -c ../tg/conf/client_'+client.IP()+'_to_'+server.IP()+ \
                 ' -l flows_'+client.IP()+'_to_'+server.IP()+'_iter'+str(args.iter)+'.out' \
                 ' -t '+str(args.time)+'  > log_'+client.IP()+'_to_'+server.IP()+'_iter'+ str(args.iter)+ ' &')
            #Popen('bwm-ng -t 100 -T rate -c 0  -o csv -C , -F %s/rates.txt &'%output_dir, shell=True)




class OneToOneWorkload(Workload):
    def __init__(self, net, iperf, seconds):
        Workload.__init__(self, net, iperf, seconds)
        hosts = list(net.hosts)
        shuffle(hosts)
        group1, group2 = hosts[::2], hosts[1::2]
        self.create_mappings(list(group1), list(group2))
        self.create_mappings(group2, group1)
        self.conn_perhost=1

    def create_mappings(self, group1, group2):
        clnts=[]
        serv=[]
        if args.mdtcp or args.dctcp:
            while group1:
                server = choice(group1)
                group1.remove(server)
                client = choice(group2)
                group2.remove(client)
                clnts.append(client)
                serv.append(server)
                self.mappings.append((server, client))
            saveClntServMapping(clnts,True)
            saveClntServMapping(serv,False)
        else:
            clnts=getClntServMapping(True)
            serv=getClntServMapping(False)
            for i in range(len(clnts)):
                for h in nets:
                    if str(h) in serv[i].split('\n')[0]:
                        srv=h
                        for hh in nets:
                            if clnts[i].split('\n')[0] in str(hh):
                                clnt=hh
                                self.mappings.append((srv, clnt))
                                break

class OneToSeveralWorkload(Workload):
    def __init__(self, net, iperf, seconds, num_conn=2):
        Workload.__init__(self, net, iperf, seconds)
        #num_conn=random.randrange(1,3)
        #num_conn=6
        self.conn_perhost=num_conn
        self.create_mappings(net.hosts, num_conn,net.hosts)

    def create_mappings(self, group, num_conn,nets):
        clnts=[]
        serv=[]
        if args.mdtcp or args.dctcp:
            for server in group:
                clients = list(group)
                clients.remove(server)
                shuffle(clients)
                for client in clients[:num_conn]:
                    clnts.append(client)
                    serv.append(server)
                    self.mappings.append((server, client))
            saveClntServMapping(clnts,True)
            saveClntServMapping(serv,False)
        else:
            clnts=getClntServMapping(True)
            serv=getClntServMapping(False)
            for i in range(len(clnts)):
                for h in nets:
                    if str(h) in serv[i].split('\n')[0]:
                        srv=h
                        for hh in nets:
                            if clnts[i].split('\n')[0] in str(hh):
                                clnt=hh
                                self.mappings.append((srv, clnt))
                                break



class OneToSeveralOffPodWorkload(Workload):
    def __init__(self, net, iperf, seconds, num_conn=2):
        Workload.__init__(self, net, iperf, seconds)
        # num_conn=randrange(1,2)
        self.create_mappings(net.hosts, num_conn)

    def create_mappings(self, group, num_conn):

        for server in group:
            clients = list(group)
            # remove self
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

def get_workload(net):
    if args.workload == "one_to_one":
        return OneToOneWorkload(net, args.iperf, args.time)
    elif args.workload == "one_to_several":
        return OneToSeveralWorkload(net, args.iperf, args.time)
    else:
        return AllToAllWorkload(net, args.iperf, args.time)


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

def get_rates(ifaces, output_dir, nsamples=NSAMPLES, period=SAMPLE_PERIOD_SEC,
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
        now = time.time()
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
    f = open("%s/link_util.txt" % output_dir, 'a')
    for iface in ret:
        f.write("%f\n" % median(ret[iface]))
    f.close()

def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
    monitor = Process(target=monitor_qlen,args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor

def get_max_throughput(net, output_dir):
    
    cprint("Finding max throughput...", 'red')
    seconds = args.time
    server, client = net.hosts[0], net.hosts[1]
    server.cmd('iperf -s -p 5001 & ')

    client.cmd('iperf -c '+ server.IP()+ ' -p 5001 -t '+ str(seconds)+ ' -yc  -i 10 > '+output_dir+'/max_throughput.txt &')
    progress(args.time + 1)
    os.system('killall -9 iperf  iperf3' )

def install_proactive(net, topo):
    """
        Install proactive flow entries for switches.
    """
    pass

def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i 
def progress(t):
    while t > 0:

        print T.colored('  %3d seconds left \r' % (t), 'cyan'),
        t -= 1
        sys.stdout.flush()
        sleep(1)
    print '\r\n'

def cprint(s, color, cr=True):
    """Print in color
       s: string to print
       color: color to use"""
    if cr:
        print T.colored(s, color)
    else:
        print T.colored(s, color),

def enableMPTCP(subflows):
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_debug=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=ndiffports")
    os.system(
        "sudo echo -n %i > /sys/module/mptcp_ndiffports/parameters/num_subflows" % int(subflows))
    # os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=olia")

def enableTCP():
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=0")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=reno")


def enableMDTCP(subflows, shift_g,use_avg_alfa):
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_debug=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=ndiffports")
    os.system(
        "sudo echo -n %i > /sys/module/mptcp_ndiffports/parameters/num_subflows" % int(subflows))
    # os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=mdtcp")
    
    #os.system(
    #    "sudo echo -n %i > /sys/module/mdtcp_coupled/parameters/mdtcp_shift_g" % int(shift_g))
    #os.system("sudo echo -n %i > /sys/module/mdtcp_coupled/parameters/mdtcp_enable_avg_alfa"%use_avg_alfa)
    #os.system("sudo echo -n %i > /sys/module/mdtcp_coupled/parameters/mdtcp_debug"%args.mdtcp_debug)
    


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

def ConfigureOffloadingAndQdisc(args,net):
    # disable offloading on host interfaces
    # nodes = net.hosts
    # for node in nodes:
    #     for port in node.ports:
    #         if str.format('{}', port) != 'lo':
    #             node.cmd(str.format('ethtool --offload {} gro off gso off tso off', port))

    # disable offloading and configure qdisc on switch interfaces
    nodes = net.hosts
    # nodes = net.switches
    for node in nodes:
        for port in node.ports:
            if str.format('{}', port) != 'lo':
                node.cmd(str.format('ethtool --offload {} gro off gso off tso off', port))
                node.cmd(str.format('tc qdisc del dev {} root',port))
                node.cmd(str.format('tc qdisc add dev {} root handle 5:0 htb default 1', port))
                node.cmd(str.format('tc class add dev {} parent 5:0 classid 5:1 htb rate {}Mbit ceil {}Mbit burst 15k', port,args.bw,args.bw))
                node_route = node.cmd("ip route show")
                node_route=node_route.rstrip()
                node.popen('ip route replace %s %s %d %s %s' % (node_route, 'initcwnd', 4,'rto_min','10ms')).wait()
                node.popen('ip route flush cache').wait()
                node.cmd('sysctl -w net.ipv4.tcp_no_metrics_save=1')
                node.cmd('sysctl -w net.ipv4.route.flush=1')                
                # node.cmdPrint('tc -s -d qdisc show dev %s'%port)
                # node.cmdPrint('ip route')

                # cmds += [ '%s qdisc add dev %s root handle 5:0 htb default 1',
                #           '%s class add dev %s parent 5:0 classid 5:1 htb ' +'rate %fMbit burst 15k' % bw ]

                # if args.mdtcp or args.dctcp:
                #     node.cmd(str.format('tc qdisc del dev {} root',port))
                #     node.cmd(str.format('tc qdisc add dev {} root handle 1: htb default 1', port))
                #     node.cmd(str.format('tc class add dev {} parent 1: classid 1:1 htb rate {}Mbit ', port,args.bw))
                #     node.cmd(str.format('tc qdisc add dev {} parent 1:1 handle 2: red limit 1000000 min {} max {} avpkt 1500 burst {} \
                #         bandwidth {} probability 1 ecn', \
                #         args.redmin,args.redmax,args.burst,args.bw, port))
                #     node.cmdPrint('tc -s -d qdisc show dev %s'%port)
                # else:
                #     node.cmd(str.format('tc qdisc del dev {} root',port))
                #     node.cmd(str.format('tc qdisc add dev {} root handle 1: htb default 1', port))
                #     node.cmd(str.format('tc class add dev {} parent 1: classid 1:1 htb rate {}Mbit ', port,args.bw))
                #     node.cmd(str.format('tc qdisc add dev {} parent 1:1 handle 2: red limit 1000000 min 45000 max 90000 avpkt 1500 \
                #         burst 31 bandwidth {} probability 0.1',args.bw, port))
                #     node.cmdPrint('tc -s -d qdisc show dev %s'%port)


    return net

def clean():
    ''' Clean any running instances of POX '''

    p = Popen("ps aux | grep 'pox' | awk '{print $2}'",
            stdout=PIPE, shell=True)
    p.wait()
    procs = (p.communicate()[0]).split('\n')
    for pid in procs:
        try:
            pid = int(pid)
            Popen('kill %d' % pid, shell=True).wait()
        except:
            pass
    Popen("killall -9 top bwm-ng iperf ping", shell=True).wait()

def main():
    top_dir = os.path.join(args.output_dir, 'ft'+str(args.K), args.workload)
    if not os.path.exists(top_dir):
        os.makedirs(top_dir)

    start = time()
    droptail = {'max_queue_size': args.queue}
    red = {'max_queue_size': args.queue,'enable_red':1,'enable_ecn': 0, 'red_burst':31,'red_prob':0.1,\
            'red_avpkt':1500,'red_min':45000, 'red_max':90000,'red_limit':1000000}
    red_ecn = {'max_queue_size': args.queue, \
    'enable_ecn': args.enable_ecn, 'enable_red': args.enable_red,'red_min': args.redmin, \
    'red_max': args.redmax, 'red_burst': args.burst, 'red_prob': args.prob, 'red_avpkt': 1500, 'red_limit': 1000000}

    if args.mdtcp or args.dctcp:
        topo = topoCreate(args.K, args.density,red_ecn, droptail)
    else:
        topo = topoCreate(args.K, args.density,red, droptail)

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
    enableDCTCP()
    if args.test==0:
        get_max_throughput(net, args.output_dir)
    for nflows in [4,3,2,1]:
        cwd = os.path.join(args.output_dir, "flows%dg%d" % (nflows,args.g))
        # Popen("echo > /dev/null | sudo tee /var/log/syslog",shell=True).wait()
        # Popen("echo > /dev/null | sudo tee /var/log/kern.log",shell=True).wait()
        Popen("rm conf/client_* ",shell=True).wait()
        Popen("rm *reqs.out flows_10.* log_10.*  ",shell=True).wait()

        if not os.path.exists(cwd):
            os.makedirs(cwd)

        if args.mdtcp:
            if nflows==1:
                enableDCTCP()
            else:
                enableMDTCP(nflows, args.g,args.avg_alfa)
        elif args.dctcp:
            enableDCTCP()
        else:
            if nflows == 1:
                enableTCP()
            else:
                enableMPTCP(nflows)


        cprint("Starting experiment for workload %s with %i subflows" % (
            args.workload, nflows), "green")

        workload.run(cwd,nflows)

        # Shut down iperf processes
        os.system('killall -9 iperf iperf3 netperf netserver server tcpdump client tg' )
        Popen("rm *reqs.out ",shell=True).wait()

        Popen("mv flows_10.*  %s"%cwd,shell=True).wait()
        Popen("mv log_10.*  %s"%cwd,shell=True).wait()
        sleep(1)

    disableMDTCP()
    net.stop()
 
if __name__ == '__main__':

    setLogLevel( 'output' )
    Popen("killall -9 top bwm-ng iperf ping tg netperf netserver", shell=True).wait()
    try:
        main()
    except:
        print "-"*80
        print "Caught exception.  Cleaning up..."
        print "-"*80
        import traceback
        #reset()
        disableMDTCP()
        traceback.print_exc()
        os.system("killall -9 top bwm-ng tcpdump cat mnexec iperf; mn -c")
    # clean()

   
