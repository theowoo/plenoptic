import pytest
import torch
import requests
import math
import tqdm
import tarfile
import os
import numpy as np
import pyrtools as pt
import plenoptic as po
import os.path as op
import matplotlib.pyplot as plt


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
dtype = torch.float32
DATA_DIR = op.join(op.dirname(op.realpath(__file__)), '..', 'data')
print("On device %s" % device)

@pytest.fixture
def test_files_dir():
    path = op.join(op.dirname(op.realpath(__file__)), '..', 'data', 'plenoptic-test-files')
    if not op.exists(path):
        print("matfiles required for testing not found, downloading now...")
        # Streaming, so we can iterate over the response.
        r = requests.get("https://osf.io/q9kn8/download", stream=True)

        # Total size in bytes.
        total_size = int(r.headers.get('content-length', 0))
        block_size = 1024*1024
        wrote = 0
        with open(path + ".tar.gz", 'wb') as f:
            for data in tqdm.tqdm(r.iter_content(block_size), unit='MB', unit_scale=True,
                                  total=math.ceil(total_size//block_size)):
                wrote += len(data)
                f.write(data)
        if total_size != 0 and wrote != total_size:
            raise Exception("Error downloading test files!")
        with tarfile.open(path + ".tar.gz") as f:
            f.extractall(op.dirname(path))
        os.remove(path + ".tar.gz")
    return path


class TestLinear(object):

    def test_linear(self):
        model = po.simul.Linear()
        x = po.make_basic_stimuli()
        assert model(x).requires_grad

    def test_linear_metamer(self):
        model = po.simul.Linear()
        image = plt.imread(op.join(DATA_DIR, 'nuts.pgm')).astype(float) / 255.
        im0 = torch.tensor(image, requires_grad=True, dtype=dtype).squeeze().unsqueeze(0).unsqueeze(0)
        M = po.synth.Metamer(im0, model)
        matched_image, matched_representation = M.synthesize(max_iter=3, learning_rate=1, seed=1)

class TestLinearNonlinear(object):

    def test_linear_nonlinear(self):
        model = po.simul.Linear_Nonlinear()
        x = po.make_basic_stimuli()
        assert model(x).requires_grad

    def test_linear_nonlinear_metamer(self):
        model = po.simul.Linear_Nonlinear()
        image = plt.imread(op.join(DATA_DIR, 'metal.pgm')).astype(float) / 255.
        im0 = torch.tensor(image,requires_grad=True,dtype = torch.float32).squeeze().unsqueeze(0).unsqueeze(0)
        M = po.synth.Metamer(im0, model)
        matched_image, matched_representation = M.synthesize(max_iter=3, learning_rate=1,seed=0)


# class TestConv(object):
# TODO expand, arbitrary shapes, dim


class TestLaplacianPyramid(object):

    def test_grad(self):
        L = po.simul.Laplacian_Pyramid()
        y = L.analysis(po.make_basic_stimuli())
        assert y[0].requires_grad


class TestSteerablePyramid(object):

    @pytest.mark.parametrize("height", [3, 4, 5])
    @pytest.mark.parametrize("order", [1, 2, 3])
    def test_real(self, height, order):
        x = po.make_basic_stimuli()
        spc = po.simul.Steerable_Pyramid_Freq(x.shape[-2:], height=height, order=order, is_complex=False)
        y = spc(x)

    @pytest.mark.parametrize("height", [3,4,5])
    @pytest.mark.parametrize("order", [1,2,3])
    def test_complex(self, height, order):
        x = po.make_basic_stimuli()
        spc = po.simul.Steerable_Pyramid_Freq(x.shape[-2:], height=height, order=order, is_complex=True)
        y = spc(x)

    # TODO reconstruction


class TestNonLinearities(object):

    def test_coordinatetransform(self):
        a = torch.randn(10, 5, 256, 256)
        b = torch.randn(10, 5, 256, 256)

        A, B = po.polar_to_rectangular(*po.rectangular_to_polar(a, b))

        assert torch.norm(a - A) < 1e-3
        assert torch.norm(b - B) < 1e-3

        a = torch.rand(10, 5, 256, 256)
        b = po.rescale(torch.randn(10, 5, 256, 256), -np.pi / 2, np.pi / 2)

        A, B = po.rectangular_to_polar(*po.polar_to_rectangular(a, b))

        assert torch.norm(a - A) < 1e-3
        assert torch.norm(b - B) < 1e-3

    def test_rectangular_to_polar_dict(self):
        x = po.make_basic_stimuli()
        spc = po.simul.Steerable_Pyramid_Freq(x.shape[-2:], height=5, order=1, is_complex=True)
        y = spc(x)
        energy, state = po.simul.non_linearities.rectangular_to_polar_dict(y)

    def test_rectangular_to_polar_real(self):
        x = torch.randn(10, 1, 256, 256)
        po.simul.non_linearities.rectangular_to_polar_real(x)

    def test_local_gain_control(self):
        x = po.make_basic_stimuli()
        spc = po.simul.Steerable_Pyramid_Freq(x.shape[-2:], height=5, order=1, is_complex=False)
        y = spc(x)
        energy, state = po.simul.non_linearities.local_gain_control(y)

    def test_normalize(self):
        x = po.make_basic_stimuli()
        # should operate on both of these, though it will do different
        # things
        po.simul.non_linearities.normalize(x[0].flatten())
        po.simul.non_linearities.normalize(x[0].flatten(), 1)
        po.simul.non_linearities.normalize(x[0])
        po.simul.non_linearities.normalize(x[0], 1)
        po.simul.non_linearities.normalize(x[0], sum_dim=1)

    def test_normalize_dict(self):
        x = po.make_basic_stimuli()
        v1 = po.simul.PrimaryVisualCortex(1, x.shape[-2:])
        v1(x[0])
        po.simul.non_linearities.normalize_dict(v1.representation)


def test_find_files(test_files_dir):
    assert op.exists(op.join(test_files_dir, 'buildSCFpyr0.mat'))


class TestPooling(object):

    def test_creation(self):
        ang_windows, ecc_windows = po.simul.pooling.create_pooling_windows(.87, (256, 256))

    def test_creation_args(self):
        ang, ecc = po.simul.pooling.create_pooling_windows(.87, (100, 100), .2, 30, 1.2, .7)
        ang, ecc = po.simul.pooling.create_pooling_windows(.87, (100, 100), .2, 30, 1.2, .5)

    def test_ecc_windows(self):
        windows = po.simul.pooling.log_eccentricity_windows((256, 256), n_windows=4)
        windows = po.simul.pooling.log_eccentricity_windows((256, 256), n_windows=4.5)
        windows = po.simul.pooling.log_eccentricity_windows((256, 256), window_width=.5)
        windows = po.simul.pooling.log_eccentricity_windows((256, 256), window_width=1)

    def test_angle_windows(self):
        windows = po.simul.pooling.polar_angle_windows(4, (256, 256))
        windows = po.simul.pooling.polar_angle_windows(4, (1000, 1000))
        with pytest.raises(Exception):
            windows = po.simul.pooling.polar_angle_windows(1.5, (256, 256))
        with pytest.raises(Exception):
            windows = po.simul.pooling.polar_angle_windows(1, (256, 256))

    def test_calculations(self):
        # these really shouldn't change, but just in case...
        assert po.simul.pooling.calc_angular_window_width(2) == np.pi
        assert po.simul.pooling.calc_angular_n_windows(2) == np.pi
        with pytest.raises(Exception):
            po.simul.pooling.calc_eccentricity_window_width()
        assert po.simul.pooling.calc_eccentricity_window_width(n_windows=4) == 0.8502993454155389
        assert po.simul.pooling.calc_eccentricity_window_width(scaling=.87) == 0.8446653390527211
        assert po.simul.pooling.calc_eccentricity_window_width(5, 10, scaling=.87) == 0.8446653390527211
        assert po.simul.pooling.calc_eccentricity_window_width(5, 10, n_windows=4) == 0.1732867951399864
        assert po.simul.pooling.calc_eccentricity_n_windows(0.8502993454155389) == 4
        assert po.simul.pooling.calc_eccentricity_n_windows(0.1732867951399864, 5, 10) == 4
        assert po.simul.pooling.calc_scaling(4) == 0.8761474337786708
        assert po.simul.pooling.calc_scaling(4, 5, 10) == 0.17350368946058647
        assert np.isinf(po.simul.pooling.calc_scaling(4, 0))

    def test_PoolingWindows(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:])
        pw = pw.to(device)
        pw(im)
        pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:], num_scales=3)
        pw = pw.to(device)
        pw(im)
        pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:], transition_region_width=1)
        pw = pw.to(device)
        pw(im)
        with pytest.raises(Exception):
            po.simul.PoolingWindows(.2, (64, 64), .5)

    def test_PoolingWindows_project(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:])
        pw = pw.to(device)
        pooled = pw(im)
        pw.project(pooled)
        pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:], num_scales=3)
        pw = pw.to(device)
        pooled = pw(im)
        pw.project(pooled)

    def test_PoolingWindows_nonsquare(self):
        # test PoolingWindows with weirdly-shaped iamges
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device)
        for sh in [(256, 128), (256, 127), (256, 125), (125, 125), (127, 125)]:
            tmp = im[:sh[0], :sh[1]].unsqueeze(0).unsqueeze(0)
            rgc = po.simul.RetinalGanglionCells(.9, tmp.shape[2:])
            rgc = rgc.to(device)
            rgc(tmp)
            v1 = po.simul.RetinalGanglionCells(.9, tmp.shape[2:])
            v1 = v1.to(device)
            v1(tmp)

    def test_PoolingWindows_plotting(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device)
        pw = po.simul.PoolingWindows(.8, im.shape, num_scales=2)
        pw = pw.to(device)
        pw.plot_window_areas()
        pw.plot_window_widths()
        for i in range(2):
            pw.plot_window_areas('pixels', i)
            pw.plot_window_widths('pixels', i)
        fig = pt.imshow(po.to_numpy(im))
        pw.plot_windows(fig.axes[0])

    def test_PoolingWindows_caching(self, tmp_path):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device)
        # first time we save, second we load
        pw = po.simul.PoolingWindows(.8, im.shape, num_scales=2, cache_dir=tmp_path)
        pw = po.simul.PoolingWindows(.8, im.shape, num_scales=2, cache_dir=tmp_path)

    def test_PoolingWindows_parallel(self, tmp_path):
        if torch.cuda.device_count() > 1:
            devices = list(range(torch.cuda.device_count()))
            im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
            im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
            pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:])
            pw = pw.parallel(devices)
            pw(im)
            pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:], num_scales=3)
            pw = pw.parallel(devices)
            pw(im)
            pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:], transition_region_width=1)
            pw = pw.parallel(devices)
            pw(im)
            for sh in [(256, 128), (256, 127), (256, 125), (125, 125), (127, 125)]:
                tmp = im[:sh[0], :sh[1]]
                rgc = po.simul.RetinalGanglionCells(.9, tmp.shape[2:])
                rgc = rgc.parallel(devices)
                rgc(tmp)
                v1 = po.simul.RetinalGanglionCells(.9, tmp.shape[2:])
                v1 = v1.parallel(devices)
                v1(tmp)
            pw = po.simul.PoolingWindows(.8, im.shape[2:], num_scales=2)
            pw = pw.parallel(devices)
            pw.plot_window_areas()
            pw.plot_window_widths()
            for i in range(2):
                pw.plot_window_areas('pixels', i)
                pw.plot_window_widths('pixels', i)
            fig = pt.imshow(po.to_numpy(im).squeeze())
            pw.plot_windows(fig.axes[0])
            pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:])
            pw = pw.parallel(devices)
            pooled = pw(im)
            pw.project(pooled)
            pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:], num_scales=3)
            pw = pw.parallel(devices)
            pooled = pw(im)
            pw.project(pooled)

    def test_PoolingWindows_sep(self):
        # test the window and pool function separate of the forward function
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        pw = po.simul.pooling.PoolingWindows(.5, im.shape[2:])
        pw.pool(pw.window(im))

# class TestSpectral(object):
#


class TestVentralStream(object):

    def test_rgc(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
        rgc = rgc.to(device)
        rgc(im)
        _ = rgc.plot_window_widths('degrees')
        _ = rgc.plot_window_widths('degrees', jitter=0)
        _ = rgc.plot_window_widths('pixels')
        _ = rgc.plot_window_areas('degrees')
        _ = rgc.plot_window_areas('degrees')
        _ = rgc.plot_window_areas('pixels')
        fig = pt.imshow(po.to_numpy(im).squeeze())
        _ = rgc.plot_windows(fig.axes[0])
        rgc.plot_representation()
        rgc.plot_representation_image()
        fig, axes = plt.subplots(2, 1, figsize=(5, 12))
        rgc.plot_representation(ax=axes[1])
        rgc.plot_representation_image(ax=axes[0])

    def test_rgc_2(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:], transition_region_width=1)
        rgc = rgc.to(device)
        rgc(im)
        _ = rgc.plot_window_widths('degrees')
        _ = rgc.plot_window_widths('degrees', jitter=0)
        _ = rgc.plot_window_widths('pixels')
        _ = rgc.plot_window_areas('degrees')
        _ = rgc.plot_window_areas('degrees')
        _ = rgc.plot_window_areas('pixels')
        fig = pt.imshow(po.to_numpy(im).squeeze())
        _ = rgc.plot_windows(fig.axes[0])
        rgc.plot_representation()
        rgc.plot_representation_image()
        fig, axes = plt.subplots(2, 1, figsize=(5, 12))
        rgc.plot_representation(ax=axes[1])
        rgc.plot_representation_image(ax=axes[0])

    def test_rgc_metamer(self):
        # literally just testing that it runs
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
        rgc = rgc.to(device)
        metamer = po.synth.Metamer(im, rgc)
        metamer.synthesize(max_iter=3)
        assert not torch.isnan(metamer.matched_image).any(), "There's a NaN here!"

    def test_rgc_save_load(self, tmp_path):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)
        # first time we cache the windows...
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:], cache_dir=tmp_path)
        rgc = rgc.to(device)
        rgc(im)
        rgc.save_reduced(op.join(tmp_path, 'test_rgc_save_load.pt'))
        rgc_copy = po.simul.RetinalGanglionCells.load_reduced(op.join(tmp_path,
                                                                      'test_rgc_save_load.pt'))
        rgc_copy = rgc_copy.to(device)
        if not len(rgc.PoolingWindows.angle_windows) == len(rgc_copy.PoolingWindows.angle_windows):
            raise Exception("Something went wrong saving and loading, the lists of angle windows"
                            " are not the same length!")
        if not len(rgc.PoolingWindows.ecc_windows) == len(rgc_copy.PoolingWindows.ecc_windows):
            raise Exception("Something went wrong saving and loading, the lists of ecc windows"
                            " are not the same length!")
        # we don't recreate everything, e.g., the representation, but windows is the most important
        for i in range(len(rgc.PoolingWindows.angle_windows)):
            if not rgc.PoolingWindows.angle_windows[i].allclose(rgc_copy.PoolingWindows.angle_windows[i]):
                raise Exception("Something went wrong saving and loading, the angle_windows %d are"
                                " not identical!" % i)
        for i in range(len(rgc.PoolingWindows.ecc_windows)):
            if not rgc.PoolingWindows.ecc_windows[i].allclose(rgc_copy.PoolingWindows.ecc_windows[i]):
                raise Exception("Something went wrong saving and loading, the ecc_windows %d are"
                                " not identical!" % i)
        # ...second time we load them
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:], cache_dir=tmp_path)

    def test_rgc_parallel(self):
        if torch.cuda.device_count() > 1:
            devices = list(range(torch.cuda.device_count()))
            im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
            im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
            rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
            rgc = rgc.parallel(devices)
            metamer = po.synth.Metamer(im, rgc)
            metamer.synthesize(max_iter=3)
            rgc.plot_representation()
            rgc.plot_representation_image()
            metamer.plot_representation_error()

    def test_frontend(self):
        im = po.make_basic_stimuli()
        frontend = po.simul.Front_End()
        frontend(im)

    def test_frontend_plot(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        frontend = po.simul.Front_End()
        po.tools.display.plot_representation(data=frontend(im), figsize=(11, 5))
        metamer = po.synth.Metamer(im, frontend)
        metamer.synthesize(max_iter=3, store_progress=1)
        metamer.plot_metamer_status(figsize=(35, 5))
        metamer.animate(figsize=(35, 5))

    def test_frontend_PoolingWindows(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        frontend = po.simul.Front_End()
        pw = po.simul.PoolingWindows(.5, (256, 256))
        pw(frontend(im))
        po.tools.display.plot_representation(data=pw(frontend(im)))

    def test_frontend_eigendistortion(self):
        im = plt.imread(op.join(DATA_DIR, 'einstein.png'))[:,:,0]
        im = torch.tensor(im, dtype=dtype, device=device, requires_grad=True).unsqueeze(0).unsqueeze(0)
        frontend = po.simul.Front_End()
        edist = po.synth.Eigendistortion(im, frontend)
        edist.synthesize(jac=False, n_steps=5)

    def test_v1(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        v1(im)
        _ = v1.plot_window_widths('pixels')
        _ = v1.plot_window_areas('pixels')
        for i in range(v1.num_scales):
            _ = v1.plot_window_widths('pixels', i)
            _ = v1.plot_window_areas('pixels', i)
        v1.plot_representation()
        v1.plot_representation_image()
        fig, axes = plt.subplots(2, 1, figsize=(27, 12))
        v1.plot_representation(ax=axes[1])
        v1.plot_representation_image(ax=axes[0])

    def test_v1_norm(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        stats = po.simul.non_linearities.generate_norm_stats(v1, DATA_DIR, img_shape=(256, 256))
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:], normalize_dict=stats)
        v1 = v1.to(device)
        v1(im)
        _ = v1.plot_window_widths('pixels')
        _ = v1.plot_window_areas('pixels')
        for i in range(v1.num_scales):
            _ = v1.plot_window_widths('pixels', i)
            _ = v1.plot_window_areas('pixels', i)
        v1.plot_representation()
        v1.plot_representation_image()
        fig, axes = plt.subplots(2, 1, figsize=(27, 12))
        v1.plot_representation(ax=axes[1])
        v1.plot_representation_image(ax=axes[0])

    def test_v1_parallel(self):
        if torch.cuda.device_count() > 1:
            devices = list(range(torch.cuda.device_count()))
            im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
            im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
            v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:]).to(device)
            v1 = v1.parallel(devices)
            metamer = po.synth.Metamer(im, v1)
            metamer.synthesize(max_iter=3)
            v1.plot_representation()
            v1.plot_representation_image()
            metamer.plot_representation_error()

    def test_v1_2(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:], transition_region_width=1)
        v1 = v1.to(device)
        v1(im)
        _ = v1.plot_window_widths('pixels')
        _ = v1.plot_window_areas('pixels')
        for i in range(v1.num_scales):
            _ = v1.plot_window_widths('pixels', i)
            _ = v1.plot_window_areas('pixels', i)
        v1.plot_representation()
        v1.plot_representation_image()
        fig, axes = plt.subplots(2, 1, figsize=(27, 12))
        v1.plot_representation(ax=axes[1])
        v1.plot_representation_image(ax=axes[0])

    def test_v1_mean_luminance(self):
        for fname in ['nuts', 'einstein']:
            im = plt.imread(op.join(DATA_DIR, fname+'.pgm'))
            im = torch.tensor(im, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)
            v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
            v1 = v1.to(device)
            v1_rep = v1(im)
            rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
            rgc = rgc.to(device)
            rgc_rep = rgc(im)
            if not torch.allclose(rgc.representation, v1.mean_luminance):
                raise Exception("Somehow RGC and V1 mean luminance representations are not the "
                                "same for image %s!" % fname)
            if not torch.allclose(rgc_rep, v1_rep[..., -rgc_rep.shape[-1]:]):
                raise Exception("Somehow V1's representation does not have the mean luminance "
                                "in the location expected! for image %s!" % fname)

    def test_v1_save_load(self, tmp_path):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)
        # first time we cache the windows...
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:], cache_dir=tmp_path)
        v1 = v1.to(device)
        v1(im)
        v1.save_reduced(op.join(tmp_path, 'test_v1_save_load.pt'))
        v1_copy = po.simul.PrimaryVisualCortex.load_reduced(op.join(tmp_path,
                                                                    'test_v1_save_load.pt'))
        v1_copy = v1_copy.to(device)
        if not len(v1.PoolingWindows.angle_windows) == len(v1_copy.PoolingWindows.angle_windows):
            raise Exception("Something went wrong saving and loading, the lists of angle windows"
                            " are not the same length!")
        if not len(v1.PoolingWindows.ecc_windows) == len(v1_copy.PoolingWindows.ecc_windows):
            raise Exception("Something went wrong saving and loading, the lists of ecc windows"
                            " are not the same length!")
        # we don't recreate everything, e.g., the representation, but windows is the most important
        for i in range(len(v1.PoolingWindows.angle_windows)):
            if not v1.PoolingWindows.angle_windows[i].allclose(v1_copy.PoolingWindows.angle_windows[i]):
                raise Exception("Something went wrong saving and loading, the angle_windows %d are"
                                " not identical!" % i)
        for i in range(len(v1.PoolingWindows.ecc_windows)):
            if not v1.PoolingWindows.ecc_windows[i].allclose(v1_copy.PoolingWindows.ecc_windows[i]):
                raise Exception("Something went wrong saving and loading, the ecc_windows %d are"
                                " not identical!" % i)
        # ...second time we load them
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:], cache_dir=tmp_path)

    def test_v1_metamer(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=3)

    @pytest.mark.parametrize("frontend", [True, False])
    @pytest.mark.parametrize("steer", [True, False])
    def test_v2(self, frontend, steer):
        x = po.make_basic_stimuli()
        v2 = po.simul.V2(frontend=frontend, steer=steer)
        v2(x)

    @pytest.mark.parametrize("frontend", [True, False])
    @pytest.mark.parametrize("steer", [True, False])
    def test_v2_metamer(self, frontend, steer):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device, requires_grad=True).unsqueeze(0).unsqueeze(0)
        v2 = po.simul.V2(frontend=frontend, steer=steer)
        v2 = v2.to(device)
        metamer = po.synth.Metamer(im, v2)
        metamer.synthesize(max_iter=3)


class TestMetamers(object):

    def test_metamer_save_load(self, tmp_path):

        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=3, store_progress=True)
        metamer.save(op.join(tmp_path, 'test_metamer_save_load.pt'))
        met_copy = po.synth.Metamer.load(op.join(tmp_path, "test_metamer_save_load.pt"),
                                         map_location=device)
        for k in ['target_image', 'saved_representation', 'saved_image', 'matched_representation',
                  'matched_image', 'target_representation']:
            if not getattr(metamer, k).allclose(getattr(met_copy, k)):
                raise Exception("Something went wrong with saving and loading! %s not the same"
                                % k)

    def test_metamer_save_load_reduced(self, tmp_path):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=3, store_progress=True)
        metamer.save(op.join(tmp_path, 'test_metamer_save_load_reduced.pt'), True)
        with pytest.raises(Exception):
            met_copy = po.synth.Metamer.load(op.join(tmp_path,
                                                     "test_metamer_save_load_reduced.pt"))
        met_copy = po.synth.Metamer.load(op.join(tmp_path, 'test_metamer_save_load_reduced.pt'),
                                         po.simul.PrimaryVisualCortex.from_state_dict_reduced,
                                         map_location=device)
        for k in ['target_image', 'saved_representation', 'saved_image', 'matched_representation',
                  'matched_image', 'target_representation']:
            if not getattr(metamer, k).allclose(getattr(met_copy, k)):
                raise Exception("Something went wrong with saving and loading! %s not the same" % k)

    def test_metamer_store_rep(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=3, store_progress=2)

    def test_metamer_store_rep_2(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=3, store_progress=True)

    def test_metamer_store_rep_3(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=6, store_progress=3)

    def test_metamer_store_rep_4(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        with pytest.raises(Exception):
            metamer.synthesize(max_iter=3, store_progress=False, save_progress=True)

    def test_metamer_plotting_v1(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=6, store_progress=True)
        metamer.plot_representation_error()
        metamer.model.plot_representation_image(data=metamer.representation_error())
        metamer.plot_metamer_status()
        metamer.plot_metamer_status(iteration=1)

    def test_metamer_plotting_rgc(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
        rgc = rgc.to(device)
        metamer = po.synth.Metamer(im, rgc)
        metamer.synthesize(max_iter=6, store_progress=True)
        metamer.plot_representation_error()
        metamer.model.plot_representation_image(data=metamer.representation_error())
        metamer.plot_metamer_status()
        metamer.plot_metamer_status(iteration=1)

    def test_metamer_continue(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
        rgc = rgc.to(device)
        metamer = po.synth.Metamer(im, rgc)
        metamer.synthesize(max_iter=3, store_progress=True)
        metamer.synthesize(max_iter=3, initial_image=metamer.matched_image.detach().clone())

    def test_metamer_animate(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
        rgc = rgc.to(device)
        metamer = po.synth.Metamer(im, rgc)
        metamer.synthesize(max_iter=3, store_progress=True)
        # this will test several related functions for us:
        # plot_metamer_status, plot_representation_error,
        # representation_error
        metamer.animate(figsize=(17, 5), plot_representation_error=True, ylim='rescale100',
                        framerate=40)

    def test_metamer_nans(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = im / 255
        im = torch.tensor(im, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)
        initial_image = .5*torch.ones_like(im, requires_grad=True, device=device,
                                           dtype=torch.float32)

        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        clamper = po.RangeClamper((0, 1))
        # this gets raised because we try to use saved_image_ticker,
        # which was never initialized, since we're not saving images
        with pytest.raises(IndexError):
            metamer.synthesize(clamper=clamper, learning_rate=10, max_iter=4, loss_thresh=1e-8,
                               initial_image=initial_image)
        # need to re-initialize this for the following run
        initial_image = .5*torch.ones_like(im, requires_grad=True, device=device,
                                           dtype=torch.float32)
        matched_im, _ = metamer.synthesize(clamper=clamper, learning_rate=10, store_progress=True,
                                           max_iter=4, loss_thresh=1e-8,
                                           initial_image=initial_image)
        # this should hit a nan as it runs, leading the second saved
        # image to be all nans, but, because of our way of handling
        # this, matched_image should have no nans
        assert torch.isnan(metamer.saved_image[-1]).all(), "This should be all NaNs!"
        assert not torch.isnan(metamer.matched_image).any(), "There should be no NaNs!"

    def test_metamer_save_progress(self, tmp_path):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        save_path = op.join(tmp_path, 'test_metamer_save_progress.pt')
        metamer.synthesize(max_iter=3, store_progress=True, save_progress=True,
                           save_path=save_path)
        po.synth.Metamer.load(save_path, po.simul.PrimaryVisualCortex.from_state_dict_reduced)

    def test_metamer_fraction_removed(self):

        X = np.load(op.join(op.join(op.dirname(op.realpath(__file__)), '..', 'examples'), 'metamer_PS_samples.npy'))
        sigma = X.std(axis=1)
        sigma[sigma < .00001] = 1
        normalizationFactor = 1 / sigma
        normalizationFactor = torch.diag(torch.tensor(normalizationFactor, dtype=torch.float32))

        model = po.simul.Texture_Statistics([256, 256], normalizationFactor=normalizationFactor)
        image = plt.imread(op.join(DATA_DIR, 'nuts.pgm')).astype(float) / 255.
        im0 = torch.tensor(image, requires_grad=True, dtype=torch.float32).squeeze().unsqueeze(0).unsqueeze(0)
        c = po.RangeClamper([image.min(), image.max()])
        M = po.synth.Metamer(im0, model)

        matched_image, matched_representation = M.synthesize(max_iter=3, learning_rate=1, seed=1, optimizer='SGD',
                                                             fraction_removed=.1, clamper=c)

    def test_metamer_loss_change(self):
        # literally just testing that it runs
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        rgc = po.simul.RetinalGanglionCells(.5, im.shape[2:])
        rgc = rgc.to(device)
        metamer = po.synth.Metamer(im, rgc)
        metamer.synthesize(max_iter=10, loss_change_iter=1, loss_change_thresh=1,
                           loss_change_fraction=.5)
        metamer.synthesize(max_iter=10, loss_change_iter=1, loss_change_thresh=1,
                           loss_change_fraction=.5, fraction_removed=.1)

    def test_metamer_coarse_to_fine(self):
        im = plt.imread(op.join(DATA_DIR, 'nuts.pgm'))
        im = torch.tensor(im, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
        v1 = po.simul.PrimaryVisualCortex(.5, im.shape[2:])
        v1 = v1.to(device)
        metamer = po.synth.Metamer(im, v1)
        metamer.synthesize(max_iter=10, loss_change_iter=1, loss_change_thresh=10,
                           coarse_to_fine=True)
        metamer.synthesize(max_iter=10, loss_change_iter=1, loss_change_thresh=10,
                           coarse_to_fine=True, fraction_removed=.1)
        metamer.synthesize(max_iter=10, loss_change_iter=1, loss_change_thresh=10,
                           coarse_to_fine=True, loss_change_fraction=.5)
        metamer.synthesize(max_iter=10, loss_change_iter=1, loss_change_thresh=10,
                           coarse_to_fine=True, loss_change_fraction=.5, fraction_removed=.1)


class TestPerceptualMetrics(object):

    im1 = po.rescale(plt.imread(op.join(DATA_DIR, 'einstein.png')).astype(float)[:, :, 0])
    im1 = torch.tensor(im1, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)
    im2 = torch.rand_like(im1, requires_grad=True, device=device)

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_ssim(self, im1, im2):
        assert po.metric.ssim(im1, im2).requires_grad

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_msssim(self, im1, im2):
        assert po.metric.msssim(im1, im2).requires_grad

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_nlpd(self, im1, im2):
        assert po.metric.nlpd(im1, im2).requires_grad

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_nspd(self, im1, im2):
        assert po.metric.nspd(im1, im2).requires_grad

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_nspd2(self, im1, im2):
        assert po.metric.nspd(im1, im2, O=3, S=5, complex=True).requires_grad

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_nspd3(self, im1, im2):
        assert po.metric.nspd(im1, im2, O=1, S=5, complex=False).requires_grad

    @pytest.mark.parametrize("im1, im2", [(im1, im2)])
    def test_model_metric(self, im1, im2):
        model = po.simul.Front_End(disk_mask=True)
        assert po.metric.model_metric(im1, im2, model).requires_grad