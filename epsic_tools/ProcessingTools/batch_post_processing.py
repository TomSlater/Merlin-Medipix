# -*- coding: utf-8 -*-
"""
Created on Fri Aug  9 11:47:53 2019

@author: gys37319
"""

import argparse
import sys
import hyperspy.api as hs
import numpy as np
import os
import time
from IdentifyHDF5_files import get_HDF5_files
import functions_4DSTEM as fs
import py4DSTEM
from py4DSTEM.process.calibration import get_probe_size
from py4DSTEM.process.dpc import get_CoM_images, get_rotation_and_flip, get_phase_from_CoM
from py4DSTEM.process.dpc import get_wavenumber, get_interaction_constant

def scan_processing_file(proc_path):
    # scans the 'processing_params.txt' file and returns a dictionary of contents
    # 'processing_params.txt' must be of the format
    # key:value
    
    proc_path  = os.path.split(proc_path)[0]
    proc_file_path =  os.path.join(proc_path, 'processing_params.txt')
    if os.path.exists(proc_file_path) :
        proc_dict = {}
        #read value from text parameter file into dictionary
        with open(proc_file_path) as f:
            for line in f:
                #ignore commented lines
                if line.startswith('#'):
                    next
                #ignore blank lines
                elif line.startswith('\n'):
                    next
                else:
                    (key, val) = line.split(sep = ':')
                    proc_dict[key] = float(val)
    else:
        #processing_params.txt doesn't exist  - jump out. 
        print('no processing_params.txt file in ', proc_path)
        sys.exit()
    #return the dictionary
    return proc_dict
    
def define_bf_disk(dp, proc_dict):
    #define bf disk 
    #get threshold values 
    if 'BF_thresh_low' in proc_dict:
        bf_thresh_low = proc_dict['BF_thresh_low']
    else:
        bf_thresh_low = 0.01
    
    if 'BF_thresh_high' in proc_dict:
        bf_thresh_high = proc_dict['BF_thresh_high']
    else:
        bf_thresh_high = 0.05
    
        
    #print(bf_thresh)
    #bf= fs.get_bf_disk(dp, sub = 20, threshold = bf_thresh, plot_me = True)
    #build PACBED from every 10th diff pattern
    PACBED = np.average(dp.data[::10, ::10, :,:], axis = (0,1))
    r, x0, y0 = get_probe_size(PACBED,thresh_lower=bf_thresh_low, thresh_upper=bf_thresh_high)
    bf = [r,x0,y0]
    bf_exist = 1
    return bf, bf_exist

def get_adf(dp, bf, expand):
    #r, x0, y0 = bf
    #px,py,dx,dy = dp.data.shape
    #qy,qx = np.meshgrid(np.arange(dx),np.arange(dy))
    #qr = np.hypot(qx-x0,qy-y0)
    mask = get_mask(dp, bf, expand, bf_df = 'df')
    ADF = np.average(mask * dp.data, axis = (2,3))
    return ADF
    
def get_mask(dp, bf, expand, bf_df = 'bf'):
    #dp: 4D data set
    #bf: bright field disc object
    #expand = integer ; number of px to step out of bright field disc 
    #bf_df  = string ; 'bf': bright field mask ; 'df' : dark field mask
    r, x0, y0 = bf
    try:
        #if hs object
        px,py,dx,dy = dp.data.shape
    except:
        #if py4DSTEM object
        px,py,dx,dy = dp.data4D.shape
    qy,qx = np.meshgrid(np.arange(dx),np.arange(dy))
    qr = np.hypot(qx-x0,qy-y0)
    if bf_df == 'df':
        mask = qr > r + expand
    elif bf_df =='bf':
        mask = qr < r + expand
    return mask    
    
def process_data(proc_path,proc_bin_path, proc_dict):
    if 'Overwrite' in proc_dict:
        Overwrite = bool(proc_dict['Overwrite'] )
    else:
        Overwrite = False
    print('Overwrite : ', Overwrite)
    #load data lazily
    print('loading : ' , proc_path)
    time0 = time.time()
    dp = hs.load(proc_path, lazy = True)
    time1 = time.time()
    print('lazy loaded full data in :', time1 - time0,  ' s')
    dp_bin = hs.load(proc_bin_path, lazy = True)
    time2 = time.time()
    print('lazy loaded binned data in :', time2 - time1, 's')
    #flag to tell if bf has already been calculated
    bf_bin_exist = 0
    bf_exist = 0
    
    #ADF analysis
    if 'ADF' in proc_dict:
        #pass ADF value from config file 
        run_ADF = proc_dict['ADF']
        #define file save names
        ADF_file = proc_bin_path.rpartition('.')[0] + '_ADF'
        #print('ADF_file : ', ADF_file)
        if os.path.isfile(ADF_file + '.hspy'):
            #check overwrite flag and skip processing if set to zero
            if Overwrite == False:
                print('ADF data exists, skipping ADF analysis')
                run_ADF = 0 
            else:
                print('ADF data exists, overwriting')
        #run adf analysis
        if run_ADF == 1:
            print('Running ADF analysis')
            time_ADF0 = time.time()
            #check if lazy and compute
            #if dp_bin._lazy:
                #dp_bin = dp_bin.compute() 
            time_ADF1 = time.time()
            print('loaded binned data into memory in : ', time_ADF1 - time_ADF0)
            if bf_bin_exist == 0:
                #get bf thrershold value
                bf_bin, bf_bin_exist = define_bf_disk(dp_bin, proc_dict)
            #get ADF inner angle
            if 'ADF_expand' in proc_dict:
                ADF_expand = proc_dict['ADF_expand']
            else:
                ADF_expand = 20
            #get ADF image
            ADF = get_adf(dp_bin, bf_bin, ADF_expand)
            #save ADF image
            ADF_file = proc_bin_path.rpartition('.')[0] + '_ADF'
            hs_ADF = hs.signals.Signal2D(ADF)
            hs_ADF.save(ADF_file, overwrite = Overwrite) 
            hs_ADF.save(ADF_file, overwrite = Overwrite, extension = 'png') 
            time_ADF2 = time.time()
            print('ADF analysis completed and saved in : ', time_ADF2 - time_ADF0, ' s') 
    #CoM analysis
    if 'CoM' in proc_dict:
        run_COM = proc_dict['CoM']
        #define file save names
        if 'bin_CoM' in proc_dict:
            if proc_dict['bin_CoM'] ==1:
                file_path = proc_bin_path.rpartition('.')[0]
            elif proc_dict['bin_CoM'] ==0:
                file_path = proc_path.rpartition('.')[0]
        CoMx_file = file_path + '_CoMx'
        CoMy_file = file_path +  '_CoMy'
        #check if file exists
        if os.path.isfile(CoMx_file + '.hspy'):
            #check overwrite flag and skip processing if set to zero
            if Overwrite == False:
                print('CoM data exists, skipping CoM analysis')
                run_COM = 0 
            else:
                print('CoM data exists, overwriting')
        #run CoM analysis
        if run_COM ==1:     
            print('Running CoM analysis')
            time_CoM1 = time.time()
            if 'bin_CoM' in proc_dict:
                if proc_dict['bin_CoM'] ==1:
                    #if dp_bin._lazy:
                        #dp_bin = dp_bin.compute() 
                    if bf_bin_exist == 0:
                        #get BF thrershold value
                        bf_bin, bf_bin_exist = define_bf_disk(dp_bin, proc_dict)
                    bf_CoM = bf_bin
                    dp_CoM = py4DSTEM.file.datastructure.DataCube(dp_bin.data)
                    
                elif proc_dict['bin_CoM'] ==0:
                    if bf_exist ==0:
                        bf, bf_exist = define_bf_disk(dp, proc_dict)
                    bf_CoM = bf
                    dp_CoM = py4DSTEM.file.datastructure.DataCube(dp.data)
                    
            #get BF outer angle
            if 'BF_expand' in proc_dict:
                BF_expand = proc_dict['ADF_expand']
            else:
                BF_expand = 20
            #build mask
            mask = get_mask(dp_CoM, bf_CoM, BF_expand, bf_df = 'bf')     
            #set normalise CoM parameter 
            if 'Normalize_CoM' in proc_dict:
                Normalize_CoM = bool(proc_dict['Normalize_CoM'])
            else:
                Normalize_CoM = True
            #get CoM 
            CoMx, CoMy = get_CoM_images(dp_CoM, mask = mask, normalize = Normalize_CoM)
            #pass to hyperspy and save
            hs_CoMx = hs.signals.Signal2D(CoMx)
            hs_CoMx.save(CoMx_file, overwrite = Overwrite)
            hs_CoMx.save(CoMx_file, overwrite = Overwrite, extension = 'png')
            
            hs_CoMy = hs.signals.Signal2D(CoMy)
            hs_CoMy.save(CoMy_file, overwrite = Overwrite)
            hs_CoMy.save(CoMy_file, overwrite = Overwrite, extension = 'png')
            time_CoM2 = time.time()
            print('CoM analysis completed and saved in : ', time_CoM2 - time_CoM1, ' s') 
            
    if 'DPC' in proc_dict:
        run_DPC = proc_dict['DPC']
        #define file name
        phase_file = file_path + '_phase'
        if os.path.isfile(phase_file + '.hspy'):
            #check overwrite flag and skip processing if set to zero
            if Overwrite == False:
                print('DPC data exists, skipping DPC analysis')
                run_DPC = 0
            else:
                print('DPC data exists, overwriting')
        if run_DPC ==1:
            print('Running DPC analysis')
            time_DPC1 = time.time()
            #get parameters
            theta = proc_dict['DPC_theta']
            flip = bool(proc_dict['DPC_flip'])
            pad_factor = int(proc_dict['DPC_pad'])
            low_pass = proc_dict['DPC_lowpass']
            high_pass = proc_dict['DPC_highpass']
            step_size = proc_dict['DPC_stepsize']
            niter = int(proc_dict['DPC_niter'])
            #load CoMx and CoMy if not already calculated
            try:
                CoMx
            except NameError:
                CoM_flag = False
            else:
                CoM_flag = True
            if CoM_flag == False:
                try:
                    CoMx_file = file_path + '_CoMx.hspy'
                    CoMy_file = file_path +  '_CoMy.hspy'
                    CoMx = hs.load(CoMx_file)
                    CoMy = hs.load(CoMy_file) 
                    CoMx = CoMx.data
                    CoMy = CoMy.data
                except:
                    print('CoM files do not exist - run CoM caculation')
            #calulate phase from CoM
            phase, error = get_phase_from_CoM(CoMx, CoMy, theta = theta, flip = flip, paddingfactor=pad_factor, regLowPass=low_pass, regHighPass= high_pass, stepsize=step_size, n_iter=niter )
            #pass to hyperspy object and save
            phase_file = file_path + '_phase'
            hs_phase = hs.signals.Signal2D(phase)
            hs_phase.save(phase_file, overwrite=Overwrite)
            hs_phase.save(phase_file, overwrite=Overwrite, extension = 'png')
            time_DPC2 = time.time()
            print('DPC analysis completed and saved in : ', time_DPC2 - time_DPC1, ' s') 
    time2 = time.time()
    print('Processing complete in : ', time2 - time0 , ' s')
#%%
def main(beamline, year, visit, folder_num, folder = None):
    #check_differences(beamline, year, visit, folder = None)
    #%%
    #testing useage
    #beamline = 'e02'
    #year = '2019'
    #visit = 'mg22549-6'
    #get hdf5 files
    HDF5_dict= get_HDF5_files(beamline, year, visit, folder)
    #get processing parameters
    proc_path = HDF5_dict['processing_path']
    proc_dict = scan_processing_file(proc_path)
    print(proc_dict)
    print(HDF5_dict)
    print(folder_num)
    #just do one file  -1 as python indexing starts at 0
    folder_num = int(folder_num) -1
    #for file_n in np.arange(len(HDF5_dict['HDF5_files'])):
    this_fp = os.path.join(HDF5_dict['HDF5_paths'][folder_num], HDF5_dict['HDF5_files'][folder_num])
    this_bin_fp = os.path.join(HDF5_dict['binned_HDF5_paths'][folder_num], HDF5_dict['binned_HDF5_files'][folder_num])
    print(this_fp)
    try:
        process_data(this_fp, this_bin_fp, proc_dict)
    except Exception as e:
        print('** ERROR processing** \n ' , e)
#%%
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('beamline', help='Beamline name')
    parser.add_argument('year', help='Year')
    parser.add_argument('visit', help='Session visit code')
    parser.add_argument('folder_num', nargs= '?', help='passed by scheduler')
    parser.add_argument('folder', nargs= '?', help='folder to process')
    v_help = "Display all debug log messages"
    parser.add_argument("-v", "--verbose", help=v_help, action="store_true",
                        default=False)

    args = parser.parse_args()
    
    main(args.beamline, args.year, args.visit, args.folder_num, args.folder)            
            

        
    
            
            

            
        
    

