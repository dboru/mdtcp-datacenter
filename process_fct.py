import sys
import os
import argparse
import csv
# import matplotlib as m
# import matplotlib.pyplot as plt
import numpy as np
from numpy import average, std
from math import sqrt
from util.helper import *

parser = argparse.ArgumentParser()
parser.add_argument('-f', dest="files", nargs='+', required=True)
parser.add_argument('-o', '--out', dest="out", default=None)
# parser.add_argument('-k', dest="k", default=None)
# parser.add_argument('-w', dest="workload", default=None)
# parser.add_argument('-t', dest="time", type=int, default=None)

args = parser.parse_args()


''' Parse a file to get FCT and goodput results '''
def parse_file(file_name,bw,rtt):
    results = []
    f = open(file_name)

    while True:
        line = f.readline().rstrip()

        if not line:
            break
        arr = line.split(',')
        # Size:34075, Duration(usec):9098403
        
        '''Size:flowsize, Duration(usec):fct'''
        if len(arr) == 2:
            '''[size, fct]'''

            optimal_fct=rtt+(8000000*int(arr[0].split(':')[1]))/bw
            measured_fct=float(arr[1].split(':')[1]);
            normalized_fct=measured_fct/optimal_fct
            results.append([int(arr[0].split(':')[1]), normalized_fct])
            #results.append([int(arr[0].split(':')[1]), int(arr[1].split(':')[1])])
    f.close()
    return results

''' Get average result '''
def average_result(input_tuple_list, index):
    input_list = [x[index] for x in input_tuple_list]
    if len(input_list) > 0:
        return sum(input_list) / len(input_list)
    else:
        return 0
def median_result(input_tuple_list, index):
    input_list = [x[index] for x in input_tuple_list]
    if len(input_list) > 0:
        return np.median(input_list)
    else:
        return 0

''' Get cumulative distribution function (CDF) result '''
def cdf_result(input_tuple_list, index, cdf):
    input_list = [x[index] for x in input_tuple_list]
    input_list.sort()
    if len(input_list) > 0 and cdf >= 0 and cdf <= 1:
        return input_list[int(cdf * len(input_list))]
    else:
        return 0

def average_fct_result(input_tuple_list):
    return average_result(input_tuple_list, 1)

def median_fct_result(input_tuple_list):
    return median_result(input_tuple_list, 1)

def average_goodput_result(input_tuple_list):
    return average_result(input_tuple_list, 2)

def cdf_fct_result(input_tuple_list, cdf):
    return cdf_result(input_tuple_list, 1, cdf)

def cdf_goodput_result(input_tuple_list, cdf):
    return cdf_result(input_tuple_list, 2, cdf)


def compute_fct_stats(results,subflow):
     # (0, 100KB)
    small = filter(lambda x: x[0] < 100 * 1024, results['size_fct'][subflow])

    # (100KB, 10MB)
    medium = filter(lambda x: 100 * 1024 <= x[0] < 10 * 1024 * 1024, results['size_fct'][subflow])
    # (10MB, infi)
    large = filter(lambda x: x[0] >= 10 * 1024 * 1024, results['size_fct'][subflow])
    results[subflow]={}
    total_transfer=0
    for size in results['size_fct'][subflow]:
        total_transfer=total_transfer+size[0]
    total_transfer=total_transfer/(1024.0*1024.0*1024.0)

    results[subflow]['overall']=float(average_fct_result(results['size_fct'][subflow]))
    results[subflow]['(0, 100KB)']=float(average_fct_result(small))
    results[subflow]['(0, 100KB)_50']=float(median_fct_result(small))
    results[subflow]['(0, 100KB)_95']=float(cdf_fct_result(small, 0.95))
    results[subflow]['(0, 100KB)_99']=float(cdf_fct_result(small, 0.99))

    
    results[subflow]['[100KB, 10MB)']=float(average_fct_result(medium))
    results[subflow]['[100KB, 10MB)_50']=float(median_fct_result(medium))
    results[subflow]['[100KB, 10MB)_95']=float(cdf_fct_result(medium, 0.95))
    results[subflow]['[100KB, 10MB)_99']=float(cdf_fct_result(medium,0.99))
    
    results[subflow]['[10MB, )']=float(average_fct_result(large))
    results[subflow]['[10MB, )_50']=float(median_fct_result(large))
    results[subflow]['[10MB, )_95']=float(cdf_fct_result(large, 0.95))
    results[subflow]['[10MB, )_99']=float(cdf_fct_result(large,0.99))
    results[subflow]['total_GB']=total_transfer
    return results



    # print '%d flows/requests overall average completion time: %d us' % (len(results), average_fct_result(results))
    # print '%d flows/requests (0, 100KB) average completion time: %d us' % (len(small), average_fct_result(small))
    # print '%d flows/requests (0, 100KB) 99th percentile completion time: %d us' % (len(small), cdf_fct_result(small, 0.99))
    # print '%d flows/requests [100KB, 10MB) average completion time: %d us' % (len(medium), average_fct_result(medium))
    # print '%d flows/requests [10MB, ) average completion time: %d us' % (len(large), average_fct_result(large))
    # print '%d flows/requests overall average goodput: %d Mbps' % (len(results), average_goodput_result(results))

def plot_fct(results):
    m.rc('figure', figsize=(8, 6))
    m.rcParams['font.family'] = 'sans'
    m.rcParams['font.style']='normal'
    m.rcParams['font.size']=10
    fig = plt.figure()
    # m.rc('figure', figsize=(8, 6))
    axPlot = fig.add_subplot(2, 1, 1)
    axPlot.grid(True)
    patterns=['-','+','x','\\\\','*','o','0','.']
   
    colors = ['red','blue','green','cyan','magenta', '#ff0000','yellow', '#4B0082','#8F00FF','#ff0000','#ff7f00','#ffff00','#00ff00','#00ffff', '#0000ff', '#4B0082','#8F00FF']
    # colors=['red','blue','magenta']
    hatches=['//','\\','++/','xx','*','o//','//--','\\.']
    fct=[]
    N=3;
    xaxis = np.arange(N)  # the x locations for the groups
    width = 0.1 
    xoffset = 0.1

    flows=[1,4]
    # flows=[1,2,3,4]
    sizes=['(0, 100KB)_n','[100KB, 10MB)_n','[10MB, )_n']
    xticklabel=['<100KB','100KB-10MB','>=10MB']
    bars=''
    j=0
    for f in flows:
        y=[]
        for s in sizes:
            y.append(results[str(f)][s])
        axPlot.bar(xaxis + (f-1)*xoffset, y, width,label=str(f), color=colors[j],edgecolor='black',hatch=hatches[j]) #, yerr=menStd)
        j=j+1
        if(j==len(colors)):
            j=0
        

    # axPlot.legend(loc='upper right',ncol=2,columnspacing=0.3,title='No.subflows')
    axPlot.set_xlim(xmin=-0.1,xmax=2.85)
    # axPlot.set_ylim(ymax=1.05)
    axPlot.set_ylabel("Normalized mean FCT")
    # axPlot.set_xlabel("Flow sizes",fontsize=14)
    axPlot.set_xticklabels(xticklabel)
    axPlot.set_xticks(xaxis + 0.35)
    axPlot.legend(loc='upper center', bbox_to_anchor=(0.5, 1.3),fancybox=True, columnspacing=0.3,shadow=True, ncol=8,title='No. subflows')
    

    axPlot = fig.add_subplot(2, 1, 2)
    axPlot.grid(True)
    sizes=['(0, 100KB)_99_n','[100KB, 10MB)_99_n','[10MB, )_99_n']

    j=0
    for f in flows:
        y=[]
        for s in sizes:
            y.append(results[str(f)][s])
        axPlot.bar(xaxis + (f-1)*xoffset, y, width,label=str(f), color=colors[j],edgecolor='black',hatch=hatches[j]) #, yerr=menStd)
        j=j+1
        if(j==len(colors)):
            j=0
    
    # axPlot.legend(loc='upper right',ncol=2,columnspacing=0.3,title='No.subflows')
    axPlot.set_xlim(xmin=-0.1,xmax=2.85)
    # axPlot.set_ylim(ymax=1.05)
    axPlot.set_ylabel("Normalized 99th FCT")
    axPlot.set_xlabel("Flow size")
    axPlot.set_xticklabels(xticklabel)
    axPlot.set_xticks(xaxis + 0.35)
    plt.savefig(args.out)


    fig = plt.figure()

    axPlot = fig.add_subplot(2, 1, 1)
    axPlot.grid(True)

    sizes=['(0, 100KB)','[100KB, 10MB)','[10MB, )']

    xticklabel=['<100KB','100KB-10MB','>=10MB']
    j=0
    for f in flows:
        y=[]
        for s in sizes:
            y.append(results[str(f)][s])
        axPlot.bar(xaxis + (f-1)*xoffset, y, width,label=str(f), color=colors[j],edgecolor='black',hatch=hatches[j]) #, yerr=menStd)
        j=j+1
        if(j==len(colors)):
            j=0
        

    # axPlot.legend(loc='upper right',ncol=2,columnspacing=0.3,title='No.subflows')
    axPlot.set_xlim(xmin=-0.1,xmax=2.85)
    # axPlot.set_ylim(ymax=1.05)
    axPlot.set_ylabel("Average FCT [ms]")
    # axPlot.set_xlabel("Flow sizes",fontsize=14)
    axPlot.set_xticklabels(xticklabel)
    axPlot.set_xticks(xaxis + 0.35)
    axPlot.legend(loc='upper center', bbox_to_anchor=(0.5, 1.3),fancybox=True, columnspacing=0.3,shadow=True, ncol=8,title='No. subflows')

    axPlot = fig.add_subplot(2, 1, 2)
    axPlot.grid(True)

    sizes=['(0, 100KB)_99','[100KB, 10MB)_99','[10MB, )_99']

    j=0
    for f in flows:
        y=[]
        for s in sizes:
            y.append(results[str(f)][s])
        axPlot.bar(xaxis + (f-1)*xoffset, y, width,label=str(f), color=colors[j],edgecolor='black',hatch=hatches[j]) #, yerr=menStd)
        j=j+1
        if(j==len(colors)):
            j=0
    
    # axPlot.legend(loc='upper right',ncol=2,columnspacing=0.3,title='No.subflows')
    axPlot.set_xlim(xmin=-0.1,xmax=2.85)
    # axPlot.set_ylim(ymax=1.05)
    axPlot.set_ylabel("99th FCT [ms]")
    axPlot.set_xlabel("Flow size")
    axPlot.set_xticklabels(xticklabel)
    axPlot.set_xticks(xaxis + 0.35)
    plt.savefig(args.out+'real.png')



    # plt.show()

    fig = plt.figure()

    axPlot = fig.add_subplot(2, 1, 1)
    axPlot.grid(True)
    sizes=['(0, 100KB)_50_n','[100KB, 10MB)_50_n','[10MB, )_50_n']

    j=0
    for f in flows:
        y=[]
        for s in sizes:
            y.append(results[str(f)][s])
        axPlot.bar(xaxis + (f-1)*xoffset, y, width,label=str(f), color=colors[j],edgecolor='black',hatch=hatches[j]) #, yerr=menStd)
        j=j+1
        if(j==len(colors)):
            j=0
        

    # axPlot.legend(loc='upper center',ncol=2,columnspacing=0.3,title='No.subflows')
    axPlot.legend(loc='upper center', bbox_to_anchor=(0.5, 1.3),fancybox=True, columnspacing=0.3,shadow=True, ncol=8,title='No. subflows')

    axPlot.set_xlim(xmin=-0.1,xmax=2.85)
    # axPlot.set_ylim(ymax=1.05)
    axPlot.set_ylabel("Normalized Median FCT")
    axPlot.set_xlabel("Flow Size")
    axPlot.set_xticklabels(xticklabel)
    axPlot.set_xticks(xaxis + 0.35)

    axPlot = fig.add_subplot(2, 1, 2)
    axPlot.grid(True)
    sizes=['(0, 100KB)_50','[100KB, 10MB)_50','[10MB, )_50']

    j=0
    for f in flows:
        y=[]
        for s in sizes:
            y.append(results[str(f)][s])
        axPlot.bar(xaxis + (f-1)*xoffset, y, width,label=str(f), color=colors[j],edgecolor='black',hatch=hatches[j]) #, yerr=menStd)
        j=j+1
        if(j==len(colors)):
            j=0
        
    
    # axPlot.legend(loc='upper right',ncol=2,columnspacing=0.3,title='No.subflows')
    axPlot.set_xlim(xmin=-0.1,xmax=2.85)
    # axPlot.set_ylim(ymax=1.05)
    axPlot.set_ylabel("Median FCT")
    axPlot.set_xlabel("Flow Size")
    axPlot.set_xticklabels(xticklabel)
    axPlot.set_xticks(xaxis + 0.35)
    plt.savefig(args.out+'median.png')

    

if __name__ == '__main__':

    # fct-bw10g-2delay-0.025avgalfa-1num_reqs-50ft-8
    final_results={'size_fct':{}}
    # num_file_parse=0
    psubflow=0;
    load=0
    protocol=''
    for f in args.files:
        bw=1000*1000*float(f.split('bw')[1].split('delay')[0])
        rtt=float(f.split('delay')[1].split('ft')[0])
        srcdst=f.split('_10')
        srcr=srcdst[1].split('.')
        src=[srcr[1],srcr[2],srcr[3][0]]
        dstr=srcdst[2].split('.')
        dst=[dstr[1],dstr[2],dstr[3][0]]
        if int(src[0])==int(dst[0]) and int(src[1])==int(dst[1]):
            rtt=2000*rtt
        elif int(src[0])==int(dst[0]) and int(src[1])!=int(dst[1]):
             rtt=4000*rtt
        elif int(src[0])!=int(dst[0]):
             rtt=6000*rtt
        if load == 0:
            load=float(f[f.find('load')+len('load')+2])/10
        if 'mptcp' in f:
            protocol='mptcp'
        elif 'mdtcp' in f:
            protocol='mdtcp'

        
        subflow = f[f.find('flows') + len('flows')]
        if psubflow<subflow:
            if psubflow>0:
                final_results=compute_fct_stats(final_results,psubflow)
            psubflow=subflow
            final_results['size_fct'][subflow]=[]
        
        if os.path.isfile(f):
            final_results['size_fct'][subflow].extend(parse_file(f,bw,rtt))
            # num_file_parse = num_file_parse + 1
    final_results=compute_fct_stats(final_results,psubflow)
    # print('subflow','load','overall','avg_(0, 100KB)','avg_[100KB, 10MB)','avg_[10MB, )',\
    #'median_(0, 100KB)','median_[100KB, 10MB)','median_[10MB, )',\
    #'99th_(0, 100KB)','99th_[100KB, 10MB)','99th_[10MB, )')

    with open('fct_mptcp_mdtcp_websearch_181225',mode='a') as csv_file:
        fct_writer=csv.writer(csv_file,delimiter=',')
        nflows=[1,2,3,4]
        for i in nflows:

            fct_writer.writerow([protocol,i,load,final_results[str(i)]['overall'],final_results[str(i)]['(0, 100KB)'],\
                final_results[str(i)]['[100KB, 10MB)'],final_results[str(i)]['[10MB, )'],\
                final_results[str(i)]['(0, 100KB)_50'],final_results[str(i)]['[100KB, 10MB)_50'],final_results[str(i)]['[10MB, )_50'],\
                final_results[str(i)]['(0, 100KB)_99'],final_results[str(i)]['[100KB, 10MB)_99'],final_results[str(i)]['[10MB, )_99'],\
                final_results[str(i)]['total_GB']])

            if i == 1:
                final_results[str(i)]['overall_n']=1.0
               
                final_results[str(i)]['(0, 100KB)_n']=1.0
                final_results[str(i)]['(0, 100KB)_50_n']=1.0
                final_results[str(i)]['(0, 100KB)_95_n']=1.0
                final_results[str(i)]['(0, 100KB)_99_n']=1.0
                

                final_results[str(i)]['[100KB, 10MB)_n']=1.0
                final_results[str(i)]['[100KB, 10MB)_50_n']=1.0
                final_results[str(i)]['[100KB, 10MB)_95_n']=1.0
                final_results[str(i)]['[100KB, 10MB)_99_n']=1.0

                final_results[str(i)]['[10MB, )_n']=1.0
                final_results[str(i)]['[10MB, )_50_n']=1.0
                final_results[str(i)]['[10MB, )_95_n']=1.0
                final_results[str(i)]['[10MB, )_99_n']=1.0
            else:
                final_results[str(i)]['overall_n']=float(final_results[str(i)]['overall']/final_results[str(1)]['overall'])
                
                final_results[str(i)]['(0, 100KB)_n']=float(final_results[str(i)]['(0, 100KB)']/final_results[str(1)]['(0, 100KB)'])
                
                final_results[str(i)]['(0, 100KB)_50_n']=float(final_results[str(i)]['(0, 100KB)_50']/final_results[str(1)]['(0, 100KB)_50'])
                final_results[str(i)]['(0, 100KB)_95_n']=float(final_results[str(i)]['(0, 100KB)_95']/final_results[str(1)]['(0, 100KB)_95'])
                final_results[str(i)]['(0, 100KB)_99_n']=float(final_results[str(i)]['(0, 100KB)_99']/final_results[str(1)]['(0, 100KB)_99'])

                final_results[str(i)]['[100KB, 10MB)_n']=float(final_results[str(i)]['[100KB, 10MB)']/final_results[str(1)]['[100KB, 10MB)'])
                final_results[str(i)]['[100KB, 10MB)_50_n']=float(final_results[str(i)]['[100KB, 10MB)_50']/final_results[str(1)]['[100KB, 10MB)_50'])
                final_results[str(i)]['[100KB, 10MB)_95_n']=float(final_results[str(i)]['[100KB, 10MB)_95']/final_results[str(1)]['[100KB, 10MB)_95'])
                final_results[str(i)]['[100KB, 10MB)_99_n']=float(final_results[str(i)]['[100KB, 10MB)_99']/final_results[str(1)]['[100KB, 10MB)_99'])
                

                final_results[str(i)]['[10MB, )_n']=float(final_results[str(i)]['[10MB, )']/final_results[str(1)]['[10MB, )'])
                final_results[str(i)]['[10MB, )_50_n']=float(final_results[str(i)]['[10MB, )_50']/final_results[str(1)]['[10MB, )_50'])
                final_results[str(i)]['[10MB, )_95_n']=float(final_results[str(i)]['[10MB, )_95']/final_results[str(1)]['[10MB, )_95'])
                final_results[str(i)]['[10MB, )_99_n']=float(final_results[str(i)]['[10MB, )_99']/final_results[str(1)]['[10MB, )_99'])





        # print (i,load,final_results[str(i)]['overall_n'],final_results[str(i)]['(0, 100KB)_n'],\
        #     final_results[str(i)]['[100KB, 10MB)_n'],final_results[str(i)]['[10MB, )_n'],\
        #     final_results[str(i)]['(0, 100KB)_50_n'],final_results[str(i)]['[100KB, 10MB)_50_n'],final_results[str(i)]['[10MB, )_50_n'],\
        #     final_results[str(i)]['(0, 100KB)_99_n'],final_results[str(i)]['[100KB, 10MB)_99_n'],final_results[str(i)]['[10MB, )_99_n'])

    plot_fct(final_results)
        # print (final_results[str(i)]['(0, 100KB)'])
    


    
    # if len(sys.argv) < 2:
    #     print 'Usages: %s <file1> [file2 ...]' % sys.argv[0]
    #     sys.exit()

    # files = sys.argv[1:]
    # final_results = []
    # num_file_parse = 0

    # for f in files:
    #     if os.path.isfile(f):
    #         final_results.extend(parse_file(f))
    #         num_file_parse = num_file_parse + 1

    # if num_file_parse <= 1:
    #     print "Parse %d file" % num_file_parse
    # else:
    #     print "Parse %d files" % num_file_parse

    # print_result(final_results)
