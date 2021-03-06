
import json
import os.path as op
import numpy as np
from pandas import DataFrame
import matplotlib.pyplot as plt
from pymatgen.core.periodic_table import Element
from pymatgen.core.composition import Composition
from pymatgen.analysis.phase_diagram import PDEntry, PhaseDiagram, GrandPotentialPhaseDiagram, PDPlotter
from pynter.tools.format import format_composition

class Reservoirs:
    
    def __init__(self,res_dict,phase_diagram=None,are_chempots_delta=False):
        """
        Class to handle dictionaries of chemical potentials. Works almost completely like a python dictionary.

        Parameters
        ----------
        res_dict : (dict)
            Dictionary with reservoir names as key and dictionaries of chemical potentials as values.
        phase_diagram : (PhaseDiagram object), optional
            PhaseDiagram object (Pymatgen), useful to convert absolute chempots in referenced chempots. The default is None.
        are_chempots_delta : (bool), optional
            Set this variable to True if chempots in dictionary are referenced values. The default is False.
        """
        self.res_dict = res_dict
        self.phase_diagram = phase_diagram if phase_diagram else None
        self.are_chempots_delta = are_chempots_delta


    def __str__(self):
        df = self.get_dataframe()
        return df.__str__()
    
    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self.res_dict)

    def __iter__(self):
        return self.res_dict.keys().__iter__()

    def __getitem__(self,reskey):
        return self.res_dict[reskey]

    def __setitem__(self,reskey,chempots):
        self.res_dict[reskey] = chempots
        return

    def keys(self):
        return self.res_dict.keys()

    def values(self):
        return self.res_dict.values()
    
    def items(self):
        return self.res_dict.items()

    def copy(self):
        return Reservoirs(self.res_dict.copy(),phase_diagram=self.phase_diagram,are_chempots_delta=self.are_chempots_delta)
    
    def as_dict(self):
        """
        Json-serializable dict representation of a Reservoirs object. The Pymatgen element 
        is expressed with the symbol of the element.

        Returns
        -------
        dict
            Json-serializable dict of a Reservoirs object.
        """
        d = {}
        d['@module'] = self.__class__.__module__
        d['@class'] = self.__class__.__name__
        d['res_dict'] = {}
        for res,chempots in self.res_dict.items():
            d['res_dict'][res] = {}
            for el in chempots:
                d['res_dict'][res][el.symbol] = chempots[el]
        d['phase_diagram'] = self.phase_diagram.as_dict()
        d['are_chempots_delta'] = self.are_chempots_delta
        return d


    def to_json(self,path):
        """
        Save Reservoirs object as json string or file

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


    @classmethod
    def from_dict(cls,d):
        """
        Constructor of Reservoirs object from dictionary representation.
        
        Parameters
        ----------
        d : dict
        
        Returns
        -------
        Reservoirs object.
        """
        res_dict = {}
        for res,chempots in d['res_dict'].items():
            res_dict[res] = {Element(el):chempots[el] for el in chempots}
        phase_diagram = PhaseDiagram.from_dict(d['phase_diagram'])
        are_chempots_delta = d['are_chempots_delta']
            
        return cls(res_dict,phase_diagram,are_chempots_delta)


    @staticmethod
    def from_json(path_or_string):
        """
        Build Reservoirs object from json file or string.

        Parameters
        ----------
        path_or_string : (str)
            If an existing path to a file is given the object is constructed reading the json file.
            Otherwise it will be read as a string.

        Returns
        -------
        Reservoir object.

        """
        if op.isfile(path_or_string):
            with open(path_or_string) as file:
                d = json.load(file)
        else:
            d = json.load(path_or_string)
        return Reservoirs.from_dict(d)


    def get_referenced_chempots(self):
        """ 
        Convert values of chempots from absolute to referenced 
        based on the information in the PhaseDiagram
        """
        chempots_delta = {}
        ca = ChempotAnalysis(self.phase_diagram)
        if self.are_chempots_delta:
            raise ValueError('Chemical potential values are already with respect to reference')
        else:
            for res,chem in self.res_dict.items():
                chempots_delta[res] = ca.get_chempots_delta(chem)
        return chempots_delta
    
    
    def get_absolute_chempots(self):
        """ 
        Convert values of chempots from referenced to absolute 
        based on the information in the PhaseDiagram
        """
        chempots_abs = {}
        ca = ChempotAnalysis(self.phase_diagram)
        if self.are_chempots_delta:
            for res,chem in self.res_dict.items():
                chempots_abs[res] = ca.get_chempots_abs(chem)
        else:
            raise ValueError('Chemical potential values are already absolute')
        return chempots_abs
                

    def get_reference_chempots_values(self):
        """
        Get dictionary with values of reference chemical potentials based on data in the PhaseDiagram
        """
        return PDHandler(self.phase_diagram).get_chempots_reference()

    
    def get_dataframe(self,format_compositions=False,all_math=False):
        """
        Get DataFrame object of the dictionary of reservoirs

        Parameters
        ----------
        format_compositions : (bool), optional
            Get Latex format of compositions. The default is False.
        all_math : (bool), optional
            Get all characters in composition written in Latex's math format. The default is False.

        Returns
        -------
        df : 
            DataFrame object.
        """
        df = DataFrame(self.res_dict)
        df = df.transpose()
        if format_compositions:
            new_index = []
            for string in df.index:
                new_string = format_composition(string,all_math=all_math)
                new_index.append(new_string)
            df.index = new_index
        return df
        
     
    def set_chempots_to_absolute(self):
        """
        Set reservoir dictionary to absolute values of chempots.
        """
        new_res_dict = self.get_absolute_chempots()
        self.res_dict = new_res_dict
        self.are_chempots_delta = False
        return

        
    def set_chempots_to_reference(self):
        """
        Set reservoir dictionary to referenced values of chempots.
        """
        new_res_dict = self.get_referenced_chempots()
        self.res_dict = new_res_dict
        self.are_chempots_delta = True
        return    
    
       
class ChempotAnalysis:
    
    def __init__(self,phase_diagram):
        """
        Initializes class to analyse chemical potentials of a phase diagram generated with Pymatgen.
        All of the functions in this class take the Referenced chemical potentials values as argument,
        to facilitate the connection with stability diagram visualization.
        
        Parameters
        ----------
        phase_diagram : (PhaseDiagram)
            Pymatgen PhaseDiagram object
        """
        self.pd = phase_diagram
        self.chempots_reference = PDHandler(phase_diagram).get_chempots_reference()
    

    def boundary_analysis(self,comp,fixed_chempot_delta):
        """
        Given a composition and a fixed chemical potential, this function analises the composition of the boundary phases
        and the associated chemical potentials at the boundaries. Only works for 3 component PD.

        Parameters
        ----------
        comp : (Pymatgen Composition object)
            Composition of the phase you want to get the chemical potentials at the boundary.
        fixed_chempot_delta : (Dict)
            Dictionary with fixed Element as key and respective chemical potential as value ({Element:chempot}).
            The chemical potential here is the referenced value. 
        Returns
        -------
        chempots : (Dict)
            Dictionary with compositions at the boundaries as keys and delta chemical potentials as value.
        """       
        chempots = {}
        comp1,comp2 = self.get_composition_boundaries(comp, fixed_chempot_delta)
        
        boundary = '-'.join([comp1.reduced_formula,comp.reduced_formula])
        chempots[boundary] = self.get_chempots_boundary(comp1, comp, fixed_chempot_delta)
        
        boundary = '-'.join([comp.reduced_formula,comp2.reduced_formula])
        chempots[boundary] = self.get_chempots_boundary(comp, comp2, fixed_chempot_delta)
        
        return chempots        
        

    def calculate_single_chempot(self,comp,fixed_chempots_delta):
        """
        Calculate chemical potential in a given composition and given the chemical potentials of the other elements.

        Parameters
        ----------
        comp : (Pymatgen Composition object)
            Compositions of the phase.
        fixed_chempot_delta : (Dict)
            Dictionary with Element as keys and respective chemical potential as value ({Element:chempot}).
            The chemical potentials used here are the ones relative to the reference (delta_mu)

        Returns
        -------
        mu : (float)
            Chemical potential.
        """        
        form_energy = PDHandler(self.pd).get_formation_energy_from_stable_comp(comp)
        mu = form_energy
        for el,coeff in comp.items():
            if el in fixed_chempots_delta:
                mu += -1*coeff * fixed_chempots_delta[el]
            else:
                factor = coeff
        
        return mu/factor
                

    def get_chempots_abs(self,chempots_delta):
        """
        Add energy per atom of elemental phases to dictionary of relative chemical potentials ({Element:chempot}) 
        to get the total chemical potentials.
        The energy of the elemental phase is taken from the input PhaseDiagram 
        Parameters
        ----------
        chempots_delta : (Dict)
            Dictionary of relative (delta) chemical potentials, format ({Pymatgen Element object:chempot value}).
        Returns
        -------
        chempots_abs : (Dict)
            Dictionary of total chemical potentials, format ({Pymatgen Element object:chempot value}).
        """
        return {el:chempots_delta[el] + self.chempots_reference[el] for el in chempots_delta}
        
        
    def get_chempots_delta(self,chempots_abs):
        """
        Subtract energy per atom of elemental phases to dictionary of chemical potentials ({Element:chempot})
        The energy of the elemental phase is taken from the input PhaseDiagram
        Parameters
        ----------
        chempots_abs : (Dict)
            Dictionary of absolute chemical potentials, format ({Pymatgen Element object:chempot value}).
        Returns
        -------
        chempots_delta : (Dict)
            Dictionary of chemical potentials relative to elemental phase, format ({Pymatgen Element object:chempot value}).
        """
        return {el:chempots_abs[el] - self.chempots_reference[el] for el in chempots_abs}
                    

    def get_chempots_boundary(self,comp1,comp2,fixed_chempot_delta):
        """
        Given a fixed chemical potential, gets the values of the remaining two chemical potentials
        in the boundary between two phases (region where the two phases coexist). Only works for 3-component PD (to check).
        Given a phase P1 (formula AxByOz) and a phase P2 (formula AiBjOk) the chemical potentials have to satisfy the conditions:
            form_energy(P1) = x*mu(A) + y*mu(B) +z*mu(O)
            form_energy(P2) = i*mu(A) + j*mu(B) +k*mu(O)
        From these conditions the values of mu(A) and mu(B) are determined given a fixed value of mu(O).
        All of the chemical potentials used here are delta_mu, i.e. relative to the elemental phase(delta_mu(O) = mu(O) - mu_ref(O))

        Parameters
        ----------
        comp1,comp2 : (Pymatgen Composition object)
            Compositions of the two phases at the boundary.
        fixed_chempot_delta : (Dict)
            Dictionary with fixed Element as key and respective chemical potential as value ({Element:chempot}). The chemical potential
            used here is the one relative to the reference (delta_mu)

        Returns
        -------
        chempots_boundary : (Dict)
            Dictionary of chemical potentials.
        """
        chempots_boundary ={}
        for el,chempot in fixed_chempot_delta.items():
            el_fixed, mu_fixed = el, chempot
        pdhandler = PDHandler(self.pd)
        e1 = pdhandler.get_formation_energy_from_stable_comp(comp1)
        e2 = pdhandler.get_formation_energy_from_stable_comp(comp2)
        
        coeff1 = []
        coeff2 = []
        # order of variables (mu) will follow the order of self.chempots_reference which is alphabetically ordered
        for el in self.chempots_reference:
            if el != el_fixed:
                if el not in comp1:
                    coeff1.append(0)
                else:
                    coeff1.append(comp1[el])
                if el not in comp2:
                    coeff2.append(0)
                else:
                    coeff2.append(comp2[el])                
        a = np.array([coeff1,coeff2])
        
        const1 = e1 - comp1[el_fixed]*mu_fixed if el_fixed in comp1 else e1 
        const2 = e2 - comp2[el_fixed]*mu_fixed if el_fixed in comp2 else e2
        b = np.array([const1,const2])
        
        x = np.linalg.solve(a, b)
        # output will follow the order given in input
        counter = 0
        for el in self.chempots_reference:
            if el != el_fixed:
                chempots_boundary[el] = x[counter]
                counter += 1
        chempots_boundary[el_fixed] = mu_fixed        
        return chempots_boundary
                  
    
    def get_composition_boundaries(self,comp,fixed_chempot_delta):
        """
        Get compositions of phases in boundary of stability with a target composition given a fixed chemical potential 
        on one component. Currently only works for 3-component PD (to check). 
        Used Pymatgen GrandPotentialPhaseDiagram class. The fixed chemical potential is the referenced value that is
        converted in the global value for the analysis with the GrandPotentialPhaseDiagram class.

        Parameters
        ----------
        comp : (Pymatgen Composition object)
            Target composition for which you want to get the bounday phases.
        fixed_chempots_delta : (Dict)
            Dictionary with fixed Element as key and respective chemical potential as value ({Element:chempot}).
            The chemical potential is the referenced value

        Returns
        -------
        comp1,comp2 : (Pymatgen Composition object)
            Compositions of the boundary phases given a fixed chemical potential for one element.
        """
        
        fixed_chempot = self.get_chempots_abs(fixed_chempot_delta)
        
        entries = self.pd.all_entries
        gpd = GrandPotentialPhaseDiagram(entries, fixed_chempot)
        stable_entries = gpd.stable_entries
        comp_in_stable_entries = False
        for e in stable_entries:
            if e.original_comp.reduced_composition == comp:
                comp_in_stable_entries = True
        if comp_in_stable_entries == False:
            raise ValueError('Target composition %s is not a stable entry for fixed chemical potential: %s' %(comp.reduced_formula,fixed_chempot))
        
        el = comp.elements[0]
        x_target = comp.get_wt_fraction(el)
        x_max_left = 0
        x_min_right = 1
        for e in stable_entries:
            c = e.original_comp
            if c != comp:
                x = c.get_wt_fraction(el)
                if x < x_target and x >= x_max_left:
                    x_max_left = x
                    comp1 = c
                if x > x_target and x <= x_min_right:
                    x_min_right = x
                    comp2 = c
        return comp1.reduced_composition,comp2.reduced_composition
            
        
        
class PDHandler:
    
    def __init__(self,phase_diagram):
        """
        Class to generate and handle Pymatgen phase diagram more rapidly.

        Parameters
        ----------
        phase_diagram : (PhaseDiagram)
            Pymatgen PhaseDiagram object
        """
        self.pd = phase_diagram 

        
    def get_chempots_reference(self):
        """
        Gets elemental reference compounds and respective e.p.a with Pymatgen el_ref attribute in PhaseDiagram class.

        Returns
        -------
        chempot_ref: (Dict)
            Dictionary of elemental chemical potentials 
        """
        
        chempots_ref = {}
        pd = self.pd
        for el in pd.el_refs:
            chempots_ref[el] = pd.el_refs[el].energy_per_atom
        chempots_ref = {k: v for k, v in sorted(chempots_ref.items(), key=lambda item: item[0])}
        return chempots_ref
       
        
    def get_entries_from_comp(self,comp):
       """
       Get a list of entries corrisponding to the target composition.
       
       Parameters
       ----------
       comp : (Pymatgen Composition object)
       Returns
       -------
       List of Pymatgen PDEntry objects
       """
       target_entries=[]
       pd = self.pd
       for e in pd.all_entries:
           if e.composition.reduced_composition == comp:
               target_entries.append(e)
       if target_entries != []:
           return target_entries
       else:
           raise ValueError('No entry has been found for target composition:%s' %comp.reduced_formula)
               

    def get_formation_energies_from_comp(self,comp):
        """
        Get dictionary of formation energies for all entries of a given reduced composition

        Parameters
        ----------
        comp : (Pymatgen Composition object)
        Returns
        -------
        from_energies : (Dict)
            Dictionary with PDEntry objects as keys and formation energies as values.
        """
        pd = self.pd
        form_energies = {}
        for e in self.get_entries_from_comp(comp):
            factor = e.composition.get_reduced_composition_and_factor()[1]
            form_energies[e] = pd.get_form_energy(e)/factor
        return form_energies
            

    def get_formation_energy_from_stable_comp(self,comp):
        """
        Get formation energy of a target stable composition

        Parameters
        ----------
        comp : (Pymatgen Composition object)

        Returns
        -------
        Formation energy (float)
        """
        pd = self.pd
        entry = self.get_stable_entry_from_comp(comp)
        factor = entry.composition.get_reduced_composition_and_factor()[1]
        return pd.get_form_energy(entry)/factor


    def get_stability_diagram(self,elements,size=None):
        """
        Method to get stability diagram with 'get_chempot_range_map_plot' method in pymatgen

        Parameters
        ----------
        elements : (list)
            List with strings of the elements to be used as free variables.
        size : (tuple)
            New size in inches.

        Returns
        -------
        plt : 
            Matplotlib object
        """
        pd = self.pd
        elements = [Element(el) for el in elements]
        PDPlotter(pd).get_chempot_range_map_plot(elements)
        if size:
            fig = plt.gcf()
            fig.set_size_inches(size[0],size[1])
        
        return plt


    def get_stable_entry_from_comp(self,comp):
        """
        Get the PDEntry of the stable entry of a target composition

        Parameters
        ----------
        comp : (Pymatgen Composition object)
        Returns
        -------
        Pymatgen PDEntry object
        """
        target_entry=None
        pd = self.pd
        for e in pd.stable_entries:
            if e.composition.reduced_composition == comp:
                target_entry = e
                break
        if target_entry is not None:
            return target_entry
        else:
            raise ValueError('No stable entry has been found for target composition:%s' %comp.reduced_formula)
        

    

    