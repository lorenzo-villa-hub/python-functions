

import unittest

import os.path as op
import pynter
from pathlib import Path
from pynter.vasp.default_inputs import DefaultInputs
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar, Potcar, VaspInput


module_dir = Path(__file__).absolute().parent
test_files_dir = op.join(Path(pynter.__file__).absolute().parent.parent,'test-files/vasp')


class TestDefaultInputs(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        structure = Poscar.from_file(op.join(test_files_dir,'POSCAR_Si')).structure
        cls.default_inputs = DefaultInputs(structure)

    def test_get_incar_PBE(self):
        incar = self.default_inputs.get_incar_default()
        self.assertIsInstance(incar,dict,'Output of DefaultInputs.get_incar_default() is not dictionary')
        
    def test_get_incar_HSE(self):
        incar = self.default_inputs.get_incar_default(xc='HSE06',aexx=0.30)
        self.assertEqual(incar['HFSCREEN'],0.2,'HFSCREEN is not set to 0.2 in incar dict')
        self.assertIsInstance(incar,dict,'Output of DefaultInputs.get_incar_default() is not dictionary')
        
    def test_get_poscar(self):
        poscar = self.default_inputs.get_poscar()
        self.assertIsInstance(poscar,Poscar,'Output of DefaultInputs.get_poscar() is not a Poscar object')
        
if __name__ == "__main__":
    unittest.main()
        
        
        
    
    

