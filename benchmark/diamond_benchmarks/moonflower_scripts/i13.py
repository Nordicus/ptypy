"""
This script is a test for ptychographic reconstruction in the absence
of actual data. It uses the test Scan class
`ptypy.core.data.MoonFlowerScan` to provide "data".
"""
from ptypy.core import Ptycho
from ptypy import utils as u
import ptypy
ptypy.load_gpu_engines("cuda")
import time

import os
import getpass
from pathlib import Path
username = getpass.getuser()
tmpdir = os.path.join('/dls/tmp', username, 'dumps', 'ptypy')
Path(tmpdir).mkdir(parents=True, exist_ok=True)

p = u.Param()

# for verbose output
p.verbose_level = "info"
p.frames_per_block = 100
# set home path
p.io = u.Param()
p.io.home = tmpdir
p.io.autosave = u.Param(active=False) #(active=True, interval=50000)
p.io.autoplot = u.Param(active=False)
p.io.interaction = u.Param()
p.io.interaction.server = u.Param(active=False)

# max 200 frames (128x128px) of diffraction data
p.scans = u.Param()
p.scans.i13 = u.Param()
# now you have to specify which ScanModel to use with scans.XX.name,
# just as you have to give 'name' for engines and PtyScan subclasses.
p.scans.i13.name = 'BlockFull' # or 'Full'
p.scans.i13.data= u.Param()
p.scans.i13.data.name = 'MoonFlowerScan'
p.scans.i13.data.shape = 512
p.scans.i13.data.num_frames = 5000
p.scans.i13.data.save = None

p.scans.i13.illumination = u.Param()
p.scans.i13.coherence = u.Param(num_probe_modes=1)
p.scans.i13.illumination.diversity = u.Param()
p.scans.i13.illumination.diversity.noise = (0.5, 1.0)
p.scans.i13.illumination.diversity.power = 0.1

# position distance in fraction of illumination frame
p.scans.i13.data.density = 0.2
# total number of photon in empty beam
p.scans.i13.data.photons = 1e8
# Gaussian FWHM of possible detector blurring
p.scans.i13.data.psf = 0.2

# attach a reconstrucion engine
p.engines = u.Param()
p.engines.engine00 = u.Param()
p.engines.engine00.name = 'DM_pycuda'
p.engines.engine00.numiter = 1000
p.engines.engine00.numiter_contiguous = 20
p.engines.engine00.probe_update_start = 1
p.engines.engine00.probe_update_cuda_atomics = False
p.engines.engine00.object_update_cuda_atomics = True


# prepare and run
P = Ptycho(p,level=4)
t1 = time.perf_counter()
P.run()
t2 = time.perf_counter()
P.print_stats()
print('Elapsed Compute Time: {} seconds'.format(t2-t1))

