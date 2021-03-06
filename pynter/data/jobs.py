
from abc import ABCMeta, abstractmethod
import os
import os.path as op
import shutil
from pymatgen.io.vasp.inputs import VaspInput, Poscar, Incar, Kpoints, Potcar
from pymatgen.io.vasp.outputs import Vasprun, Oszicar
from pymatgen.core.structure import Structure
from pymatgen.electronic_structure.dos import CompleteDos
from pymatgen.electronic_structure.bandstructure import BandStructure
from pymatgen.analysis.transition_state import NEBAnalysis
from pymatgen.entries.computed_entries import ComputedStructureEntry
from pynter.slurm.job_script import ScriptHandler
from pynter.slurm.interface import HPCInterface
from pynter.tools.utils import grep_list
from pynter.data.database.creator import VaspJobDrone
import importlib
import numpy as np
import json
from glob import glob
from pynter.tools.utils import grep

class Job:
    
    def __init__(self,path=None,inputs=None,job_settings=None,outputs=None,job_script_filename=None,name=None):
        """
        Class to control and organize inputs and outputs of a generic job.

        Parameters
        ----------
        path : (str), optional
            Path where job is stored. The default is None. If None the work dir is used.
        inputs : (dict), optional
            Dictionary with input data. The default is None.
        job_settings : (dict), optional
            Dictionary with job settings. The default is None. Documentation in ScriptHandler class in slurm.job_script module
        outputs : (dict), optional
            Dictionary with output data. The default is None.
        job_script_filename : (str), optional
            Filename of job script. The default is taken from the key 'filename' in the job_settings in the config file.
        name : (str)
            Name of the job. If none the name is searched in the job script.

        """
                
        self.path = path if path else os.getcwd()
        self.inputs = inputs
        self.job_settings = job_settings
        self.outputs = outputs
        self.job_script_filename = job_script_filename if job_script_filename else ScriptHandler().filename
        
        self._localdir = HPCInterface().localdir
        self._workdir = HPCInterface().workdir
        self._path_relative = op.abspath(self.path).replace(self._localdir,'')
        
        self.path_in_hpc = self._workdir + self._path_relative
        
        
        if outputs:
            self.get_output_properties()
        
        
        if name:
            self.name = name
        elif self.job_settings:
            self.name = self.job_settings['name']
        elif op.isfile(op.join(self.path,self.job_script_filename)):
            s = ScriptHandler.from_file(self.path,filename=self.job_script_filename)
            self.name = s.settings['name']
        else:
            self.name = 'no_name'
            
        if not self.job_settings:
            self.job_settings = {}
        self.job_settings['name'] = self.name


    def __str__(self):
        jobclass = self.jobclass
        if hasattr(self,'group'):
            if self.group != '':
                printout = '%s "%s" of group "%s"' %(jobclass, self.name, self.group)
            else:
                printout = '%s "%s"' %(jobclass, self.name)
        else:
            self.group = ''
            printout = '%s "%s"' %(jobclass, self.name)
        
        return printout
    
    def __repr__(self):
        return self.__str__()
        
    @property
    def jobclass(self):
        return self.__class__.__name__

        
    def cancel_job(self):
        """Cancel job on HPC"""
        hpc = HPCInterface()
        job_id = self.job_id()
        hpc.cancel_jobs(job_id)
        
        return 

    
    def delete_job_files(self,safety=True):
        """
        Delete Job folder (self.path)

        Parameters
        ----------
        safety : (bool), optional
            Ask confirmation to delete job. The default is True.
        """
        if safety:
            inp = input('Are you sure you want to delete Job %s ? (y/n) : ' %self.name)
            if inp in ('y','Y'):
                shutil.rmtree(self.path)
                print('Deleted Job %s'%self.name)
            else:
                print('Job %s is left unchanged'%self.name)
        else:
            shutil.rmtree(self.path)
            print('Deleted Job %s'%self.name)
        return


    @abstractmethod
    def get_inputs(self):
        pass

    @abstractmethod
    def get_outputs(self):
        pass
    
    @abstractmethod
    def get_output_properties(self):
        pass

    @abstractmethod
    def insert_in_database(self):
        pass


    def job_id(self):
        """Get job ID from the queue on HPC"""        
        hpc = HPCInterface()
        stdout,stderr = hpc.qstat(printout=False)
        queue = stdout.splitlines()
        job_lines = grep_list(self.name,queue)
        if job_lines == []:
            raise ValueError (f'Job named "{self.name}" is not currently running or pending')
        elif len(job_lines) > 1:
            raise ValueError (f'More than one job named "{self.name}" has been found in queue:\n{stdout}')
        else:
            job_line = job_lines[0].split()
            job_id = job_line[0]
        
        return job_id


    def job_queue(self):
        """
        Print job queue from HPC on screen
        
        Returns
        -------
        stdout : (str)
            Output.
        stderr : (str)
            Error.
        """
        hpc = HPCInterface()
        stdout,stderr = hpc.qstat()
        
        return stdout,stderr
        

    def run_job(self,write_input=True,sync=True):
        """
        Run job on HPC. Input files are automatically written and sync to HPC is performed.

        Parameters
        ----------
        write_input : (bool), optional
            Write input file stored in "inputs" dictionary. The default is True.
        sync : (bool), optional
            Sync files to HPC before running. The default is True

        Returns
        -------
        stdout : (str)
            Output.
        stderr : (str)
            Error.
        """
        if write_input:
            self.write_input()
        hpc = HPCInterface()
        if sync:
            self.sync_to_hpc()
        stdout,stderr = hpc.sbatch(path=self.path_in_hpc,job_script_filename=self.job_script_filename)
        
        return stdout,stderr
    

    def sync_from_hpc(self,stdouts=False):
        """
        Sync job data from HPC to local machine

        Parameters
        ----------
        stdouts : (bool), optional
            Return output and error strings. The default is False.

        Returns
        -------
        stdout : (str)
            Output.
        stderr : (str)
            Error.

        """
        hpc = HPCInterface()
        abs_path = op.abspath(self.path)
        localdir = abs_path 
        stdout,stderr = hpc.rsync_from_hpc(remotedir=self.path_in_hpc,localdir=localdir)
        if stdouts:
            return stdout,stderr
        else:
            return
        
        
    def sync_to_hpc(self,stdouts=False):
        """
        Sync job data from local machine to HPC

        Parameters
        ----------
        stdouts : (bool), optional
            Return output and error strings. The default is False.

        Returns
        -------
        stdout : (str)
            Output.
        stderr : (str)
            Error.

        """
        hpc = HPCInterface()
        abs_path = op.abspath(self.path)
        localdir = abs_path 
        stdout,stderr = hpc.rsync_to_hpc(localdir=localdir,remotedir=self.path_in_hpc)
        if stdouts:
            return stdout,stderr
        else:
            return


    def status(self):
        """
        Get job status from HPC. 

        Returns
        -------
        status : (str)
            Job status. Possible status are 'PENDING','RUNNING','NOT IN QUEUE'.
        """
        hpc = HPCInterface()
        stdout,stderr = hpc.qstat(printout=False)
        queue = stdout.splitlines()
        job_lines = grep_list(self.name,queue)
        if job_lines == []:
            status = 'NOT IN QUEUE'
        elif len(job_lines) > 1:
            raise ValueError (f'More than one job named "{self.name}" has been found in queue:\n{stdout}')
        else:
            job_line = job_lines[0].split()
            status = job_line[4]
            if status == 'PD':
                status = 'PENDING'
            if status == 'R':
                status = 'RUNNING'
            if status == 'CG':
                status = 'COMPLETED'
            
        return status
 
           
    @abstractmethod
    def write_input():
        pass
        
     
class VaspJob(Job):
 
    
    def as_dict(self,**kwargs):        
        """
        Get VaspJob as dictionary. The Vasprun ouput object is not exported.
        
        Parameters
        ----------
        get_band_structure : (bool), optional
            Export BandStructure as dict. The default is False.
            
        Returns:
            Json-serializable dict representation of VaspJob.
        """
        kwargs = self._parse_kwargs(**kwargs)
                
        d = {"@module": self.__class__.__module__,
             "@class": self.__class__.__name__,
             "path": self.path,
             "inputs": self.inputs.as_dict(),             
             "job_settings": self.job_settings,
             "job_script_filename":self.job_script_filename,
             "name":self.name}
        
        d["outputs"] = {}
        if "ComputedStructureEntry" in self.outputs.keys():
            d["outputs"]["ComputedStructureEntry"] = self.computed_entry.as_dict()
        
        d["is_converged"] = self.is_converged
        d["band_structure"] = self.band_structure.as_dict() if kwargs['get_band_structure'] else None
        return d


    def to_json(self,path,**kwargs):
        """
        Save VaspJob object as json string or file

        Parameters
        ----------
        path : (str), optional
            Path to the destination file.  If None a string is exported.
        get_band_structure : (bool), optional
            Export BandStructure as dict. The default is False.

        Returns
        -------
        d : (str)
            If path is not set a string is returned.

        """
        d = self.as_dict(**kwargs)
        if path:
            with open(path,'w') as file:
                json.dump(d,file)
            return
        else:
            return d.__str__()   

    
    @staticmethod
    def from_dict(d):
        """
        Construct VaspJob object from python dictionary.
        
        Returns
        -------
        VaspJob object
        """
        path = d['path']
        inputs = VaspInput.from_dict(d['inputs'])
        job_settings = d['job_settings']
        job_script_filename = d['job_script_filename']
        name = d['name']
        outputs={}
        if d['outputs']:
            outputs['ComputedStructureEntry'] = ComputedStructureEntry.from_dict(d['outputs']['ComputedStructureEntry'])
        
        vaspjob = VaspJob(path,inputs,job_settings,outputs,job_script_filename,name)
        
        vaspjob._band_structure = BandStructure.from_dict(d['band_structure']) if d['band_structure'] else None
        vaspjob._is_converged = d['is_converged']
        if outputs:
            for k,v in vaspjob.computed_entry.data.items():
                if k not in vaspjob._default_data_computed_entry:
                    setattr(vaspjob,k,v)
        
        return vaspjob
        
    
    @staticmethod
    def from_directory(path,job_script_filename='job.sh',load_outputs=True,**kwargs):
        """
        Builds VaspJob object from data stored in a directory. Input files are read using Pymatgen VaspInput class.
        Output files are read usign Pymatgen Vasprun class.
        Job settings are read from the job script file.

        Parameters
        ----------
        path : (str)
            Path were job data is stored.
        job_script_filename : (str), optional
            Filename of job script. The default is 'job.sh'.
        kwargs : (dict)
            Arguments to pass to Vasprun parser.
        Returns
        -------
        VaspJob object.
        
        """
                
        inputs = VaspInput.from_directory(path)
        outputs = {}
        if load_outputs:
            if op.isfile(op.join(path,'vasprun.xml')):
                try:
                    outputs['Vasprun'] = Vasprun(op.join(path,'vasprun.xml'),**kwargs)
                except:
                    print('Warning: Reading of vasprun.xml in "%s" failed'%path)
                    outputs['Vasprun'] = None
        
        s = ScriptHandler.from_file(path,filename=job_script_filename)
        job_settings =  s.settings
        
        return VaspJob(path,inputs,job_settings,outputs)


    @staticmethod
    def from_json(path_or_string):
        """
        Build VaspJob object from json file or string.

        Parameters
        ----------
        path_or_string : (str)
            If an existing path to a file is given the object is constructed reading the json file.
            Otherwise it will be read as a string.

        Returns
        -------
        VaspJob object.

        """
        if op.isfile(path_or_string):
            with open(path_or_string) as file:
                d = json.load(file)
        else:
            d = json.load(path_or_string)
        return VaspJob.from_dict(d)
        

    @property
    def incar(self):
        return self.inputs['INCAR']
    
    @property
    def kpoints(self):
        return self.inputs['KPOINTS']
    
    @property
    def poscar(self):
        return self.inputs['POSCAR']
    
    @property
    def potcar(self):
        return self.inputs['POTCAR']

    @property
    def vasprun(self):
        if 'Vasprun' in self.outputs.keys():
            return self.outputs['Vasprun']
        else:
            if not op.exists(op.join(self.path,'vasprun.xml')):
                print('Warning: "vasprun.xml" file is not present in Job directory')
            return None

    @property
    def computed_entry(self):
        if 'ComputedStructureEntry' in self.outputs.keys():
            return self.outputs['ComputedStructureEntry']
        else:
            return None
        

    @property
    def band_structure(self):
        return self._band_structure

    
    @property
    def charge(self):
        """
        Charge of the system calculated as the difference between the value of "NELECT"
        in the INCAR and the number of electrons in POTCAR. If "NELECT" is not present 
        charge is set to 0.
        """
        charge = 0
        if 'NELECT' in self.incar.keys():
            nelect = self.incar['NELECT']
            val = {}
            for p in self.potcar:
                val[p.element] = p.nelectrons
            neutral = sum([ val[el.symbol]*self.initial_structure.composition[el] 
                           for el in self.initial_structure.composition])
            charge = neutral - nelect
        if not isinstance(charge,int):
            charge = np.around(charge,decimals=1)
        return charge


    @property
    def energy_gap(self):
        """Energy gap read from vasprun.xml with Pymatgen"""
        band_gap = None
        if self.computed_entry:
            band_gap = self.computed_entry.data['eigenvalue_band_properties'][0]
            
        return band_gap
    

    @property
    def final_energy(self):
        """Final total energy of the calculation read from vasprun.xml with Pymatgen"""
        final_energy = None
        if self.computed_entry:
            final_energy = self.computed_entry.data['final_energy']
            
        return final_energy
    
    
    @property
    def final_structure(self):
        """Final structure read from "vasprun.xml" with Pymatgen"""
        final_structure = None
        if self.computed_entry:
            if self.computed_entry.data['structures']:
                final_structure = self.computed_entry.data['structures'][-1]
            
        return final_structure 
    
            
    @property
    def formula(self):
        """Complete formula from initial structure (read with Pymatgen)"""
        if self.initial_structure:
            return self.initial_structure.composition.formula
        else:
            return None

    
    @property
    def hubbards(self):
        """
        Generate dictionary with U paramenters from LDAUU tag in INCAR file

        Returns
        -------
        U_dict : (dict)
            Dictionary with Elements as keys and U parameters as values.
        """
        U_dict = {}
        incar = self.incar
        if 'LDAUU' in incar.keys():
            ldauu = incar['LDAUU']
            elements = self.initial_structure.composition.elements
            if isinstance(ldauu,str):
                ldauu = ldauu.split()
            for i in range(0,len(ldauu)):
                U_dict[elements[i]] = int(ldauu[i])
        else:
            print('No LDAUU tag present in INCAR in Job "%s"' %self.name)
            
        return U_dict
        
    @property
    def initial_structure(self):
        """Initial structure read from poscar"""
        if self.poscar:
            poscar = self.poscar
            return poscar.structure            
        else:
            print('Warning: inputs["POSCAR"] is not defined')
            return None
    
    
    @property
    def is_converged(self):
        """
        Reads Pymatgen Vasprun object and returns "True" if the calculation is converged,
        "False" if reading failed, and "None" if is not present in the outputs dictionary.
        """
        if hasattr(self,'_is_converged'):
            return self._is_converged
        else:
            return None
            

    @property
    def nelectrons(self):
        """
        Number of electrons in the system. If 'NELECT' tag is in INCAR that value is returned.
        Else the sum of valence electrons from POTCAR is returned.
        """
        if 'NELECT' in self.incar.keys():
            nelect = self.incar['NELECT']
        else:
            val = {}
            for p in self.potcar:
                val[p.element] = p.nelectrons
            nelect = sum([ val[el.symbol]*self.initial_structure.composition[el] 
                           for el in self.initial_structure.composition])
        return nelect    
    

    def delete_output_files(self,safety=True):
        """
        Delete files that aren't input files (INCAR,KPOINTS,POSCAR,POTCAR)
        """
        if safety:
            inp = input('Are you sure you want to delete outputs of Job %s ?: (y/n)' %self.name)
            if inp in ('y','Y'):
                delete = True
            else:
                delete = False
        else:
            delete= True
            
        if delete:                
            files = [f for f in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, f))]
            for f in files:
                if f not in ['INCAR','KPOINTS','POSCAR','POTCAR',self.job_script_filename]:
                    os.remove(os.path.join(self.path,f))
                    print('Deleted file %s'%os.path.join(self.path,f))   
        return
                    

    def get_inputs(self,sync=False):
        """
        Read VaspInput from directory
        """
        if sync:
            self.sync_from_hpc()
        inputs = VaspInput.from_directory(self.path)
        self.inputs = inputs
        return
    
    
    def get_outputs(self,sync=False,get_output_properties=True):
        """
        Get outputs dictionary from the data stored in the job directory. "vasprun.xml" is 
        read with Pymatgen
        """
        if sync:
            self.sync_from_hpc()
        path = self.path
        outputs = {}
        if op.isfile(op.join(path,'vasprun.xml')):
            try:
                outputs['Vasprun'] = Vasprun(op.join(path,'vasprun.xml'))
            except:
                print('Warning: Reading of vasprun.xml in "%s" failed'%path)
                outputs['Vasprun'] = None
        self.outputs = outputs
        if get_output_properties:
            self.get_output_properties()
        return

    
    def get_output_properties(self,**kwargs):
        """
        Parse outputs properties from VaspJob.outputs.

        Parameters
        ----------
        get_band_structure : (bool), optional
            Get BandStructure object from vasprun. The default is False.
        data : (list), optional
            List of attributes of Vasprun to parse in ComputedStructureEntry. The default is None.
        """                
        self._is_converged = self._get_convergence()
        
        self._default_data_computed_entry = ['final_energy','structures','eigenvalue_band_properties'] # default imports from Vasprun

        kwargs = self._parse_kwargs(**kwargs)  
        if self.vasprun:
            data = self._default_data_computed_entry 
            optional_attributes = []
            if kwargs['data']:
                for attr in kwargs['data']:
                    data.append(attr)
                    optional_attributes.append(attr)
            self.outputs['ComputedStructureEntry'] = self.vasprun.get_computed_entry(data=data)
            
            if optional_attributes:
                for attr in optional_attributes:
                    value = self.computed_entry.data[attr]
                    setattr(self,attr,value)

        self._band_structure = self._get_band_structure() if kwargs['get_band_structure'] else None
        
        return


    def insert_in_database(self,get_doc_only=False,safety=True,check_convergence=True,**kwargs):
        """
        Get VaspJob doc and insert in pynter default database with matgendb's VaspToDbTaskDrone.

        Parameters
        ----------
        get_doc_only: (bool), optional
            Get only doc with get_task_doc but does not perform the insertion into db. Default is False.
        safety : (bool), optional
            Ask confirmation to insert job. The default is True.
        check_convergence: (bool), optional
            Insert job in DB only if is_converged is True. The default is True.
        **kwargs :
            Args to pass to VaspToDbTaskDrone
            
        Returns
        -------
        drone: 
            VaspJobDrone object that contains all attributes of VaspToDbTaskDrone.
        """
        drone = VaspJobDrone(self,**kwargs)
        if get_doc_only:
            return drone.get_task_doc_from_files()
        if safety:
            inp = input('Are you sure you want to insert VaspJob %s in database "%s", collection "%s"? (y/n) : ' 
                        %(self.name,drone.database,drone.collection))        
            if inp in ('y','Y'):
                assimilate = True
            else:
                assimilate = False
        if assimilate:
            drone.assimilate_job(check_convergence=check_convergence)
        return 

    
    def write_input(self):
        """Write "inputs" dictionary to files. The VaspInput class from Pymatgen is used."""
        script_handler = ScriptHandler(**self.job_settings)
        script_handler.write_script(path=self.path)
        inputs = self.inputs
        inputs.write_input(output_dir=self.path,make_dir_if_not_present=True)
        return


    def _get_band_structure(self):
        """Get BandStructure objects from Vasprun"""
        if self.vasprun:
            return self.vasprun.get_band_structure(kpoints_filename=op.join(self.path,'KPOINTS'))
        else:
            return None
            

    def _get_convergence(self):
        """
        Reads Pymatgen Vasprun object and returns "True" if the calculation is converged,
        "False" if reading failed, and "None" if is not present in the outputs dictionary.
        """
        is_converged = None
        if self.outputs:
            if 'Vasprun' in self.outputs.keys():
                is_converged = False
                if self.vasprun:
                    vasprun = self.vasprun
                    conv_el, conv_ionic = False, False
                    if vasprun:
                        conv_el = vasprun.converged_electronic
                        conv_ionic = vasprun.converged_ionic
                    if conv_el and conv_ionic:
                        is_converged = True                    
        return is_converged


    def _parse_kwargs(self,**kwargs):
        kwargs['data'] = kwargs['data'] if 'data' in kwargs.keys() else None
        kwargs['get_band_structure'] = kwargs['get_band_structure'] if 'get_band_structure' in kwargs.keys() else False 
        return kwargs



class VaspNEBJob(Job):
    
    
    def as_dict(self):
        
        d = {"@module": self.__class__.__module__,
             "@class": self.__class__.__name__,
             "path": self.path,             
             "job_settings": self.job_settings,
             "job_script_filename":self.job_script_filename,
             "name":self.name}
        
        inputs_as_dict = {}
        inputs_as_dict['structures'] = [s.as_dict() for s in self.structures]
        inputs_as_dict['INCAR'] = self.incar.as_dict()
        inputs_as_dict['KPOINTS'] = self.kpoints.as_dict()
        inputs_as_dict['POTCAR'] = self.potcar.as_dict()
        
        d["inputs"] = inputs_as_dict
        d["is_step_limit_reached"] = self.is_step_limit_reached
        d["is_converged"] = self.is_converged
        d["r"] = self.r.tolist()
        d["energies"] = self.energies.tolist()
        d["forces"] = self.forces.tolist()
        
        return d
    

    def to_json(self,path):
        """
        Save VaspNEBJob object as json string or file
        Parameters
        ----------
        path : (str), optional
            Path to the destination file.  If None a string is exported.
            
        Returns
        -------
        d : (str)
            If path is not set a string is returned.
        """
        d = self.as_dict()
        if path:
            with open(path,'w') as file:
                json.dump(d,file)
            return
        else:
            return d.__str__() 

    
    @staticmethod
    def from_dict(d):

        path = d['path']
        inputs = {}
        inputs["structures"] = [Structure.from_dict(s) for s in d['inputs']['structures']]
        inputs["INCAR"] = Incar.from_dict(d['inputs']['INCAR'])
        inputs["KPOINTS"] = Kpoints.from_dict(d['inputs']['KPOINTS'])
        inputs["POTCAR"] = Potcar.from_dict(d['inputs']['POTCAR'])
        job_settings = d['job_settings']
        job_script_filename = d['job_script_filename']
        name = d['name']
        outputs={}
        
        vaspNEBjob = VaspNEBJob(path,inputs,job_settings,outputs,job_script_filename,name)
        
        vaspNEBjob._is_step_limit_reached = d['is_step_limit_reached']
        vaspNEBjob._is_converged = d['is_converged']
        vaspNEBjob._r = np.array(d['r'])
        vaspNEBjob._energies = np.array(d['energies'])
        vaspNEBjob._forces = np.array(d['forces'])
        
        return vaspNEBjob
    
    
    @staticmethod
    def from_directory(path,job_script_filename='job.sh',load_outputs=True):
        """
        Builds VaspNEBjob object from data stored in a directory. Inputs dict is constructed
        by reading with Pymatgen INCAR, KPOINTS and POTCAR and creating a series of Structure 
        objects read from POSCARs in the images folders. 
        Inputs is thus a dict with "structures", "INCAR","KPOINTS","POTCAR" as keys.
        Output files are read usign Pymatgen NEBAnalysis and Vasprun classes.
        Job settings are read from the job script file.

        Parameters
        ----------
        path : (str)
            Path were job data is stored.
        job_script_filename : (str), optional
            Filename of job script. The default is 'job.sh'.

        Returns
        -------
        VaspNEBJob object.
        
        """                
        inputs = {}
        structures = []
        path = op.abspath(path)
        dirs = [d[0] for d in os.walk(path)]
        for d in dirs:
            image_name = op.relpath(d,start=path)
            if all(c.isdigit() for c in list(image_name)): #check if folder is image (all characters in folder rel path need to be numbers)
                image_path = d
                structure = Poscar.from_file(op.join(image_path,'POSCAR')).structure
                structures.append(structure)

        inputs['structures'] = structures           
        inputs['INCAR'] = Incar.from_file(op.join(path,'INCAR'))
        inputs['KPOINTS'] = Kpoints.from_file(op.join(path,'KPOINTS'))
        inputs['POTCAR'] = Potcar.from_file(op.join(path,'POTCAR'))
        
        outputs = {}
        if load_outputs:
            try:
                outputs['NEBAnalysis'] = NEBAnalysis.from_dir(path)
            except:
                print('Warning: NEB output reading with NEBAnalysis in "%s" failed'%path)
                outputs['NEBAnalysis'] = None
            
        s = ScriptHandler.from_file(path,filename=job_script_filename)
        job_settings =  s.settings
        
        return VaspNEBJob(path,inputs,job_settings,outputs)


    @staticmethod
    def from_json(path_or_string):
        """
        Build VaspJob object from json file or string.
        Parameters
        ----------
        path_or_string : (str)
            If an existing path to a file is given the object is constructed reading the json file.
            Otherwise it will be read as a string.
        Returns
        -------
        VaspJob object.
        """
        if op.isfile(path_or_string):
            with open(path_or_string) as file:
                d = json.load(file)
        else:
            d = json.load(path_or_string)
        return VaspNEBJob.from_dict(d)

 
    def delete_outputs(self,safety=True):
        """
        Delete files that aren't input files (INCAR,KPOINTS,POSCAR,POTCAR)
        """
        if safety:
            inp = input('Are you sure you want to delete outputs of Job %s ?: (y/n)' %self.name)
            if inp in ('y','Y'):
                delete = True
            else:
                delete = False
        else:
            delete= True
            
        if delete:
            dirs = self.image_dirs
            dirs.append(self.path)
            for d in dirs:                
                files = [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]
                for f in files:
                    if f not in ['INCAR','KPOINTS','POSCAR','POTCAR',self.job_script_filename]:
                        os.remove(os.path.join(d,f))
                        print('Deleted file %s'%os.path.join(d,f))   
        return

    
    @property
    def images(self):
        return len(self.inputs['structures'])-2
    
    @property
    def image_dirs(self):
        """
        Directories of images for NEB calculations. Directories are selected if all characters in the
        directory name are digits.
        """
        dirs = []
        path = self.path
        path = op.abspath(path)
        for d in os.walk(path):
            directory = d[0]
            image_name = op.relpath(directory,start=path)
            if all(c.isdigit() for c in list(image_name)): #check if folder is image (all characters in folder rel path need to be numbers)
                dirs.append(directory)
        dirs.sort()
        return dirs
    
    @property
    def structures(self):
        return self.inputs['structures']

    @property
    def incar(self):
        return self.inputs['INCAR']
    
    @property
    def kpoints(self):
        return self.inputs['KPOINTS']
    
    @property
    def potcar(self):
        return self.inputs['POTCAR']


    @property
    def charge(self):
        """
        Charge of the system calculated as the difference between the value of "NELECT"
        in the INCAR and the number of electrons in POTCAR. If "NELECT" is not present 
        charge is set to 0.
        """
        charge = 0
        if 'NELECT' in self.incar.keys():
            nelect = self.incar['NELECT']
            val = {}
            for p in self.potcar:
                val[p.element] = p.nelectrons
            neutral = sum([ val[el.symbol]*self.initial_structure.composition[el] 
                           for el in self.initial_structure.composition])
            charge = neutral - nelect
        if not isinstance(charge,int):
            charge = np.around(charge,decimals=1)
        return charge


    @property
    def energies(self):
        """
        Energies of images read with NEBAnalysis
        """
        return self._energies

    @property
    def forces(self):
        """
        Forces of images read with NEBAnalysis
        """
        return self._forces
        
        
    @property
    def formula(self):
        """Complete formula from initial structure (read with Pymatgen)"""
        if self.initial_structure:
            return self.initial_structure.composition.formula
        else:
            return None

        
    @property
    def initial_structure(self):
        """Initial structure read from first element of ""structures" attribute. """
        return self.structures[0]

    
    @property
    def is_converged(self):
        """
        Reads Pymatgen Vasprun object and returns "True" if the calculation is converged,
        or the ionic step limit has been reached reading from the OSZICAR file.
        "False" if reading failed, and "None" if is not present in the outputs dictionary.
        """
        if hasattr(self,'_is_converged'):
            return self._is_converged
        else:
            return None


    @property
    def is_required_accuracy_reached(self):
        """
        True if "reached required accuracy - stopping structural energy minimisation" 
        is found in most recent out.* file. 
        False if file exists but no line is found.
        None if no out.* file exists.
        """
        return self._is_required_accuracy_reached
    
    
    @property
    def is_step_limit_reached(self):
        """
        Reads number of ionic steps from the OSZICAR file with Pymatgen and returns True if 
        is equal to the step limit in INCAR file (NSW tag)
        """
        return self._is_step_limit_reached


    @property
    def neb_analysis(self):
        """
        Get NEBAnalysis object from r, energies and forces. Returns None if any of the inputs is None.
        """
        if self.r is not None and self.energies is not None and self.forces is not None:
            return NEBAnalysis(self.r, self.energies, self.forces, self.structures)
        else:
            return None


    @property
    def nelectrons(self):
        """
        Number of electrons in the system. If 'NELECT' tag is in INCAR that value is returned.
        Else the sum of valence electrons from POTCAR is returned.
        """
        if 'NELECT' in self.incar.keys():
            nelect = self.incar['NELECT']
        else:
            val = {}
            for p in self.potcar:
                val[p.element] = p.nelectrons
            nelect = sum([ val[el.symbol]*self.initial_structure.composition[el] 
                           for el in self.initial_structure.composition])
        return nelect


    @property
    def r(self):
        """
        Root mean square distances between structures read with NEBAnalysis
        """
        return self._r


    def get_inputs(self,sync=False):
        """
        Read inputs from Job directory
        """
        if sync:
            self.sync_from_hpc()
        inputs = {}
        structures = []
        path = op.abspath(self.path)
        dirs = [d[0] for d in os.walk(path)]
        for d in dirs:
            image_name = op.relpath(d,start=path)
            if all(c.isdigit() for c in list(image_name)): #check if folder is image (all characters in folder rel path need to be numbers)
                image_path = d
                structure = Poscar.from_file(op.join(image_path,'POSCAR')).structure
                structures.append(structure)

        inputs['structures'] = structures           
        inputs['INCAR'] = Incar.from_file(op.join(path,'INCAR'))
        inputs['KPOINTS'] = Kpoints.from_file(op.join(path,'KPOINTS'))
        inputs['POTCAR'] = Potcar.from_file(op.join(path,'POTCAR'))
        
        self.inputs = inputs
        return


    def get_outputs(self,sync=False,get_output_properties=True):
        """
        Read outputs from Job directory
        """
        if sync:
            self.sync_from_hpc()
        outputs = {}
        path = self.path  
        try:
            outputs['NEBAnalysis'] = NEBAnalysis.from_dir(path)
        except:
            print('Warning: NEB output reading with NEBAnalysis in "%s" failed'%path)
            outputs['NEBAnalysis'] = None
            
        self.outputs = outputs
        if get_output_properties:
            self.get_output_properties()
        return
    

    def get_output_properties(self):
        """
        Parse outputs properties from VaspNEBJob.outputs.
        """
        
        self._is_required_accuracy_reached = self._get_ionic_relaxation_from_outfile()
        self._is_step_limit_reached = self._get_step_limit_reached()                
        self._is_converged = self._get_convergence()
        
        neb = self.outputs['NEBAnalysis']
        self._r = neb.r  if neb else None
        self._energies = neb.energies  if neb else None
        self._forces = neb.forces  if neb else None

        return

    
    def write_input(self,write_structures=True):
        """
        Write input files in all image directories
        """
        path = op.abspath(self.path)
        
        self.job_settings['nodes'] = self.images               
        incar = self.inputs['INCAR']
        kpoints = self.inputs['KPOINTS']
        potcar = self.inputs['POTCAR']
        job_settings = self.job_settings

        if write_structures:
            self.write_structures()
        
        incar.write_file(op.join(path,'INCAR'))
        kpoints.write_file(op.join(path,'KPOINTS'))
        potcar.write_file(op.join(path,'POTCAR'))
        ScriptHandler(**job_settings).write_script(path=path)

    
    def write_structures(self):
        """
        Writes POSCAR files in image directories
        """
        path = self.path
        structures = self.inputs['structures']
        for s in structures:
            index = structures.index(s)
            image_path = op.join(path,str(index).zfill(2)) #folders will be named 00,01,..,XX
            if not op.exists(image_path):
                os.makedirs(image_path)
            Poscar(s).write_file(op.join(image_path,'POSCAR'))
        return

    
    def _get_convergence(self):
        """
        Returns True if:
            - "reached required accuracy - stopping structural energy minimisation" is found in the most recent out file.
                OR
            - Ionic step limit has been reached, which means the step # in OSZICAR file matches the "NSW" tag in INCAR.
        Returns False if files named out.* exist but the no "reached required accuracy" has been found AND step limit 
            has not been reached.
        Returns None if no out.* files have been found.
        """
        is_converged = self._get_ionic_relaxation_from_outfile()
        if not is_converged:
            if self.is_step_limit_reached:
                is_converged = True
            
        return is_converged     


    def _get_ionic_relaxation_from_outfile(self):
        """
        Useful for NEB because Pymatgen fails to read vasprun file for NEB calculations.
        This function reads the outfile with highest number in the dir and checks for the 
        string: "reached required accuracy - stopping structural energy minimisation". 
        """
        reached_accuracy = None
        outfiles = glob(os.path.join(self.path,'out*'))
        if outfiles:
            outfiles.sort()
            outfile = outfiles[-1] #taking more recent out file ("out.jobid" with bigger job id)
            lines = grep('reached required accuracy - stopping structural energy minimisation',outfile)
            if lines:
                print('"reached required accuracy - stopping structural energy minimisation" found in %s' %outfile)
                reached_accuracy = True
            else:
                reached_accuracy = False
        
        return reached_accuracy
        
        
    def _get_step_limit_reached(self):
        """
        Reads number of ionic steps from the OSZICAR file with Pymatgen and returns True if 
        is equal to the step limit in INCAR file (NSW tag)
        """
        limit_reached = True
        image_dirs = self.image_dirs
        for d in image_dirs:
            if d != image_dirs[0] and d != image_dirs[-1]:
                if not os.path.isfile(os.path.join(d,'OSZICAR')): # check if OSZICAR files are present 
                    limit_reached = False
                else:                
                    n_steps = len(Oszicar(os.path.join(d,'OSZICAR')).ionic_steps)
                    nsw = Incar.from_file(op.join(self.path,'INCAR'))['NSW'] # check NSW from INCAR in parent directory
                    if nsw != n_steps:
                        limit_reached = False
        return limit_reached    