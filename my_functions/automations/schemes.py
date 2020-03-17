#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  3 19:25:00 2020

@author: villa
"""
import os
from glob import glob
from shutil import copyfile
from my_functions.automations.core import CommandHandler, VaspAutomation

class VaspSchemes:
    
    def __init__(self,vasp_automation,status=[],**kwargs):
        """
        Class to organize automation schemes for Vasp

        Parameters
        ----------
        vasp_automation : (VaspAutomation object)
            VaspAutomation object.
        status : (list), optional
            List of lines containing the report of the automation. The default is [].
        **kwargs :
            If None the default arguments created by the CommandHandler class are used.
        """
        
        self.vasp_automation = vasp_automation
        self.status = status
        self.path = vasp_automation.path
        
        if kwargs:
            for key, value in kwargs.items():
                setattr(self,key,value)
        else:
            args = CommandHandler().args()
            for key, value in args.__dict__.items():
                setattr(self,key,value)
    
    
    def compare_next_step_kpoints(self):
        """
        Compare KPOINTS file in current and next step directory 

        Returns
        -------
        kpoints_are_same : bool
            True if KPOINTS files are the same.
        """
        kpoints_are_same = self.vasp_automation.compare_kpoints()
        if kpoints_are_same:
            self.status.append('KPOINTS of current and next step are the same')
        else:
            self.status.append('KPOINTS of current and next step are different')
        return kpoints_are_same 
            
      
    def check_convergence(self):
        """
        Get information on electronic and ionic convergence and adds it to status.

        Returns
        -------
        conv_el : (bool)
            Electronic convergence reached.
        conv_ionic : (bool)
            Ionic convergence reached.

        """        
        conv_el, conv_ionic = self.vasp_automation.convergence()
        self.status.append('Job exit. Analysing "vasprun.xml"... ')
        self.status.append(f'\nElectronic convergence: {conv_el}')
        self.status.append(f'Ionic convergence: {conv_ionic}\n') 
        if conv_el == False and conv_ionic == False:
            self.status.append('Calculation probably FAILED, control manually')
        return conv_el,conv_ionic


    def next_step_relaxation_schemes(self):
        """
        If next step exists, transfer output files from the current calculation to 
        the next step calculation and submits the new job. \n
        If "check_kpoints" attribute is set to True, CHGCAR and WAVECAR are copied 
        only if KPOINTS file of current and next step are the same. \n
        CHGCAR,WAVECAR and CONTCAR can be copied if their related attributes ("chgcar","wavecar","contcar") are set to True. \n
        This can be done either manually or by including the commands (-C or --chgcar, -W or --wavecar, -c or --contcar) in the command line.
        """
        v = self.vasp_automation
        if v.get_next_step():
            # if True copy CHGCAR and WAVECAR only if KPOINTS are the same, else copy them in any case
            if self.check_kpoints:
                if self.compare_next_step_kpoints():
                    if self.chgcar:
                        self.transfer_chgcar()
                    if self.wavecar:
                        self.transfer_wavecar()                       
            else:
                if self.chgcar:
                    self.transfer_chgcar()
                if self.wavecar:
                    self.transfer_wavecar()                
            # if True copy CONTCAR to next step POSCAR
            if self.contcar:
                self.transfer_contcar_to_poscar()
                                                  
            v.submit_job()
            self.status.append('\nNext step calculation submitted in dir "../%s"' %os.path.basename(v.get_next_step()))            
        else:
            self.status.append('\nNo next step found, no other calculation submitted')        


    def print_status(self):
        """
        Print status lines on terminal
        """
        print('\n'.join(self.status))


    def step_limits_reached(self):
        """
        Check if electronic or ionic steps limit has been reached. \n
        Electronic steps limit is taken from the "NELM" flag in the INCAR file. \n
        Ionic steps limit is taken from the "NSW" flag in the INCAR file

        Returns
        -------
        el_limit_reached : (bool)
        
        ionic_limit_reached : (bool)
        """
        v = self.vasp_automation
        if v.limit_electronic_steps_reached():
            el_limit_reached = True
            self.status.append('Maximum limit of electronic steps has been reached')
        else:
            el_limit_reached = False
        if v.limit_ionic_steps_reached():
            ionic_limit_reached = True
            self.status.append('Maximum limit of ionic steps has been reached')
        else:
            ionic_limit_reached = False
        return el_limit_reached, ionic_limit_reached
                    

    def resubmit_if_step_limits_reached(self):
        """
        To use if calculation is not converged. Does not perform actions in case the number of files named "out.*"
        in the working directory is >= 2. The idea is that if the calculation hasn't converged after reaching the limit
        twice, is better to control manually. \n
        
        Check if electronic or ionic steps limit has been reached. \n
        In case electronic steps limit is reached, resubmits calculation without doing anything. \n
        In case ionic steps limit is reached copies CONTCAR to POSCAR and resubmits calculation.
        """
        
        number_of_out_files = len(glob(os.path.join(self.path,'out*')) )
        if number_of_out_files < 2:
            v = self.vasp_automation
            self.status.append('Checking if limit of electronic or ionic steps have been reached...')
            el_limit, ionic_limit = self.step_limits_reached()
            
            if el_limit==True and ionic_limit==False:
                v.submit_job(job_script_path = self.path)
                self.status.append('Resubmitting calculation. Be sure "ISTART" in your INCAR is set to 1 or default.')
            
            if el_limit==False and ionic_limit==True:
                copyfile(os.path.join(self.path,'CONTCAR'),os.path.join(self.path,'POSCAR'))
                v.submit_job(job_script_path = self.path)
                self.status.append('Resubmitting calculation. Be sure "ISTART" in your INCAR is set to 1 or default.')
            
            if el_limit==False and ionic_limit==False:
                self.status.append('Problem is not due to steps limit being reached, controll manually...')
        else:
            self.status.append('Two out.* files are already present, control manually...')


    def transfer_chgcar(self):
        """
        Copy CHGCAR file to next step directory
        """
        v = self.vasp_automation
        v.copy_files_to_next_step_dir('CHGCAR')
        self.status.append('CHGCAR copied in dir "../%s"' %os.path.basename(v.get_next_step()))

           
    def transfer_contcar_to_poscar(self):
        """
        Copy CONTCAR file to POSCAR file in next step directory
        """
        v = self.vasp_automation
        v.copy_files_to_next_step_dir(('CONTCAR','POSCAR'))
        self.status.append('CONTCAR copied in POSCAR in dir "../%s"' %os.path.basename(v.get_next_step()))
        return

    
    def transfer_wavecar(self):
        """
        Copy WAVECAR file to next step directory
        """
        v = self.vasp_automation
        v.copy_files_to_next_step_dir('WAVECAR')
        self.status.append('WAVECAR copied in dir "../%s"' %os.path.basename(v.get_next_step()))        
        return
    
                
    def write_status(self,filename=None,path=None):
        """
        Write status lines to file

        Parameters
        ----------
        filename : (str), optional
            Filename. The default is None. If None "status_filename" attribute is used.
        path : (str), optional
            Path of file to write. The default is None. If None "path" attribute is used.
        """

        filename = filename if filename else self.status_filename
        path = path if path else self.path
        if filename:
            with open(filename,'w') as f:
                f.write('\n'.join(self.status))
                print('Automation report written in "%s" file in directory "%s"' %(filename,path))
        else:
            print('Writing status file is disabled, if needed please set "status_filename" kwarg or "--status" optional argument on command line')
            
            