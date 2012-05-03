# Authors: Alexandre Gramfort <gramfort@nmr.mgh.harvard.edu>
#          Matti Hamalainen <msh@nmr.mgh.harvard.edu>
#          Martin Luessi <mluessi@nmr.mgh.harvard.edu>
#
# License: BSD (3-clause)

import os

import numpy as np

from .. import Epochs, compute_proj_evoked, compute_proj_epochs
from ..fiff import Raw, pick_types, make_eeg_average_ref_proj
from ..artifacts import find_ecg_events, find_eog_events


def _compute_exg_proj(mode, raw, tmin, tmax,
                      n_grad, n_mag, n_eeg, l_freq, h_freq,
                      average, filter_length, n_jobs, ch_name,
                      reject, bads, avg_ref, no_proj, event_id):
    """Compute SSP/PCA projections for ECG or EOG artifacts

    Note: raw has to be constructed with preload=True (or string)
    Warning: raw will be modified by this function

    Parameters
    ----------
    mode: sting ('ECG', or 'EOG')
        What type of events to detect

    raw: mne.fiff.Raw
        Raw input file

    tmin: float
        Time before event in second

    tmax: float
        Time after event in seconds

    n_grad: int
        Number of SSP vectors for gradiometers

    n_mag: int
        Number of SSP vectors for magnetometers

    n_eeg: int
        Number of SSP vectors for EEG

    l_freq: float
        Filter low cut-off frequency in Hz

    h_freq: float
        Filter high cut-off frequency in Hz

    average: bool
        Compute SSP after averaging

    filter_length: int
        Number of taps to use for filtering

    n_jobs: int
        Number of jobs to run in parallel

    ch_name: string (or None)
        Channel to use for ECG event detection

    reject: dict
        Epoch rejection configuration (see Epochs)

    bads: list
        List with (additional) bad channels

    avg_ref: bool
        Add EEG average reference proj

    no_proj: bool
        Exclude the SSP projectors currently in the fiff file

    event_id: int
        ID to use for events

    Returns
    -------
    proj : list
        Computed SSP projectors

    events : ndarray
        Detected events
    """
    if not raw._preloaded:
        raise ValueError('raw needs to be preloaded, use preload=True in constructor')

    if no_proj:
        projs = []
    else:
        projs = raw.info['projs']
        print 'Including %d SSP projectors from raw file' % len(projs)

    if avg_ref:
        print 'Adding average EEG reference projection.'
        eeg_proj = make_eeg_average_ref_proj(raw.info)
        projs.append(eeg_proj)

    if mode == 'ECG':
        print 'Running ECG SSP computation'
        events, _, _ = find_ecg_events(raw, ch_name=ch_name, event_id=event_id)
    elif mode == 'EOG':
        print 'Running EOG SSP computation'
        events = find_eog_events(raw, event_id=event_id)
    else:
        ValueError("mode must be 'ECG' or 'EOG'")

    print 'Computing projector'

    # Handler rejection parameters
    if len(pick_types(raw.info, meg='grad', eeg=False, eog=False)) == 0:
        del reject['grad']
    if len(pick_types(raw.info, meg='mag', eeg=False, eog=False)) == 0:
        del reject['mag']
    if len(pick_types(raw.info, meg=False, eeg=True, eog=False)) == 0:
        del reject['eeg']
    if len(pick_types(raw.info, meg=False, eeg=False, eog=True)) == 0:
        del reject['eog']

    picks = pick_types(raw.info, meg=True, eeg=True, eog=True,
                       exclude=raw.info['bads'] + bads)
    if l_freq is None and h_freq is not None:
        raw.high_pass_filter(picks, h_freq, filter_length, n_jobs)
    if l_freq is not None and h_freq is None:
        raw.low_pass_filter(picks, h_freq, filter_length, n_jobs)
    if l_freq is not None and h_freq is not None:
        raw.band_pass_filter(picks, l_freq, h_freq, filter_length, n_jobs)

    epochs = Epochs(raw, events, None, tmin, tmax, baseline=None,
                    picks=picks, reject=reject, proj=True)

    if average:
        evoked = epochs.average()
        ev_projs = compute_proj_evoked(evoked, n_grad=n_grad, n_mag=n_mag,
                                        n_eeg=n_eeg)
    else:
        ev_projs = compute_proj_epochs(epochs, n_grad=n_grad, n_mag=n_mag,
                                        n_eeg=n_eeg)
    projs.extend(ev_projs)

    print 'Done.'

    return projs, events


def compute_proj_ecg(raw, tmin=-0.2, tmax=0.4,
                     n_grad=2, n_mag=2, n_eeg=2, l_freq=1.0, h_freq=35.0,
                     average=False, filter_length=2048, n_jobs=1, ch_name=None,
                     reject=dict(grad=2000e-13, mag=3000e-15, eeg=50e-6,
                     eog=250e-6), bads=[], avg_ref=False, no_proj=True,
                     event_id=999):
    """Compute SSP/PCA projections for ECG artifacts

    Note: raw has to be constructed with preload=True (or string)
    Warning: raw will be modified by this function

    Parameters
    ----------
    raw: mne.fiff.Raw
        Raw input file

    tmin: float
        Time before event in second

    tmax: float
        Time after event in seconds

    n_grad: int
        Number of SSP vectors for gradiometers

    n_mag: int
        Number of SSP vectors for magnetometers

    n_eeg: int
        Number of SSP vectors for EEG

    l_freq: float
        Filter low cut-off frequency in Hz

    h_freq: float
        Filter high cut-off frequency in Hz

    average: bool
        Compute SSP after averaging

    filter_length: int
        Number of taps to use for filtering

    n_jobs: int
        Number of jobs to run in parallel

    ch_name: string (or None)
        Channel to use for ECG detection (Required if no ECG found)

    reject: dict
        Epoch rejection configuration (see Epochs)

    bads: list
        List with (additional) bad channels

    avg_ref: bool
        Add EEG average reference proj

    no_proj: bool
        Exclude the SSP projectors currently in the fiff file

    event_id: int
        ID to use for events

    Returns
    -------
    proj : list
        Computed SSP projectors

    ecg_events : ndarray
        Detected ECG events
    """

    projs, ecg_events = _compute_exg_proj('ECG', raw, tmin, tmax,
                        n_grad, n_mag, n_eeg, l_freq, h_freq,
                        average, filter_length, n_jobs, ch_name,
                        reject, bads, avg_ref, no_proj, event_id)

    return projs, ecg_events


def compute_proj_eog(raw, tmin=-0.15, tmax=0.15,
                     n_grad=2, n_mag=2, n_eeg=2, l_freq=1.0, h_freq=35.0,
                     average=False, filter_length=2048, n_jobs=1,
                     reject=dict(grad=2000e-13, mag=3000e-15, eeg=500e-6,
                     eog=np.inf), bads=[], avg_ref=False, no_proj=True,
                     event_id=998):
    """Compute SSP/PCA projections for EOG artifacts

    Note: raw has to be constructed with preload=True (or string)
    Warning: raw will be modified by this function

    Parameters
    ----------
    raw: mne.fiff.Raw
        Raw input file

    tmin: float
        Time before event in second

    tmax: float
        Time after event in seconds

    n_grad: int
        Number of SSP vectors for gradiometers

    n_mag: int
        Number of SSP vectors for magnetometers

    n_eeg: int
        Number of SSP vectors for EEG

    l_freq: float
        Filter low cut-off frequency in Hz

    h_freq: float
        Filter high cut-off frequency in Hz

    average: bool
        Compute SSP after averaging

    preload: string (or True)
        Temporary file used during computaion

    filter_length: int
        Number of taps to use for filtering

    n_jobs: int
        Number of jobs to run in parallel

    reject: dict
        Epoch rejection configuration (see Epochs)

    bads: list
        List with (additional) bad channels

    avg_ref: bool
        Add EEG average reference proj

    no_proj: bool
        Exclude the SSP projectors currently in the fiff file

    event_id: int
        ID to use for events

    Returns
    -------
    proj : list
        Computed SSP projectors

    eog_events : ndarray
        Detected ECG events
    """

    projs, eog_events = _compute_exg_proj('EOG', raw, tmin, tmax,
                        n_grad, n_mag, n_eeg, l_freq, h_freq,
                        average, filter_length, n_jobs, None,
                        reject, bads, avg_ref, no_proj, event_id)

    return projs, eog_events
