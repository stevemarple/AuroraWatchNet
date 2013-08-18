#!/usr/bin/env python

import math
import matplotlib as mpl
import os
from numpy.f2py.auxfuncs import throw_error
from logging import exception
if os.environ.get("DISPLAY", "") == "":
    mpl.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
    
# import matplotlib.pyplot as plt
    
import datetime
import math
import numpy as np
import pandas as pd
import pylab

from optparse import OptionParser
import time

epoch = datetime.datetime(1970,1,1)

# TODO: Put in shared library
def roundTime(t, to, function=round):
    # Convert datetime or date to datetime
    global epoch
    fromEpoch = (datetime.datetime(*t.timetuple()[:6]) -
                 epoch).total_seconds()
    try:
        if t >= epoch:
            fromEpoch += t.microsecond/1e6
        else:
            fromEpoch -= t.microsecond/1e6
    except:
        pass
    rts = to.total_seconds() + to.microseconds/1e6
    return (int(function((fromEpoch / rts))) * to) + epoch


def labelPlot(ax, starttime, endtime, units):
    if units == 's':
        multiplier = 1
    elif units == 'ms':
        multiplier = 1e-3
    elif units == 'us':
        multiplier = 1e-6
    else:
        raise exception("Unknown time unit")

    st = starttime * multiplier
    et = endtime * multiplier
    ax.set_xlim(starttime, endtime, auto=False)
    #ax.set_autoscalex_on(False)
    # plt.setp(ax, xlim=[starttime, endtime])
    # ax.set(xlim=[starttime, endtime])
    print('starttime: ' + str(starttime))
    
    # step = 3 * 3600 / multiplier
    step = 4 * 3600 / multiplier
    xticks = np.arange(starttime, endtime+step, step)
    # xticklabels = ['00', '03', '06', '09', '12', '15', '18', '21', '00']
    xticklabels = ['00', '04', '08', '12', '16', '20', '00']
    print(xticks)
    minorLocator = mpl.ticker.AutoMinorLocator(n=4)
    ax.xaxis.set_minor_locator(minorLocator)
    mpl.pyplot.grid(True, axes=ax, which='major', linestyle=':')
    mpl.pyplot.grid(True, axes=ax, which='minor', linestyle=':', 
                    color=[0.7, 0.7, 0.7])
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)
    ax.set_xlabel('Time (UT)')
    degree_sign= u'\N{DEGREE SIGN}'
    ax.set_ylabel('Temperature (' + degree_sign + 'C)')
    ax.set_title('Cloud detection')
    ax.tick_params(direction='out')


def calc_dew_point(T, RH, a=6.1121, b=18.678, c=257.14, d=234.5):
    # Calculate dew point using Arden-Buck equation

    P_sat_mod = a * np.exp((b - (T/a)) * (T / (c+T)))

    gamma_mod = np.log((RH/100) * np.exp( (b - (T/d)) * (T / (c+T))))

    return (c * gamma_mod) / (b - gamma_mod)

def calc_cloud_temp_height(T, T_dp):
    # Difference between dry adiabatic lapse rate and dew lapse rate
    # is 8K per 1000 metres
    height = 125 * (T - T_dp) 
    temp = T - (0.0098 * height)
    return temp, height
# ==========================================================================

# Parse command line options
optParser = OptionParser()
# optParser.add_option("-c", "--config-file", dest="configFile",
#                      default="/etc/awnet.ini",
#                      help="Configuration file")
# optParser.add_option("--acknowledge", action="store_true",
#                      dest="acknowledge", default=True,
#                      help="Transmit acknowledgement");
optParser.add_option("--date", dest="date");
optParser.add_option("-v", "--verbose", dest="verbosity", action="count", 
                     default=0, help="Increase verbosity")

(options, args) = optParser.parse_args()

outfilename = "/tmp/cloud.png"
if options.date is None or options.date == "today": 
    date = roundTime(datetime.datetime.utcnow(), 
                          datetime.timedelta(days=1),
                          math.floor)
    outfilename = "/tmp/today.png"
elif options.date == "yesterday":
    date = roundTime(datetime.datetime.utcnow(), 
                          datetime.timedelta(days=1),
                          math.floor) - datetime.timedelta(days=1)
    outfilename = "/tmp/yesterday.png"
else:
    date = datetime.datetime.strptime(options.date, "%Y-%m-%d")
print("Date: " + date.isoformat())

# # Convert date to datetime64 in microseconds
# td = date - epoch
# starttime = np.int64((td.days * 86400000000L) + (td.seconds * 1000000)
#                      + td.microseconds)
# endtime = starttime + 86400000000L

# Convert date to seconds since 1970
td = date - epoch
starttime = (td.days * 86400) + td.seconds + float(td.microseconds)*1e-6
endtime = starttime + 86400


fstr = "/data/aurorawatch/net/test2/%Y/%m/test2_%Y%m%d_cloud.txt"
filename = date.strftime(fstr)
print("loading " + filename)

if 0:
    fromtimestamp = lambda x:datetime.datetime.fromtimestamp(float(x))
    data = pd.read_csv(filename, sep=None, 
                       names=['timestamp', 'ambient', 'sky'],
                       converters={'timestamp': fromtimestamp})
elif 0:
    fromtimestamp = lambda x:datetime.datetime.utcfromtimestamp(float(x))
    data = pd.read_csv(filename, sep=None, 
                       names=['timestamp', 'ambient', 'sky'],
                       converters={'timestamp': fromtimestamp})
elif 0:
    fromtimestamp = lambda x:np.int64(float(x)*1e6).astype('M8[us]')
    data = pd.read_csv(filename, sep=None, 
                       names=['timestamp', 'ambient', 'sky'],
                       converters={'timestamp': fromtimestamp})
else:
    data = pd.read_csv(filename, sep=None, 
                       names=['timestamp', 'detector', 'sky', 'ambient', 'RH'])

#data.set_index(pd.DatetimeIndex(data['timestamp']), inplace=True)
#data.set_index(np.int64(data['timestamp'] * 1000000L), inplace=True)

#data.set_index(data['timestamp'], inplace=True)
data.set_index((data['timestamp'] + 0.5).astype('int'), inplace=True)

data.sort('timestamp', inplace=True)
data.drop_duplicates(cols='timestamp', inplace=True)


data.ambient[data.ambient > 50] = np.nan
data.ambient[data.ambient < -40] = np.nan
data.sky[data.sky > 50] = np.nan
data.sky[data.sky < -40] = np.nan


# print(data['timestamp'].values)
#ts = np.int64(data['timestamp']*1e6).astype('M8[us]')
#print(ts.values)
#print(data)
#print("Index: ")
#print(data.index)
#data.set_index(ts, inplace=True)
#print(data)
#data.set_index(pd.DatetimeIndex(data['timestamp']), inplace=True)
#data.set_index(pd.DatetimeIndex(samt), inplace=True)
#data.set_index(samt, inplace=True)
data['tempdiff'] = data['ambient'] - data['sky']
data['dew_point'] = calc_dew_point(data['ambient'], data['RH'])
data['cloudtemp'], data['cloudbase'] = \
    calc_cloud_temp_height(data['ambient'], data['dew_point'])

# print(data.index.dtype)

# print(data)
#tsAmbient = pd.Series(data['ambient'], data['timestamp'])
#tsAmbient.plot()

#tsSky = pd.Series(data['sky'], data['timestamp'])
#tsSky.plot()


#pylab.plot(data['timestamp'], data['ambient'])
#pylab.show()
fig, ax = plt.subplots()

print("XLIM: ")
print(ax.get_xlim())
print(np.diff(ax.get_xlim()))

data['ambient'].plot(ax=ax, color=[0, 0.6, 0])
data['sky'].plot(ax=ax, color='b')
data['detector'].plot(ax=ax, color=[0.5, 0.5, 0.5])
data['tempdiff'].plot(ax=ax, color='r')
data['dew_point'].plot(ax=ax, color='cyan')
data['cloudtemp'].plot(ax=ax, color='k')

print("MIN X: ")
print(data.index.values.min())
print("MAX X: ")
print(data.index.values.max())


lw = 0.1;
lines = ax.get_lines()
plt.setp(lines, 'linewidth', lw, 'antialiased', False)

lh = ax.legend(lines, ['Ambient', 'Sky', 'Detector', 'Ambient - sky',
                       'Dew point', 'LCL'],
               fancybox=True, loc='best')
lh.get_frame().set_alpha(0.7)
plt.setp(lh.get_lines(), 'antialiased', False)

#formatter = mdates.DateFormatter('%H')
# plt.gcf().axes[0]
#ax.xaxis.set_major_formatter(formatter) 

#formatter = mdates.DateFormatter('%H')
# ax.set_xlim(np.datetime64(date), np.datetime64(date + datetime.timedelta(days=1)))
#ax.set_xlim(1369440024, 1369518174)
#ax.xaxis.set_major_formatter(formatter) 
#ax.set_xlim(date, date + datetime.timedelta(days=1))

# print(date)
# ax.set_xlim((date - epoch).total_seconds(), 
#             ((date + datetime.timedelta(days=1)) - epoch).total_seconds())
# 
# print("XLIM: ")
# print(ax.get_xlim())



print("XLIM: ")
print(ax.get_xlim())
print(np.diff(ax.get_xlim()))

# labelPlot(ax, np.int64(np.datetime64(date)), np.int64(np.datetime64(date)), units)
labelPlot(ax, starttime, endtime, 's')
print("XLIM: ")
print(ax.get_xlim())
print(np.diff(ax.get_xlim()))
#fig.show()
fig.savefig(outfilename)

print("XLIM: ")
print(ax.get_xlim())
print(np.diff(ax.get_xlim()))

# plt.close("all")
# fig, ax = plt.subplots(1)
# lines = ax.plot(timestamp, data['ambient'], 
#                 timestamp, data['sky'],
#                 timestamp, tempdiff)
# #lines.set_antialiased(False)
# plt.setp(lines, 'linewidth', 0.1, 'antialiased', False)
# plt.setp(lines[0], 'color', [0, 0.6, 0])
# plt.setp(lines[1], 'color', 'b')
# plt.setp(lines[2], 'color', 'r')
# 
# #lh = ax.legend(lines, ['Ground', 'Sky', 'Ground - sky'])
# #plt.setp(lh.get_lines, 'linewidth', 0.1, 'antialiased', False)
# 
# # rotate and align the tick labels so they look better
# #ax.fmt_xdata = mdates.DateFormatter('%H')
# 
# #fig.autofmt_xdate()
# 
# formatter = mdates.DateFormatter('%H')
# # plt.gcf().axes[0]
# ax.xaxis.set_major_formatter(formatter) 
# ax.set_xlim(date, date + datetime.timedelta(days=1))
# 
# plt.savefig("/tmp/sky.png")
