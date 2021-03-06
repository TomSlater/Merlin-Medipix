
import os
import numpy.testing as nptest
from epsic_tools import api as epsic

def test_sim_to_hs():
    root_path = os.path.dirname(epsic.__file__)
    test_data_path = os.path.join(root_path , 'tests', 'test_data', 'test_sim.h5')
    d = epsic.sim_utils.sim_to_hs(test_data_path)
    shape = d.data.shape
    nptest.assert_equal(shape, (4, 4, 256, 256))

def test_parse_params_file():
    root_path = os.path.dirname(epsic.__file__)
    test_data_path = os.path.join(root_path , 'tests', 'test_data', 'test_sim.h5')
    test_params_path = os.path.join(root_path , 'tests', 'test_data', 'test_sim_params.txt')
    d = epsic.sim_utils.parse_params_file(test_params_path, test_data_path)
    assert d['accel_voltage(eV)'] == 80000
    


