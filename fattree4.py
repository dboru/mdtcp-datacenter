# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, China.
# Copyright (C) 2016 Li Cheng at Beijing University of Posts
# and Telecommunications. www.muzixing.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import Link, TCLink
from mininet.topo import Topo
from mininet.util import dumpNodeConnections
from mininet.link import TCIntf
import random
from time import sleep, time
from subprocess import Popen, PIPE
import termcolor as T
# from argparse import ArgumentParser

# from workloads import OneToOneWorkload, OneToSeveralWorkload, AllToAllWorkload, progress

import logging
import os


class Fattree(Topo):
    """
            Class of Fattree Topology.
    """
    CoreSwitchList = []
    AggSwitchList = []
    EdgeSwitchList = []
    HostList = []

    def __init__(self, k, density):
        self.pod = k
        self.density = density
        self.iCoreLayerSwitch = (k / 2)**2
        self.iAggLayerSwitch = k * k / 2
        self.iEdgeLayerSwitch = k * k / 2
        self.iHost = self.iEdgeLayerSwitch * density

        # Init Topo
        Topo.__init__(self)

    def createNodes(self):
        self.createCoreLayerSwitch(self.iCoreLayerSwitch)
        self.createAggLayerSwitch(self.iAggLayerSwitch)
        self.createEdgeLayerSwitch(self.iEdgeLayerSwitch)
        self.createHost(self.iHost)

    # Create Switch and Host
    def _addSwitch(self, number, level, switch_list):
        """
                Create switches.
        """
        for i in xrange(1, number + 1):
            PREFIX = str(level) + "00"
            if i >= 10:
                PREFIX = str(level) + "0"
            switch_list.append(self.addSwitch(PREFIX + str(i)))

    def createCoreLayerSwitch(self, NUMBER):
        self._addSwitch(NUMBER, 1, self.CoreSwitchList)

    def createAggLayerSwitch(self, NUMBER):
        self._addSwitch(NUMBER, 2, self.AggSwitchList)

    def createEdgeLayerSwitch(self, NUMBER):
        self._addSwitch(NUMBER, 3, self.EdgeSwitchList)

    def createHost(self, NUMBER):
        """
                Create hosts.
        """
        for i in xrange(1, NUMBER + 1):
            if i >= 100:
                PREFIX = "h"
            elif i >= 10:
                PREFIX = "h0"
            else:
                PREFIX = "h00"
            self.HostList.append(self.addHost(
                PREFIX + str(i), cpu=1.0 / NUMBER))

    def createLinks(self, sw2sw, edge2h):
        """
                Add network links.
        """
        # Core to Agg
        end = self.pod / 2
        for x in xrange(0, self.iAggLayerSwitch, end):
            for i in xrange(0, end):
                for j in xrange(0, end):
                    self.addLink(
                        self.CoreSwitchList[i * end + j],
                        self.AggSwitchList[x + i], cls=Link, cls1=TCIntf, cls2=TCIntf, params1=sw2sw, params2=sw2sw)

        # Agg to Edge
        for x in xrange(0, self.iAggLayerSwitch, end):
            for i in xrange(0, end):
                for j in xrange(0, end):
                    self.addLink(
                        self.AggSwitchList[x + i], self.EdgeSwitchList[x + j],
                        cls=Link, cls1=TCIntf, cls2=TCIntf, params1=sw2sw, params2=sw2sw)   # use_htb=False

        # Edge to Host
        for x in xrange(0, self.iEdgeLayerSwitch):
            for i in xrange(0, self.density):
                self.addLink(
                    self.EdgeSwitchList[x],
                    self.HostList[self.density * x + i],
                    cls=Link, cls1=TCIntf, cls2=TCIntf, params1=sw2sw, params2=edge2h)   # use_htb=False

    def set_ovs_protocol_13(self):
        """
                Set the OpenFlow version for switches.
        """
        self._set_ovs_protocol_13(self.CoreSwitchList)
        self._set_ovs_protocol_13(self.AggSwitchList)
        self._set_ovs_protocol_13(self.EdgeSwitchList)

    def _set_ovs_protocol_13(self, sw_list):
        for sw in sw_list:
            cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
            os.system(cmd)


def set_host_ip(net, topo):
    hostlist = []
    for k in xrange(len(topo.HostList)):
        hostlist.append(net.get(topo.HostList[k]))
    i = 1
    j = 1
    for host in hostlist:
        host.setIP("10.%d.0.%d" % (i, j))
        j += 1
        if j == topo.density + 1:
            j = 1
            i += 1


def create_subnetList(topo, num):
    """
            Create the subnet list of the certain Pod.
    """
    subnetList = []
    remainder = num % (topo.pod / 2)
    if topo.pod == 4:
        if remainder == 0:
            subnetList = [num - 1, num]
        elif remainder == 1:
            subnetList = [num, num + 1]
        else:
            pass
    elif topo.pod == 8:
        if remainder == 0:
            subnetList = [num - 3, num - 2, num - 1, num]
        elif remainder == 1:
            subnetList = [num, num + 1, num + 2, num + 3]
        elif remainder == 2:
            subnetList = [num - 1, num, num + 1, num + 2]
        elif remainder == 3:
            subnetList = [num - 2, num - 1, num, num + 1]
        else:
            pass
    else:
        pass
    return subnetList


def install_proactive(net, topo):
    """
            Install proactive flow entries for switches.
    """
    # Edge Switch
    for sw in topo.EdgeSwitchList:
        num = int(sw[-2:])

        # Downstream.
        for i in xrange(1, topo.density + 1):
            cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
                'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
                nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod / 2 + i)
            os.system(cmd)
            cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
                'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
                nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod / 2 + i)
            os.system(cmd)

        # Upstream.
        if topo.pod == 4:
            cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
            'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
        elif topo.pod == 8:
            cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
            'group_id=1,type=select,bucket=output:1,bucket=output:2,\
            bucket=output:3,bucket=output:4'" % sw
        else:
            pass
        os.system(cmd)
        cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
        'table=0,priority=10,arp,actions=group:1'" % sw
        os.system(cmd)
        cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
        'table=0,priority=10,ip,actions=group:1'" % sw
        os.system(cmd)

    # Aggregate Switch
    for sw in topo.AggSwitchList:
        num = int(sw[-2:])
        subnetList = create_subnetList(topo, num)

        # Downstream.
        k = 1
        for i in subnetList:
            cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
                'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
                nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod / 2 + k)
            os.system(cmd)
            cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
                'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
                nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod / 2 + k)
            os.system(cmd)
            k += 1

        # Upstream.
        if topo.pod == 4:
            cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
            'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
        elif topo.pod == 8:
            cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
            'group_id=1,type=select,bucket=output:1,bucket=output:2,\
            bucket=output:3,bucket=output:4'" % sw
        else:
            pass
        os.system(cmd)
        cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
        'table=0,priority=10,arp,actions=group:1'" % sw
        os.system(cmd)
        cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
        'table=0,priority=10,ip,actions=group:1'" % sw
        os.system(cmd)

    # Core Switch
    for sw in topo.CoreSwitchList:
        j = 1
        k = 1
        for i in xrange(1, len(topo.EdgeSwitchList) + 1):
            cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
                'table=0,idle_timeout=0,hard_timeout=0,priority=10,arp, \
                nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, j)
            os.system(cmd)
            cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
                'table=0,idle_timeout=0,hard_timeout=0,priority=10,ip, \
                nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, j)
            os.system(cmd)
            k += 1
            if k == topo.pod / 2 + 1:
                j += 1
                k = 1


def iperfTest(net, topo):
    """
            Start iperf test.
    """
    h001, h015, h016 = net.get(
        topo.HostList[0], topo.HostList[14], topo.HostList[15])
    # iperf Server
    h001.popen('iperf -s -u -i 1 > iperf_server_differentPod_result', shell=True)
    # iperf Server
    h015.popen('iperf -s -u -i 1 > iperf_server_samePod_result', shell=True)
    # iperf Client
    h016.cmdPrint('iperf -c ' + h001.IP() + ' -u -t 10 -i 1 -b 10m')
    h016.cmdPrint('iperf -c ' + h015.IP() + ' -u -t 10 -i 1 -b 10m')


# def get_workload(net, aworkload="one_to_one"):
#     if aworkload == "one_to_one":
#         return OneToOneWorkload(net, 'iperf', 30)
#     elif aworkload == "one_to_several":
#         return OneToSeveralWorkload(net, 'iperf', 30)
#     else:
#         return AllToAllWorkload(net, 'iperf', 30)


def iperfTcpTest(net, topo, runtime):
    """
            Start iperf test.
    """
    Popen("tcpdump -i 3003-eth4 -s 96 -w pkt-dump", shell=True)
    for i in range(5):
        serv = net.get(topo.HostList[5])
        clnt = net.get(topo.HostList[i])
        if i == 4:

            serv.popen("iperf -s -i 1 ")
            serv.popen("netserver ")
            # clnt.popen("ping "+ serv.IP() + " -c 1000 -i 1 > mdtcp_sf4_clnt_%s_serv_%s &" %(clnt,serv),shell=True)
            clnt.cmdPrint("netperf -H " + serv.IP() +
                          " -t TCP_RR -l 60 -D 1 -- -r 256,256 -o P50_LATENCY,P90_LATENCY,P99_LATENCY > netperf_sender%s_serv%s.txt &" % (clnt, serv))
            clnt.popen("iperf -c " + serv.IP() +
                       "  -t %i -i 1  > clnt_%s_serv_%s &" % (int(runtime), clnt, serv), shell=True)

        else:
            serv.popen("iperf -s -i 1 ")
            clnt.popen("iperf -c " + serv.IP() +
                       "  -t %i -i 1  > clnt_%s_serv_%s &" % (int(runtime), clnt, serv), shell=True)

    start_time = time()
    while True:
        now = time()
        delta = now - start_time
        if delta > int(runtime):
            break
    Popen("killall -s 9 tcpdump", shell=True).wait()
    Popen("killall -s 9 netperf", shell=True).wait()


def enableMPTCP():
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=ndiffports")
    os.system(
        "sudo echo -n 4 > /sys/module/mptcp_ndiffports/parameters/num_subflows")
    # os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=olia")


def enableMDTCP(subflows, shift_g):
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
    # os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=dctcp")


def disableMDTCP():
    os.system("sudo sysctl -w net.ipv4.tcp_ecn=0")
    os.system("sudo sysctl -w net.mptcp.mptcp_enabled=1")
    os.system("sudo sysctl -w net.mptcp.mptcp_path_manager=fullmesh")
    os.system("sudo sysctl -w net.ipv4.tcp_congestion_control=olia")


def pingTest(net):
    """
            Start ping test.
    """
    net.pingAll()


# def cprint(s, color, cr=True):
#     """Print in color
#        s: string to print
#        color: color to use"""
#     if cr:
#         print T.colored(s, color)
#     else:
#         print T.colored(s, color),


def topoCreate(pod, density, sw2sw, edge2h):
    topo = Fattree(pod, density)
    topo.createNodes()
    topo.createLinks(sw2sw, edge2h)

    return topo


# def createTopo(pod, density, ip="127.0.0.1", port=6633, bw_c2a=5, bw_a2e=5, bw_e2h=5):
#     """
#             Create network topology and run the Mininet.
#     """
#     # Create Topo.
#     topo = Fattree(pod, density)
#     topo.createNodes()
#     topo.createLinks(bw_c2a=bw_c2a, bw_a2e=bw_a2e, bw_e2h=bw_e2h)

#     # Start Mininet.
#     CONTROLLER_IP = ip
#     CONTROLLER_PORT = port
#     net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
#     net.addController(
#         'controller', controller=RemoteController,
#         ip=CONTROLLER_IP, port=CONTROLLER_PORT)
#     net.start()

#     # Set OVS's protocol as OF13.
#     topo.set_ovs_protocol_13()
#     # Set hosts IP addresses.
#     set_host_ip(net, topo)
#     # Install proactive flow entries
#     install_proactive(net, topo)
#     # dumpNodeConnections(net.hosts)

#     workload = get_workload(net)
#     # net.pingAll()
#     # sleep(3)

#     pingTest(net)
#     # iperfTest(net, topo)
#     # tcp test
#     enableMDTCP()
#     # enableDCTCP()
#     # enableMDTCP()

#     for nflows in range(1, 2):
#         cwd = os.path.join("test-mptcp", "flows%d" % nflows)

#         if not os.path.exists(cwd):
#             os.makedirs(cwd)
#         # enable_mptcp(nflows)
#         wtype = 'one_to_one'

#         cprint("Starting experiment for workload %s with %i subflows" % (
#             wtype, nflows), "green")

#         workload.run(cwd, False)

#         # Shut down iperf processes
#         # os.system('killall -9 ' + CUSTOM_IPERF_PATH)

#     # iperfTcpTest(net, topo, 60)

#     disableMDTCP()

#     # CLI(net)
#     net.stop()


# if __name__ == '__main__':
#     setLogLevel('info')
#     if os.getuid() != 0:
#         logging.debug("You are NOT root")
#     elif os.getuid() == 0:
#         createTopo(4, 2)
#         # createTopo(8, 4)
