

import unittest

import os.path as op
import pynter
from pathlib import Path
from pynter.vasp.default_inputs import DefaultInputs
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar, Potcar, PotcarSingle,VaspInput


module_dir = Path(__file__).absolute().parent
test_files_dir = op.join(Path(pynter.__file__).absolute().parent.parent,'test-files/vasp')


class TestDefaultInputs(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        structure = Poscar.from_file(op.join(test_files_dir,'POSCAR_Si')).structure
        cls.default_inputs = DefaultInputs(structure)


    def test_get_incar_PBE_without_structure(self):
        incar = DefaultInputs().get_incar_default()
        self.assertIsInstance(incar,dict,'Output of DefaultInputs.get_incar_default() is not dictionary')
        self.assertEqual(incar['SYSTEM'], 'No system info','Value of incar["SYSTEM"] is not "No system info"')

    def test_get_incar_PBE(self):
        incar = self.default_inputs.get_incar_default()
        self.assertIsInstance(incar,dict,'Output of DefaultInputs.get_incar_default() is not dictionary')
        
        
    def test_get_incar_HSE(self):
        incar = self.default_inputs.get_incar_default(xc='HSE06',aexx=0.30)
        self.assertEqual(incar['HFSCREEN'],0.2,'HFSCREEN is not set to 0.2 in incar dict')
        self.assertIsInstance(incar,dict,'Output of DefaultInputs.get_incar_default() is not dictionary')
        
        
    def test_get_kpoints_default(self):
        kpoints = self.default_inputs.get_kpoints_default()
        self.assertIsInstance(kpoints,Kpoints,'Output of DefaultInputs is not a Kpoints object')
        
        
    def test_get_poscar(self):
        poscar = self.default_inputs.get_poscar()
        self.assertIsInstance(poscar,Poscar,'Output of DefaultInputs.get_poscar() is not a Poscar object')
        
        
    def test_get_potcar(self):
        NN_structure = Poscar.from_file(op.join(test_files_dir,'POSCAR_NaNbO3_cubic')).structure
        self.default_inputs.structure = NN_structure
        
        potcar = self.default_inputs.get_potcar()
        self.assertIsInstance(potcar,Potcar,'Output of DefaultInputs.get_potcar() is not a Potcar object')
        for p in potcar:
            self.assertEqual(p.symbol,self.default_inputs.default_potcar_symbols[p.element],'PotcarSingle symbol is not equal to default')
        
        potcar_symbols = ['Na','Nb_pv','O']
        potcar = self.default_inputs.get_potcar(potcar_symbols=potcar_symbols)
        self.assertIsInstance(potcar,Potcar,'Output of DefaultInputs.get_potcar() is not a Potcar object')
        for p in potcar:
            self.assertEqual(p.symbol,potcar_symbols[potcar.index(p)],'PotcarSingle symbol is not equal to str provided in potcar_symbols')
        
        
if __name__ == "__main__":
    unittest.main()
        
        
        
    
    

